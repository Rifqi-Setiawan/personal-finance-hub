"""Google Sheets integration engine using gspread and Service Account authentication."""

import os
import logging
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

from finance_hub.models import ParsedTransaction, TransactionType

logger = logging.getLogger(__name__)

DEFAULT_CREDENTIALS_FILE = "credentials/google_service_account.json"
EXPECTED_SHEET_TABS = [
    "Dashboard",
    "Transactions_Raw",
    "Ledger_Clean",
    "Categories",
    "Monthly_Summary",
]
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSheetsSync:
    """Synchronizes bronze and silver transactions to target Google Sheets."""

    def __init__(
        self,
        credentials_file: Optional[str] = None,
        spreadsheet_id: Optional[str] = None,
        client: Optional[Any] = None,
    ):
        self.credentials_file = (
            credentials_file
            or os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", DEFAULT_CREDENTIALS_FILE)
        )
        self.spreadsheet_id = (
            spreadsheet_id or os.environ.get("GOOGLE_SPREADSHEET_ID", "")
        )
        self._client = client
        self._spreadsheet = None
        self._synced_hashes: Set[str] = set()

    def is_configured(self) -> bool:
        """Check if spreadsheet ID and credentials are available."""
        has_id = bool(self.spreadsheet_id and self.spreadsheet_id.strip())
        has_creds = (self._client is not None) or (
            bool(self.credentials_file) and os.path.isfile(self.credentials_file)
        )
        return has_id and has_creds

    def _get_client(self) -> gspread.Client:
        """Initialize or return gspread client."""
        if self._client is None:
            if not self.is_configured():
                raise ValueError(
                    "Google Sheets integration is not configured. "
                    "Set GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_SPREADSHEET_ID."
                )
            creds = Credentials.from_service_account_file(
                self.credentials_file, scopes=GOOGLE_SCOPES
            )
            self._client = gspread.authorize(creds)
        return self._client

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        """Open target spreadsheet by key."""
        if self._spreadsheet is None:
            client = self._get_client()
            self._spreadsheet = client.open_by_key(self.spreadsheet_id)
        return self._spreadsheet

    @staticmethod
    def _format_budget_bucket(bucket: Optional[Any], tx_type: Optional[Any] = None) -> str:
        """Map budget bucket to master Categories capitalization: Needs, Wants, Savings, Income, Transfer."""
        val = ""
        if bucket is not None:
            val = bucket.value if hasattr(bucket, "value") else str(bucket)
        val = val.strip().upper()

        if val in ("NEEDS", "NEED"):
            return "Needs"
        elif val in ("WANTS", "WANT"):
            return "Wants"
        elif "SAVING" in val or "INVEST" in val:
            return "Savings"
        elif val in ("INCOME", "EARNINGS"):
            return "Income"
        elif val in ("TRANSFER", "TRF"):
            return "Transfer"

        # Fallback to tx_type if bucket is unspecified or not recognized
        type_val = ""
        if tx_type is not None:
            type_val = tx_type.value if hasattr(tx_type, "value") else str(tx_type)
        type_val = type_val.strip().upper()

        if type_val == "INCOME":
            return "Income"
        elif type_val == "TRANSFER":
            return "Transfer"

        return "Wants"

    def _prepare_raw_row(self, parsed_tx: ParsedTransaction) -> List[Any]:
        """
        Row format for Transactions_Raw (Bronze layer - 10 columns):
        [raw_id, ingestion_timestamp, source_institution, channel, raw_payload, parsed_amount, parsed_direction, payload_hash, processing_status, clean_ledger_ref]
        """
        ts = parsed_tx.timestamp
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            date_compact = dt.strftime("%Y%m%d")
        except Exception:
            clean_ts = ts[:10].replace("-", "")
            date_compact = (
                clean_ts
                if len(clean_ts) == 8
                else datetime.now(timezone.utc).strftime("%Y%m%d")
            )

        raw_id = f"RAW-{date_compact}-{parsed_tx.raw_hash[:8].upper()}"
        clean_ledger_ref = f"TX-{date_compact}-{parsed_tx.raw_hash[:8].upper()}"

        inst_str = (
            parsed_tx.source_institution.value
            if hasattr(parsed_tx.source_institution, "value")
            else str(parsed_tx.source_institution)
        )

        channel = getattr(parsed_tx, "channel", None) or "PUSH_NOTIFICATION"

        is_income = (
            parsed_tx.transaction_type == TransactionType.INCOME
            or (
                hasattr(parsed_tx.transaction_type, "value")
                and parsed_tx.transaction_type.value == "INCOME"
            )
            or str(parsed_tx.transaction_type) == "INCOME"
        )
        direction = "CR" if is_income else "DB"

        return [
            raw_id,
            parsed_tx.timestamp,
            inst_str,
            channel,
            parsed_tx.raw_text,
            float(parsed_tx.amount),
            direction,
            parsed_tx.raw_hash,
            "PROCESSED",
            clean_ledger_ref,
        ]

    def _prepare_clean_row(self, parsed_tx: ParsedTransaction) -> List[Any]:
        """
        Row format for Ledger_Clean (Silver layer - 13 columns):
        [transaction_id, date, time, source_account, destination_merchant, type, category, budget_bucket, amount, notes, payment_method, raw_ref_id, status]
        """
        ts = parsed_tx.timestamp
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M:%S")
        except Exception:
            date_str = (
                ts[:10]
                if len(ts) >= 10
                else datetime.now(timezone.utc).strftime("%Y-%m-%d")
            )
            time_str = (
                ts[11:19]
                if len(ts) >= 19
                else datetime.now(timezone.utc).strftime("%H:%M:%S")
            )

        date_compact = date_str.replace("-", "")
        tx_id = f"TX-{date_compact}-{parsed_tx.raw_hash[:8].upper()}"

        # Standardize account name to match Dashboard Tab Column G exact names
        inst_to_sheet_acct = {
            "BCA": "BCA",
            "MANDIRI": "Mandiri",
            "BRI": "BRI",
            "BNI": "BNI",
            "JAGO": "Bank Jago",
            "SEABANK": "SeaBank",
            "GOPAY": "GoPay",
            "OVO": "OVO",
            "DANA": "DANA",
            "SHOPEEPAY": "ShopeePay",
            "CASH": "Cash",
        }
        inst_key = (
            parsed_tx.source_institution.value.upper()
            if hasattr(parsed_tx.source_institution, "value")
            else str(parsed_tx.source_institution).upper()
        )
        account = inst_to_sheet_acct.get(inst_key, parsed_tx.account_name or inst_key)

        destination_merchant = (
            getattr(parsed_tx, "to_account", None) or parsed_tx.merchant or ""
        )

        tx_type_str = (
            parsed_tx.transaction_type.value
            if hasattr(parsed_tx.transaction_type, "value")
            else str(parsed_tx.transaction_type)
        )

        budget_bucket = self._format_budget_bucket(
            parsed_tx.budget_bucket, parsed_tx.transaction_type
        )

        return [
            tx_id,
            date_str,
            time_str,
            account,
            destination_merchant,
            tx_type_str,
            parsed_tx.category or "",
            budget_bucket,
            float(parsed_tx.amount),
            parsed_tx.notes or "",
            parsed_tx.payment_method or "",
            parsed_tx.raw_hash,
            "VERIFIED",
        ]

    def append_transaction(self, parsed_tx: ParsedTransaction) -> bool:
        """
        Append a single transaction to Transactions_Raw and Ledger_Clean tabs.
        Provides robust exception handling and idempotency.
        """
        if not self.is_configured():
            logger.warning(
                "Google Sheets sync skipped: service account or spreadsheet ID not configured."
            )
            return False

        # Idempotency check in-memory
        if parsed_tx.raw_hash in self._synced_hashes:
            logger.info(
                f"Transaction {parsed_tx.raw_hash} already synced (idempotent skip)."
            )
            return True

        try:
            sh = self._get_spreadsheet()
            ws_raw = sh.worksheet("Transactions_Raw")
            ws_clean = sh.worksheet("Ledger_Clean")

            raw_row = self._prepare_raw_row(parsed_tx)
            clean_row = self._prepare_clean_row(parsed_tx)

            ws_raw.append_row(raw_row, value_input_option="USER_ENTERED")
            ws_clean.append_row(clean_row, value_input_option="USER_ENTERED")

            self._synced_hashes.add(parsed_tx.raw_hash)
            logger.info(
                f"Successfully synced transaction {parsed_tx.raw_hash} to Google Sheets."
            )
            return True
        except Exception as exc:
            logger.error(
                f"Failed to append transaction {parsed_tx.raw_hash} to Google Sheets: {exc}",
                exc_info=True,
            )
            return False

    def sync_batch(self, transactions: List[ParsedTransaction]) -> int:
        """
        Append multiple transactions to Transactions_Raw and Ledger_Clean in a single batch.
        Deduplicates within the batch and skips already synced transactions.
        Returns the count of successfully synced transactions.
        """
        if not transactions:
            return 0

        if not self.is_configured():
            logger.warning(
                "Google Sheets sync_batch skipped: service account or spreadsheet ID not configured."
            )
            return 0

        # Filter out already synced transactions and intra-batch duplicates
        to_sync: List[ParsedTransaction] = []
        seen_in_batch: Set[str] = set()

        for tx in transactions:
            if tx.raw_hash in self._synced_hashes or tx.raw_hash in seen_in_batch:
                continue
            seen_in_batch.add(tx.raw_hash)
            to_sync.append(tx)

        if not to_sync:
            logger.info("All transactions in batch are already synced.")
            return 0

        try:
            sh = self._get_spreadsheet()
            ws_raw = sh.worksheet("Transactions_Raw")
            ws_clean = sh.worksheet("Ledger_Clean")

            raw_rows = [self._prepare_raw_row(tx) for tx in to_sync]
            clean_rows = [self._prepare_clean_row(tx) for tx in to_sync]

            ws_raw.append_rows(raw_rows, value_input_option="USER_ENTERED")
            ws_clean.append_rows(clean_rows, value_input_option="USER_ENTERED")

            for tx in to_sync:
                self._synced_hashes.add(tx.raw_hash)

            logger.info(
                f"Successfully synced batch of {len(to_sync)} transactions to Google Sheets."
            )
            return len(to_sync)
        except Exception as exc:
            logger.error(
                f"Failed to execute sync_batch to Google Sheets: {exc}", exc_info=True
            )
            return 0

    def verify_structure(self) -> Dict[str, Any]:
        """Check presence of 5 required tabs in the target spreadsheet."""
        if not self.is_configured():
            return {
                "valid": False,
                "error": "Google Sheets integration is not configured",
                "expected_tabs": EXPECTED_SHEET_TABS,
                "existing_tabs": [],
                "missing_tabs": EXPECTED_SHEET_TABS,
            }

        try:
            sh = self._get_spreadsheet()
            worksheets = sh.worksheets()
            existing_tabs = [ws.title for ws in worksheets]
            missing_tabs = [
                tab for tab in EXPECTED_SHEET_TABS if tab not in existing_tabs
            ]

            return {
                "valid": len(missing_tabs) == 0,
                "expected_tabs": EXPECTED_SHEET_TABS,
                "existing_tabs": existing_tabs,
                "missing_tabs": missing_tabs,
            }
        except Exception as exc:
            logger.error(
                f"Failed to verify Google Sheets structure: {exc}", exc_info=True
            )
            return {
                "valid": False,
                "error": str(exc),
                "expected_tabs": EXPECTED_SHEET_TABS,
                "existing_tabs": [],
                "missing_tabs": EXPECTED_SHEET_TABS,
            }
