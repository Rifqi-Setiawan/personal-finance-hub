#!/usr/bin/env python3
"""
Personal Finance Hub — Spreadsheet Template Generator (.xlsx)
Generates a production-ready, beautifully formatted 5-tab workbook
compatible with Microsoft Excel and Google Sheets.
"""

import hashlib
import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule

def generate_personal_finance_hub_template(output_filepath: str):
    wb = Workbook()
    
    # ----------------------------------------------------
    # Design System & Palette (Modern Slate & Emerald)
    # ----------------------------------------------------
    font_main = "Segoe UI"
    
    # Typography
    f_banner = Font(name=font_main, size=15, bold=True, color="FFFFFF")
    f_section = Font(name=font_main, size=11, bold=True, color="FFFFFF")
    f_tbl_head = Font(name=font_main, size=10, bold=True, color="FFFFFF")
    f_kpi_head = Font(name=font_main, size=9, bold=True, color="FFFFFF")
    f_bold = Font(name=font_main, size=10, bold=True, color="0F172A")
    f_norm = Font(name=font_main, size=10, color="1E293B")
    f_mono = Font(name="Consolas", size=9, color="475569")
    
    # KPI Big Values
    f_kpi_val_green = Font(name=font_main, size=16, bold=True, color="047857")
    f_kpi_val_red = Font(name=font_main, size=16, bold=True, color="B91C1C")
    f_kpi_val_indigo = Font(name=font_main, size=16, bold=True, color="4338CA")
    f_kpi_val_blue = Font(name=font_main, size=16, bold=True, color="1D4ED8")

    # Fills & Accents
    fill_slate_dark = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    fill_slate_navy = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    fill_slate_sub = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
    fill_total_row = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    # KPI Themes
    fill_kpi_green_h = PatternFill(start_color="065F46", end_color="065F46", fill_type="solid")
    fill_kpi_green_b = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
    fill_kpi_red_h = PatternFill(start_color="9F1239", end_color="9F1239", fill_type="solid")
    fill_kpi_red_b = PatternFill(start_color="FFF1F2", end_color="FFF1F2", fill_type="solid")
    fill_kpi_ind_h = PatternFill(start_color="3730A3", end_color="3730A3", fill_type="solid")
    fill_kpi_ind_b = PatternFill(start_color="EEF2FF", end_color="EEF2FF", fill_type="solid")
    fill_kpi_blu_h = PatternFill(start_color="1E40AF", end_color="1E40AF", fill_type="solid")
    fill_kpi_blu_b = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")

    # Badges for 50/30/20 & Statuses
    fill_badge_needs = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
    fill_badge_wants = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    fill_badge_savings = PatternFill(start_color="E0E7FF", end_color="E0E7FF", fill_type="solid")
    fill_badge_income = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
    fill_badge_transfer = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    # Borders
    c_border = "CBD5E1"
    b_thin = Border(
        left=Side(style='thin', color=c_border),
        right=Side(style='thin', color=c_border),
        top=Side(style='thin', color=c_border),
        bottom=Side(style='thin', color=c_border)
    )
    b_double = Border(
        left=Side(style='thin', color=c_border),
        right=Side(style='thin', color=c_border),
        top=Side(style='thin', color=c_border),
        bottom=Side(style='double', color="0F172A")
    )

    # Alignments
    a_center = Alignment(horizontal='center', vertical='center')
    a_left = Alignment(horizontal='left', vertical='center')
    a_right = Alignment(horizontal='right', vertical='center')

    # Standard Formats
    fmt_curr = '"Rp "#,##0;[Red]("Rp "#,##0);"-"'
    fmt_pct = '0.0%'
    fmt_dt = 'yyyy-mm-dd'
    fmt_tm = 'hh:mm:ss'

    # =========================================================================
    # 1. TAB: Dashboard
    # =========================================================================
    ws_d = wb.active
    ws_d.title = "Dashboard"
    ws_d.views.sheetView[0].showGridLines = True

    # Row Heights
    ws_d.row_dimensions[2].height = 36
    ws_d.row_dimensions[3].height = 24
    ws_d.row_dimensions[5].height = 26
    ws_d.row_dimensions[6].height = 20
    ws_d.row_dimensions[7].height = 22
    ws_d.row_dimensions[8].height = 22
    ws_d.row_dimensions[10].height = 26
    ws_d.row_dimensions[11].height = 24
    ws_d.row_dimensions[17].height = 26
    ws_d.row_dimensions[18].height = 24
    ws_d.row_dimensions[23].height = 26

    # Banner
    ws_d.merge_cells("B2:J2")
    ws_d["B2"] = "PERSONAL FINANCE HUB — EXECUTIVE FINANCIAL DASHBOARD"
    ws_d["B2"].font = f_banner
    ws_d["B2"].fill = fill_slate_dark
    ws_d["B2"].alignment = a_center

    ws_d.merge_cells("B3:D3")
    ws_d["B3"] = "Active Period: 2026-09"
    ws_d["B3"].font = f_bold
    ws_d["B3"].fill = fill_total_row
    ws_d["B3"].alignment = a_center

    ws_d.merge_cells("E3:G3")
    ws_d["E3"] = "Currency: Indonesian Rupiah (IDR)"
    ws_d["E3"].font = f_bold
    ws_d["E3"].fill = fill_total_row
    ws_d["E3"].alignment = a_center

    ws_d.merge_cells("H3:J3")
    ws_d["H3"] = "Standard: 50/30/20 Budgeting Rule"
    ws_d["H3"].font = f_bold
    ws_d["H3"].fill = fill_total_row
    ws_d["H3"].alignment = a_center

    for r in range(2, 4):
        for c in range(2, 11):
            ws_d.cell(row=r, column=c).border = b_thin

    # KPI Section Banner
    ws_d.merge_cells("B5:J5")
    ws_d["B5"] = "EXECUTIVE KPI METRICS (ACTIVE MONTH: SEPTEMBER 2026)"
    ws_d["B5"].font = f_section
    ws_d["B5"].fill = fill_slate_navy
    ws_d["B5"].alignment = a_center
    for c in range(2, 11):
        ws_d.cell(row=5, column=c).border = b_thin

    # KPI 1: Inflow
    ws_d.merge_cells("B6:C6")
    ws_d["B6"] = "TOTAL INFLOW (INCOME)"
    ws_d["B6"].font = f_kpi_head
    ws_d["B6"].fill = fill_kpi_green_h
    ws_d["B6"].alignment = a_center
    
    ws_d.merge_cells("B7:C8")
    ws_d["B7"] = '=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$F$3:$F$100,"INCOME")'
    ws_d["B7"].font = f_kpi_val_green
    ws_d["B7"].fill = fill_kpi_green_b
    ws_d["B7"].alignment = a_center
    ws_d["B7"].number_format = fmt_curr

    # KPI 2: Outflow Living
    ws_d.merge_cells("D6:E6")
    ws_d["D6"] = "LIVING OUTFLOW (NEEDS + WANTS)"
    ws_d["D6"].font = f_kpi_head
    ws_d["D6"].fill = fill_kpi_red_h
    ws_d["D6"].alignment = a_center
    
    ws_d.merge_cells("D7:E8")
    ws_d["D7"] = '=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$F$3:$F$100,"EXPENSE",Ledger_Clean!$H$3:$H$100,"<>Savings")'
    ws_d["D7"].font = f_kpi_val_red
    ws_d["D7"].fill = fill_kpi_red_b
    ws_d["D7"].alignment = a_center
    ws_d["D7"].number_format = fmt_curr

    # KPI 3: Savings
    ws_d.merge_cells("F6:G6")
    ws_d["F6"] = "SAVINGS & INVESTMENTS"
    ws_d["F6"].font = f_kpi_head
    ws_d["F6"].fill = fill_kpi_ind_h
    ws_d["F6"].alignment = a_center
    
    ws_d.merge_cells("F7:G8")
    ws_d["F7"] = '=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$F$3:$F$100,"EXPENSE",Ledger_Clean!$H$3:$H$100,"Savings")'
    ws_d["F7"].font = f_kpi_val_indigo
    ws_d["F7"].fill = fill_kpi_ind_b
    ws_d["F7"].alignment = a_center
    ws_d["F7"].number_format = fmt_curr

    # KPI 4: Net Savings Rate
    ws_d.merge_cells("H6:J6")
    ws_d["H6"] = "NET SAVINGS RATE (SAVINGS + SURPLUS)"
    ws_d["H6"].font = f_kpi_head
    ws_d["H6"].fill = fill_kpi_blu_h
    ws_d["H6"].alignment = a_center
    
    ws_d.merge_cells("H7:J8")
    ws_d["H7"] = '=IF(B7>0,(F7+(B7-D7-F7))/B7,0)'
    ws_d["H7"].font = f_kpi_val_blue
    ws_d["H7"].fill = fill_kpi_blu_b
    ws_d["H7"].alignment = a_center
    ws_d["H7"].number_format = fmt_pct

    for r in range(6, 9):
        for c in range(2, 11):
            ws_d.cell(row=r, column=c).border = b_thin

    # Section Headers (Row 10)
    ws_d.merge_cells("B10:E10")
    ws_d["B10"] = "50/30/20 BUDGET COMPLIANCE & HEALTH"
    ws_d["B10"].font = f_section
    ws_d["B10"].fill = fill_slate_navy
    ws_d["B10"].alignment = a_center
    for c in range(2, 6):
        ws_d.cell(row=10, column=c).border = b_thin

    ws_d.merge_cells("G10:J10")
    ws_d["G10"] = "MULTI-ACCOUNT LIQUIDITY & RECONCILIATION"
    ws_d["G10"].font = f_section
    ws_d["G10"].fill = fill_slate_navy
    ws_d["G10"].alignment = a_center
    for c in range(7, 11):
        ws_d.cell(row=10, column=c).border = b_thin

    # 50/30/20 Table Headers (Row 11)
    b_heads = ["Budget Bucket", "Actual Spent", "Target Budget", "Health Status"]
    for i, h in enumerate(b_heads, start=2):
        c_cell = ws_d.cell(row=11, column=i, value=h)
        c_cell.font = f_tbl_head
        c_cell.fill = fill_slate_sub
        c_cell.alignment = a_center
        c_cell.border = b_thin

    # 50/30/20 Table Rows (12-15)
    b_rows = [
        ("Needs (Max 50%)", '=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$F$3:$F$100,"EXPENSE",Ledger_Clean!$H$3:$H$100,"Needs")', '=B7*0.5', '=IF(C12<=D12,"✅ OPTIMAL (<50%)","⚠️ OVERSPENT (>50%)")'),
        ("Wants (Max 30%)", '=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$F$3:$F$100,"EXPENSE",Ledger_Clean!$H$3:$H$100,"Wants")', '=B7*0.3', '=IF(C13<=D13,"✅ OPTIMAL (<30%)","⚠️ OVERSPENT (>30%)")'),
        ("Savings / Invest (Min 20%)", '=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$F$3:$F$100,"EXPENSE",Ledger_Clean!$H$3:$H$100,"Savings")', '=B7*0.2', '=IF(C14>=D14,"✅ ON TRACK (>=20%)","⚠️ UNDERFUNDED (<20%)")'),
        ("Total Living Outflow", '=SUM(C12:C14)', '=SUM(D12:D14)', '=IF(C15<=B7,"✅ HEALTHY SURPLUS","⚠️ CASHFLOW DEFICIT")')
    ]

    for idx, (b_name, a_form, t_form, s_form) in enumerate(b_rows, start=12):
        is_tot = (idx == 15)
        ws_d.row_dimensions[idx].height = 22
        
        ws_d.cell(row=idx, column=2, value=b_name).font = f_bold if is_tot else f_norm
        ws_d.cell(row=idx, column=2).alignment = a_left
        
        c_a = ws_d.cell(row=idx, column=3, value=a_form)
        c_a.font = f_bold if is_tot else f_norm
        c_a.alignment = a_right
        c_a.number_format = fmt_curr
        
        c_t = ws_d.cell(row=idx, column=4, value=t_form)
        c_t.font = f_bold if is_tot else f_norm
        c_t.alignment = a_right
        c_t.number_format = fmt_curr
        
        c_s = ws_d.cell(row=idx, column=5, value=s_form)
        c_s.font = f_bold
        c_s.alignment = a_center
        
        for c in range(2, 6):
            cell = ws_d.cell(row=idx, column=c)
            cell.border = b_double if is_tot else b_thin
            if is_tot:
                cell.fill = fill_total_row

    # Top Expense Categories Breakdown Header (Row 17)
    ws_d.merge_cells("B17:E17")
    ws_d["B17"] = "TOP EXPENSE CATEGORIES BREAKDOWN"
    ws_d["B17"].font = f_section
    ws_d["B17"].fill = fill_slate_navy
    ws_d["B17"].alignment = a_center
    for c in range(2, 6):
        ws_d.cell(row=17, column=c).border = b_thin

    cat_break_headers = ["Category Name", "Bucket", "Actual Spent", "% of Total Income"]
    for i, h in enumerate(cat_break_headers, start=2):
        c_cell = ws_d.cell(row=18, column=i, value=h)
        c_cell.font = f_tbl_head
        c_cell.fill = fill_slate_sub
        c_cell.alignment = a_center
        c_cell.border = b_thin

    sample_top_cats = [
        ("Groceries & Food Supplies", "Needs"),
        ("Utilities & Bills (PLN, Water, Net)", "Needs"),
        ("Transportation & Commute", "Needs"),
        ("Healthcare & Pharmacy", "Needs"),
        ("Dining Out & Cafes", "Wants"),
        ("Entertainment & Subscriptions", "Wants"),
        ("Shopping & Retail", "Wants"),
        ("Mutual Funds & Stocks", "Savings"),
        ("Emergency Fund Reserve", "Savings")
    ]

    for idx, (cat_name, bkt_name) in enumerate(sample_top_cats, start=19):
        ws_d.row_dimensions[idx].height = 20
        ws_d.cell(row=idx, column=2, value=cat_name).font = f_norm
        ws_d.cell(row=idx, column=2).alignment = a_left
        
        b_cell = ws_d.cell(row=idx, column=3, value=bkt_name)
        b_cell.font = f_bold
        b_cell.alignment = a_center
        if bkt_name == "Needs":
            b_cell.fill = fill_badge_needs
        elif bkt_name == "Wants":
            b_cell.fill = fill_badge_wants
        else:
            b_cell.fill = fill_badge_savings
            
        c_sp = ws_d.cell(row=idx, column=4, value=f'=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$G$3:$G$100,B{idx},Ledger_Clean!$F$3:$F$100,"EXPENSE")')
        c_sp.font = f_norm
        c_sp.alignment = a_right
        c_sp.number_format = fmt_curr
        
        c_pc = ws_d.cell(row=idx, column=5, value=f'=IF($B$7>0,D{idx}/$B$7,0)')
        c_pc.font = f_norm
        c_pc.alignment = a_right
        c_pc.number_format = fmt_pct
        
        for c in range(2, 6):
            ws_d.cell(row=idx, column=c).border = b_thin

    # Account Balances Table (G11:J23)
    acct_heads = ["Account / Wallet", "Institution Type", "Starting Balance", "Current Balance"]
    for i, h in enumerate(acct_heads, start=7):
        c_cell = ws_d.cell(row=11, column=i, value=h)
        c_cell.font = f_tbl_head
        c_cell.fill = fill_slate_sub
        c_cell.alignment = a_center
        c_cell.border = b_thin

    accounts_list = [
        ("BCA", "Commercial Bank", 15000000),
        ("Mandiri", "Commercial Bank", 8500000),
        ("BRI", "Commercial Bank", 2000000),
        ("BNI", "Commercial Bank", 1000000),
        ("Bank Jago", "Digital Bank", 5000000),
        ("SeaBank", "Digital Bank", 4000000),
        ("GoPay", "E-Wallet", 150000),
        ("OVO", "E-Wallet", 75000),
        ("DANA", "E-Wallet", 120000),
        ("ShopeePay", "E-Wallet", 90000),
        ("Cash", "Physical Cash", 500000)
    ]

    for idx, (acct_name, acct_type, st_bal) in enumerate(accounts_list, start=12):
        ws_d.row_dimensions[idx].height = 20
        ws_d.cell(row=idx, column=7, value=acct_name).font = f_bold
        ws_d.cell(row=idx, column=7).alignment = a_left
        
        ws_d.cell(row=idx, column=8, value=acct_type).font = f_norm
        ws_d.cell(row=idx, column=8).alignment = a_center
        
        c_sb = ws_d.cell(row=idx, column=9, value=st_bal)
        c_sb.font = f_norm
        c_sb.alignment = a_right
        c_sb.number_format = fmt_curr
        
        # Real-time Reconciled Balance Formula:
        # Starting + Inflows (Transfer In + Income) - Outflows (Transfer Out + Expense)
        formula_bal = (
            f'=I{idx}'
            f'+SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$E$3:$E$100,G{idx},Ledger_Clean!$F$3:$F$100,"TRANSFER")'
            f'-SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$D$3:$D$100,G{idx},Ledger_Clean!$F$3:$F$100,"TRANSFER")'
            f'+SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$D$3:$D$100,G{idx},Ledger_Clean!$F$3:$F$100,"INCOME")'
            f'-SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$D$3:$D$100,G{idx},Ledger_Clean!$F$3:$F$100,"EXPENSE")'
        )
        c_cb = ws_d.cell(row=idx, column=10, value=formula_bal)
        c_cb.font = f_bold
        c_cb.alignment = a_right
        c_cb.number_format = fmt_curr
        
        for c in range(7, 11):
            ws_d.cell(row=idx, column=c).border = b_thin

    # Net Worth Total Row (Row 23)
    ws_d.row_dimensions[23].height = 26
    ws_d.merge_cells("G23:I23")
    ws_d["G23"] = "TOTAL LIQUID NET WORTH (ALL ACCOUNTS)"
    ws_d["G23"].font = f_bold
    ws_d["G23"].alignment = a_right
    ws_d["G23"].fill = fill_total_row

    c_nw = ws_d.cell(row=23, column=10, value="=SUM(J12:J22)")
    c_nw.font = f_kpi_val_green
    c_nw.alignment = a_right
    c_nw.number_format = fmt_curr
    c_nw.fill = fill_kpi_green_b
    
    for c in range(7, 11):
        ws_d.cell(row=23, column=c).border = b_double

    dash_widths = {
        'A': 4, 'B': 30, 'C': 22, 'D': 22, 'E': 24,
        'F': 2, 'G': 18, 'H': 20, 'I': 22, 'J': 24
    }
    for c_let, w in dash_widths.items():
        ws_d.column_dimensions[c_let].width = w

    # =========================================================================
    # 2. TAB: Transactions_Raw (Bronze Layer)
    # =========================================================================
    ws_r = wb.create_sheet(title="Transactions_Raw")
    ws_r.views.sheetView[0].showGridLines = True

    ws_r.row_dimensions[1].height = 30
    ws_r.row_dimensions[2].height = 24

    ws_r.merge_cells("A1:J1")
    ws_r["A1"] = "TRANSACTIONS_RAW — BRONZE INGESTION LOG (IMMUTABLE AUDIT TRAIL)"
    ws_r["A1"].font = f_section
    ws_r["A1"].fill = fill_slate_navy
    ws_r["A1"].alignment = a_center

    raw_headers = [
        "raw_id", "ingestion_timestamp", "source_institution", "channel",
        "raw_payload", "parsed_amount", "parsed_direction", "payload_hash",
        "processing_status", "clean_ledger_ref"
    ]
    for col_idx, h in enumerate(raw_headers, start=1):
        cell = ws_r.cell(row=2, column=col_idx, value=h)
        cell.font = f_tbl_head
        cell.fill = fill_slate_dark
        cell.alignment = a_center
        cell.border = b_thin

    raw_data = [
        ("RAW-20260901-001", "2026-09-01 07:14:00", "BCA", "PUSH_NOTIFICATION", "m-Transfer: 01/09 07:14 TRSF DARI PT TECH NUSANTARA Rp 25.000.000,00 KE REK 5310294821", 25000000, "CR", "PROCESSED", "TX-202609-001"),
        ("RAW-20260901-002", "2026-09-01 10:30:15", "BCA", "PUSH_NOTIFICATION", "m-Transfer: 01/09 10:30 TOPUP KE GOPAY RIFQI Rp 1.000.000,00 REK 5310294821", 1000000, "DB", "PROCESSED", "TX-202609-002"),
        ("RAW-20260902-003", "2026-09-02 14:15:30", "Mandiri", "SMS_NOTIFICATION", "Livin' Mandiri: 02/09 14:15 PEMBAYARAN PLN PASCA IDPEL 53210984 Rp 850.000,00 SUKSES", 850000, "DB", "PROCESSED", "TX-202609-003"),
        ("RAW-20260902-004", "2026-09-02 19:20:05", "BCA", "EMAIL_RECEIPT", "BCA Autodebet: 02/09 19:20 TAGIHAN INTERNET INDIHOME NO 12249821 Rp 450.000,00 BERHASIL", 450000, "DB", "PROCESSED", "TX-202609-004"),
        ("RAW-20260903-005", "2026-09-03 16:45:10", "BCA", "PUSH_NOTIFICATION", "Debit BCA: 03/09 16:45 EDC INDOMARET FRESH TB SIMATUPANG Rp 1.450.000,00 SUKSES", 1450000, "DB", "PROCESSED", "TX-202609-005"),
        ("RAW-20260904-006", "2026-09-04 09:12:44", "GoPay", "PUSH_NOTIFICATION", "GoPay: 04/09 09:12 Pembayaran QRIS Kopi Kenangan Menara Astra Rp 48.000 Berhasil", 48000, "DB", "PROCESSED", "TX-202609-006"),
        ("RAW-20260905-007", "2026-09-05 08:30:12", "GoPay", "PUSH_NOTIFICATION", "GoPay: 05/09 08:30 GoCar ke Pacific Place SCBD Rp 65.000 Berhasil", 65000, "DB", "PROCESSED", "TX-202609-007"),
        ("RAW-20260906-008", "2026-09-06 12:35:50", "ShopeePay", "PUSH_NOTIFICATION", "ShopeePay: 06/09 12:35 QRIS Restoran Sederhana Padang Rp 45.000 Sukses", 45000, "DB", "PROCESSED", "TX-202609-008"),
        ("RAW-20260907-009", "2026-09-07 17:20:00", "Cash", "MANUAL_ENTRY", "Struk Pembelian Tunai Apotek Kimia Farma Resep Vitamin Rp 175.000", 175000, "DB", "PROCESSED", "TX-202609-009"),
        ("RAW-20260908-010", "2026-09-08 03:00:18", "Bank Jago", "PUSH_NOTIFICATION", "Bank Jago: 08/09 03:00 Kantong Utama Debit Netflix Premium Rp 186.000 Berhasil", 186000, "DB", "PROCESSED", "TX-202609-010"),
        ("RAW-20260909-011", "2026-09-09 15:40:22", "DANA", "PUSH_NOTIFICATION", "DANA Protection: 09/09 15:40 QRIS Indomaret Snack & Minuman Rp 54.000 Berhasil", 54000, "DB", "PROCESSED", "TX-202609-011"),
        ("RAW-20260910-012", "2026-09-10 11:00:00", "Bank Jago", "PUSH_NOTIFICATION", "Bank Jago: 10/09 11:00 Kantong Investasi Top Up Bibit Reksadana Indeks Rp 3.000.000 Berhasil", 3000000, "DB", "PROCESSED", "TX-202609-012"),
        ("RAW-20260911-013", "2026-09-11 20:15:35", "BCA", "PUSH_NOTIFICATION", "Debit BCA: 11/09 20:15 EDC Sushi Tei Senayan City Rp 420.000,00 Sukses", 420000, "DB", "PROCESSED", "TX-202609-013"),
        ("RAW-20260912-014", "2026-09-12 10:10:45", "Mandiri", "PUSH_NOTIFICATION", "Livin' Mandiri: 12/09 10:10 QRIS SPBU Shell TB Simatupang Rp 350.000,00 Sukses", 350000, "DB", "PROCESSED", "TX-202609-014"),
        ("RAW-20260913-015", "2026-09-13 14:50:11", "SeaBank", "EMAIL_RECEIPT", "SeaBank: 13/09 14:50 Transfer Pembayaran Tokopedia Buku & Keyboard Rp 280.000 Berhasil", 280000, "DB", "PROCESSED", "TX-202609-015"),
        ("RAW-20260914-016", "2026-09-14 16:30:29", "OVO", "PUSH_NOTIFICATION", "OVO Cash: 14/09 16:30 Transaksi QRIS Fore Coffee Menara Mandiri Rp 35.000 Berhasil", 35000, "DB", "PROCESSED", "TX-202609-016"),
        ("RAW-20260915-017", "2026-09-15 09:30:00", "BCA", "PUSH_NOTIFICATION", "m-Transfer: 15/09 09:30 TRSF KE RDN STOCKBIT BCA SEKURITAS Rp 2.500.000,00", 2500000, "DB", "PROCESSED", "TX-202609-017"),
        ("RAW-20260916-018", "2026-09-16 18:00:20", "Bank Jago", "PUSH_NOTIFICATION", "Bank Jago: 16/09 18:00 Uang Masuk dari PT Kreasi Digital Konsultasi UI/UX Rp 4.500.000", 4500000, "CR", "PROCESSED", "TX-202609-018"),
        ("RAW-20260917-019", "2026-09-17 21:00:15", "SeaBank", "PUSH_NOTIFICATION", "SeaBank: 17/09 21:00 Alokasi Tabungan Kantong Dana Darurat SeaBank Rp 1.500.000 Berhasil", 1500000, "DB", "PROCESSED", "TX-202609-019"),
        ("RAW-20260918-020", "2026-09-18 11:45:00", "GoPay", "PUSH_NOTIFICATION", "GoPay: 18/09 11:45 Pembayaran QRIS Infaq Masjid Nurul Iman Rp 100.000 Berhasil", 100000, "DB", "PROCESSED", "TX-202609-020")
    ]

    for row_idx, r in enumerate(raw_data, start=3):
        ws_r.row_dimensions[row_idx].height = 20
        raw_id, ts, inst, chan, payload, amt, direct, status, clean_ref = r
        hash_val = hashlib.sha256(f"{ts}{inst}{amt}{payload}".encode()).hexdigest()
        
        ws_r.cell(row=row_idx, column=1, value=raw_id).font = f_bold
        ws_r.cell(row=row_idx, column=1).alignment = a_center
        
        ws_r.cell(row=row_idx, column=2, value=ts).font = f_norm
        ws_r.cell(row=row_idx, column=2).alignment = a_center
        
        ws_r.cell(row=row_idx, column=3, value=inst).font = f_bold
        ws_r.cell(row=row_idx, column=3).alignment = a_left
        
        ws_r.cell(row=row_idx, column=4, value=chan).font = f_norm
        ws_r.cell(row=row_idx, column=4).alignment = a_center
        
        ws_r.cell(row=row_idx, column=5, value=payload).font = f_norm
        ws_r.cell(row=row_idx, column=5).alignment = a_left
        
        c_amt = ws_r.cell(row=row_idx, column=6, value=amt)
        c_amt.font = f_bold
        c_amt.alignment = a_right
        c_amt.number_format = fmt_curr
        
        c_dir = ws_r.cell(row=row_idx, column=7, value=direct)
        c_dir.font = f_bold
        c_dir.alignment = a_center
        c_dir.fill = fill_badge_income if direct == "CR" else fill_badge_needs
        
        ws_r.cell(row=row_idx, column=8, value=hash_val).font = f_mono
        ws_r.cell(row=row_idx, column=8).alignment = a_left
        
        c_st = ws_r.cell(row=row_idx, column=9, value=status)
        c_st.font = f_bold
        c_st.alignment = a_center
        c_st.fill = fill_badge_income
        
        ws_r.cell(row=row_idx, column=10, value=clean_ref).font = f_bold
        ws_r.cell(row=row_idx, column=10).alignment = a_center
        
        for c in range(1, 11):
            ws_r.cell(row=row_idx, column=c).border = b_thin

    raw_widths = {
        'A': 20, 'B': 22, 'C': 16, 'D': 20, 'E': 68,
        'F': 18, 'G': 10, 'H': 26, 'I': 16, 'J': 18
    }
    for c_let, w in raw_widths.items():
        ws_r.column_dimensions[c_let].width = w

    # =========================================================================
    # 3. TAB: Categories (Master Taxonomy Dimension)
    # =========================================================================
    ws_c = wb.create_sheet(title="Categories")
    ws_c.views.sheetView[0].showGridLines = True

    ws_c.row_dimensions[1].height = 30
    ws_c.row_dimensions[2].height = 24

    ws_c.merge_cells("A1:F1")
    ws_c["A1"] = "CATEGORIES — MASTER TAXONOMY & 50/30/20 BUDGET DIMENSION"
    ws_c["A1"].font = f_section
    ws_c["A1"].fill = fill_slate_navy
    ws_c["A1"].alignment = a_center

    cat_headers = [
        "category_code", "category_name", "budget_bucket",
        "icon_tag", "monthly_budget_idr", "description"
    ]
    for col_idx, h in enumerate(cat_headers, start=1):
        cell = ws_c.cell(row=2, column=col_idx, value=h)
        cell.font = f_tbl_head
        cell.fill = fill_slate_dark
        cell.alignment = a_center
        cell.border = b_thin

    categories_data = [
        ("INC-01", "Salary & Compensation", "Income", "💼 Payroll", 0, "Base monthly salary, corporate payroll bonus"),
        ("INC-02", "Freelance & Consulting", "Income", "💻 Project", 0, "Secondary gig income, consulting, advisory fees"),
        ("INC-03", "Investment Returns", "Income", "📈 Passive", 0, "Stock dividends, p2p interest, crypto yield"),
        ("INC-04", "Cashback & Gifts", "Income", "🎁 Rebate", 0, "Marketplace cashback, cash prizes, gifts"),
        ("NED-01", "Groceries & Food Supplies", "Needs", "🛒 Groceries", 3000000, "Supermarket, Indomaret Fresh, food provisions"),
        ("NED-02", "Utilities & Bills (PLN, Water, Net)", "Needs", "⚡ Utilities", 1500000, "PLN electricity, PDAM, Indihome, Biznet, Telkomsel"),
        ("NED-03", "Housing & Maintenance", "Needs", "🏠 Housing", 5000000, "Apartment/kost rental, maintenance, IPL fees"),
        ("NED-04", "Transportation & Commute", "Needs", "🚗 Commute", 1200000, "Bensin Pertamax/Shell, Tol, KRL, Grab/Gojek commute"),
        ("NED-05", "Healthcare & Pharmacy", "Needs", "🏥 Medical", 800000, "BPJS, insurance, pharmacy prescriptions, vitamins"),
        ("NED-06", "Family Support & Charity", "Needs", "🤲 Social", 1000000, "Family allowances, Zakat, regular infaq"),
        ("WNT-01", "Dining Out & Cafes", "Wants", "☕ F&B", 1500000, "Coffee shops, restaurants, casual eat-outs"),
        ("WNT-02", "Entertainment & Subscriptions", "Wants", "🍿 Media", 500000, "Netflix, Spotify, YouTube, ChatGPT, games"),
        ("WNT-03", "Shopping & Retail", "Wants", "🛍️ Retail", 1500000, "Tokopedia, Shopee, clothing, electronics"),
        ("WNT-04", "Hobbies & Recreation", "Wants", "✈️ Leisure", 1000000, "Weekend trips, gym membership, sports, hobbies"),
        ("WNT-05", "Personal Care & Grooming", "Wants", "💈 Salon", 500000, "Barbershop, skincare, spa, self-care"),
        ("SAV-01", "Emergency Fund Reserve", "Savings", "🛡️ Reserve", 2000000, "Liquid high yield deposits (SeaBank, Jago)"),
        ("SAV-02", "Mutual Funds & Stocks", "Savings", "📊 Equity", 3000000, "Reksadana Indeks Bibit, Saham Stockbit IHSG"),
        ("SAV-03", "Crypto & Digital Assets", "Savings", "🪙 Crypto", 1000000, "Bitcoin (BTC) & Ethereum (ETH) long-term DCA"),
        ("SAV-04", "Government Bonds & Gold", "Savings", "🥇 Gold/Bond", 1000000, "SBN, Sukuk, Antam gold via Pluang/Pegadaian"),
        ("TRF-01", "Internal Account Transfer", "Transfer", "🔄 Transfer", 0, "Inter-account rebalancing, wallet top up")
    ]

    for row_idx, cat in enumerate(categories_data, start=3):
        ws_c.row_dimensions[row_idx].height = 20
        c_code, c_name, c_bucket, c_icon, c_budget, c_desc = cat
        
        ws_c.cell(row=row_idx, column=1, value=c_code).font = f_bold
        ws_c.cell(row=row_idx, column=1).alignment = a_center
        
        ws_c.cell(row=row_idx, column=2, value=c_name).font = f_bold
        ws_c.cell(row=row_idx, column=2).alignment = a_left
        
        b_cell = ws_c.cell(row=row_idx, column=3, value=c_bucket)
        b_cell.font = f_bold
        b_cell.alignment = a_center
        if c_bucket == "Needs":
            b_cell.fill = fill_badge_needs
        elif c_bucket == "Wants":
            b_cell.fill = fill_badge_wants
        elif c_bucket == "Savings":
            b_cell.fill = fill_badge_savings
        elif c_bucket == "Income":
            b_cell.fill = fill_badge_income
        else:
            b_cell.fill = fill_badge_transfer
            
        ws_c.cell(row=row_idx, column=4, value=c_icon).font = f_norm
        ws_c.cell(row=row_idx, column=4).alignment = a_center
        
        c_bud = ws_c.cell(row=row_idx, column=5, value=c_budget)
        c_bud.font = f_norm
        c_bud.alignment = a_right
        c_bud.number_format = fmt_curr
        
        ws_c.cell(row=row_idx, column=6, value=c_desc).font = f_norm
        ws_c.cell(row=row_idx, column=6).alignment = a_left
        
        for c in range(1, 7):
            ws_c.cell(row=row_idx, column=c).border = b_thin

    cat_widths = {
        'A': 16, 'B': 36, 'C': 16, 'D': 16, 'E': 22, 'F': 50
    }
    for c_let, w in cat_widths.items():
        ws_c.column_dimensions[c_let].width = w

    # =========================================================================
    # 4. TAB: Ledger_Clean (Silver Layer)
    # =========================================================================
    ws_l = wb.create_sheet(title="Ledger_Clean")
    ws_l.views.sheetView[0].showGridLines = True

    ws_l.row_dimensions[1].height = 30
    ws_l.row_dimensions[2].height = 24

    ws_l.merge_cells("A1:M1")
    ws_l["A1"] = "LEDGER_CLEAN — SILVER CONFORMED DOUBLE-ENTRY TRANSACTION JOURNAL"
    ws_l["A1"].font = f_section
    ws_l["A1"].fill = fill_slate_navy
    ws_l["A1"].alignment = a_center

    clean_headers = [
        "transaction_id", "date", "time", "source_account",
        "destination_merchant", "type", "category", "budget_bucket",
        "amount", "notes", "payment_method", "raw_ref_id", "status"
    ]
    for col_idx, h in enumerate(clean_headers, start=1):
        cell = ws_l.cell(row=2, column=col_idx, value=h)
        cell.font = f_tbl_head
        cell.fill = fill_slate_dark
        cell.alignment = a_center
        cell.border = b_thin

    ledger_entries = [
        ("TX-202609-001", datetime.date(2026, 9, 1), datetime.time(7, 14, 0), "BCA", "PT Tech Nusantara", "INCOME", "Salary & Compensation", 25000000, "Gaji Payroll Bulanan September 2026", "TRANSFER", "RAW-20260901-001", "VERIFIED"),
        ("TX-202609-002", datetime.date(2026, 9, 1), datetime.time(10, 30, 15), "BCA", "GoPay", "TRANSFER", "Internal Account Transfer", 1000000, "Top up saldo operasional harian GoPay", "TRANSFER", "RAW-20260901-002", "VERIFIED"),
        ("TX-202609-003", datetime.date(2026, 9, 2), datetime.time(14, 15, 30), "Mandiri", "PLN Pascabayar", "EXPENSE", "Utilities & Bills (PLN, Water, Net)", 850000, "Tagihan listrik rumah September 2026", "TRANSFER", "RAW-20260902-003", "VERIFIED"),
        ("TX-202609-004", datetime.date(2026, 9, 2), datetime.time(19, 20, 5), "BCA", "Indihome Internet", "EXPENSE", "Utilities & Bills (PLN, Water, Net)", 450000, "Tagihan internet fiber optical 50 Mbps", "AUTODEBET", "RAW-20260902-004", "VERIFIED"),
        ("TX-202609-005", datetime.date(2026, 9, 3), datetime.time(16, 45, 10), "BCA", "Indomaret Fresh TB Simatupang", "EXPENSE", "Groceries & Food Supplies", 1450000, "Belanja mingguan bahan makanan & buah", "DEBIT", "RAW-20260903-005", "VERIFIED"),
        ("TX-202609-006", datetime.date(2026, 9, 4), datetime.time(9, 12, 44), "GoPay", "Kopi Kenangan Menara Astra", "EXPENSE", "Dining Out & Cafes", 48000, "2x Kopi Kenangan Mantan Large QRIS", "QRIS", "RAW-20260904-006", "VERIFIED"),
        ("TX-202609-007", datetime.date(2026, 9, 5), datetime.time(8, 30, 12), "GoPay", "Gojek Transport", "EXPENSE", "Transportation & Commute", 65000, "GoCar transport kantor SCBD meeting", "E_WALLET", "RAW-20260905-007", "VERIFIED"),
        ("TX-202609-008", datetime.date(2026, 9, 6), datetime.time(12, 35, 50), "ShopeePay", "Restoran Sederhana Padang", "EXPENSE", "Groceries & Food Supplies", 45000, "Makan siang rendang & perkedel QRIS", "QRIS", "RAW-20260906-008", "VERIFIED"),
        ("TX-202609-009", datetime.date(2026, 9, 7), datetime.time(17, 20, 0), "Cash", "Apotek Kimia Farma", "EXPENSE", "Healthcare & Pharmacy", 175000, "Beli suplemen vitamin C & obat flu", "CASH", "RAW-20260907-009", "VERIFIED"),
        ("TX-202609-010", datetime.date(2026, 9, 8), datetime.time(3, 0, 18), "Bank Jago", "Netflix Premium Indonesia", "EXPENSE", "Entertainment & Subscriptions", 186000, "Langganan bulanan 4K family plan", "DEBIT", "RAW-20260908-010", "VERIFIED"),
        ("TX-202609-011", datetime.date(2026, 9, 9), datetime.time(15, 40, 22), "DANA", "Indomaret Point", "EXPENSE", "Dining Out & Cafes", 54000, "Beli camilan sore & minuman dingin", "QRIS", "RAW-20260909-011", "VERIFIED"),
        ("TX-202609-012", datetime.date(2026, 9, 10), datetime.time(11, 0, 0), "Bank Jago", "Bibit Reksadana", "EXPENSE", "Mutual Funds & Stocks", 3000000, "DCA rutin reksadana indeks saham BNI-AM30", "TRANSFER", "RAW-20260910-012", "VERIFIED"),
        ("TX-202609-013", datetime.date(2026, 9, 11), datetime.time(20, 15, 35), "BCA", "Sushi Tei Senayan City", "EXPENSE", "Dining Out & Cafes", 420000, "Makan malam weekend keluarga Senayan", "DEBIT", "RAW-20260911-013", "VERIFIED"),
        ("TX-202609-014", datetime.date(2026, 9, 12), datetime.time(10, 10, 45), "Mandiri", "Shell TB Simatupang", "EXPENSE", "Transportation & Commute", 350000, "Isi bensin full tank Shell V-Power", "QRIS", "RAW-20260912-014", "VERIFIED"),
        ("TX-202609-015", datetime.date(2026, 9, 13), datetime.time(14, 50, 11), "SeaBank", "Tokopedia Marketplace", "EXPENSE", "Shopping & Retail", 280000, "Buku teknikal data engineering & kabel", "TRANSFER", "RAW-20260913-015", "VERIFIED"),
        ("TX-202609-016", datetime.date(2026, 9, 14), datetime.time(16, 30, 29), "OVO", "Fore Coffee Menara Mandiri", "EXPENSE", "Dining Out & Cafes", 35000, "1x Aren Latte iced cup QRIS OVO", "QRIS", "RAW-20260914-016", "VERIFIED"),
        ("TX-202609-017", datetime.date(2026, 9, 15), datetime.time(9, 30, 0), "BCA", "Stockbit BCA Sekuritas", "EXPENSE", "Mutual Funds & Stocks", 2500000, "Top up RDN & buy saham bluechip BBCA", "TRANSFER", "RAW-20260915-017", "VERIFIED"),
        ("TX-202609-018", datetime.date(2026, 9, 16), datetime.time(18, 0, 20), "Bank Jago", "PT Kreasi Digital", "INCOME", "Freelance & Consulting", 4500000, "Pelunasan invoice UI/UX data audit project", "BI_FAST", "RAW-20260916-018", "VERIFIED"),
        ("TX-202609-019", datetime.date(2026, 9, 17), datetime.time(21, 0, 15), "SeaBank", "SeaBank Deposito Ekstra", "EXPENSE", "Emergency Fund Reserve", 1500000, "Alokasi dana darurat bunga tinggi harian", "TRANSFER", "RAW-20260917-019", "VERIFIED"),
        ("TX-202609-020", datetime.date(2026, 9, 18), datetime.time(11, 45, 0), "GoPay", "Masjid Nurul Iman SCBD", "EXPENSE", "Family Support & Charity", 100000, "Sedekah subuh & infaq sholat Jumat QRIS", "QRIS", "RAW-20260918-020", "VERIFIED")
    ]

    for row_idx, item in enumerate(ledger_entries, start=3):
        ws_l.row_dimensions[row_idx].height = 20
        tx_id, dt_val, tm_val, src, dest, t_type, cat, amt, notes, p_meth, raw_id, stat = item
        
        ws_l.cell(row=row_idx, column=1, value=tx_id).font = f_bold
        ws_l.cell(row=row_idx, column=1).alignment = a_center
        
        c_dt = ws_l.cell(row=row_idx, column=2, value=dt_val)
        c_dt.font = f_norm
        c_dt.alignment = a_center
        c_dt.number_format = fmt_dt
        
        c_tm = ws_l.cell(row=row_idx, column=3, value=tm_val)
        c_tm.font = f_norm
        c_tm.alignment = a_center
        c_tm.number_format = fmt_tm
        
        ws_l.cell(row=row_idx, column=4, value=src).font = f_bold
        ws_l.cell(row=row_idx, column=4).alignment = a_left
        
        ws_l.cell(row=row_idx, column=5, value=dest).font = f_norm
        ws_l.cell(row=row_idx, column=5).alignment = a_left
        
        c_type = ws_l.cell(row=row_idx, column=6, value=t_type)
        c_type.font = f_bold
        c_type.alignment = a_center
        if t_type == "INCOME":
            c_type.fill = fill_badge_income
        elif t_type == "EXPENSE":
            c_type.fill = fill_badge_wants
        else:
            c_type.fill = fill_badge_transfer
            
        ws_l.cell(row=row_idx, column=7, value=cat).font = f_norm
        ws_l.cell(row=row_idx, column=7).alignment = a_left
        
        # Dynamic Bucket Lookup Formula from Categories sheet
        bucket_formula = f'=IFERROR(INDEX(Categories!$C$3:$C$22,MATCH(G{row_idx},Categories!$B$3:$B$22,0)),"Uncategorized")'
        c_bkt = ws_l.cell(row=row_idx, column=8, value=bucket_formula)
        c_bkt.font = f_bold
        c_bkt.alignment = a_center
        
        c_amt = ws_l.cell(row=row_idx, column=9, value=amt)
        c_amt.font = f_bold
        c_amt.alignment = a_right
        c_amt.number_format = fmt_curr
        
        ws_l.cell(row=row_idx, column=10, value=notes).font = f_norm
        ws_l.cell(row=row_idx, column=10).alignment = a_left
        
        ws_l.cell(row=row_idx, column=11, value=p_meth).font = f_norm
        ws_l.cell(row=row_idx, column=11).alignment = a_center
        
        ws_l.cell(row=row_idx, column=12, value=raw_id).font = f_norm
        ws_l.cell(row=row_idx, column=12).alignment = a_center
        
        c_st = ws_l.cell(row=row_idx, column=13, value=stat)
        c_st.font = f_bold
        c_st.alignment = a_center
        c_st.fill = fill_badge_income
        
        for c in range(1, 14):
            ws_l.cell(row=row_idx, column=c).border = b_thin

    # Add Data Validations for Ledger_Clean
    dv_acct = DataValidation(type="list", formula1='"BCA,Mandiri,BRI,BNI,Bank Jago,SeaBank,GoPay,OVO,DANA,ShopeePay,Cash"', allow_blank=True)
    ws_l.add_data_validation(dv_acct)
    dv_acct.add("D3:D100")

    dv_type = DataValidation(type="list", formula1='"INCOME,EXPENSE,TRANSFER"', allow_blank=True)
    ws_l.add_data_validation(dv_type)
    dv_type.add("F3:F100")

    dv_cat = DataValidation(type="list", formula1="Categories!$B$3:$B$22", allow_blank=True)
    ws_l.add_data_validation(dv_cat)
    dv_cat.add("G3:G100")

    dv_pay = DataValidation(type="list", formula1='"QRIS,BI_FAST,DEBIT,TRANSFER,AUTODEBET,E_WALLET,CASH"', allow_blank=True)
    ws_l.add_data_validation(dv_pay)
    dv_pay.add("K3:K100")

    dv_stat = DataValidation(type="list", formula1='"VERIFIED,PENDING_REVIEW,RECONCILED"', allow_blank=True)
    ws_l.add_data_validation(dv_stat)
    dv_stat.add("M3:M100")

    clean_widths = {
        'A': 16, 'B': 14, 'C': 12, 'D': 16, 'E': 32, 'F': 14,
        'G': 34, 'H': 18, 'I': 18, 'J': 45, 'K': 16, 'L': 18, 'M': 16
    }
    for c_let, w in clean_widths.items():
        ws_l.column_dimensions[c_let].width = w

    # =========================================================================
    # 5. TAB: Monthly_Summary (Gold Layer)
    # =========================================================================
    ws_m = wb.create_sheet(title="Monthly_Summary")
    ws_m.views.sheetView[0].showGridLines = True

    ws_m.row_dimensions[1].height = 30
    ws_m.row_dimensions[2].height = 24

    ws_m.merge_cells("A1:N1")
    ws_m["A1"] = "MONTHLY_SUMMARY — GOLD ANALYTICAL MART & 50/30/20 VARIANCE ENGINE"
    ws_m["A1"].font = f_section
    ws_m["A1"].fill = fill_slate_navy
    ws_m["A1"].alignment = a_center

    month_headers = [
        "month_period", "total_income", "needs_actual", "needs_target_50pct",
        "needs_variance", "wants_actual", "wants_target_30pct", "wants_variance",
        "savings_actual", "savings_target_20pct", "total_living_expenses",
        "net_cash_surplus", "savings_rate_pct", "compliance_status"
    ]
    for col_idx, h in enumerate(month_headers, start=1):
        cell = ws_m.cell(row=2, column=col_idx, value=h)
        cell.font = f_tbl_head
        cell.fill = fill_slate_dark
        cell.alignment = a_center
        cell.border = b_thin

    months_list = [
        ("2026-09", 2026, 9, 1, 30),
        ("2026-10", 2026, 10, 1, 31),
        ("2026-11", 2026, 11, 1, 30),
        ("2026-12", 2026, 12, 1, 31),
    ]

    for idx, (m_code, yr, mo, d1, d2) in enumerate(months_list, start=3):
        ws_m.row_dimensions[idx].height = 22
        
        # Period
        ws_m.cell(row=idx, column=1, value=m_code).font = f_bold
        ws_m.cell(row=idx, column=1).alignment = a_center
        
        # Formula date boundaries
        d_start = f"DATE({yr},{mo},{d1})"
        d_end = f"DATE({yr},{mo},{d2})"
        
        # Col B: Total Income
        c_inc = ws_m.cell(row=idx, column=2, value=f'=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$F$3:$F$100,"INCOME",Ledger_Clean!$B$3:$B$100,">="&{d_start},Ledger_Clean!$B$3:$B$100,"<="&{d_end})')
        c_inc.font = f_bold
        c_inc.alignment = a_right
        c_inc.number_format = fmt_curr
        
        # Col C: Needs Actual
        c_na = ws_m.cell(row=idx, column=3, value=f'=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$F$3:$F$100,"EXPENSE",Ledger_Clean!$H$3:$H$100,"Needs",Ledger_Clean!$B$3:$B$100,">="&{d_start},Ledger_Clean!$B$3:$B$100,"<="&{d_end})')
        c_na.font = f_norm
        c_na.alignment = a_right
        c_na.number_format = fmt_curr
        
        # Col D: Needs Target 50%
        c_nt = ws_m.cell(row=idx, column=4, value=f'=B{idx}*0.5')
        c_nt.font = f_norm
        c_nt.alignment = a_right
        c_nt.number_format = fmt_curr
        
        # Col E: Needs Variance (Target - Actual)
        c_nv = ws_m.cell(row=idx, column=5, value=f'=D{idx}-C{idx}')
        c_nv.font = f_norm
        c_nv.alignment = a_right
        c_nv.number_format = fmt_curr
        
        # Col F: Wants Actual
        c_wa = ws_m.cell(row=idx, column=6, value=f'=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$F$3:$F$100,"EXPENSE",Ledger_Clean!$H$3:$H$100,"Wants",Ledger_Clean!$B$3:$B$100,">="&{d_start},Ledger_Clean!$B$3:$B$100,"<="&{d_end})')
        c_wa.font = f_norm
        c_wa.alignment = a_right
        c_wa.number_format = fmt_curr
        
        # Col G: Wants Target 30%
        c_wt = ws_m.cell(row=idx, column=7, value=f'=B{idx}*0.3')
        c_wt.font = f_norm
        c_wt.alignment = a_right
        c_wt.number_format = fmt_curr
        
        # Col H: Wants Variance
        c_wv = ws_m.cell(row=idx, column=8, value=f'=G{idx}-F{idx}')
        c_wv.font = f_norm
        c_wv.alignment = a_right
        c_wv.number_format = fmt_curr
        
        # Col I: Savings Actual
        c_sa = ws_m.cell(row=idx, column=9, value=f'=SUMIFS(Ledger_Clean!$I$3:$I$100,Ledger_Clean!$F$3:$F$100,"EXPENSE",Ledger_Clean!$H$3:$H$100,"Savings",Ledger_Clean!$B$3:$B$100,">="&{d_start},Ledger_Clean!$B$3:$B$100,"<="&{d_end})')
        c_sa.font = f_norm
        c_sa.alignment = a_right
        c_sa.number_format = fmt_curr
        
        # Col J: Savings Target 20%
        c_st = ws_m.cell(row=idx, column=10, value=f'=B{idx}*0.2')
        c_st.font = f_norm
        c_st.alignment = a_right
        c_st.number_format = fmt_curr
        
        # Col K: Total Living Expenses (Needs + Wants)
        c_tle = ws_m.cell(row=idx, column=11, value=f'=C{idx}+F{idx}')
        c_tle.font = f_bold
        c_tle.alignment = a_right
        c_tle.number_format = fmt_curr
        
        # Col L: Net Cash Surplus (Income - Living - Savings)
        c_sur = ws_m.cell(row=idx, column=12, value=f'=B{idx}-K{idx}-I{idx}')
        c_sur.font = f_bold
        c_sur.alignment = a_right
        c_sur.number_format = fmt_curr
        
        # Col M: Savings Rate % = (Savings + Surplus) / Income
        c_sr = ws_m.cell(row=idx, column=13, value=f'=IF(B{idx}>0,(I{idx}+L{idx})/B{idx},0)')
        c_sr.font = f_bold
        c_sr.alignment = a_right
        c_sr.number_format = fmt_pct
        
        # Col N: Compliance Status
        comp_formula = f'=IF(B{idx}=0,"PENDING DATA",IF(AND(C{idx}<=D{idx},F{idx}<=G{idx},(I{idx}+L{idx})>=J{idx}),"✅ BALANCED (50/30/20)",IF((I{idx}+L{idx})<J{idx},"⚠️ LOW SAVINGS (<20%)","⚠️ OVER BUDGET")))'
        c_cs = ws_m.cell(row=idx, column=14, value=comp_formula)
        c_cs.font = f_bold
        c_cs.alignment = a_center
        
        for c in range(1, 15):
            ws_m.cell(row=idx, column=c).border = b_thin

    month_widths = {
        'A': 15, 'B': 20, 'C': 18, 'D': 20, 'E': 18, 'F': 18,
        'G': 20, 'H': 18, 'I': 18, 'J': 20, 'K': 22, 'L': 20,
        'M': 18, 'N': 28
    }
    for c_let, w in month_widths.items():
        ws_m.column_dimensions[c_let].width = w

    # Save finalized workbook
    wb.save(output_filepath)
    print(f"[OK] Generated Personal Finance Hub template at: {output_filepath}")

if __name__ == "__main__":
    target_path = "templates/Personal_Finance_Hub_Template.xlsx"
    generate_personal_finance_hub_template(target_path)
