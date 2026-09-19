"""Unit and integration tests for Google Sheets synchronization, offline resilience, and idempotency."""

import os
from typing import Optional
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from finance_hub.models import (
    NotificationPayload,
    ParsedTransaction,
    Institution,
    TransactionType,
    CategoryBucket,
    compute_raw_hash,
)
from finance_hub.storage import StorageManager
from finance_hub.integrations.sheets_sync import GoogleSheetsSync, EXPECTED_SHEET_TABS
from finance_hub.server import create_app
from finance_hub.cli import main, cmd_sync_sheets


def make_test_tx(
    raw_hash: str = "hash1234567890",
    tx_type: TransactionType = TransactionType.EXPENSE,
    amount: float = 55000.0,
    merchant: str = "Kopi Kenangan",
    category: str = "Dining Out & Cafes",
    account: str = "BCA",
    to_account: str = None,
    raw_text: str = "Pembayaran QRIS Kopi Kenangan Rp 55.000",
    device: str = "Galaxy-S24",
    budget_bucket: Optional[CategoryBucket] = None,
) -> ParsedTransaction:
    if budget_bucket is None:
        if tx_type == TransactionType.EXPENSE:
            budget_bucket = CategoryBucket.WANTS
        elif tx_type == TransactionType.INCOME:
            budget_bucket = CategoryBucket.INCOME
        elif tx_type == TransactionType.TRANSFER:
            budget_bucket = CategoryBucket.TRANSFER

    return ParsedTransaction(
        raw_hash=raw_hash,
        source_institution=Institution.BCA,
        transaction_type=tx_type,
        amount=amount,
        merchant=merchant,
        category=category,
        subcategory="Coffee",
        account_name=account,
        timestamp="2026-09-01T12:30:00",
        raw_text=raw_text,
        budget_bucket=budget_bucket,
        notes="Testing sync",
        payment_method="QRIS",
        source_device=device,
        to_account=to_account,
    )


class TestGoogleSheetsSyncConfig:
    def test_is_configured_false_when_empty(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SPREADSHEET_ID", raising=False)
        monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
        sync = GoogleSheetsSync(credentials_file="/nonexistent/creds.json", spreadsheet_id="")
        assert sync.is_configured() is False

    def test_is_configured_false_when_file_missing(self, monkeypatch):
        sync = GoogleSheetsSync(credentials_file="/nonexistent/creds.json", spreadsheet_id="sheet-id-xyz")
        assert sync.is_configured() is False

    def test_is_configured_true_when_file_and_id_present(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        sync = GoogleSheetsSync(credentials_file=str(creds_file), spreadsheet_id="sheet-id-xyz")
        assert sync.is_configured() is True

    def test_is_configured_true_with_injected_client(self):
        mock_client = MagicMock()
        sync = GoogleSheetsSync(spreadsheet_id="sheet-id-xyz", client=mock_client)
        assert sync.is_configured() is True


class TestGoogleSheetsAppendAndBatch:
    @pytest.fixture
    def mock_sheets_env(self):
        mock_client = MagicMock()
        mock_sh = MagicMock()
        mock_ws_raw = MagicMock()
        mock_ws_clean = MagicMock()

        def get_worksheet(name):
            if name == "Transactions_Raw":
                return mock_ws_raw
            elif name == "Ledger_Clean":
                return mock_ws_clean
            raise ValueError(f"Unknown worksheet {name}")

        mock_sh.worksheet.side_effect = get_worksheet
        mock_client.open_by_key.return_value = mock_sh

        sync = GoogleSheetsSync(spreadsheet_id="mock-sheet-123", client=mock_client)
        return sync, mock_ws_raw, mock_ws_clean

    def test_append_transaction_success(self, mock_sheets_env):
        sync, ws_raw, ws_clean = mock_sheets_env
        tx = make_test_tx(raw_hash="abc123456789")

        success = sync.append_transaction(tx)
        assert success is True

        # Check Transactions_Raw row format (10 columns):
        # [raw_id, ingestion_timestamp, source_institution, channel, raw_payload, parsed_amount, parsed_direction, payload_hash, processing_status, clean_ledger_ref]
        assert ws_raw.append_row.call_count == 1
        raw_args = ws_raw.append_row.call_args[0][0]
        assert len(raw_args) == 10
        assert raw_args == [
            "RAW-20260901-ABC12345",
            tx.timestamp,
            "BCA",
            "PUSH_NOTIFICATION",
            tx.raw_text,
            55000.0,
            "DB",
            tx.raw_hash,
            "PROCESSED",
            "TX-20260901-ABC12345",
        ]

        # Check Ledger_Clean row format (13 columns):
        # [transaction_id, date, time, source_account, destination_merchant, type, category, budget_bucket, amount, notes, payment_method, raw_ref_id, status]
        assert ws_clean.append_row.call_count == 1
        clean_args = ws_clean.append_row.call_args[0][0]
        assert len(clean_args) == 13
        assert clean_args == [
            "TX-20260901-ABC12345",
            "2026-09-01",
            "12:30:00",
            "BCA",
            "Kopi Kenangan",
            "EXPENSE",
            "Dining Out & Cafes",
            "Wants",
            55000.0,
            "Testing sync",
            "QRIS",
            "abc123456789",
            "VERIFIED",
        ]

    def test_append_transaction_transfer_populates_to_account(self, mock_sheets_env):
        sync, ws_raw, ws_clean = mock_sheets_env
        tx = make_test_tx(
            raw_hash="trf123456789",
            tx_type=TransactionType.TRANSFER,
            merchant="GoPay",
            account="BCA",
            to_account="GoPay Operational",
        )

        success = sync.append_transaction(tx)
        assert success is True

        assert ws_raw.append_row.call_count == 1
        raw_args = ws_raw.append_row.call_args[0][0]
        assert len(raw_args) == 10
        assert raw_args[6] == "DB"
        assert raw_args[7] == "trf123456789"
        assert raw_args[9] == "TX-20260901-TRF12345"

        assert ws_clean.append_row.call_count == 1
        clean_args = ws_clean.append_row.call_args[0][0]
        assert len(clean_args) == 13
        assert clean_args[0] == "TX-20260901-TRF12345"
        assert clean_args[4] == "GoPay Operational"  # to_account takes precedence
        assert clean_args[5] == "TRANSFER"
        assert clean_args[7] == "Transfer"
        assert clean_args[11] == "trf123456789"
        assert clean_args[12] == "VERIFIED"

    def test_append_transaction_income(self, mock_sheets_env):
        sync, ws_raw, ws_clean = mock_sheets_env
        tx = make_test_tx(
            raw_hash="inc123456789",
            tx_type=TransactionType.INCOME,
            amount=15000000.0,
            merchant="PT Tech Indonesia",
            category="Salary & Compensation",
            account="BCA",
            raw_text="Gaji transfer PT Tech Rp 15.000.000",
        )

        success = sync.append_transaction(tx)
        assert success is True

        raw_args = ws_raw.append_row.call_args[0][0]
        assert len(raw_args) == 10
        assert raw_args[0] == "RAW-20260901-INC12345"
        assert raw_args[5] == 15000000.0
        assert raw_args[6] == "CR"  # Credit / Inflow
        assert raw_args[7] == "inc123456789"
        assert raw_args[8] == "PROCESSED"
        assert raw_args[9] == "TX-20260901-INC12345"

        clean_args = ws_clean.append_row.call_args[0][0]
        assert len(clean_args) == 13
        assert clean_args[0] == "TX-20260901-INC12345"
        assert clean_args[4] == "PT Tech Indonesia"
        assert clean_args[5] == "INCOME"
        assert clean_args[6] == "Salary & Compensation"
        assert clean_args[7] == "Income"
        assert clean_args[8] == 15000000.0
        assert clean_args[11] == "inc123456789"
        assert clean_args[12] == "VERIFIED"

    def test_sync_batch_success(self, mock_sheets_env):
        sync, ws_raw, ws_clean = mock_sheets_env
        tx1 = make_test_tx(raw_hash="batch_tx_1", amount=10000.0)
        tx2 = make_test_tx(raw_hash="batch_tx_2", amount=20000.0)

        count = sync.sync_batch([tx1, tx2])
        assert count == 2

        assert ws_raw.append_rows.call_count == 1
        raw_rows = ws_raw.append_rows.call_args[0][0]
        assert len(raw_rows) == 2
        assert len(raw_rows[0]) == 10
        assert len(raw_rows[1]) == 10
        assert raw_rows[0][0] == "RAW-20260901-BATCH_TX"
        assert raw_rows[0][7] == "batch_tx_1"
        assert raw_rows[1][7] == "batch_tx_2"
        assert raw_rows[0][9] == "TX-20260901-BATCH_TX"

        assert ws_clean.append_rows.call_count == 1
        clean_rows = ws_clean.append_rows.call_args[0][0]
        assert len(clean_rows) == 2
        assert len(clean_rows[0]) == 13
        assert len(clean_rows[1]) == 13
        assert clean_rows[0][0] == "TX-20260901-BATCH_TX"
        assert clean_rows[0][7] == "Wants"
        assert clean_rows[0][8] == 10000.0
        assert clean_rows[1][8] == 20000.0
        assert clean_rows[0][11] == "batch_tx_1"
        assert clean_rows[1][11] == "batch_tx_2"
        assert clean_rows[0][12] == "VERIFIED"
        assert clean_rows[1][12] == "VERIFIED"

    def test_sync_batch_empty_list(self, mock_sheets_env):
        sync, ws_raw, ws_clean = mock_sheets_env
        count = sync.sync_batch([])
        assert count == 0
        assert ws_raw.append_rows.call_count == 0
        assert ws_clean.append_rows.call_count == 0


class TestIdempotency:
    def test_append_transaction_idempotent_skip(self):
        mock_client = MagicMock()
        mock_sh = MagicMock()
        mock_ws_raw = MagicMock()
        mock_ws_clean = MagicMock()
        mock_sh.worksheet.side_effect = lambda name: mock_ws_raw if name == "Transactions_Raw" else mock_ws_clean
        mock_client.open_by_key.return_value = mock_sh

        sync = GoogleSheetsSync(spreadsheet_id="idemp-sheet", client=mock_client)
        tx = make_test_tx(raw_hash="idemp_hash_001")

        # 1st append
        assert sync.append_transaction(tx) is True
        assert mock_ws_raw.append_row.call_count == 1
        assert mock_ws_clean.append_row.call_count == 1

        # 2nd append with same hash -> must skip calling Google Sheets API again
        assert sync.append_transaction(tx) is True
        assert mock_ws_raw.append_row.call_count == 1  # Still 1
        assert mock_ws_clean.append_row.call_count == 1  # Still 1

    def test_sync_batch_deduplicates_intra_batch_and_history(self):
        mock_client = MagicMock()
        mock_sh = MagicMock()
        mock_ws = MagicMock()
        mock_sh.worksheet.return_value = mock_ws
        mock_client.open_by_key.return_value = mock_sh

        sync = GoogleSheetsSync(spreadsheet_id="idemp-sheet", client=mock_client)
        tx1 = make_test_tx(raw_hash="dup_hash_1")
        tx2 = make_test_tx(raw_hash="dup_hash_1")  # Duplicate within batch
        tx3 = make_test_tx(raw_hash="dup_hash_2")

        # First batch
        count1 = sync.sync_batch([tx1, tx2, tx3])
        assert count1 == 2  # Only 2 unique transactions synced

        # Second batch with already synced tx1
        tx4 = make_test_tx(raw_hash="dup_hash_3")
        count2 = sync.sync_batch([tx1, tx4])
        assert count2 == 1  # tx1 skipped, only tx4 synced


class TestOfflineFallbackAndErrorHandling:
    def test_append_transaction_network_error_graceful(self):
        mock_client = MagicMock()
        mock_sh = MagicMock()
        mock_ws_raw = MagicMock()
        mock_ws_raw.append_row.side_effect = ConnectionError("Network dropped")
        mock_sh.worksheet.return_value = mock_ws_raw
        mock_client.open_by_key.return_value = mock_sh

        sync = GoogleSheetsSync(spreadsheet_id="offline-sheet", client=mock_client)
        tx = make_test_tx(raw_hash="offline_hash_1")

        # Must not crash, should log error and return False
        success = sync.append_transaction(tx)
        assert success is False
        assert tx.raw_hash not in sync._synced_hashes

    def test_sync_batch_network_error_graceful(self):
        mock_client = MagicMock()
        mock_sh = MagicMock()
        mock_ws_raw = MagicMock()
        mock_ws_raw.append_rows.side_effect = RuntimeError("Google API 503 Backend Error")
        mock_sh.worksheet.return_value = mock_ws_raw
        mock_client.open_by_key.return_value = mock_sh

        sync = GoogleSheetsSync(spreadsheet_id="offline-sheet", client=mock_client)
        tx = make_test_tx(raw_hash="offline_hash_2")

        count = sync.sync_batch([tx])
        assert count == 0
        assert tx.raw_hash not in sync._synced_hashes

    def test_append_transaction_when_unconfigured(self):
        sync = GoogleSheetsSync(credentials_file="/none/file.json", spreadsheet_id="")
        tx = make_test_tx(raw_hash="unconf_hash")
        assert sync.append_transaction(tx) is False

    def test_sync_batch_when_unconfigured(self):
        sync = GoogleSheetsSync(credentials_file="/none/file.json", spreadsheet_id="")
        tx = make_test_tx(raw_hash="unconf_hash")
        assert sync.sync_batch([tx]) == 0


class TestVerifyStructure:
    def test_verify_structure_all_tabs_present(self):
        mock_client = MagicMock()
        mock_sh = MagicMock()
        mock_worksheets = [MagicMock(title=t) for t in EXPECTED_SHEET_TABS]
        mock_sh.worksheets.return_value = mock_worksheets
        mock_client.open_by_key.return_value = mock_sh

        sync = GoogleSheetsSync(spreadsheet_id="struct-sheet", client=mock_client)
        res = sync.verify_structure()

        assert res["valid"] is True
        assert res["missing_tabs"] == []
        assert set(res["existing_tabs"]) == set(EXPECTED_SHEET_TABS)

    def test_verify_structure_missing_tabs(self):
        mock_client = MagicMock()
        mock_sh = MagicMock()
        # Only 3 tabs present
        mock_worksheets = [
            MagicMock(title="Dashboard"),
            MagicMock(title="Transactions_Raw"),
            MagicMock(title="Ledger_Clean"),
        ]
        mock_sh.worksheets.return_value = mock_worksheets
        mock_client.open_by_key.return_value = mock_sh

        sync = GoogleSheetsSync(spreadsheet_id="struct-sheet", client=mock_client)
        res = sync.verify_structure()

        assert res["valid"] is False
        assert "Categories" in res["missing_tabs"]
        assert "Monthly_Summary" in res["missing_tabs"]

    def test_verify_structure_unconfigured(self):
        sync = GoogleSheetsSync(credentials_file="/none.json", spreadsheet_id="")
        res = sync.verify_structure()
        assert res["valid"] is False
        assert "error" in res


class TestStorageSyncMethods:
    @pytest.fixture
    def storage(self):
        sm = StorageManager(db_path=":memory:")
        yield sm
        sm.close()

    def test_mark_synced_and_get_unsynced_transactions(self, storage):
        payload1 = NotificationPayload(
            text="m-Transfer: 01/09 07:14 TRSF DARI PT TECH Rp 10.000.000,00",
            package_name="com.bca",
            title="m-BCA",
            timestamp="2026-09-01T07:15:00",
        )
        tx1 = make_test_tx(raw_hash=compute_raw_hash(payload1), amount=10000000.0)
        storage.save_transaction(payload1, tx1)

        payload2 = NotificationPayload(
            text="Livin' Mandiri: 02/09 10:00 QRIS Resto Rp 75.000 Sukses",
            package_name="com.mandiri",
            title="Livin Mandiri",
            timestamp="2026-09-02T10:00:00",
        )
        tx2 = make_test_tx(raw_hash=compute_raw_hash(payload2), amount=75000.0)
        storage.save_transaction(payload2, tx2)

        # Initial state: 2 unsynced transactions
        assert storage.get_unsynced_count() == 2
        unsynced = storage.get_unsynced_transactions()
        assert len(unsynced) == 2
        assert isinstance(unsynced[0], ParsedTransaction)
        assert isinstance(unsynced[1], ParsedTransaction)

        # Mark 1st transaction as synced
        storage.mark_synced(tx1.raw_hash)
        assert storage.get_unsynced_count() == 1

        remaining = storage.get_unsynced_transactions()
        assert len(remaining) == 1
        assert remaining[0].raw_hash == tx2.raw_hash

        # Verify sheets_synced in get_transaction_by_hash
        rec1 = storage.get_transaction_by_hash(tx1.raw_hash)
        rec2 = storage.get_transaction_by_hash(tx2.raw_hash)
        assert rec1["sheets_synced"] is True
        assert rec2["sheets_synced"] is False


class TestServerSheetsEndpoints:
    @pytest.fixture
    def test_env(self):
        storage = StorageManager(db_path=":memory:")
        mock_sheets = MagicMock(spec=GoogleSheetsSync)
        mock_sheets.is_configured.return_value = True
        mock_sheets.spreadsheet_id = "test-sheet-id-456"
        mock_sheets.credentials_file = "/path/to/creds.json"
        mock_sheets.append_transaction.return_value = True
        mock_sheets.sync_batch.return_value = 1
        mock_sheets.verify_structure.return_value = {
            "valid": True,
            "expected_tabs": EXPECTED_SHEET_TABS,
            "existing_tabs": EXPECTED_SHEET_TABS,
            "missing_tabs": [],
        }

        app = create_app(storage_manager=storage, sheets_sync=mock_sheets)
        with TestClient(app) as client:
            yield client, storage, mock_sheets
        storage.close()

    def test_webhook_background_sync_successful(self, test_env):
        client, storage, mock_sheets = test_env
        payload = {
            "package_name": "com.bca",
            "title": "m-BCA",
            "text": "m-Transfer: 01/09 07:14 TRSF DARI PT TECH NUSANTARA Rp 25.000.000,00 KE REK 5310294821",
            "timestamp": "2026-09-01T07:15:00",
            "source_device": "Samsung Galaxy S24",
        }

        # POST webhook
        response = client.post("/webhook/transaction", json=payload)
        assert response.status_code == 200
        data = response.json()
        raw_hash = data["raw_hash"]

        # Background task must have called append_transaction
        assert mock_sheets.append_transaction.call_count == 1
        appended_tx = mock_sheets.append_transaction.call_args[0][0]
        assert appended_tx.raw_hash == raw_hash

        # Storage should show 0 pending sync
        assert storage.get_unsynced_count() == 0

    def test_webhook_offline_resilience_preserves_pending(self, test_env):
        client, storage, mock_sheets = test_env
        # Simulate offline / sheets failure
        mock_sheets.append_transaction.return_value = False

        payload = {
            "package_name": "id.dana",
            "title": "DANA",
            "text": "DANA Protection: 09/09 15:40 QRIS Indomaret Snack Rp 54.000 Berhasil",
            "timestamp": "2026-09-09T15:40:00",
        }

        response = client.post("/webhook/transaction", json=payload)
        assert response.status_code == 200

        # Webhook still succeeds, but DuckDB keeps sheets_synced=False for later backfill
        assert storage.get_unsynced_count() == 1

    def test_api_sync_sheets_endpoint(self, test_env):
        client, storage, mock_sheets = test_env

        # Ingest offline
        mock_sheets.append_transaction.return_value = False
        payload = {
            "text": "Livin' Mandiri: 02/09 14:15 PEMBAYARAN PLN Rp 850.000,00 SUKSES",
            "package_name": "com.mandiri",
            "title": "Mandiri",
        }
        client.post("/webhook/transaction", json=payload)
        assert storage.get_unsynced_count() == 1

        # Now trigger manual sync
        mock_sheets.sync_batch.return_value = 1
        sync_res = client.post("/api/sync-sheets")
        assert sync_res.status_code == 200
        sync_data = sync_res.json()
        assert sync_data["status"] == "success"
        assert sync_data["synced_count"] == 1
        assert sync_data["pending_remaining"] == 0
        assert mock_sheets.sync_batch.call_count == 1

    def test_api_sync_sheets_when_unconfigured(self):
        storage = StorageManager(db_path=":memory:")
        mock_sheets = MagicMock(spec=GoogleSheetsSync)
        mock_sheets.is_configured.return_value = False

        app = create_app(storage_manager=storage, sheets_sync=mock_sheets)
        with TestClient(app) as client:
            res = client.post("/api/sync-sheets")
            assert res.status_code == 503
            assert "not configured" in res.json()["message"]
        storage.close()

    def test_api_sheets_status_endpoint(self, test_env):
        client, storage, mock_sheets = test_env

        res = client.get("/api/sheets-status?verify=true")
        assert res.status_code == 200
        data = res.json()
        assert data["configured"] is True
        assert data["spreadsheet_id"] == "test-sheet-id-456"
        assert data["pending_sync_count"] == 0
        assert "structure_verification" in data
        assert data["structure_verification"]["valid"] is True


class TestCLISyncSheets:
    def test_cli_sync_sheets_status(self, capsys):
        test_args = ["finance_hub.cli", "sync-sheets", "--status"]
        with patch("sys.argv", test_args):
            main()

        captured = capsys.readouterr().out
        assert "PERSONAL FINANCE HUB — GOOGLE SHEETS CONNECTION STATUS" in captured
        assert "Pending Sync Count" in captured

    def test_cli_sync_sheets_all(self, capsys):
        test_args = ["finance_hub.cli", "sync-sheets", "--all"]
        with patch("sys.argv", test_args):
            main()

        captured = capsys.readouterr().out
        assert "PERSONAL FINANCE HUB — GOOGLE SHEETS BACKFILL SYNC" in captured
