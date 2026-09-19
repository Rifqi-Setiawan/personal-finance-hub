"""Command-line interface (CLI) for Personal Finance Hub."""

import sys
import os
import argparse
import json
import urllib.request
from typing import Optional, Dict, Any

# Ensure src is in sys.path when executed directly
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from finance_hub.models import NotificationPayload, compute_raw_hash
from finance_hub.parser.engine import default_engine
from finance_hub.storage import get_storage
from finance_hub.integrations.sheets_sync import GoogleSheetsSync


def format_idr(amount: float) -> str:
    """Format float into IDR string: Rp 25,000,000."""
    return f"Rp {amount:,.0f}".replace(",", ".")


def cmd_parse_text(
    text: str,
    package_name: Optional[str] = None,
    title: Optional[str] = None,
) -> None:
    """Parse raw notification text and print structured extraction."""
    payload = NotificationPayload(text=text, package_name=package_name, title=title)
    raw_hash = compute_raw_hash(payload)
    parsed = default_engine.parse(payload, raw_hash=raw_hash)

    bucket_val = parsed.budget_bucket.value if parsed.budget_bucket else "UNASSIGNED"
    print("=" * 64)
    print(" PERSONAL FINANCE HUB — PARSER EXTRACTION RESULT")
    print("=" * 64)
    if package_name:
        print(f" Package        : {package_name}")
    if title:
        print(f" Title          : {title}")
    print(f" Institution    : {parsed.source_institution.value}")
    print(f" Transaction    : {parsed.transaction_type.value}")
    print(f" Amount         : {format_idr(parsed.amount)}")
    print(f" Merchant/Party : {parsed.merchant}")
    print(f" Category       : {parsed.category}")
    print(f" Subcategory    : {parsed.subcategory or '-'}")
    print(f" 50/30/20 Bucket: {bucket_val}")
    print(f" Account/Source : {parsed.account_name or '-'}")
    print(f" Timestamp      : {parsed.timestamp}")
    print(f" Payment Method : {parsed.payment_method or '-'}")
    print(f" Raw Hash       : {parsed.raw_hash}")
    print("=" * 64)


def cmd_status() -> None:
    """Print system health, database status, and total transactions recorded."""
    storage = get_storage()
    count = storage.get_transaction_count()
    db_path = storage.db_path

    print("=" * 64)
    print(" PERSONAL FINANCE HUB — SYSTEM STATUS")
    print("=" * 64)
    print(" Status          : HEALTHY")
    print(" Engine Version  : 2.0.0")
    print(f" DuckDB Database : {os.path.abspath(db_path)}")
    print(f" Total Ingested  : {count} transactions")
    print(" Supported Rails : BCA, Mandiri, BRI, BNI, Jago, SeaBank,")
    print("                   GoPay, DANA, OVO, ShopeePay, Cash")
    print("=" * 64)


def cmd_summary() -> None:
    """Print 50/30/20 financial allocations and executive summary."""
    storage = get_storage()
    summary = storage.get_summary()

    status_icon = {
        "BALANCED": "✅ BALANCED",
        "LOW SAVINGS": "⚠️ LOW SAVINGS",
        "OVERSPENT": "⚠️ OVERSPENT",
        "NO_INCOME_RECORDED": "ℹ️ NO INCOME RECORDED"
    }.get(summary["compliance_status"], summary["compliance_status"])

    print("=" * 64)
    print(" PERSONAL FINANCE HUB — 50/30/20 EXECUTIVE SUMMARY")
    print("=" * 64)
    print(f" Total Inflow (Income)   : {format_idr(summary['total_income'])}")
    print(f" Total Living Outflow    : {format_idr(summary['total_expense'])}")
    print(f" Savings & Investments   : {format_idr(summary['savings_investments'])}")
    print(f" Net Monthly Surplus     : {format_idr(summary['net_surplus'])}")
    print(f" Effective Savings Rate  : {summary['savings_rate_pct']:.1f}%")
    print(f" 50/30/20 Health Status  : {status_icon}")
    print("-" * 64)
    print(" BUDGET ALLOCATION BREAKDOWN (50/30/20)")
    print(f"   Needs (Max 50%)       : {format_idr(summary['needs_expense'])} / Target: {format_idr(summary['target_needs_50pct'])}")
    print(f"   Wants (Max 30%)       : {format_idr(summary['wants_expense'])} / Target: {format_idr(summary['target_wants_30pct'])}")
    print(f"   Savings (Min 20%)     : {format_idr(summary['savings_investments'])} / Target: {format_idr(summary['target_savings_20pct'])}")
    print("=" * 64)


def cmd_sync_sheets(all_sync: bool = False, status_check: bool = False) -> None:
    """Sync transactions from DuckDB to Google Sheets or check connection status."""
    sheets = GoogleSheetsSync()
    storage = get_storage()
    is_conf = sheets.is_configured()
    pending = storage.get_unsynced_count()

    # If --status or if neither --all nor --status was explicitly set, show status
    if status_check or not all_sync:
        print("=" * 64)
        print(" PERSONAL FINANCE HUB — GOOGLE SHEETS CONNECTION STATUS")
        print("=" * 64)
        print(f" Configured         : {'YES ✅' if is_conf else 'NO ❌'}")
        print(f" Spreadsheet ID     : {sheets.spreadsheet_id or '(Not configured)'}")
        print(f" Credentials File   : {sheets.credentials_file}")
        print(f" Credentials Exist  : {'YES ✅' if os.path.isfile(sheets.credentials_file) else 'NO ❌'}")
        print(f" Pending Sync Count : {pending} transactions")
        if is_conf:
            print("-" * 64)
            print(" Verifying spreadsheet structure...")
            structure = sheets.verify_structure()
            if structure.get("valid"):
                print(" Structure Check    : ✅ All 5 tabs found (Dashboard, Transactions_Raw, Ledger_Clean, Categories, Monthly_Summary)")
            else:
                err = structure.get("error")
                if err:
                    print(f" Structure Check    : ⚠️ Error: {err}")
                else:
                    missing = structure.get("missing_tabs", [])
                    print(f" Structure Check    : ⚠️ Missing tabs: {', '.join(missing)}")
        else:
            print("-" * 64)
            print(" ℹ️ Setup guide available at: docs/runbooks/GOOGLE_SHEETS_SETUP_RUNBOOK.md")
        print("=" * 64)

    if all_sync:
        print("=" * 64)
        print(" PERSONAL FINANCE HUB — GOOGLE SHEETS BACKFILL SYNC")
        print("=" * 64)
        if not is_conf:
            print(" ❌ Google Sheets integration is not configured.")
            print(" Please set GOOGLE_SPREADSHEET_ID and place service account JSON at:")
            print(f"   {sheets.credentials_file}")
            print(" Or read the setup guide: docs/runbooks/GOOGLE_SHEETS_SETUP_RUNBOOK.md")
            print("=" * 64)
            return

        unsynced = storage.get_unsynced_transactions()
        if not unsynced:
            print(" ✅ All transactions are already synchronized (0 pending).")
            print("=" * 64)
            return

        print(f" Found {len(unsynced)} unsynced transaction(s). Syncing...")
        synced = sheets.sync_batch(unsynced)
        if synced > 0:
            for tx in unsynced[:synced]:
                storage.mark_synced(tx.raw_hash)
            remaining = storage.get_unsynced_count()
            print(f" ✅ Successfully synced {synced} transaction(s) to Google Sheets.")
            print(f" Remaining pending in DuckDB: {remaining}")
        else:
            print(" ❌ Sync failed. Please verify spreadsheet permissions or network connection.")
        print("=" * 64)


def _fetch_api_or_storage(api_path: str, storage_method_name: str, *args, **kwargs) -> Dict[str, Any]:
    """Fetch query data from local running FastAPI server or fallback to direct DuckDB storage."""
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            url = f"http://127.0.0.1:8085{api_path}"
            req = urllib.request.Request(url, headers={"User-Agent": "FinanceHubCLI/1.0"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
    storage = get_storage()
    method = getattr(storage, storage_method_name)
    return method(*args, **kwargs)


def cmd_weekly(ref_date: Optional[str] = None) -> None:
    """Print weekly cash flow analysis (Income, Expenses, Net Remaining)."""
    api_path = f"/api/query/weekly?ref_date={ref_date}" if ref_date else "/api/query/weekly"
    data = _fetch_api_or_storage(api_path, "get_weekly_cashflow", ref_date=ref_date)

    print("=" * 64)
    print(" PERSONAL FINANCE HUB — SISA UANG MINGGU INI")
    print("=" * 64)
    print(f" Periode Minggu        : {data['period']}")
    print(f" Rentang Tanggal       : {data['start_date']} s/d {data['end_date']}")
    print(f" Total Pemasukan       : {data['formatted_income']}")
    print(f" Total Pengeluaran     : {data['formatted_expense']}")
    print("-" * 64)
    print(f" Sisa Uang Minggu Ini  : {data['formatted_net_remaining']}")
    if data.get("top_categories"):
        print("-" * 64)
        print(" Top Pengeluaran Minggu Ini:")
        for cat in data["top_categories"]:
            print(f"   • {cat['category']} ({cat['bucket']}): {cat['formatted']}")
    print("=" * 64)


def cmd_allowance() -> None:
    """Print remaining allowance tracking from last transfer / initial balance."""
    data = _fetch_api_or_storage("/api/query/allowance", "get_transfer_allowance_status")

    print("=" * 64)
    print(" PERSONAL FINANCE HUB — SISA DUIT TRANSFER / ALLOWANCE")
    print("=" * 64)
    if data["has_transfer"]:
        print(" Status                : Transfer Masuk Terdeteksi ✅")
        print(f" Tanggal Transfer      : {data['transfer_date']} {data['transfer_time']}")
        print(f" Akun Penerima         : {data['transfer_account'] or '-'}")
        print(f" Pengirim / Keterangan : {data['transfer_from'] or '-'}")
        print(f" Nominal Transfer      : {data['formatted_transfer_amount']}")
        print(f" Pengeluaran Sejak Itu : {data['formatted_expenses_since']}")
        print("-" * 64)
        print(f" Sisa Duit Transfer    : {data['formatted_remaining_balance']}")
        if "days_since_transfer" in data:
            print(f" Hari Berjalan         : {data['days_since_transfer']} hari")
            print(f" Rata-rata Burn Rate   : {data['formatted_daily_burn']} / hari")
    else:
        print(" Status                : Belum Ada Transfer Masuk Baru ℹ️")
        print(f" Saldo Awal Riil       : {data['formatted_initial_balance']}")
        print(f" Total Pengeluaran     : {data['formatted_expenses_since']}")
        print("-" * 64)
        print(f" Sisa Kas dari Saldo   : {data['formatted_remaining_balance']}")
    print("=" * 64)


def cmd_balances() -> None:
    """Print multi-account liquid balances and net worth."""
    data = _fetch_api_or_storage("/api/query/balances", "get_account_balances")

    print("=" * 64)
    print(" PERSONAL FINANCE HUB — SALDO REKENING & DOMPET DIGITAL")
    print("=" * 64)
    print(f" {'Akun / Dompet':<15} | {'Saldo Awal':<14} | {'Masuk':<12} | {'Keluar':<12} | {'Saldo Saat Ini':<14}")
    print("-" * 64)
    for acct, info in data["accounts"].items():
        st = info["formatted_starting_balance"]
        inf = info["formatted_inflows"]
        outf = info["formatted_outflows"]
        cur = info["formatted_current_balance"]
        print(f" {acct:<15} | {st:<14} | {inf:<12} | {outf:<12} | {cur:<14}")
    print("=" * 64)
    print(f" TOTAL LIQUID NET WORTH : {data['formatted_total_net_worth']}")
    print("=" * 64)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m finance_hub.cli",
        description="Personal Finance Hub CLI — Parsing, Status & Financial Summary"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: parse-text
    parse_cmd = subparsers.add_parser("parse-text", help="Parse a single notification or SMS string")
    parse_cmd.add_argument("text", type=str, help="Notification raw text string")
    parse_cmd.add_argument(
        "--package",
        "-p",
        type=str,
        default=None,
        help="Android package name (e.g. com.bca, id.dana)"
    )
    parse_cmd.add_argument(
        "--title",
        "-t",
        type=str,
        default=None,
        help="Notification title string (e.g. BCA mobile, DANA)"
    )

    # Command: status
    subparsers.add_parser("status", help="Show system status and database metrics")

    # Command: summary
    subparsers.add_parser("summary", help="Show 50/30/20 financial allocations and KPIs")

    # Command: sync-sheets
    sync_cmd = subparsers.add_parser("sync-sheets", help="Sync transactions with Google Sheets")
    sync_cmd.add_argument(
        "--all",
        action="store_true",
        help="Backfill all unsynced transactions from DuckDB to Google Sheets"
    )
    sync_cmd.add_argument(
        "--status",
        action="store_true",
        help="Check Google Sheets connection and pending sync status"
    )

    # Command: weekly
    weekly_cmd = subparsers.add_parser("weekly", help="Show weekly cashflow and remaining money")
    weekly_cmd.add_argument(
        "--date",
        "-d",
        type=str,
        default=None,
        help="Reference date in YYYY-MM-DD format (default: today)"
    )

    # Command: allowance
    subparsers.add_parser("allowance", help="Show remaining allowance from last transfer")

    # Command: balances
    subparsers.add_parser("balances", help="Show current balances across all accounts")

    args = parser.parse_args()

    if args.command == "parse-text":
        cmd_parse_text(args.text, package_name=args.package, title=args.title)
    elif args.command == "status":
        cmd_status()
    elif args.command == "summary":
        cmd_summary()
    elif args.command == "sync-sheets":
        cmd_sync_sheets(all_sync=args.all, status_check=args.status)
    elif args.command == "weekly":
        cmd_weekly(ref_date=args.date)
    elif args.command == "allowance":
        cmd_allowance()
    elif args.command == "balances":
        cmd_balances()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
