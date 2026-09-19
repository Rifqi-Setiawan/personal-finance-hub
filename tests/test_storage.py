"""Unit tests for DuckDB storage manager and SHA-256 idempotency guarantee."""

import pytest
from finance_hub.models import (
    NotificationPayload,
    ParsedTransaction,
    Institution,
    TransactionType,
    CategoryBucket,
    compute_raw_hash,
)
from finance_hub.storage import StorageManager


@pytest.fixture
def storage():
    sm = StorageManager(db_path=":memory:")
    yield sm
    sm.close()


def make_sample_tx(text: str, amount: float = 50000.0, tx_type: TransactionType = TransactionType.EXPENSE):
    payload = NotificationPayload(
        package_name="com.bca",
        title="m-BCA",
        text=text,
        timestamp="2026-09-01T12:00:00"
    )
    raw_hash = compute_raw_hash(payload)
    parsed = ParsedTransaction(
        raw_hash=raw_hash,
        source_institution=Institution.BCA,
        transaction_type=tx_type,
        amount=amount,
        merchant="Sample Merchant",
        category="Dining Out & Cafes" if tx_type == TransactionType.EXPENSE else "Salary & Compensation",
        subcategory="Sample Sub",
        account_name="BCA Account",
        timestamp="2026-09-01T12:00:00",
        raw_text=text,
        budget_bucket=CategoryBucket.WANTS if tx_type == TransactionType.EXPENSE else CategoryBucket.INCOME,
        payment_method="QRIS"
    )
    return payload, parsed


class TestStorageManager:
    def test_tables_initialization(self, storage):
        # Verify both tables exist
        tables = storage._conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "raw_notifications" in table_names
        assert "ledger_transactions" in table_names

    def test_save_transaction_success(self, storage):
        payload, parsed = make_sample_tx("Pembayaran QRIS Kopi Kenangan Rp 50.000", 50000.0)
        saved, tx_id = storage.save_transaction(payload, parsed)

        assert saved is True
        assert tx_id.startswith("TX-20260901-")
        assert storage.get_transaction_count() == 1
        assert storage.is_hash_exists(parsed.raw_hash) is True

    def test_idempotency_duplicate_ignored(self, storage):
        payload, parsed = make_sample_tx("Pembayaran QRIS Kopi Kenangan Rp 50.000", 50000.0)

        # First ingestion
        saved1, tx_id1 = storage.save_transaction(payload, parsed)
        assert saved1 is True

        # Second ingestion with identical payload and hash
        saved2, tx_id2 = storage.save_transaction(payload, parsed)
        assert saved2 is False
        assert tx_id2 == "duplicate_ignored"

        # Ledger transaction count must remain 1
        assert storage.get_transaction_count() == 1

    def test_get_transaction_by_hash(self, storage):
        payload, parsed = make_sample_tx("Pembayaran Tagihan Listrik Rp 350.000", 350000.0)
        storage.save_transaction(payload, parsed)

        record = storage.get_transaction_by_hash(parsed.raw_hash)
        assert record is not None
        assert record["amount"] == 350000.0
        assert record["raw_ref_id"] == parsed.raw_hash
        assert record["destination_merchant"] == "Sample Merchant"

    def test_get_recent_transactions_pagination(self, storage):
        for i in range(5):
            payload, parsed = make_sample_tx(f"Transaksi Ke-{i} Rp 10.000", 10000.0 * (i + 1))
            # Vary payload slightly so hashes differ
            payload.text = f"Transaksi Unique {i} Rp 10.000"
            parsed.raw_hash = compute_raw_hash(payload)
            storage.save_transaction(payload, parsed)

        assert storage.get_transaction_count() == 5

        page1 = storage.get_recent_transactions(limit=3, offset=0)
        assert len(page1) == 3

        page2 = storage.get_recent_transactions(limit=3, offset=3)
        assert len(page2) == 2

    def test_financial_summary_calculation(self, storage):
        # 1. Add Income
        p_inc, t_inc = make_sample_tx("Gaji Payroll Rp 20.000.000", 20000000.0, TransactionType.INCOME)
        storage.save_transaction(p_inc, t_inc)

        # 2. Add Needs Expense
        p_ned, t_ned = make_sample_tx("Indomaret Groceries Rp 2.000.000", 2000000.0, TransactionType.EXPENSE)
        t_ned.budget_bucket = CategoryBucket.NEEDS
        t_ned.raw_hash = compute_raw_hash(p_ned)
        storage.save_transaction(p_ned, t_ned)

        # 3. Add Wants Expense
        p_wnt, t_wnt = make_sample_tx("Cafe Dining Rp 1.000.000", 1000000.0, TransactionType.EXPENSE)
        t_wnt.budget_bucket = CategoryBucket.WANTS
        t_wnt.raw_hash = compute_raw_hash(p_wnt)
        storage.save_transaction(p_wnt, t_wnt)

        # 4. Add Savings
        p_sav, t_sav = make_sample_tx("Bibit Investasi Rp 4.000.000", 4000000.0, TransactionType.EXPENSE)
        t_sav.budget_bucket = CategoryBucket.SAVINGS_INVESTMENTS
        t_sav.raw_hash = compute_raw_hash(p_sav)
        storage.save_transaction(p_sav, t_sav)

        summary = storage.get_summary()
        assert summary["total_income"] == 20000000.0
        assert summary["needs_expense"] == 2000000.0
        assert summary["wants_expense"] == 1000000.0
        assert summary["total_expense"] == 3000000.0  # needs + wants
        assert summary["savings_investments"] == 4000000.0
        assert summary["compliance_status"] == "BALANCED"
        assert summary["savings_rate_pct"] > 0
