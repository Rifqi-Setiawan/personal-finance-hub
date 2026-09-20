"""Unit and integration tests for financial queries:
- Weekly cash flow (sisa uang minggu ini)
- Allowance / transfer tracking (sisa duit transfer)
- Multi-account liquid balances (saldo rekening & dompet)
- Server API endpoints
- CLI subcommands
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient

from finance_hub.storage import StorageManager, STARTING_BALANCES, format_idr
from finance_hub.server import create_app
from finance_hub.cli import main, cmd_weekly, cmd_allowance, cmd_balances
from finance_hub.models import (
    NotificationPayload,
    ParsedTransaction,
    TransactionType,
    CategoryBucket,
    Institution,
    compute_raw_hash,
)


@pytest.fixture
def storage():
    """Isolated in-memory database fixture."""
    sm = StorageManager(db_path=":memory:")
    yield sm
    sm.close()


from unittest.mock import MagicMock
from finance_hub.integrations.sheets_sync import GoogleSheetsSync


@pytest.fixture
def app_client(storage):
    """Test client wired to the isolated in-memory storage."""
    mock_sheets = MagicMock(spec=GoogleSheetsSync)
    mock_sheets.is_configured.return_value = False
    mock_sheets.append_transaction.return_value = True
    app = create_app(storage_manager=storage, sheets_sync=mock_sheets)
    with TestClient(app) as client:
        yield client


def add_tx(
    sm: StorageManager,
    amount: float,
    tx_type: TransactionType,
    account: str = "Mandiri",
    merchant: str = "Toko Merchant",
    category: str = "Food & Beverage",
    date_str: str = "2026-09-15",
    time_str: str = "12:00:00",
    bucket: CategoryBucket = CategoryBucket.WANTS,
    raw_hash: str = None,
):
    """Helper to add transactions to storage."""
    ts = f"{date_str}T{time_str}Z"
    text = f"{tx_type.value} {amount} {merchant} {date_str} {time_str}"
    h = raw_hash or compute_raw_hash(NotificationPayload(text=text, timestamp=ts))

    # Match Institution enum if possible
    inst = Institution.MANDIRI
    for i in Institution:
        if i.value.lower() in account.lower():
            inst = i
            break

    parsed = ParsedTransaction(
        raw_hash=h,
        source_institution=inst,
        transaction_type=tx_type,
        amount=amount,
        merchant=merchant,
        category=category,
        subcategory="General",
        account_name=account,
        timestamp=ts,
        raw_text=text,
        budget_bucket=bucket,
        payment_method="QRIS" if tx_type == TransactionType.EXPENSE else "TRANSFER",
    )
    payload = NotificationPayload(text=text, timestamp=ts)
    sm.save_transaction(payload, parsed)
    return h


class TestStartingBalances:
    def test_baseline_starting_balances(self):
        """Verify baseline balances configured for Rifqi."""
        assert STARTING_BALANCES["Mandiri"] == 20152955.0
        assert STARTING_BALANCES["GoPay"] == 7458.0
        assert STARTING_BALANCES["DANA"] == 5933.0
        assert STARTING_BALANCES["ShopeePay"] == 6112.0
        assert STARTING_BALANCES["BCA"] == 0.0
        assert STARTING_BALANCES["BRI"] == 0.0
        assert STARTING_BALANCES["BNI"] == 0.0
        assert STARTING_BALANCES["Bank Jago"] == 0.0
        assert STARTING_BALANCES["SeaBank"] == 0.0
        assert STARTING_BALANCES["OVO"] == 0.0
        assert STARTING_BALANCES["Cash"] == 0.0

        total = sum(STARTING_BALANCES.values())
        assert total == 20172458.0


class TestWeeklyCashflow:
    def test_empty_database_weekly_cashflow(self, storage):
        """Weekly cashflow on empty database returns zeroed metrics."""
        res = storage.get_weekly_cashflow(ref_date="2026-09-15")
        assert res["total_income"] == 0.0
        assert res["total_expense"] == 0.0
        assert res["net_remaining"] == 0.0
        assert res["start_date"] == "2026-09-14"  # Monday of that week
        assert res["end_date"] == "2026-09-20"    # Sunday of that week
        assert res["formatted_net_remaining"] == "Rp 0"

    def test_weekly_cashflow_with_transactions(self, storage):
        """Transactions inside the week are counted; outside are ignored."""
        # Inside the week (2026-09-14 to 2026-09-20)
        add_tx(storage, 5000000.0, TransactionType.INCOME, date_str="2026-09-15")
        add_tx(storage, 200000.0, TransactionType.EXPENSE, category="Dining", date_str="2026-09-16")
        add_tx(storage, 300000.0, TransactionType.EXPENSE, category="Groceries", date_str="2026-09-17")

        # Outside the week (2026-09-08 and 2026-09-25)
        add_tx(storage, 1000000.0, TransactionType.INCOME, date_str="2026-09-08")
        add_tx(storage, 500000.0, TransactionType.EXPENSE, date_str="2026-09-25")

        res = storage.get_weekly_cashflow(ref_date="2026-09-18")
        assert res["total_income"] == 5000000.0
        assert res["total_expense"] == 500000.0
        assert res["net_remaining"] == 4500000.0
        assert res["formatted_income"] == "Rp 5.000.000"
        assert res["formatted_expense"] == "Rp 500.000"
        assert res["formatted_net_remaining"] == "Rp 4.500.000"
        assert len(res["top_categories"]) == 2

    def test_weekly_cashflow_negative_net_remaining(self, storage):
        """Expense exceeds income produces negative net remaining."""
        add_tx(storage, 100000.0, TransactionType.INCOME, date_str="2026-09-15")
        add_tx(storage, 350000.0, TransactionType.EXPENSE, date_str="2026-09-16")

        res = storage.get_weekly_cashflow(ref_date=date(2026, 9, 17))
        assert res["net_remaining"] == -250000.0
        assert "-Rp 250.000" in res["formatted_net_remaining"]


class TestTransferAllowanceStatus:
    def test_allowance_no_transfer_fallback_to_starting_balance(self, storage):
        """When no transfer in is recorded, fallback to starting balance (20.172.458) minus expenses."""
        add_tx(storage, 172458.0, TransactionType.EXPENSE, date_str="2026-09-15")

        res = storage.get_transfer_allowance_status()
        assert res["has_transfer"] is False
        assert res["total_initial_balance"] == 20172458.0
        assert res["expenses_since"] == 172458.0
        assert res["remaining_balance"] == 20000000.0
        assert res["formatted_remaining_balance"] == "Rp 20.000.000"

    def test_allowance_with_transfer_inflow(self, storage):
        """When transfer in is present, calculates remaining from that transfer."""
        # Expense before transfer (should NOT be subtracted)
        add_tx(storage, 100000.0, TransactionType.EXPENSE, date_str="2026-09-10", time_str="09:00:00")

        # Transfer in on 2026-09-10 at 12:00:00
        add_tx(
            storage,
            3000000.0,
            TransactionType.INCOME,
            account="Mandiri",
            merchant="TRANSFER DARI KELUARGA",
            date_str="2026-09-10",
            time_str="12:00:00"
        )

        # Expenses after transfer
        add_tx(storage, 250000.0, TransactionType.EXPENSE, date_str="2026-09-11", time_str="14:00:00")
        add_tx(storage, 150000.0, TransactionType.EXPENSE, date_str="2026-09-12", time_str="18:00:00")

        res = storage.get_transfer_allowance_status()
        assert res["has_transfer"] is True
        assert res["transfer_amount"] == 3000000.0
        assert res["expenses_since"] == 400000.0
        assert res["remaining_balance"] == 2600000.0
        assert res["formatted_remaining_balance"] == "Rp 2.600.000"
        assert res["transfer_account"] == "Mandiri"
        assert "TRANSFER DARI KELUARGA" in res["transfer_from"]

    def test_allowance_picks_most_recent_transfer(self, storage):
        """When multiple transfers occur, the latest one is used as baseline."""
        # Old transfer
        add_tx(
            storage, 2000000.0, TransactionType.INCOME,
            date_str="2026-08-01", time_str="10:00:00", merchant="TRANSFER LAMA"
        )
        add_tx(storage, 500000.0, TransactionType.EXPENSE, date_str="2026-08-15")

        # Latest transfer
        add_tx(
            storage, 5000000.0, TransactionType.INCOME,
            date_str="2026-09-01", time_str="10:00:00", merchant="TRANSFER BARU BULANAN"
        )
        add_tx(storage, 1000000.0, TransactionType.EXPENSE, date_str="2026-09-02")

        res = storage.get_transfer_allowance_status()
        assert res["has_transfer"] is True
        assert res["transfer_amount"] == 5000000.0
        assert res["expenses_since"] == 1000000.0
        assert res["remaining_balance"] == 4000000.0
        assert "TRANSFER BARU BULANAN" in res["transfer_from"]


class TestAccountBalances:
    def test_initial_account_balances(self, storage):
        """Empty database reflects starting balances and total net worth."""
        res = storage.get_account_balances()
        assert res["total_liquid_net_worth"] == 20172458.0
        assert res["formatted_total_net_worth"] == "Rp 20.172.458"

        accounts = res["accounts"]
        assert accounts["Mandiri"]["current_balance"] == 20152955.0
        assert accounts["GoPay"]["current_balance"] == 7458.0
        assert accounts["DANA"]["current_balance"] == 5933.0
        assert accounts["ShopeePay"]["current_balance"] == 6112.0
        assert accounts["BCA"]["current_balance"] == 0.0

    def test_account_balances_with_transactions(self, storage):
        """Inflows and outflows correctly adjust per-account balances."""
        # Mandiri expense: 152,955
        add_tx(storage, 152955.0, TransactionType.EXPENSE, account="Mandiri", date_str="2026-09-10")

        # GoPay expense: 2,458
        add_tx(storage, 2458.0, TransactionType.EXPENSE, account="GoPay", date_str="2026-09-11")

        # Transfer from Mandiri to GoPay: 500,000
        add_tx(
            storage, 500000.0, TransactionType.TRANSFER,
            account="Mandiri", merchant="Transfer to GoPay", date_str="2026-09-12"
        )

        # Inflow to BCA: 1,000,000
        add_tx(storage, 1000000.0, TransactionType.INCOME, account="BCA", date_str="2026-09-13")

        res = storage.get_account_balances()
        accounts = res["accounts"]

        # Mandiri: 20152955 - 152955 - 500000 = 19500000
        assert accounts["Mandiri"]["current_balance"] == 19500000.0
        assert accounts["Mandiri"]["outflows"] == 652955.0

        # GoPay: 7458 - 2458 + 500000 = 505000
        assert accounts["GoPay"]["current_balance"] == 505000.0
        assert accounts["GoPay"]["inflows"] == 500000.0
        assert accounts["GoPay"]["outflows"] == 2458.0

        # BCA: 0 + 1000000 = 1000000
        assert accounts["BCA"]["current_balance"] == 1000000.0
        assert accounts["BCA"]["inflows"] == 1000000.0

        # DANA & ShopeePay unchanged
        assert accounts["DANA"]["current_balance"] == 5933.0
        assert accounts["ShopeePay"]["current_balance"] == 6112.0

        expected_total = 19500000.0 + 505000.0 + 1000000.0 + 5933.0 + 6112.0
        assert res["total_liquid_net_worth"] == expected_total


class TestAPIEndpoints:
    def test_api_query_weekly(self, app_client):
        """GET /api/query/weekly returns status 200 and weekly cash flow data."""
        res = app_client.get("/api/query/weekly?ref_date=2026-09-15")
        assert res.status_code == 200
        data = res.json()
        assert "start_date" in data
        assert "end_date" in data
        assert "total_income" in data
        assert "total_expense" in data
        assert "net_remaining" in data

    def test_api_query_allowance(self, app_client):
        """GET /api/query/allowance returns status 200 and allowance tracking data."""
        res = app_client.get("/api/query/allowance")
        assert res.status_code == 200
        data = res.json()
        assert "has_transfer" in data
        assert "remaining_balance" in data
        assert "formatted_remaining_balance" in data

    def test_api_query_balances(self, app_client):
        """GET /api/query/balances returns status 200 and account balances."""
        res = app_client.get("/api/query/balances")
        assert res.status_code == 200
        data = res.json()
        assert "accounts" in data
        assert "total_liquid_net_worth" in data
        assert data["total_liquid_net_worth"] == 20172458.0


class TestCLIQueries:
    def test_cli_weekly(self, capsys, storage):
        """CLI weekly command output verification."""
        add_tx(storage, 1500000.0, TransactionType.INCOME, date_str="2026-09-15")
        add_tx(storage, 300000.0, TransactionType.EXPENSE, date_str="2026-09-16")

        with patch("finance_hub.cli.get_storage", return_value=storage):
            with patch("sys.argv", ["finance_hub.cli", "weekly", "--date", "2026-09-15"]):
                main()

        out = capsys.readouterr().out
        assert "PERSONAL FINANCE HUB — SISA UANG MINGGU INI" in out
        assert "Total Pemasukan       : Rp 1.500.000" in out
        assert "Total Pengeluaran     : Rp 300.000" in out
        assert "Sisa Uang Minggu Ini  : Rp 1.200.000" in out

    def test_cli_allowance(self, capsys, storage):
        """CLI allowance command output verification."""
        with patch("finance_hub.cli.get_storage", return_value=storage):
            with patch("sys.argv", ["finance_hub.cli", "allowance"]):
                main()

        out = capsys.readouterr().out
        assert "PERSONAL FINANCE HUB — SISA DUIT TRANSFER / ALLOWANCE" in out
        assert "Saldo Awal Riil       : Rp 20.172.458" in out
        assert "Sisa Kas dari Saldo   : Rp 20.172.458" in out

    def test_cli_balances(self, capsys, storage):
        """CLI balances command output verification."""
        with patch("finance_hub.cli.get_storage", return_value=storage):
            with patch("sys.argv", ["finance_hub.cli", "balances"]):
                main()

        out = capsys.readouterr().out
        assert "PERSONAL FINANCE HUB — SALDO REKENING & DOMPET DIGITAL" in out
        assert "Mandiri" in out
        assert "Rp 20.152.955" in out
        assert "GoPay" in out
        assert "Rp 7.458" in out
        assert "DANA" in out
        assert "Rp 5.933" in out
        assert "ShopeePay" in out
        assert "Rp 6.112" in out
        assert "TOTAL LIQUID NET WORTH : Rp 20.172.458" in out
