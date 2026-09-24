"""Telegram Notification Integration for Personal Finance Hub."""

import os
import json
import html
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from finance_hub.models import ParsedTransaction, TransactionType

logger = logging.getLogger(__name__)


def format_idr(amount: float) -> str:
    """Format floating point number into Indonesian Rupiah string (e.g. Rp 50.000)."""
    return f"Rp {int(amount):,}".replace(",", ".")


class TelegramNotifier:
    """Dispatches transaction alerts to Telegram bot/chat."""

    enabled: bool = True

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: Optional[bool] = None,
        base_url: str = "https://api.telegram.org",
        urlopen: Optional[Callable[..., Any]] = None,
    ):
        if bot_token is not None:
            self.bot_token = bot_token.strip()
        else:
            self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

        if chat_id is not None:
            self.chat_id = chat_id.strip()
        else:
            self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if enabled is not None:
            self.enabled = enabled
        else:
            env_val = os.environ.get("TELEGRAM_NOTIFY_ENABLED", "true").strip().lower()
            self.enabled = env_val not in ("0", "false", "no", "off")

        self.base_url = base_url.rstrip("/")
        self._urlopen = urlopen or urllib.request.urlopen

    def is_configured(self) -> bool:
        """Check if bot token and chat ID are present and notifications are enabled."""
        return self.enabled and bool(self.bot_token) and bool(self.chat_id)

    def _redact_token(self, msg: str) -> str:
        """Prevent bot token from ever appearing in log traces."""
        if self.bot_token and self.bot_token in msg:
            return msg.replace(self.bot_token, "[REDACTED]")
        return msg

    def format_transaction_message(
        self,
        tx: ParsedTransaction,
        cashflow: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build HTML-formatted alert message for Telegram (bulletproof against special chars)."""
        tx_type = tx.transaction_type

        if tx_type == TransactionType.INCOME:
            header = "💰 <b>Pemasukan Baru Dicatat!</b>"
            sign = "+"
        elif tx_type == TransactionType.TRANSFER:
            header = "🔁 <b>Transfer Dana Dicatat!</b>"
            sign = ""
        else:
            header = "💸 <b>Pengeluaran Baru Dicatat!</b>"
            sign = "-"

        inst = tx.source_institution.value if hasattr(tx.source_institution, "value") else str(tx.source_institution)
        account = tx.account_name or inst

        amount_str = f"{sign}{format_idr(tx.amount)}"

        # Time formatting
        time_display = tx.timestamp
        try:
            dt = datetime.fromisoformat(tx.timestamp)
            time_display = dt.strftime("%d %b %Y, %H:%M WIB")
        except Exception:
            pass

        safe_inst = html.escape(str(inst))
        safe_account = html.escape(str(account))
        safe_merchant = html.escape(str(tx.merchant))

        lines = [
            header,
            "━━━━━━━━━━━━━━━━━━━",
            f"▫️ <b>Nominal:</b> <code>{html.escape(amount_str)}</code>",
            f"▫️ <b>Sumber:</b> {safe_inst} ({safe_account})",
            f"▫️ <b>Pihak/Merchant:</b> {safe_merchant}",
        ]

        if tx.category:
            bucket_str = f" ({tx.budget_bucket.value})" if tx.budget_bucket else ""
            safe_cat = html.escape(f"{tx.category}{bucket_str}")
            lines.append(f"▫️ <b>Kategori:</b> {safe_cat}")

        lines.append(f"▫️ <b>Waktu:</b> {html.escape(time_display)}")

        if tx.notes:
            lines.append(f"▫️ <b>Catatan:</b> <i>{html.escape(tx.notes)}</i>")

        if cashflow:
            lines.append("━━━━━━━━━━━━━━━━━━━")
            net_rem = cashflow.get("formatted_net_remaining")
            if net_rem:
                lines.append(f"📊 <b>Sisa Kas Minggu Ini:</b> <code>{html.escape(net_rem)}</code>")
            exp_tot = cashflow.get("formatted_expense")
            if exp_tot:
                lines.append(f"📉 <b>Total Pengeluaran Minggu Ini:</b> <code>{html.escape(exp_tot)}</code>")

        return "\n".join(lines)

    def send_transaction_alert(
        self,
        tx: ParsedTransaction,
        cashflow: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send formatted alert to Telegram chat synchronously (designed to run in background tasks)."""
        if not self.is_configured():
            logger.debug("Telegram notification skipped: not configured or disabled.")
            return False

        message_text = self.format_transaction_message(tx, cashflow=cashflow)
        url = f"{self.base_url}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "personal-finance-hub/2.0.0",
        }

        req = urllib.request.Request(url, data=data, headers=headers)

        for attempt in range(1, 3):
            try:
                with self._urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        logger.info(
                            f"Telegram alert delivered for tx {tx.raw_hash[:8]} ({tx.merchant}, {format_idr(tx.amount)})"
                        )
                        return True
                    logger.warning(
                        f"Telegram API non-200 status {resp.status} on attempt {attempt}"
                    )
            except urllib.error.HTTPError as exc:
                err_msg = self._redact_token(str(exc))
                logger.error(f"Telegram HTTP error on attempt {attempt}: {err_msg}")
            except Exception as exc:
                err_msg = self._redact_token(str(exc))
                logger.error(f"Telegram send failure on attempt {attempt}: {err_msg}")

        return False
