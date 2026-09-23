"""FastAPI Webhook Server for Personal Finance Hub."""

from typing import Optional, List, Dict, Any
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from finance_hub.models import (
    NotificationPayload,
    ParsedTransaction,
    compute_raw_hash,
)
from finance_hub.parser.engine import default_engine, ParserEngine
from finance_hub.parser.base import is_promo_or_non_financial
from finance_hub.storage import get_storage, StorageManager
from finance_hub.integrations.sheets_sync import GoogleSheetsSync
from finance_hub.integrations.telegram_notify import TelegramNotifier

logger = logging.getLogger(__name__)


class ParseTestRequest(BaseModel):
    text: str = Field(..., description="Raw notification or SMS text")
    package_name: Optional[str] = Field(default=None, description="App package name (e.g. com.bca)")
    title: Optional[str] = Field(default=None, description="Notification title")
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp if available")


class HealthResponse(BaseModel):
    status: str
    engine_version: str
    transaction_count: int
    db_status: str


class DuplicateResponse(BaseModel):
    status: str = "duplicate_ignored"
    raw_hash: str
    message: str


def create_app(
    storage_manager: Optional[StorageManager] = None,
    sheets_sync: Optional[GoogleSheetsSync] = None,
    telegram_notifier: Optional[TelegramNotifier] = None,
) -> FastAPI:
    """Application factory allowing custom storage, sheets sync, and telegram notifier injection."""
    class StorageProxy:
        def __getattr__(self, name):
            nonlocal storage_manager
            if storage_manager is None:
                storage_manager = get_storage()
            return getattr(storage_manager, name)

    storage: Any = storage_manager if storage_manager is not None else StorageProxy()
    sheets = sheets_sync if sheets_sync is not None else GoogleSheetsSync()
    notifier = telegram_notifier if telegram_notifier is not None else TelegramNotifier()
    engine = default_engine

    app = FastAPI(
        title="Personal Finance Hub — Automated Ingestion Webhook",
        description="FastAPI Webhook and Ingestion API for Indonesian m-banking and e-wallet notifications",
        version="2.0.0",
    )

    @app.get("/health", response_model=HealthResponse)
    def health_check():
        """Health check returning system status, transaction counts, and engine version."""
        count = storage.get_transaction_count()
        return HealthResponse(
            status="healthy",
            engine_version="2.0.0",
            transaction_count=count,
            db_status="connected"
        )

    @app.post("/webhook/transaction", response_model=Any)
    def receive_webhook_transaction(
        payload: NotificationPayload,
        background_tasks: BackgroundTasks,
    ):
        """
        Ingest mobile push notification or SMS webhook.
        Guarantees idempotency via SHA-256 payload hashing.
        Saves synchronously to DuckDB, then schedules Google Sheets sync in the background.
        """
        raw_hash = compute_raw_hash(payload)

        # 1. Check idempotency
        if storage.is_hash_exists(raw_hash):
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "duplicate_ignored",
                    "raw_hash": raw_hash,
                    "message": "Transaction notification has already been processed."
                }
            )

        # 2. Parse & Classify
        parsed = engine.parse(payload, raw_hash=raw_hash)

        # 2b. Laya System 1 Anomaly & Quality Audit
        try:
            from finance_hub.laya_guard import audit_transaction_anomaly
            is_anomaly, score, reason = audit_transaction_anomaly(
                amount=parsed.amount, raw_text=payload.text, category=parsed.category
            )
            if is_anomaly:
                logger.warning(f"Laya Anomaly Detected [{score:.2f}]: {reason} for hash {raw_hash}")
        except Exception as guard_err:
            logger.debug(f"Laya guard check skipped: {guard_err}")

        # If payload had no timestamp, ensure parsed timestamp reflects the current hit time (WIB)
        if not (payload.timestamp and len(payload.timestamp) >= 10):
            from datetime import datetime
            parsed.timestamp = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")

        # Skip non-financial notifications (promo, advertisements, news with amount <= 0, or failed transactions)
        if is_promo_or_non_financial(payload.text) or parsed.amount <= 0.0:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "non_financial_ignored",
                    "raw_hash": raw_hash,
                    "message": "Notification is a promotional message, failed transaction, or informational text."
                }
            )

        # 3. Store to DuckDB
        saved, result = storage.save_transaction(payload, parsed)
        if not saved:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "duplicate_ignored",
                    "raw_hash": raw_hash,
                    "message": "Transaction already recorded in ledger."
                }
            )

        # 4. Schedule Google Sheets sync in background task for fast webhook response (<50ms)
        def _bg_sync_sheets(tx: ParsedTransaction):
            try:
                if sheets.is_configured():
                    success = sheets.append_transaction(tx)
                    if success:
                        storage.mark_synced(tx.raw_hash)
            except Exception as exc:
                logger.error(f"Background Google Sheets sync failed for {tx.raw_hash}: {exc}")

        # 5. Schedule Telegram notification alert in background task
        def _bg_notify_telegram(tx: ParsedTransaction):
            try:
                if notifier.is_configured():
                    cashflow = None
                    try:
                        cashflow = storage.get_weekly_cashflow()
                    except Exception as cf_err:
                        logger.debug(f"Could not fetch cashflow for alert: {cf_err}")
                    notifier.send_transaction_alert(tx, cashflow=cashflow)
            except Exception as exc:
                logger.error(f"Background Telegram notification failed for {tx.raw_hash}: {exc}")

        background_tasks.add_task(_bg_sync_sheets, parsed)
        background_tasks.add_task(_bg_notify_telegram, parsed)

        return parsed

    @app.post("/api/sync-sheets")
    def trigger_sheets_sync():
        """Manually trigger synchronization of unsynced transactions to Google Sheets."""
        if not sheets.is_configured():
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "error",
                    "message": "Google Sheets integration is not configured. Set GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_SPREADSHEET_ID.",
                    "synced_count": 0,
                    "pending_remaining": storage.get_unsynced_count(),
                }
            )

        unsynced = storage.get_unsynced_transactions()
        if not unsynced:
            return {
                "status": "success",
                "synced_count": 0,
                "pending_remaining": 0,
                "message": "No pending transactions to sync."
            }

        synced_count = sheets.sync_batch(unsynced)
        if synced_count > 0:
            for tx in unsynced[:synced_count]:
                storage.mark_synced(tx.raw_hash)

        remaining = storage.get_unsynced_count()
        return {
            "status": "success" if synced_count > 0 else "partial_or_failed",
            "synced_count": synced_count,
            "pending_remaining": remaining,
            "message": f"Successfully synced {synced_count} transaction(s) to Google Sheets."
        }

    @app.get("/api/sheets-status")
    def get_sheets_status(
        verify: bool = Query(default=False, description="Verify sheet tab structure via API call")
    ):
        """Display Google Sheets connection status, configured spreadsheet ID, and pending sync count."""
        configured = sheets.is_configured()
        pending_count = storage.get_unsynced_count()

        status_info: Dict[str, Any] = {
            "configured": configured,
            "spreadsheet_id": sheets.spreadsheet_id if sheets.spreadsheet_id else None,
            "credentials_file": sheets.credentials_file,
            "credentials_exist": os.path.isfile(sheets.credentials_file) if sheets.credentials_file else False,
            "pending_sync_count": pending_count,
            "status": "configured" if configured else "unconfigured",
        }

        if verify:
            status_info["structure_verification"] = sheets.verify_structure()

        return status_info

    @app.post("/api/parse-test", response_model=ParsedTransaction)
    def parse_test_dry_run(req: ParseTestRequest):
        """
        Test parser and classifier logic without persisting data to database.
        """
        payload = NotificationPayload(
            text=req.text,
            package_name=req.package_name,
            title=req.title,
            timestamp=req.timestamp
        )
        raw_hash = compute_raw_hash(payload)
        parsed = engine.parse(payload, raw_hash=raw_hash)
        return parsed

    @app.get("/api/transactions")
    def list_transactions(
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0)
    ):
        """Retrieve recent normalized transactions from the Silver ledger layer."""
        total = storage.get_transaction_count()
        transactions = storage.get_recent_transactions(limit=limit, offset=offset)
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "transactions": transactions
        }

    @app.get("/api/summary")
    def get_financial_summary():
        """Retrieve executive 50/30/20 budget allocations and financial summary."""
        return storage.get_summary()

    @app.get("/api/query/weekly")
    def get_weekly_cashflow_query(
        ref_date: Optional[str] = Query(default=None, description="Reference date in YYYY-MM-DD format")
    ):
        """Query weekly cash flow (Pemasukan vs Pengeluaran) for current week or ref_date."""
        return storage.get_weekly_cashflow(ref_date=ref_date)

    @app.get("/api/query/allowance")
    def get_allowance_status_query():
        """Query remaining allowance from last incoming transfer / starting balance."""
        return storage.get_transfer_allowance_status()

    @app.get("/api/query/balances")
    def get_account_balances_query():
        """Query current liquid balances across all accounts and wallets."""
        return storage.get_account_balances()

    @app.get("/api/telegram-status")
    def get_telegram_status():
        """Retrieve Telegram notification configuration and readiness status."""
        return {
            "enabled": notifier.enabled,
            "configured": notifier.is_configured(),
            "chat_id_configured": bool(notifier.chat_id),
            "bot_token_configured": bool(notifier.bot_token),
        }

    @app.get("/api/gmail/status")
    def get_gmail_status():
        """Retrieve Gmail API ingestion authentication and connection status."""
        from finance_hub.integrations.gmail_auth import (
            get_token_path,
            get_client_secrets_path,
            get_gmail_credentials,
        )
        token_path = get_token_path()
        secrets_path = get_client_secrets_path()
        has_secrets = os.path.isfile(secrets_path)
        has_token = os.path.isfile(token_path)
        creds = get_gmail_credentials()
        is_authenticated = creds is not None and creds.valid
        return {
            "authenticated": is_authenticated,
            "has_client_secrets": has_secrets,
            "has_token": has_token,
            "query": os.environ.get(
                "GMAIL_SEARCH_QUERY",
                'from:(bankmandiri OR mandiri) "Notifikasi Transaksi"',
            ),
        }

    @app.post("/api/gmail/poll")
    def trigger_gmail_poll(
        max_results: int = Query(default=20, ge=1, le=100),
    ):
        """Trigger on-demand polling of Gmail for transaction emails."""
        from finance_hub.integrations.gmail_poller import GmailPoller
        poller = GmailPoller(
            storage_manager=storage,
            sheets_sync=sheets,
            telegram_notifier=notifier,
        )
        if not poller.is_authenticated():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Gmail is not authenticated. Run auth-gmail first.",
            )
        result = poller.poll_recent_transactions(max_results=max_results)
        return result

    return app


# Default app instance
app = create_app()
