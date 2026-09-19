# Data Contract, Architecture, and Formula Specification
**Project:** Personal Finance Hub — Phase 1: Automated Ingestion & Ledger System  
**Author:** Muhammad Rifqi Setiawan  
**Status:** Approved / Specification Standard  
**Last Updated:** September 2026  

---

## 1. Executive Summary & Architecture Overview

The **Personal Finance Hub** is designed as a personal financial lakehouse and automation platform tailored specifically to the Indonesian financial ecosystem. It ingests semi-structured and unstructured transaction feeds (Push Notifications, SMS, Email receipts, CSV exports, QRIS receipts) across Indonesian commercial banks, digital banks, and e-wallets, cleanses and normalizes them into an immutable double-entry ledger, and aggregates them into actionable financial analytics adhering to the **50/30/20 Budgeting Rule**.

### 1.1 Medallion Architecture Mapping
```
   [Inflow Sources: BCA, Mandiri, BRI, BNI, Jago, SeaBank, GoPay, OVO, DANA, ShopeePay, Cash]
                                        │
                                        ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ BRONZE LAYER (Transactions_Raw)                                       │
   │ - Raw notification strings, SMS payloads, webhooks, OCR text           │
   │ - Append-only, immutable, raw timestamp, ingestion metadata            │
   │ - Deduplication Hash: SHA256(timestamp + source + raw_amount + text)   │
   └────────────────────────────────────┬───────────────────────────────────┘
                                        │
                         [ETL / Normalization Rules]
                         [Regex & AI Parsing Service]
                                        ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ SILVER LAYER (Ledger_Clean)                                            │
   │ - Conformed Schema: Date, Source, Merchant, Category, Bucket, Amount  │
   │ - Foreign key reference to Transactions_Raw (raw_id)                   │
   │ - Standardized transaction type: INCOME, EXPENSE, TRANSFER             │
   └───────────────────┬────────────────────────────────┬───────────────────┘
                       │                                │
                       ▼                                ▼
   ┌─────────────────────────────────────┐  ┌───────────────────────────────┐
   │ MASTER DIMENSION (Categories)       │  │ GOLD LAYER (Monthly_Summary)  │
   │ - 50/30/20 Rule Classification      │  │ - Period-level aggregations    │
   │ - Needs, Wants, Savings, Income     │  │ - KPI calculations            │
   │ - Monthly budget limits & icons     │  │ - Compliance & variance       │
   └───────────────────┬─────────────────┘  └───────────────┬───────────────┘
                       │                                    │
                       └─────────────────┬──────────────────┘
                                         ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ GOLD MART / PRESENTATION (Dashboard)                                   │
   │ - Executive KPI Cards: Net Worth, Inflow, Outflow, Net Savings Rate    │
   │ - Dynamic 50/30/20 Allocation Gauge                                    │
   │ - Real-time Liquidity per Account (Cash & Bank reconciliation)         │
   │ - Recent Transactions Activity Monitor                                 │
   └────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Multi-Institution Data Contracts

The pipeline standardizes transactions across 11 major Indonesian payment rails and banking institutions:

| Institution Code | Institution Name | Category | Primary Ingestion Channel | Key Parsing Identifiers |
| :--- | :--- | :--- | :--- | :--- |
| `BCA` | Bank Central Asia | Traditional Bank | m-BCA Push / SMS / Email | `m-Transfer`, `QR m-BCA`, `Debit BCA`, `KRIS` |
| `MANDIRI` | Bank Mandiri | Traditional Bank | Livin' by Mandiri Push / SMS | `QRIS Livin'`, `Transfer Mandiri`, `Bi-Fast` |
| `BRI` | Bank Rakyat Indonesia | Traditional Bank | BRImo Push / SMS Notification | `BRImo`, `QRIS BRImo`, `Transfer Masuk` |
| `BNI` | Bank Negara Indonesia | Traditional Bank | BNI Mobile Banking Push | `BNI Mobile`, `QRIS BNI`, `Bi-Fast` |
| `JAGO` | Bank Jago | Digital Bank | Push Notification / Webhook | `Pocket Kantong`, `QRIS Jago`, `Kirim Uang` |
| `SEABANK` | SeaBank Indonesia | Digital Bank | App Notification / Email | `SeaBank Transfer`, `Bunga Harian`, `Shopee Inflow` |
| `GOPAY` | GoPay Indonesia | E-Wallet | App Notification / Push / Receipt| `GoRide`, `GoFood`, `QRIS GoPay`, `Top Up` |
| `OVO` | OVO (PT Visionet) | E-Wallet | App Notification / SMS | `OVO Cash`, `GrabFood`, `OVO Points`, `QRIS` |
| `DANA` | DANA Indonesia | E-Wallet | App Notification / Push | `DANA Protection`, `QRIS DANA`, `Kirim Uang` |
| `SHOPEEPAY` | ShopeePay | E-Wallet | App Notification / Shopee App | `ShopeePay`, `ShopeeFood`, `QRIS ShopeePay` |
| `CASH` | Physical Cash | Physical | Manual Quick Entry Bot / Shortcut| `Cash Withdrawal`, `Kembalian Tunai` |

---

## 3. Spreadsheet Architecture & Tab Specifications

The spreadsheet model is implemented across 5 conformed tabs:

```
Personal_Finance_Hub_Template.xlsx
 ├── 1. Dashboard             (Executive summary, KPIs, 50/30/20 breakdown, account balances)
 ├── 2. Transactions_Raw     (Bronze Ingestion Log with audit trail and payload hash)
 ├── 3. Ledger_Clean         (Silver Conformed Double-Entry Journal)
 ├── 4. Categories           (Master Category Dimension & 50/30/20 Budget Mapping)
 └── 5. Monthly_Summary      (Gold Period Aggregations & Budget Variance Engine)
```

---

### Tab 1: `Dashboard` (Executive Cockpit)

#### Purpose
Provides at-a-glance executive visibility into current month liquidity, cash flow, 50/30/20 budget compliance, and account balances without requiring manual recalculation.

#### Layout Specification
- **Row 1-3: Header & Configuration Banner**
  - Title: `PERSONAL FINANCE HUB — EXECUTIVE COCKPIT`
  - Active Reporting Period: Cell `C2` (e.g., `2026-09`)
  - Last Synced Timestamp: Cell `G2`
- **Row 5-8: Executive KPI Cards (Row of 4 Cards)**
  1. **Total Net Worth / Liquid Balance**: Sum of all verified balances across banks and e-wallets.
  2. **Total Inflow (Income)**: Monthly salary, freelance, investments, and passive cashflows.
  3. **Total Outflow (Expense)**: Monthly operational expenses (Needs + Wants).
  4. **Net Savings Rate (%)**: `(Total Income - Total Expense) / Total Income` with target benchmark `>= 20%`.
- **Row 10-18: 50/30/20 Rule Health Gauge & Variance Analysis**
  - **Needs (50%)**: Actual Expense vs Maximum Budget (`50% * Total Income`). Status: `OPTIMAL` or `OVERSPENT`.
  - **Wants (30%)**: Actual Expense vs Maximum Budget (`30% * Total Income`). Status: `OPTIMAL` or `OVERSPENT`.
  - **Savings & Investments (20%)**: Actual Saved vs Minimum Target (`20% * Total Income`). Status: `ON TRACK` or `UNDERFUNDED`.
- **Row 10-24 (Right Pane): Account Liquidity & Reconciliation Table**
  - Columns: `Account Name`, `Type` (Bank / E-Wallet / Cash), `Starting Balance`, `Net Movement`, `Current Balance`, `Status`.
- **Row 20-30 (Left Pane): Top Expense Categories Breakdown**
  - Ranked breakdown of the highest spending categories for the active month.

---

### Tab 2: `Transactions_Raw` (Bronze Layer)

#### Purpose
Captures raw, untransformed transaction notifications and automated ingestion payloads. Preserves full auditability and enables idempotent deduplication.

#### Data Schema Contract
| Column Index | Field Name | Data Type | Nullable | Example | Validation / Constraints | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `A` | `raw_id` | String / UUID | No | `RAW-20260901-001` | Unique, Non-empty | Unique raw ingestion identifier |
| `B` | `ingestion_timestamp` | DateTime | No | `2026-09-01 07:15:22` | ISO 8601 | Server timestamp when payload was received |
| `C` | `source_institution` | String | No | `BCA` | In Institution list | Bank or e-wallet emitting the notice |
| `D` | `channel` | String | No | `PUSH_NOTIFICATION`| Enum(`PUSH`, `SMS`, `EMAIL`, `OCR`, `MANUAL`) | Capture vector |
| `E` | `raw_payload` | String | No | `m-Transfer: 01/09 07:14 TRSF DARI PT TECH BERSAMA Rp 25.000.000,00` | Raw message string | Original untouched text |
| `F` | `parsed_amount` | Currency (IDR) | No | `25000000` | Number > 0 | Amount extracted by parser |
| `G` | `parsed_direction` | String | No | `CR` | Enum(`CR`, `DB`) | Credit (In) or Debit (Out) |
| `H` | `payload_hash` | String (SHA256) | No | `e3b0c44298fc1c149af...`| 64-char Hex string | Dedup hash: SHA256(time + source + amount + payload) |
| `I` | `processing_status` | String | No | `PROCESSED` | Enum(`PENDING`, `PROCESSED`, `IGNORED`, `ERROR`) | ETL pipeline processing state |
| `J` | `clean_ledger_ref` | String | Yes | `TX-202609-001` | Matches `Ledger_Clean.transaction_id` | Foreign Key link to Silver table |

---

### Tab 3: `Ledger_Clean` (Silver Layer)

#### Purpose
The conformed, normalized single source of truth for all personal financial movements. Used directly for financial statements and reporting queries.

#### Data Schema Contract
| Column Index | Field Name | Data Type | Nullable | Example | Validation / Dropdown | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `A` | `transaction_id` | String | No | `TX-202609-001` | Unique Key | Unique transaction code |
| `B` | `date` | Date | No | `2026-09-01` | YYYY-MM-DD | Standard transaction posting date |
| `C` | `time` | Time | Yes | `07:14:00` | HH:MM:SS | Time of transaction |
| `D` | `source_account` | String | No | `BCA` | List: Accounts master | Debited account or primary holder |
| `E` | `destination_merchant` | String | No | `PT Tech Bersama` | String | Merchant, recipient, or target account |
| `F` | `type` | String | No | `INCOME` | Enum(`INCOME`, `EXPENSE`, `TRANSFER`) | Accounting transaction classification |
| `G` | `category` | String | No | `Salary & Compensation` | Dynamic List from `Categories` | Standardized category |
| `H` | `budget_bucket` | String | No | `Income` | Formula / Enum(`Needs`, `Wants`, `Savings`, `Income`, `Transfer`) | 50/30/20 Bucket mapping |
| `I` | `amount` | Currency (IDR) | No | `25000000` | Number > 0 | Absolute transaction value in Rupiah |
| `J` | `notes` | String | Yes | `Payroll Gaji Bulanan September 2026` | Free text | Contextual remarks or item details |
| `K` | `payment_method` | String | No | `BANK_TRANSFER` | Enum(`QRIS`, `BI_FAST`, `DEBIT`, `TRANSFER`, `E_WALLET`, `CASH`) | Payment instrument used |
| `L` | `raw_ref_id` | String | Yes | `RAW-20260901-001` | FK: `Transactions_Raw.raw_id` | Provenance traceability link |
| `M` | `reconciliation_status` | String | No | `VERIFIED` | Enum(`VERIFIED`, `PENDING_REVIEW`, `RECONCILED`) | Audit sign-off state |

---

### Tab 4: `Categories` (Dimension Table)

#### Purpose
Houses the master taxonomy for budgeting, expense categorization, and default budget caps aligned with the 50/30/20 personal finance framework.

#### Category Taxonomy Table
| Category Code | Category Name | 50/30/20 Bucket | Icon / Tag | Default Monthly Budget (IDR) | Description & Scope |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `INC-01` | Salary & Compensation | `Income` | 💼 Payroll | - | Monthly corporate payroll or base salary |
| `INC-02` | Freelance & Consulting | `Income` | 💻 Project | - | Secondary gig income, advisory, software contracts |
| `INC-03` | Investment Returns & Dividends | `Income` | 📈 Passive | - | Stock dividends, crypto staking, P2P interest |
| `INC-04` | Cashback, Gifts & Refunds | `Income` | 🎁 Rebate | - | E-wallet promos, marketplace cashback |
| `NED-01` | Groceries & Food Supplies | `Needs` | 🛒 Groceries | Rp 3,000,000 | Supermarket, raw ingredients, wet market, Indomaret |
| `NED-02` | Utilities & Bills (PLN, Water, Net)| `Needs` | ⚡ Utilities | Rp 1,500,000 | PLN Pascabayar, PDAM, Indihome, Biznet, Telkomsel |
| `NED-03` | Housing & Maintenance | `Needs` | 🏠 Rent/Home | Rp 5,000,000 | Kost / Apartment rent, IPL maintenance, home repairs |
| `NED-04` | Transportation & Commute | `Needs` | 🚗 Commute | Rp 1,200,000 | Bensin (Pertamax/Shell), Tol, KRL, MRT, Grab/Gojek commute |
| `NED-05` | Healthcare, Pharmacy & Insurance | `Needs` | 🏥 Medical | Rp 800,000 | BPJS Kesehatan, private insurance, Apotek Kimia Farma |
| `NED-06` | Family Support & Zakat/Charity | `Needs` | 🤲 Social | Rp 1,000,000 | Monthly parent stipend, Zakat Maal, regular infaq |
| `WNT-01` | Dining Out & Cafes | `Wants` | ☕ F&B Lifestyle | Rp 1,500,000 | Coffee shops (Kopi Kenangan, Fore), restaurants, GrabFood |
| `WNT-02` | Entertainment & Subscriptions | `Wants` | 🍿 Media | Rp 500,000 | Netflix, Spotify, YouTube Premium, iCloud, ChatGPT |
| `WNT-03` | Shopping, Gadgets & Apparel | `Wants` | 🛍️ Retail | Rp 1,500,000 | Tokopedia, Shopee, Uniqlo, tech accessories |
| `WNT-04` | Hobbies, Travel & Recreation | `Wants` | ✈️ Leisure | Rp 1,000,000 | Weekend trips, gym membership, sports, gaming |
| `WNT-05` | Personal Care & Grooming | `Wants` | 💈 Salon/Care | Rp 500,000 | Barbershop, skincare, spa |
| `SAV-01` | Emergency Fund (Dana Darurat) | `Savings` | 🛡️ Safety Net | Rp 2,000,000 | Liquid high-yield deposits (SeaBank, Jago Kantong) |
| `SAV-02` | Mutual Funds & Stocks (Reksadana/IHSG)| `Savings` | 📊 Equity/Bonds | Rp 3,000,000 | Bibit (Reksadana Indeks), Stockbit (BBCA, BBRI, BMRI) |
| `SAV-03` | Crypto & Digital Assets | `Savings` | 🪙 Crypto | Rp 1,000,000 | Bitcoin (BTC), Ethereum (ETH) long-term DCA |
| `SAV-04` | Government Bonds & Gold | `Savings` | 🥇 SBN/Gold | Rp 1,000,000 | ORI, SR, Antam Gold via Pegadaian / Pluang |
| `TRF-01` | Internal Account Transfer | `Transfer` | 🔄 Rebalance | - | E-wallet top-up (BCA to GoPay, Mandiri to DANA) |

---

### Tab 5: `Monthly_Summary` (Gold Layer)

#### Purpose
Rolls up financial figures per calendar month (YYYY-MM), tracking 50/30/20 compliance percentages, absolute savings rates, and budget variances.

#### Column Layout Specification
1. **Period (`month_year`)**: e.g., `2026-09`
2. **Gross Inflow (`total_income`)**: Dynamic formula filtering `Ledger_Clean` for `type = "INCOME"`.
3. **Needs Outflow (`actual_needs`)**: Dynamic formula for `type = "EXPENSE"` and `budget_bucket = "Needs"`.
4. **Needs Target (`target_needs_50pct`)**: `= 50% * total_income`.
5. **Needs Variance (`needs_variance`)**: `= target_needs - actual_needs`.
6. **Wants Outflow (`actual_wants`)**: Dynamic formula for `type = "EXPENSE"` and `budget_bucket = "Wants"`.
7. **Wants Target (`target_wants_30pct`)**: `= 30% * total_income`.
8. **Wants Variance (`wants_variance`)**: `= target_wants - actual_wants`.
9. **Savings Outflow (`actual_savings`)**: Dynamic formula for `type = "EXPENSE"` (or dedicated investment debit) with `budget_bucket = "Savings"`.
10. **Savings Target (`target_savings_20pct`)**: `= 20% * total_income`.
11. **Total Living Expenses (`total_expense`)**: `= actual_needs + actual_wants`.
12. **Net Monthly Savings (`net_surplus`)**: `= total_income - total_expense - actual_savings`.
13. **Effective Savings Rate (`savings_rate_pct`)**: `= (actual_savings + net_surplus) / total_income`.
14. **50/30/20 Compliance Status**: Formula evaluating whether actual proportions meet the framework guidelines.

---

## 4. Google Sheets & Excel Formula Specifications

To ensure 100% interoperability between native Excel `.xlsx` and Google Sheets import, all formulas are formulated to execute identically in both engines.

### 4.1 Automated Budget Bucket Lookup in `Ledger_Clean`
In `Ledger_Clean` column `H` (budget_bucket), automate classification from the category selection in column `G`:
```excel
=IFERROR(INDEX(Categories!$C$2:$C$25, MATCH(G2, Categories!$B$2:$B$25, 0)), "Uncategorized")
```
*In Google Sheets, this can be expressed as an ArrayFormula across the entire column:*
```excel
=ARRAYFORMULA(IF(G2:G="", "", IFERROR(VLOOKUP(G2:G, Categories!$B$2:$C$25, 2, FALSE), "Uncategorized")))
```

---

### 4.2 Monthly Rollup Formulas in `Monthly_Summary`
Assuming Row 2 represents `2026-09` (with period start date `2026-09-01` in helper cell or constructed via date bounds):

- **Total Monthly Income (Col B)**:
  ```excel
  =SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$F$2:$F$1000, "INCOME", Ledger_Clean!$B$2:$B$1000, ">=2026-09-01", Ledger_Clean!$B$2:$B$1000, "<=2026-09-30")
  ```

- **Total Needs Expense (Col C)**:
  ```excel
  =SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$F$2:$F$1000, "EXPENSE", Ledger_Clean!$H$2:$H$1000, "Needs", Ledger_Clean!$B$2:$B$1000, ">=2026-09-01", Ledger_Clean!$B$2:$B$1000, "<=2026-09-30")
  ```

- **Total Wants Expense (Col F)**:
  ```excel
  =SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$F$2:$F$1000, "EXPENSE", Ledger_Clean!$H$2:$H$1000, "Wants", Ledger_Clean!$B$2:$B$1000, ">=2026-09-01", Ledger_Clean!$B$2:$B$1000, "<=2026-09-30")
  ```

- **Total Savings & Investment (Col I)**:
  ```excel
  =SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$F$2:$F$1000, "EXPENSE", Ledger_Clean!$H$2:$H$1000, "Savings", Ledger_Clean!$B$2:$B$1000, ">=2026-09-01", Ledger_Clean!$B$2:$B$1000, "<=2026-09-30")
  ```

- **50/30/20 Compliance Status (Col N)**:
  ```excel
  =IF(AND(C2<=D2, F2<=G2, I2>=J2), "✅ BALANCED", IF(I2<J2, "⚠️ LOW SAVINGS", "⚠️ OVERSPENT"))
  ```

---

### 4.3 Executive Cockpit Formulas in `Dashboard`
Based on active selected period in cell `C2` (e.g. `2026-09`):

- **Income Metric Card (`C6`)**:
  ```excel
  =SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$F$2:$F$1000, "INCOME")
  ```

- **Expense Metric Card (`E6`)**:
  ```excel
  =SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$F$2:$F$1000, "EXPENSE", Ledger_Clean!$H$2:$H$1000, "<>Savings")
  ```

- **Savings & Investment Metric Card (`G6`)**:
  ```excel
  =SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$F$2:$F$1000, "EXPENSE", Ledger_Clean!$H$2:$H$1000, "Savings")
  ```

- **Net Savings Rate Card (`I6`)**:
  ```excel
  =IF(C6>0, (G6 + (C6 - E6 - G6)) / C6, 0)
  ```

- **Account Balance Calculation Engine**:
  For an account (e.g. `BCA` in cell `F12`):
  ```excel
  =Starting_Balance + SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$E$2:$E$1000, F12, Ledger_Clean!$F$2:$F$1000, "TRANSFER") - SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$D$2:$D$1000, F12, Ledger_Clean!$F$2:$F$1000, "TRANSFER") + SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$D$2:$D$1000, F12, Ledger_Clean!$F$2:$F$1000, "INCOME") - SUMIFS(Ledger_Clean!$I$2:$I$1000, Ledger_Clean!$D$2:$D$1000, F12, Ledger_Clean!$F$2:$F$1000, "EXPENSE")
  ```

---

### 4.4 Google Sheets Power Queries (Optional Advanced In-Sheet Views)
For users opening the sheet directly in Google Sheets, dynamic real-time reporting can leverage the native `QUERY` language:

- **Filter Top 10 Expenses in Real-Time**:
  ```excel
  =QUERY(Ledger_Clean!A2:J, "SELECT B, D, E, G, I WHERE F = 'EXPENSE' ORDER BY I DESC LIMIT 10 LABEL B 'Date', D 'Account', E 'Merchant', G 'Category', I 'Amount (IDR)'", 0)
  ```

- **Dynamic Monthly Breakdown Matrix**:
  ```excel
  =QUERY(Ledger_Clean!A2:I, "SELECT H, SUM(I) WHERE F = 'EXPENSE' GROUP BY H PIVOT TEXT(B, 'YYYY-MM') LABEL H 'Budget Bucket'", 0)
  ```

---

## 5. Security, Privacy & Ingestion Governance

1. **Zero Raw Secret Storage**: Account credentials, PINs, OTP codes, and full credit card PANs are NEVER ingested or stored in `Transactions_Raw`. Ingestion parsers strip verification codes before landing on the spreadsheet.
2. **Account Number Masking**: Account numbers in transaction notes are masked to `***1234` or `x-9876`.
3. **Idempotency Guarantee**: The SHA256 `payload_hash` in `Transactions_Raw` acts as a unique primary key across all webhook and webhook replay attempts, ensuring zero duplicate bookings in `Ledger_Clean`.
4. **Separation of Concerns**: Raw payloads remain immutable in Bronze. Human categorizations and reconciliations occur strictly in Silver (`Ledger_Clean`), keeping raw evidence tamper-proof.

---
*Signed and Approved for Production Delivery,*  
**Muhammad Rifqi Setiawan**
