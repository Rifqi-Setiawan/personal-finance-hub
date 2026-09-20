"""Clean all dummy data from Google Sheets, leaving only the 1 real transaction."""

from pathlib import Path
import sys
import os

# Ensure src is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from finance_hub.integrations.sheets_sync import GoogleSheetsSync

sync = GoogleSheetsSync()
sh = sync._get_spreadsheet()

print("Connected to spreadsheet:", sh.title)

# 1. Clean Ledger_Clean
ws_clean = sh.worksheet("Ledger_Clean")
clean_rows = ws_clean.get_all_values()
print(f"Ledger_Clean currently has {len(clean_rows)} rows.")

if len(clean_rows) > 3:
    num_to_delete = len(clean_rows) - 3
    print(f"Deleting {num_to_delete} extra rows from Ledger_Clean (rows 4 to {len(clean_rows)})...")
    ws_clean.delete_rows(4, len(clean_rows))
    print(f"Ledger_Clean now has {len(ws_clean.get_all_values())} rows.")
else:
    print("Ledger_Clean already has <= 3 rows.")

# 2. Clean Transactions_Raw
ws_raw = sh.worksheet("Transactions_Raw")
raw_rows = ws_raw.get_all_values()
print(f"Transactions_Raw currently has {len(raw_rows)} rows.")

if len(raw_rows) > 3:
    num_to_delete = len(raw_rows) - 3
    print(f"Deleting {num_to_delete} extra rows from Transactions_Raw (rows 4 to {len(raw_rows)})...")
    ws_raw.delete_rows(4, len(raw_rows))
    print(f"Transactions_Raw now has {len(ws_raw.get_all_values())} rows.")
else:
    print("Transactions_Raw already has <= 3 rows.")

# 3. Verify Dashboard
ws_dash = sh.worksheet("Dashboard")
print("\n=== DASHBOARD CHECK ===")
print("Inflow (B7):", ws_dash.acell("B7").value)
print("Living Outflow (D7):", ws_dash.acell("D7").value)
print("Savings (F7):", ws_dash.acell("F7").value)
print("Net Savings Rate (H7):", ws_dash.acell("H7").value)

for r in range(12, 17):
    row_vals = ws_dash.row_values(r)
    if len(row_vals) >= 10:
        print(f"  {row_vals[6]:<12} | Starting: {row_vals[8]:<14} | Current: {row_vals[9]}")

print("Total Net Worth (J23):", ws_dash.acell("J23").value)

# 4. Verify Monthly_Summary
ws_ms = sh.worksheet("Monthly_Summary")
print("\n=== MONTHLY SUMMARY CHECK ===")
print("Row 3 (2026-09):", ws_ms.row_values(3))

print("\nCleanup completed successfully!")
