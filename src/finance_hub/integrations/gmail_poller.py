"""Gmail Ingestion Engine for Personal Finance Hub.

Polls Gmail API for transaction receipt emails from Bank Mandiri / Livin',
parses them using MandiriEmailParser, records them to DuckDB with SHA-256 idempotency,
and triggers Google Sheets synchronization and Telegram alerts.
"""

import os
import base64
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from finance_hub.models import (
    ParsedTransaction,
    NotificationPayload,
    Institution,
)
from finance_hub.storage import get_storage, StorageManager
from finance_hub.integrations.gmail_auth import get_gmail_credentials
from finance_hub.integrations.sheets_sync import GoogleSheetsSync
from finance_hub.integrations.telegram_notify import TelegramNotifier
from finance_hub.parser.mandiri_email import MandiriEmailParser

logger = logging.getLogger(__name__)

DEFAULT_MANDIRI_QUERY = 'from:(bankmandiri OR mandiri) "Notifikasi Transaksi"'


def decode_gmail_body(payload: Dict[str, Any]) -> str:
    """Recursively extract and decode plain text or HTML body from Gmail message payload."""
    body_data = ""

    # 1. Direct body data
    if "body" in payload and payload["body"].get("data"):
        raw_b64 = payload["body"]["data"]
        try:
            return base64.urlsafe_b64decode(raw_b64).decode("utf-8", errors="replace")
        except Exception:
            pass

    # 2. Check multipart
    parts = payload.get("parts", [])
    text_plain = ""
    text_html = ""

    for part in parts:
        mime_type = part.get("mimeType", "")
        part_data = part.get("body", {}).get("data", "")
        if not part_data:
            # Check nested parts
            if part.get("parts"):
                nested = decode_gmail_body(part)
                if nested:
                    return nested
            continue

        try:
            decoded = base64.urlsafe_b64decode(part_data).decode("utf-8", errors="replace")
            if mime_type == "text/plain":
                text_plain = decoded
            elif mime_type == "text/html":
                text_html = decoded
        except Exception:
            continue

    if text_plain:
        return text_plain
    if text_html:
        # Simple HTML to text conversion: replace <br>, </p>, </tr> with newline, remove tags
        import re
        txt = re.sub(r'<br\s*/?>', '\n', text_html, flags=re.IGNORECASE)
        txt = re.sub(r'</(p|tr|div|h[1-6])>', '\n', txt, flags=re.IGNORECASE)
        txt = re.sub(r'<[^>]+>', ' ', txt)
        # Unescape HTML entities
        import html
        return html.unescape(txt)

    return ""


def get_header_value(headers: List[Dict[str, str]], name: str) -> str:
    """Retrieve header value by case-insensitive name."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


class GmailPoller:
    """Engine for polling Gmail for m-banking transaction emails."""

    def __init__(
        self,
        storage_manager: Optional[StorageManager] = None,
        sheets_sync: Optional[GoogleSheetsSync] = None,
        telegram_notifier: Optional[TelegramNotifier] = None,
        query: Optional[str] = None,
    ):
        self.storage = storage_manager or get_storage()
        self.sheets = sheets_sync or GoogleSheetsSync()
        self.notifier = telegram_notifier or TelegramNotifier()
        self.query = query or os.environ.get("GMAIL_SEARCH_QUERY", DEFAULT_MANDIRI_QUERY)
        self.parser = MandiriEmailParser()

    def is_authenticated(self) -> bool:
        """Check if Gmail OAuth credentials exist and are valid."""
        creds = get_gmail_credentials()
        return creds is not None and creds.valid

    def poll_recent_transactions(
        self,
        max_results: int = 20,
        sync_sheets: bool = True,
        notify_telegram: bool = True,
    ) -> Dict[str, Any]:
        """
        Poll Gmail for transaction receipt emails, parse, and persist.

        Returns:
            Dict summary: {
                "status": "success" | "unauthenticated" | "error",
                "polled_count": int,
                "saved_count": int,
                "duplicate_count": int,
                "ignored_count": int,
                "transactions": List[Dict],
            }
        """
        creds = get_gmail_credentials()
        if not creds or not creds.valid:
            logger.warning("Gmail poller called but credentials are not authenticated.")
            return {
                "status": "unauthenticated",
                "message": "Gmail OAuth token missing or invalid. Run auth-gmail first.",
                "polled_count": 0,
                "saved_count": 0,
                "duplicate_count": 0,
                "ignored_count": 0,
                "transactions": [],
            }

        try:
            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            response = service.users().messages().list(
                userId="me",
                q=self.query,
                maxResults=max_results,
            ).execute()
        except HttpError as err:
            logger.error(f"Gmail API list messages failed: {err}")
            return {
                "status": "error",
                "message": str(err),
                "polled_count": 0,
                "saved_count": 0,
                "duplicate_count": 0,
                "ignored_count": 0,
                "transactions": [],
            }

        messages = response.get("messages", [])
        logger.info(f"Found {len(messages)} matching transaction email(s) in Gmail.")

        saved_txs: List[ParsedTransaction] = []
        dup_count = 0
        ignored_count = 0

        for msg_meta in messages:
            msg_id = msg_meta.get("id")
            try:
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full",
                ).execute()
            except Exception as get_err:
                logger.warning(f"Failed to fetch message {msg_id}: {get_err}")
                continue

            payload = msg.get("payload", {})
            headers = payload.get("headers", [])

            subject = get_header_value(headers, "Subject")
            sender = get_header_value(headers, "From")
            date_str = get_header_value(headers, "Date")
            msg_id_header = get_header_value(headers, "Message-ID") or msg_id

            body_text = decode_gmail_body(payload)
            if not body_text:
                ignored_count += 1
                continue

            # Parse via MandiriEmailParser
            parsed = self.parser.parse(
                sender=sender,
                subject=subject,
                body=body_text,
                message_id=msg_id_header,
                email_date=date_str,
            )

            if not parsed or parsed.amount <= 0.0:
                ignored_count += 1
                continue

            # Check Idempotency
            if self.storage.is_hash_exists(parsed.raw_hash):
                dup_count += 1
                continue

            # Create synthetic NotificationPayload for Bronze layer
            notif_payload = NotificationPayload(
                package_name="id.bmri.livin.email",
                title=subject,
                text=body_text[:2000],
                timestamp=parsed.timestamp,
                source_device="gmail",
            )

            # Save to DuckDB
            saved, _ = self.storage.save_transaction(notif_payload, parsed)
            if saved:
                saved_txs.append(parsed)

                # Background sync to Google Sheets
                if sync_sheets and self.sheets.is_configured():
                    try:
                        if self.sheets.append_transaction(parsed):
                            self.storage.mark_synced(parsed.raw_hash)
                    except Exception as s_err:
                        logger.error(f"Google Sheets sync failed for {parsed.raw_hash}: {s_err}")

                # Background Telegram notification
                if notify_telegram and self.notifier.is_configured():
                    try:
                        cashflow = None
                        try:
                            cashflow = self.storage.get_weekly_cashflow()
                        except Exception:
                            pass
                        self.notifier.send_transaction_alert(parsed, cashflow=cashflow)
                    except Exception as t_err:
                        logger.error(f"Telegram alert failed for {parsed.raw_hash}: {t_err}")
            else:
                dup_count += 1

        return {
            "status": "success",
            "polled_count": len(messages),
            "saved_count": len(saved_txs),
            "duplicate_count": dup_count,
            "ignored_count": ignored_count,
            "transactions": [tx.model_dump() for tx in saved_txs],
        }
