"""Financial query engine for personal finance assistant.

Provides calculations for:
- Weekly cash flow (Pemasukan - Pengeluaran minggu ini)
- Allowance / Transfer tracking (Sisa uang dari transferan terakhir)
- Multi-account liquid balances
"""

from typing import Dict, Any, Optional, Tuple
from datetime import date

from finance_hub.storage import (
    STARTING_BALANCES,
    format_idr,
    get_storage,
    StorageManager,
)


def get_current_week_range(ref_date: Optional[date] = None) -> Tuple[date, date]:
    """Get Monday and Sunday of the current week."""
    from datetime import datetime, timedelta
    today = ref_date or datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    end_of_week = start_of_week + timedelta(days=6)         # Sunday
    return start_of_week, end_of_week


def query_weekly_cashflow(ref_date: Optional[Any] = None) -> Dict[str, Any]:
    """
    Menghitung sisa uang minggu ini:
    Sisa = Pemasukan Minggu Ini - Pengeluaran Minggu Ini.
    """
    return get_storage().get_weekly_cashflow(ref_date=ref_date)


def query_last_transfer_allowance() -> Dict[str, Any]:
    """
    Menghitung sisa uang dari transferan terakhir:
    Sisa = Nominal Transfer Masuk Terakhir - Total Pengeluaran Sejak Tanggal Transfer Tersebut.
    """
    return get_storage().get_transfer_allowance_status()


def query_all_account_balances() -> Dict[str, Any]:
    """
    Menghitung saldo saat ini di setiap rekening & dompet:
    Current Balance = Starting Balance + Inflow - Outflow.
    """
    return get_storage().get_account_balances()
