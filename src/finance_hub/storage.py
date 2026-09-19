"""DuckDB storage manager with SHA-256 idempotency guarantee."""

import os
import threading
from typing import Optional, List, Dict, Any, Tuple, Union
from datetime import datetime, timezone, date, timedelta
import uuid

import duckdb

from finance_hub.models import (
    NotificationPayload,
    ParsedTransaction,
    TransactionType,
    CategoryBucket,
    Institution,
    compute_text_hash,
)

# Baseline Starting Balances configured by Rifqi
STARTING_BALANCES: Dict[str, float] = {
    "Mandiri": 20152955.0,
    "GoPay": 7458.0,
    "DANA": 5933.0,
    "ShopeePay": 6112.0,
    "BCA": 0.0,
    "BRI": 0.0,
    "BNI": 0.0,
    "Bank Jago": 0.0,
    "SeaBank": 0.0,
    "OVO": 0.0,
    "Cash": 0.0,
}


def format_idr(amount: float) -> str:
    """Format float into Indonesian Rupiah format, e.g. Rp 20.152.955."""
    sign = "-" if amount < 0 else ""
    abs_amt = abs(amount)
    formatted = f"{abs_amt:,.0f}".replace(",", ".")
    return f"{sign}Rp {formatted}"


class StorageManager:
    """Manages DuckDB persistence for Bronze (raw_notifications) and Silver (ledger_transactions) layers."""

    STARTING_BALANCES = STARTING_BALANCES

    def __init__(self, db_path: str = "data/finance.duckdb"):
        self.db_path = db_path
        self._lock = threading.Lock()

        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        self._conn = duckdb.connect(self.db_path)
        self.init_tables()

    def init_tables(self) -> None:
        """Create Bronze and Silver tables if they do not exist."""
        with self._lock:
            # 1. Bronze Layer: Raw Notifications
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS raw_notifications (
                    raw_hash VARCHAR PRIMARY KEY,
                    package_name VARCHAR,
                    title VARCHAR,
                    raw_payload VARCHAR,
                    source_device VARCHAR,
                    ingestion_timestamp VARCHAR,
                    source_institution VARCHAR,
                    channel VARCHAR,
                    parsed_amount DOUBLE,
                    parsed_direction VARCHAR,
                    processing_status VARCHAR,
                    clean_ledger_ref VARCHAR,
                    sheets_synced BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Silver Layer: Ledger Transactions
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS ledger_transactions (
                    transaction_id VARCHAR PRIMARY KEY,
                    date VARCHAR,
                    time VARCHAR,
                    source_account VARCHAR,
                    destination_merchant VARCHAR,
                    type VARCHAR,
                    category VARCHAR,
                    subcategory VARCHAR,
                    budget_bucket VARCHAR,
                    amount DOUBLE,
                    notes VARCHAR,
                    payment_method VARCHAR,
                    raw_ref_id VARCHAR,
                    reconciliation_status VARCHAR,
                    sheets_synced BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Safe schema migrations for existing databases
            try:
                self._conn.execute("ALTER TABLE raw_notifications ADD COLUMN IF NOT EXISTS sheets_synced BOOLEAN DEFAULT FALSE;")
            except Exception:
                pass

            try:
                self._conn.execute("ALTER TABLE ledger_transactions ADD COLUMN IF NOT EXISTS sheets_synced BOOLEAN DEFAULT FALSE;")
            except Exception:
                pass

    def is_hash_exists(self, raw_hash: str) -> bool:
        """Check if raw_hash already exists in raw_notifications."""
        with self._lock:
            res = self._conn.execute(
                "SELECT COUNT(*) FROM raw_notifications WHERE raw_hash = ?",
                [raw_hash]
            ).fetchone()
            return res[0] > 0 if res else False

    def save_transaction(
        self,
        payload: NotificationPayload,
        parsed: ParsedTransaction,
        channel: str = "PUSH_NOTIFICATION"
    ) -> Tuple[bool, str]:
        """
        Idempotent save operation.
        Returns:
            (is_new_saved: bool, transaction_id_or_status: str)
            - If duplicate: (False, "duplicate_ignored")
            - If saved: (True, transaction_id)
        """
        with self._lock:
            # Idempotency check
            existing = self._conn.execute(
                "SELECT clean_ledger_ref FROM raw_notifications WHERE raw_hash = ?",
                [parsed.raw_hash]
            ).fetchone()

            if existing:
                return False, "duplicate_ignored"

            # Parse date and time components from ISO timestamp
            ts = parsed.timestamp
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                date_str = ts[:10] if len(ts) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
                time_str = ts[11:19] if len(ts) >= 19 else datetime.now(timezone.utc).strftime("%H:%M:%S")

            tx_id = f"TX-{date_str.replace('-', '')}-{parsed.raw_hash[:8].upper()}"
            direction = "CR" if parsed.transaction_type == TransactionType.INCOME else "DB"
            bucket_str = parsed.budget_bucket.value if parsed.budget_bucket else "WANTS"

            # Insert into raw_notifications (Bronze)
            self._conn.execute("""
                INSERT INTO raw_notifications (
                    raw_hash, package_name, title, raw_payload, source_device,
                    ingestion_timestamp, source_institution, channel,
                    parsed_amount, parsed_direction, processing_status,
                    clean_ledger_ref, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [
                parsed.raw_hash,
                payload.package_name,
                payload.title,
                payload.text,
                payload.source_device or "mobile",
                parsed.timestamp,
                parsed.source_institution.value,
                channel,
                parsed.amount,
                direction,
                "PROCESSED",
                tx_id
            ])

            # Insert into ledger_transactions (Silver)
            self._conn.execute("""
                INSERT INTO ledger_transactions (
                    transaction_id, date, time, source_account, destination_merchant,
                    type, category, subcategory, budget_bucket, amount,
                    notes, payment_method, raw_ref_id, reconciliation_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [
                tx_id,
                date_str,
                time_str,
                parsed.account_name or parsed.source_institution.value,
                parsed.merchant,
                parsed.transaction_type.value,
                parsed.category,
                parsed.subcategory,
                bucket_str,
                parsed.amount,
                parsed.notes,
                parsed.payment_method,
                parsed.raw_hash,
                "VERIFIED"
            ])

            return True, tx_id

    def get_transaction_by_hash(self, raw_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve a ledger transaction by its raw hash reference."""
        with self._lock:
            cols = [
                "transaction_id", "date", "time", "source_account", "destination_merchant",
                "type", "category", "subcategory", "budget_bucket", "amount",
                "notes", "payment_method", "raw_ref_id", "reconciliation_status", "sheets_synced", "created_at"
            ]
            res = self._conn.execute(
                f"SELECT {', '.join(cols)} FROM ledger_transactions WHERE raw_ref_id = ?",
                [raw_hash]
            ).fetchone()
            if not res:
                return None
            return dict(zip(cols, res))

    def get_recent_transactions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve recent transactions ordered by date and time descending."""
        with self._lock:
            cols = [
                "transaction_id", "date", "time", "source_account", "destination_merchant",
                "type", "category", "subcategory", "budget_bucket", "amount",
                "notes", "payment_method", "raw_ref_id", "reconciliation_status", "sheets_synced", "created_at"
            ]
            rows = self._conn.execute(
                f"""SELECT {', '.join(cols)} 
                    FROM ledger_transactions 
                    ORDER BY date DESC, time DESC, created_at DESC 
                    LIMIT ? OFFSET ?""",
                [limit, offset]
            ).fetchall()
            return [dict(zip(cols, row)) for row in rows]

    def mark_synced(self, raw_hash: str) -> None:
        """Mark transaction as synced to Google Sheets in raw_notifications and ledger_transactions."""
        with self._lock:
            self._conn.execute(
                "UPDATE raw_notifications SET sheets_synced = TRUE WHERE raw_hash = ?",
                [raw_hash]
            )
            self._conn.execute(
                "UPDATE ledger_transactions SET sheets_synced = TRUE WHERE raw_ref_id = ?",
                [raw_hash]
            )

    def get_unsynced_transactions(self) -> List[ParsedTransaction]:
        """Retrieve all transactions that haven't been synced to Google Sheets."""
        with self._lock:
            query = """
                SELECT 
                    l.raw_ref_id,
                    r.source_institution,
                    l.type,
                    l.amount,
                    l.destination_merchant,
                    l.category,
                    l.subcategory,
                    l.source_account,
                    r.ingestion_timestamp,
                    r.raw_payload,
                    l.budget_bucket,
                    l.notes,
                    l.payment_method,
                    r.source_device,
                    l.date,
                    l.time
                FROM ledger_transactions l
                LEFT JOIN raw_notifications r ON l.raw_ref_id = r.raw_hash
                WHERE l.sheets_synced = FALSE OR l.sheets_synced IS NULL
                ORDER BY l.date ASC, l.time ASC, l.created_at ASC
            """
            rows = self._conn.execute(query).fetchall()
            result: List[ParsedTransaction] = []
            for r in rows:
                (
                    raw_hash, inst_val, tx_type_val, amount, merchant,
                    category, subcat, account, ts, raw_payload,
                    bucket_val, notes, pay_method, source_dev, date_str, time_str
                ) = r

                # Determine institution
                inst = Institution.CASH
                if inst_val:
                    try:
                        inst = Institution(inst_val)
                    except ValueError:
                        pass
                elif account:
                    for i in Institution:
                        if i.value.lower() in account.lower():
                            inst = i
                            break

                # Determine transaction type
                tx_type = TransactionType.EXPENSE
                if tx_type_val:
                    try:
                        tx_type = TransactionType(tx_type_val)
                    except ValueError:
                        pass

                # Determine bucket
                bucket = None
                if bucket_val:
                    try:
                        bucket = CategoryBucket(bucket_val)
                    except ValueError:
                        pass

                timestamp = ts or f"{date_str}T{time_str}Z"
                raw_text = raw_payload or f"{tx_type.value} {amount} {merchant}"

                tx = ParsedTransaction(
                    raw_hash=raw_hash or compute_text_hash(raw_text, timestamp),
                    source_institution=inst,
                    transaction_type=tx_type,
                    amount=float(amount) if amount is not None else 0.0,
                    merchant=merchant or "",
                    category=category or "Other",
                    subcategory=subcat,
                    account_name=account,
                    timestamp=timestamp,
                    raw_text=raw_text,
                    budget_bucket=bucket,
                    notes=notes,
                    payment_method=pay_method or "UNKNOWN",
                    source_device=source_dev or "mobile",
                )
                result.append(tx)
            return result

    def get_unsynced_count(self) -> int:
        """Return total number of transactions pending sync to Google Sheets."""
        with self._lock:
            res = self._conn.execute(
                "SELECT COUNT(*) FROM ledger_transactions WHERE sheets_synced = FALSE OR sheets_synced IS NULL"
            ).fetchone()
            return res[0] if res else 0

    def get_transaction_count(self) -> int:
        """Return total number of ledger transactions recorded."""
        with self._lock:
            res = self._conn.execute("SELECT COUNT(*) FROM ledger_transactions").fetchone()
            return res[0] if res else 0

    def get_summary(self) -> Dict[str, Any]:
        """Compute aggregated KPIs, 50/30/20 budget allocations, and health statuses."""
        with self._lock:
            income_res = self._conn.execute(
                "SELECT COALESCE(SUM(amount), 0.0) FROM ledger_transactions WHERE type = 'INCOME'"
            ).fetchone()
            total_income = float(income_res[0]) if income_res else 0.0

            needs_res = self._conn.execute(
                "SELECT COALESCE(SUM(amount), 0.0) FROM ledger_transactions WHERE type = 'EXPENSE' AND budget_bucket = 'NEEDS'"
            ).fetchone()
            needs_expense = float(needs_res[0]) if needs_res else 0.0

            wants_res = self._conn.execute(
                "SELECT COALESCE(SUM(amount), 0.0) FROM ledger_transactions WHERE type = 'EXPENSE' AND budget_bucket = 'WANTS'"
            ).fetchone()
            wants_expense = float(wants_res[0]) if wants_res else 0.0

            savings_res = self._conn.execute(
                "SELECT COALESCE(SUM(amount), 0.0) FROM ledger_transactions WHERE budget_bucket = 'SAVINGS_INVESTMENTS'"
            ).fetchone()
            savings_expense = float(savings_res[0]) if savings_res else 0.0

            transfer_res = self._conn.execute(
                "SELECT COALESCE(SUM(amount), 0.0) FROM ledger_transactions WHERE type = 'TRANSFER'"
            ).fetchone()
            total_transfers = float(transfer_res[0]) if transfer_res else 0.0

            total_living_outflow = needs_expense + wants_expense
            net_surplus = total_income - total_living_outflow - savings_expense
            savings_rate = ((savings_expense + max(0.0, net_surplus)) / total_income * 100.0) if total_income > 0 else 0.0

            # 50/30/20 Targets
            target_needs = 0.50 * total_income
            target_wants = 0.30 * total_income
            target_savings = 0.20 * total_income

            # Compliance logic
            if total_income > 0:
                if needs_expense <= target_needs and wants_expense <= target_wants and savings_expense >= target_savings:
                    compliance_status = "BALANCED"
                elif savings_expense < target_savings:
                    compliance_status = "LOW SAVINGS"
                else:
                    compliance_status = "OVERSPENT"
            else:
                compliance_status = "NO_INCOME_RECORDED"

            # Top categories
            cat_rows = self._conn.execute("""
                SELECT category, budget_bucket, COALESCE(SUM(amount), 0.0) as total_amt, COUNT(*) as count
                FROM ledger_transactions
                GROUP BY category, budget_bucket
                ORDER BY total_amt DESC
                LIMIT 10
            """).fetchall()
            top_categories = [
                {"category": r[0], "bucket": r[1], "amount": float(r[2]), "count": r[3]}
                for r in cat_rows
            ]

            # Institution distribution
            inst_rows = self._conn.execute("""
                SELECT source_account, COUNT(*) as count, COALESCE(SUM(amount), 0.0) as total_amt
                FROM ledger_transactions
                GROUP BY source_account
                ORDER BY count DESC
            """).fetchall()
            institutions = [
                {"account": r[0], "count": r[1], "total_amount": float(r[2])}
                for r in inst_rows
            ]

            total_tx = self._conn.execute("SELECT COUNT(*) FROM ledger_transactions").fetchone()[0]

            return {
                "total_income": total_income,
                "total_expense": total_living_outflow,
                "needs_expense": needs_expense,
                "target_needs_50pct": target_needs,
                "wants_expense": wants_expense,
                "target_wants_30pct": target_wants,
                "savings_investments": savings_expense,
                "target_savings_20pct": target_savings,
                "total_transfers": total_transfers,
                "net_surplus": net_surplus,
                "savings_rate_pct": round(savings_rate, 2),
                "compliance_status": compliance_status,
                "total_transactions": total_tx,
                "top_categories": top_categories,
                "institutions": institutions
            }

    def get_weekly_cashflow(self, ref_date: Optional[Any] = None) -> Dict[str, Any]:
        """
        Menghitung sisa uang minggu ini:
        - Rentang minggu berjalan (Senin s/d Minggu).
        - Pemasukan minggu ini.
        - Pengeluaran minggu ini.
        - Sisa uang minggu ini = Pemasukan - Pengeluaran.
        """
        if ref_date is None:
            today = datetime.now().date()
        elif isinstance(ref_date, str):
            try:
                today = date.fromisoformat(ref_date[:10])
            except Exception:
                today = datetime.now().date()
        elif isinstance(ref_date, datetime):
            today = ref_date.date()
        elif isinstance(ref_date, date):
            today = ref_date
        else:
            today = datetime.now().date()

        start_of_week = today - timedelta(days=today.weekday())  # Monday
        end_of_week = start_of_week + timedelta(days=6)         # Sunday
        start_str = start_of_week.strftime("%Y-%m-%d")
        end_str = end_of_week.strftime("%Y-%m-%d")

        with self._lock:
            inc_res = self._conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0.0)
                FROM ledger_transactions
                WHERE type = 'INCOME' AND date >= ? AND date <= ?
                """,
                [start_str, end_str]
            ).fetchone()[0]
            total_income = float(inc_res) if inc_res else 0.0

            exp_res = self._conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0.0)
                FROM ledger_transactions
                WHERE type = 'EXPENSE' AND date >= ? AND date <= ?
                """,
                [start_str, end_str]
            ).fetchone()[0]
            total_expense = float(exp_res) if exp_res else 0.0

            cat_res = self._conn.execute(
                """
                SELECT category, budget_bucket, COALESCE(SUM(amount), 0.0) as total
                FROM ledger_transactions
                WHERE type = 'EXPENSE' AND date >= ? AND date <= ?
                GROUP BY category, budget_bucket
                ORDER BY total DESC
                LIMIT 5
                """,
                [start_str, end_str]
            ).fetchall()

            net_remaining = total_income - total_expense

            return {
                "period": f"{start_of_week.strftime('%d %b')} - {end_of_week.strftime('%d %b %Y')}",
                "start_date": start_str,
                "end_date": end_str,
                "total_income": total_income,
                "total_expense": total_expense,
                "net_remaining": net_remaining,
                "formatted_income": format_idr(total_income),
                "formatted_expense": format_idr(total_expense),
                "formatted_net_remaining": format_idr(net_remaining),
                "top_categories": [
                    {"category": r[0], "bucket": r[1], "amount": float(r[2]), "formatted": format_idr(r[2])}
                    for r in cat_res
                ]
            }

    def get_transfer_allowance_status(self) -> Dict[str, Any]:
        """
        Menghitung sisa uang dari transferan terakhir:
        - Mencari transaksi transfer masuk / pemasukan terakhir (uang bulanan / saku).
        - Menghitung total pengeluaran sejak tanggal transfer masuk tersebut.
        - Sisa duit transfer = Nominal Transfer Masuk Terakhir - Total Pengeluaran Sejak Transfer.
        - Jika belum ada transfer masuk baru, laporkan sisa kas dari saldo awal Rp 20.172.458 dikurangi pengeluaran sejak inisialisasi.
        """
        initial_balance = sum(STARTING_BALANCES.values())

        with self._lock:
            # Cari transaksi pemasukan / transfer masuk terakhir
            last_inflow = self._conn.execute(
                """
                SELECT transaction_id, date, time, source_account, destination_merchant, amount, notes, raw_ref_id
                FROM ledger_transactions
                WHERE type = 'INCOME' OR (type = 'TRANSFER' AND (
                    destination_merchant ILIKE '%mandiri%' OR destination_merchant ILIKE '%gopay%'
                    OR destination_merchant ILIKE '%dana%' OR destination_merchant ILIKE '%shopeepay%'
                    OR destination_merchant ILIKE '%rekening%' OR destination_merchant ILIKE '%tabungan%'
                ))
                ORDER BY date DESC, time DESC, created_at DESC
                LIMIT 1
                """
            ).fetchone()

            if not last_inflow:
                exp_res = self._conn.execute(
                    "SELECT COALESCE(SUM(amount), 0.0) FROM ledger_transactions WHERE type = 'EXPENSE'"
                ).fetchone()[0]
                total_expenses = float(exp_res) if exp_res else 0.0
                remaining = initial_balance - total_expenses

                return {
                    "has_transfer": False,
                    "message": f"Belum ada transfer masuk baru. Sisa kas dari saldo awal: {format_idr(remaining)}",
                    "total_initial_balance": initial_balance,
                    "formatted_initial_balance": format_idr(initial_balance),
                    "transfer_amount": 0.0,
                    "formatted_transfer_amount": format_idr(0.0),
                    "expenses_since": total_expenses,
                    "formatted_expenses_since": format_idr(total_expenses),
                    "remaining_balance": remaining,
                    "formatted_remaining_balance": format_idr(remaining),
                }

            tx_id, tx_date, tx_time, account, merchant, amount, notes, raw_ref_id = last_inflow
            amount = float(amount)
            clean_time = (tx_time or "00:00:00")[:8]

            # Hitung total pengeluaran sejak tanggal & waktu transfer masuk tersebut
            exp_res = self._conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0.0)
                FROM ledger_transactions
                WHERE type = 'EXPENSE' AND (date > ? OR (date = ? AND time >= ?))
                """,
                [tx_date, tx_date, clean_time]
            ).fetchone()[0]
            exp_since = float(exp_res) if exp_res else 0.0
            remaining = amount - exp_since

            try:
                dt_tx = datetime.strptime(f"{tx_date} {clean_time}", "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                days_passed = max((now - dt_tx).days, 0)
            except Exception:
                days_passed = 0

            daily_burn = exp_since / days_passed if days_passed > 0 else exp_since

            return {
                "has_transfer": True,
                "transfer_id": tx_id,
                "transfer_date": tx_date,
                "transfer_time": tx_time,
                "transfer_account": account,
                "transfer_from": merchant,
                "transfer_amount": amount,
                "formatted_transfer_amount": format_idr(amount),
                "expenses_since": exp_since,
                "formatted_expenses_since": format_idr(exp_since),
                "remaining_balance": remaining,
                "formatted_remaining_balance": format_idr(remaining),
                "days_since_transfer": days_passed,
                "daily_burn_rate": daily_burn,
                "formatted_daily_burn": format_idr(daily_burn),
                "message": f"Sisa transferan terakhir: {format_idr(remaining)} (dari transfer {format_idr(amount)} pada {tx_date})",
            }

    def get_account_balances(self) -> Dict[str, Any]:
        """
        Menghitung saldo saat ini di setiap rekening & dompet:
        Current Balance = Starting Balance + Inflow - Outflow.
        Total liquid net worth.
        """
        with self._lock:
            account_keywords = {
                "Mandiri": ["mandiri"],
                "GoPay": ["gopay"],
                "DANA": ["dana"],
                "ShopeePay": ["shopee"],
                "BCA": ["bca"],
                "BRI": ["bri"],
                "BNI": ["bni"],
                "Bank Jago": ["jago"],
                "SeaBank": ["seabank"],
                "OVO": ["ovo"],
                "Cash": ["cash"],
            }

            db_accounts = self._conn.execute(
                "SELECT DISTINCT source_account FROM ledger_transactions WHERE source_account IS NOT NULL"
            ).fetchall()
            all_account_names = list(STARTING_BALANCES.keys())
            for row in db_accounts:
                acc = row[0]
                if acc and not any(acc.lower() in k.lower() or k.lower() in acc.lower() for k in all_account_names):
                    all_account_names.append(acc)

            results: Dict[str, Any] = {}
            total_current = 0.0

            for acct_name in all_account_names:
                st_bal = STARTING_BALANCES.get(acct_name, 0.0)
                kw_list = account_keywords.get(acct_name, [acct_name.lower()])

                inflow_clauses = []
                inflow_params = []
                for kw in kw_list:
                    inflow_clauses.append("(type = 'INCOME' AND source_account ILIKE ?)")
                    inflow_params.append(f"%{kw}%")
                    inflow_clauses.append("(type = 'TRANSFER' AND destination_merchant ILIKE ?)")
                    inflow_params.append(f"%{kw}%")

                inflow_sql = f"SELECT COALESCE(SUM(amount), 0.0) FROM ledger_transactions WHERE {' OR '.join(inflow_clauses)}"
                inflow_res = self._conn.execute(inflow_sql, inflow_params).fetchone()[0]
                inflows = float(inflow_res) if inflow_res else 0.0

                outflow_clauses = []
                outflow_params = []
                for kw in kw_list:
                    outflow_clauses.append("(type = 'EXPENSE' AND source_account ILIKE ?)")
                    outflow_params.append(f"%{kw}%")
                    outflow_clauses.append("(type = 'TRANSFER' AND source_account ILIKE ?)")
                    outflow_params.append(f"%{kw}%")

                outflow_sql = f"SELECT COALESCE(SUM(amount), 0.0) FROM ledger_transactions WHERE {' OR '.join(outflow_clauses)}"
                outflow_res = self._conn.execute(outflow_sql, outflow_params).fetchone()[0]
                outflows = float(outflow_res) if outflow_res else 0.0

                cur_bal = st_bal + inflows - outflows
                total_current += cur_bal

                results[acct_name] = {
                    "starting_balance": st_bal,
                    "inflows": inflows,
                    "outflows": outflows,
                    "current_balance": cur_bal,
                    "formatted_starting_balance": format_idr(st_bal),
                    "formatted_inflows": format_idr(inflows),
                    "formatted_outflows": format_idr(outflows),
                    "formatted_current_balance": format_idr(cur_bal),
                }

            return {
                "accounts": results,
                "total_liquid_net_worth": total_current,
                "formatted_total_net_worth": format_idr(total_current),
                "total_starting_balance": sum(STARTING_BALANCES.values()),
                "formatted_total_starting_balance": format_idr(sum(STARTING_BALANCES.values())),
            }

    def close(self) -> None:
        """Close connection to DuckDB."""
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass


# Global storage instance
_default_storage: Optional[StorageManager] = None


def get_storage(db_path: Optional[str] = None) -> StorageManager:
    """Singleton getter for default storage manager."""
    global _default_storage
    if db_path:
        return StorageManager(db_path=db_path)
    if _default_storage is None:
        target_path = os.environ.get("FINANCE_HUB_DB_PATH", "data/finance.duckdb")
        _default_storage = StorageManager(db_path=target_path)
    return _default_storage
