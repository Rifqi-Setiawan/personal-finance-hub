# Personal Finance Hub — Automated Ingestion & Analytical Dashboard

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.1+-FFF000?logo=duckdb&logoColor=black)](https://duckdb.org/)
[![Google Sheets](https://img.shields.io/badge/Google%20Sheets-API%20v4-34A853?logo=googlesheets&logoColor=white)](https://developers.google.com/sheets/api)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-110%20passed-success)](tests/)

**Personal Finance Hub** adalah sistem pencatatan keuangan pribadi otomatis (zero manual entry) berbasis arsitektur data lakehouse untuk perbankan dan dompet digital Indonesia. Platform ini mengintegrasikan webhook notifikasi ponsel secara real-time, normalisasi data transaksi otomatis, klasifikasi anggaran 50/30/20 (*Needs, Wants, Savings*), penyimpanan in-process DuckDB berkecepatan tinggi dengan jaminan idempotensi kriptografis SHA-256, serta sinkronisasi background non-blocking ke Google Sheets.

---

## 🌟 Fitur Utama

- **⚡ Zero Manual Entry via Webhook Ingestion**: Menangkap notifikasi transaksi m-Banking & e-Wallet secara otomatis melalui webhook Android (MacroDroid/Tasker) dengan respons sub-50ms.
- **🏦 10-Rail Financial Institution Parsers**: Parser regex bawaan berperforma tinggi untuk 10 bank dan e-wallet terpopuler di Indonesia:
  - **Bank Konvensional**: BCA (`m-BCA`), Bank Mandiri (`Livin' by Mandiri`), BRI (`BRImo`), BNI (`BNI Mobile Banking`).
  - **Bank Digital**: Bank Jago, SeaBank.
  - **Dompet Digital (E-Wallet)**: GoPay, DANA, OVO, ShopeePay.
- **🔒 Idempotensi Kriptografis SHA-256**: Setiap payload mentah di-hash secara deterministik (`raw_hash`). Replay notifikasi atau notifikasi ganda dari sistem operasi otomatis dideduplikasi tanpa duplikasi data buku kas (*ledger*).
- **📊 Arsitektur Data Medallion (Bronze / Silver / Gold)**:
  - **Bronze (`Transactions_Raw`)**: Menyimpan payload notifikasi mentah, timestamp asli, dan metadata perangkat secara append-only.
  - **Silver (`Ledger_Clean`)**: Normalisasi entitas, standardisasi tipe transaksi (`INCOME`, `EXPENSE`, `TRANSFER`), masking rekening sensitif, dan penentuan kategori.
  - **Gold (`Monthly_Summary` & `Dashboard`)**: Agregasi metrik finansial, kepatuhan alokasi 50/30/20, saldo riil per rekening, dan burn-rate harian.
- **🔄 Sinkronisasi Background Google Sheets**: Integrasi non-blocking via Service Account (`gspread`) yang mengunggah baris transaksi ke Google Sheets di latar belakang tanpa menunda respons webhook klien.
- **🛡️ Offline & Failure Resilience**: Jika internet terputus atau API Google Sheets mengalami *rate-limit*, transaksi tetap tersimpan aman di DuckDB lokal dan dapat disinkronkan kembali menggunakan backfill CLI (`sync-sheets --all`).
- **💬 Interactive Financial Queries**:
  - **Weekly Cashflow**: `Pemasukan Minggu Ini - Pengeluaran Minggu Ini` beserta kategori pengeluaran terbesar.
  - **Allowance & Transfer Tracking**: Pelacakan otomatis sisa kas dari transferan/gaji terakhir dengan kalkulasi rata-rata *burn rate* harian.
  - **Multi-Account Balances**: Rekonsiliasi saldo berjalan di setiap rekening bank dan dompet digital terhadap *starting balance*.
- **🛠️ Production-Ready CLI & REST API**: Dilengkapi antarmuka terminal interaktif dan dokumentasi OpenAPI/Swagger bawaan.

---

## 🏗️ Arsitektur Sistem

```
 ┌──────────────────────────────────────────────────────────┐
 │  Perangkat Android (Samsung Galaxy / Android 13+)        │
 │  Notifikasi Masuk: BCA, Mandiri, GoPay, DANA, OVO, dsb.  │
 │  MacroDroid HTTP POST Hook (< 50ms)                      │
 └────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
 ┌──────────────────────────────────────────────────────────┐
 │  FastAPI Ingestion Gateway (:8000 / :8085)               │
 │  POST /webhook/transaction                               │
 └──────────────┬───────────────────────────┬───────────────┘
                │                           │
  (Async Background Task)          (Synchronous Storage)
                │                           │
                ▼                           ▼
 ┌──────────────────────────┐  ┌────────────────────────────┐
 │ Google Sheets Sync Engine│  │ In-Process DuckDB Database │
 │ - Transactions_Raw       │  │ - raw_notifications (Bronze│
 │ - Ledger_Clean           │  │ - ledger_transactions(Silve│
 │ - Dashboard KPI Sync     │  │ - SHA-256 Idempotency Check│
 └──────────────────────────┘  └────────────────────────────┘
                │                           │
                └─────────────┬─────────────┘
                              ▼
 ┌──────────────────────────────────────────────────────────┐
 │  Analytical Layer & User Interface                       │
 │  - Interactive CLI (`finance_hub.cli`)                   │
 │  - REST Query Endpoints (`/api/query/*`)                 │
 │  - Google Sheets Dynamic Dashboard (50/30/20 Budgeting)  │
 └──────────────────────────────────────────────────────────┘
```

---

## 📁 Struktur Direktori

```text
personal-finance-hub/
├── .env.example                       # Contoh template environment variables
├── .gitignore                         # Pengabaian rahasia, data, & cache
├── LICENSE                            # Lisensi MIT
├── README.md                          # Dokumentasi proyek
├── pyproject.toml                     # Metadata paket & konfigurasi proyek
├── pytest.ini                         # Konfigurasi pengujian pytest
├── requirements.txt                   # Daftar dependensi Python
├── create_template.py                 # Generator template spreadsheet (.xlsx)
├── docs/
│   ├── runbooks/
│   │   ├── GOOGLE_SHEETS_SETUP_RUNBOOK.md      # Panduan setup Google Service Account
│   │   └── SAMSUNG_MACRODROID_SETUP_RUNBOOK.md # Panduan setup webhook Android
│   └── specs/
│       └── DATA_CONTRACT_AND_FORMULAS.md       # Spesifikasi kontrak data & formula
├── mockups/
│   └── preview.html                   # Mockup tampilan dashboard
├── templates/
│   └── Personal_Finance_Hub_Template.xlsx      # Template 5-tab spreadsheet conformed
├── src/
│   └── finance_hub/
│       ├── __init__.py
│       ├── cli.py                     # Antarmuka CLI
│       ├── classifier.py              # Rule-based 50/30/20 & Category Classifier
│       ├── models.py                  # Pydantic data models & Enums
│       ├── query.py                   # Engine agregasi cashflow, saldo, allowance
│       ├── server.py                  # FastAPI application & webhook router
│       ├── storage.py                 # DuckDB storage engine & SQL schema
│       ├── integrations/
│       │   ├── __init__.py
│       │   └── sheets_sync.py         # Google Sheets synchronization engine
│       └── parser/
│           ├── __init__.py
│           ├── base.py                # BaseParser interface
│           ├── engine.py              # ParserEngine aggregator & dispatcher
│           ├── bca.py                 # BCA parser
│           ├── bni.py                 # BNI parser
│           ├── bri.py                 # BRI parser
│           ├── dana.py                # DANA parser
│           ├── gopay.py               # GoPay parser
│           ├── jago.py                # Bank Jago parser
│           ├── mandiri.py             # Bank Mandiri parser
│           ├── ovo.py                 # OVO parser
│           ├── seabank.py             # SeaBank parser
│           └── shopeepay.py           # ShopeePay parser
└── tests/
    ├── conftest.py                    # Fixtures pytest & mock storage
    ├── test_api.py                    # Pengujian endpoint FastAPI
    ├── test_classifier.py             # Pengujian kategorisasi 50/30/20
    ├── test_cli.py                    # Pengujian CLI
    ├── test_parsers.py                # Pengujian 10 parser institusi
    ├── test_query.py                  # Pengujian kalkulasi analitik & cashflow
    ├── test_sheets_sync.py            # Pengujian integrasi Google Sheets
    └── test_storage.py                # Pengujian DuckDB & idempotensi
```

---

## ⚙️ Panduan Instalasi & Setup

### 1. Prasyarat Sistem
- Python 3.11 atau lebih baru
- Akun Google Cloud Platform (Gratis, untuk API Google Sheets)
- Smartphone Android dengan aplikasi MacroDroid (opsional untuk ingestion otomatis)

### 2. Kloning & Virtual Environment

```bash
# Clone repository
git clone https://github.com/Rifqi-Setiawan/personal-finance-hub.git
cd personal-finance-hub

# Buat virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependensi
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Konfigurasi Environment (.env)

Salin `.env.example` ke `.env`:

```bash
cp .env.example .env
```

Edit file `.env`:

```ini
# ID spreadsheet dari tautan Google Sheets Anda
GOOGLE_SPREADSHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms

# Lokasi kredensial Google Service Account
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/google_service_account.json

# Lokasi penyimpanan database DuckDB (opsional)
FINANCE_HUB_DB_PATH=data/finance.duckdb
```

> **Catatan:** Ikuti panduan lengkap di [`docs/runbooks/GOOGLE_SHEETS_SETUP_RUNBOOK.md`](docs/runbooks/GOOGLE_SHEETS_SETUP_RUNBOOK.md) untuk langkah-langkah membuat Service Account dan membagikan spreadsheet.

---

## 🚀 Menjalankan Aplikasi

### Menjalankan Server FastAPI

Jalankan server API untuk menerima webhook:

```bash
# Menggunakan Uvicorn
uvicorn finance_hub.server:app --host 0.0.0.0 --port 8000 --reload
```

Dokumentasi interaktif OpenAPI/Swagger dapat diakses di:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

---

## 💻 Penggunaan CLI (Command-Line Interface)

Personal Finance Hub dilengkapi CLI lengkap untuk operasional harian:

### 1. Ringkasan Saldo Akun & Net Worth
```bash
python -m finance_hub.cli balances
```
*Output:*
```text
================================================================
 PERSONAL FINANCE HUB — SALDO REKENING & DOMPET DIGITAL
================================================================
 Akun / Dompet   | Saldo Awal     | Masuk        | Keluar       | Saldo Saat Ini
----------------------------------------------------------------
 Mandiri         | Rp 20.152.955  | Rp 0         | Rp 0         | Rp 20.152.955 
 GoPay           | Rp 7.458       | Rp 0         | Rp 0         | Rp 7.458      
 DANA            | Rp 5.933       | Rp 0         | Rp 0         | Rp 5.933      
 ShopeePay       | Rp 6.112       | Rp 0         | Rp 0         | Rp 6.112      
 Cash            | Rp 0           | Rp 0         | Rp 0         | Rp 0          
================================================================
 TOTAL LIQUID NET WORTH : Rp 20.172.458
================================================================
```

### 2. Sisa Uang Minggu Ini (Weekly Cashflow)
```bash
python -m finance_hub.cli weekly
```
*Output:*
```text
================================================================
 PERSONAL FINANCE HUB — SISA UANG MINGGU INI
================================================================
 Periode Minggu        : 14 Sep - 20 Sep 2026
 Rentang Tanggal       : 2026-09-14 s/d 2026-09-20
 Total Pemasukan       : Rp 1.500.000
 Total Pengeluaran     : Rp 300.000
----------------------------------------------------------------
 Sisa Uang Minggu Ini  : Rp 1.200.000
----------------------------------------------------------------
 Top Pengeluaran Minggu Ini:
   • Dining (Wants): Rp 180.000
   • Groceries (Needs): Rp 120.000
================================================================
```

### 3. Pelacakan Uang Saku / Transferan Masuk (Allowance Tracking)
```bash
python -m finance_hub.cli allowance
```

### 4. Uji Coba Parsing Teks Notifikasi Mentah
```bash
python -m finance_hub.cli parse-text "Pembayaran QRIS Rp 25.000 di Kopi Kenangan berhasil" -p "com.gojek.app" -t "GoPay"
```

### 5. Status & Sinkronisasi Manual Google Sheets
```bash
# Periksa koneksi dan tab conformed
python -m finance_hub.cli sync-sheets --status

# Sinkronkan seluruh transaksi pending
python -m finance_hub.cli sync-sheets --all
```

---

## 🧪 Pengujian (Testing Suite)

Proyek ini memiliki cakupan pengujian komprehensif (110 unit & integration tests) yang mencakup parsing notifikasi, idempotensi database, klasifikasi 50/30/20, integrasi Google Sheets, dan endpoint API:

```bash
pytest
```

Hasil pengujian:
```text
======================= 110 passed, 2 warnings in 16.19s =======================
```

---

## 📊 Klasifikasi Anggaran 50/30/20

Aturan klasifikasi transaksi dipetakan secara otomatis:

| Kategori 50/30/20 | Deskripsi | Contoh Kategori Pengeluaran |
| :--- | :--- | :--- |
| **Needs (50%)** | Kebutuhan esensial & kewajiban primer | Groceries, Tagihan Listrik/Air, Pulsa/Internet, Transport, Kesehatan, Biaya Sewa |
| **Wants (30%)** | Hiburan, gaya hidup & keinginan pribadi | Dining/Kopi, Belanja Online, Langganan Streaming, Hobi, Bioskop |
| **Savings (20%)** | Tabungan, investasi & pelunasan utang | Reksadana, Saham, Deposito, Dana Darurat |
| **Income** | Pemasukan kas aktif & pasif | Gaji/Payroll, Transfer Masuk, Cashback, Bunga Bank |

---

## 📄 Lisensi

Didistribusikan di bawah lisensi **MIT**. Lihat berkas [`LICENSE`](LICENSE) untuk informasi lebih lanjut.
