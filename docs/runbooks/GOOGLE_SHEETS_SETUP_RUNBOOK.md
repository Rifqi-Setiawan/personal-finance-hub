# Panduan Setup Google Service Account & Google Sheets Sync
**Project:** Personal Finance Hub  
**Target:** Integrasi Google Sheets API via Service Account (`gspread`)  
**Maintainer:** Muhammad Rifqi Setiawan  
**Ditujukan untuk:** Pengguna & Administrator Personal Finance Hub  
**Status:** Panduan Resmi / Operasional  

---

## 1. Pendahuluan

Personal Finance Hub menggunakan **Google Service Account** gratis (tanpa perlu kartu kredit) untuk mengotomasi sinkronisasi transaksi m-banking dan e-wallet ke Google Sheets. 

Dengan setup ini:
1. Setiap transaksi yang masuk via webhook di smartphone otomatis tersimpan di DuckDB server (<50ms).
2. Transaksi kemudian disinkronkan ke tab **`Transactions_Raw`** (Bronze) dan **`Ledger_Clean`** (Silver) di Google Sheets Anda secara background.
3. Jika internet server offline atau kuota Google Sheets sementara habis, transaksi tetap aman tersimpan di DuckDB dan bisa disinkronkan kembali via backfill CLI.

Ikuti 5 langkah mudah berikut untuk menyiapkannya dalam waktu ±5 menit.

---

## 2. Ringkasan Kebutuhan

| Parameter | Keterangan | Lokasi / Nilai |
| :--- | :--- | :--- |
| **Service Account Key** | Berkas JSON rahasia kredensial bot | `credentials/google_service_account.json` |
| **Spreadsheet ID** | Kode unik dari tautan Google Sheets | Ditentukan di environment variable `GOOGLE_SPREADSHEET_ID` |
| **Izin Spreadsheet** | Akses Edit (*Editor*) | Dibagikan ke email Service Account (berakhiran `@...iam.gserviceaccount.com`) |

---

## 3. Langkah Demi Langkah Setup

### Langkah 1: Buat Project di Google Cloud Console (100% Gratis)

1. Buka browser dan login ke akun Google Anda di [Google Cloud Console](https://console.cloud.google.com/).
2. Di pojok kiri atas (sebelah logo *Google Cloud*), klik pemilih project lalu pilih **"New Project"** (Project Baru).
3. Isi nama project, misalnya: `personal-finance-hub`.
4. Organisasi / Lokasi biarkan default (`No organization`), lalu klik **"Create"**.
5. Pastikan project yang baru dibuat telah terpilih di bar atas konsol.

---

### Langkah 2: Aktifkan Google Sheets API & Google Drive API

Bot Python (`gspread`) membutuhkan izin API Google Sheets dan Google Drive:

1. Di menu navigasi samping kiri (garis tiga / hamburger icon), buka **APIs & Services** > **Enabled APIs & Services**.
2. Klik tombol **"+ ENABLE APIS AND SERVICES"** di bagian atas.
3. Cari **"Google Sheets API"** di kotak pencarian, klik hasilnya, lalu klik **"Enable"**.
4. Kembali ke pencarian API, cari **"Google Drive API"**, klik hasilnya, lalu klik **"Enable"**.

> *Tips:* Keduanya gratis dan memiliki kuota harian yang sangat besar (ratusan request per menit), jauh melebihi kebutuhan harian pencatatan keuangan pribadi.

---

### Langkah 3: Buat Service Account & Download Kunci JSON

1. Di menu navigasi samping kiri, buka **IAM & Admin** > **Service Accounts**.
2. Klik **"+ CREATE SERVICE ACCOUNT"** di bagian atas layar.
3. Isi formulir Service Account:
   - **Service account name**: `finance-hub-bot`
   - **Service account ID**: otomatis terisi (misal: `finance-hub-bot@personal-finance-hub-xxxx.iam.gserviceaccount.com`)
   - **Service account description**: `Bot sinkronisasi Personal Finance Hub`
4. Klik **"Create and Continue"**.
5. Pada langkah *Grant this service account access to project (Optional)*, Anda bisa melewatinya (klik **"Continue"** lalu **"Done"**).
6. Di tabel daftar Service Accounts, cari akun yang baru saja dibuat, lalu **salin (copy) email Service Account tersebut** (contoh: `finance-hub-bot@personal-finance-hub-xxxx.iam.gserviceaccount.com`). *Kita akan menggunakannya di Langkah 4.*
7. Klik ikon titik tiga (Actions) di baris akun tersebut, atau klik nama akunnya, lalu masuk ke tab **"Keys"**.
8. Klik **"Add Key"** > **"Create new key"**.
9. Pilih opsi format **"JSON"**, lalu klik **"Create"**.
10. Berkas file JSON kredensial akan otomatis terdownload ke komputer Anda.

---

### Langkah 4: Bagikan (Share) Google Sheet ke Email Service Account

1. Buka Google Drive Anda, lalu buka Google Spreadsheet target keuangan Anda.
   *(Anda bisa membuat spreadsheet baru dari template `Personal_Finance_Hub_Template.xlsx` yang ada di folder `templates/` proyek).*
2. Pastikan Google Spreadsheet memiliki 5 tab conformed berikut:
   - `Dashboard`
   - `Transactions_Raw`
   - `Ledger_Clean`
   - `Categories`
   - `Monthly_Summary`
3. Klik tombol **"Share"** (Bagikan) berwarna hijau di pojok kanan atas spreadsheet.
4. Tempel (Paste) email Service Account yang Anda salin di Langkah 3:
   `finance-hub-bot@personal-finance-hub-xxxx.iam.gserviceaccount.com`
5. Pastikan role yang dipilih adalah **"Editor"** dan centang notifikasi jika diperlukan.
6. Klik **"Send"** / **"Share"**.
7. Sekarang bot memiliki izin membaca dan menulis baris transaksi ke spreadsheet Anda!

---

### Langkah 5: Salin Kunci ke Server & Konfigurasi Lingkungan

#### A. Salin File Kunci JSON ke Server
Pindahkan file JSON yang didownload tadi ke server/komputer Anda di direktori:
```bash
mkdir -p credentials
mv /path/to/downloaded-key.json credentials/google_service_account.json
chmod 600 credentials/google_service_account.json
```
*(File permission `chmod 600` memastikan hanya user pemilik proses yang dapat membaca berkas kunci rahasia ini).*

#### B. Dapatkan Spreadsheet ID
Ambil ID spreadsheet dari URL di address bar browser Anda saat membuka Google Sheet:
```text
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                   Ini adalah Spreadsheet ID
```

#### C. Atur Environment Variable
Tambahkan variabel berikut ke environment server Anda (atau file `.env`):
```bash
export GOOGLE_SERVICE_ACCOUNT_FILE="credentials/google_service_account.json"
export GOOGLE_SPREADSHEET_ID="your_spreadsheet_id_here"
```

---

## 4. Verifikasi dan Pengujian

### 1. Cek Status Koneksi via CLI
Jalankan perintah berikut menggunakan venv proyek:
```bash
python -m finance_hub.cli sync-sheets --status
```
Output sukses yang diharapkan:
```text
================================================================
 PERSONAL FINANCE HUB — GOOGLE SHEETS CONNECTION STATUS
================================================================
 Configured         : YES ✅
 Spreadsheet ID     : your_spreadsheet_id_here
 Credentials File   : credentials/google_service_account.json
 Credentials Exist  : YES ✅
 Pending Sync Count : 0 transactions
----------------------------------------------------------------
 Verifying spreadsheet structure...
 Structure Check    : ✅ All 5 tabs found (Dashboard, Transactions_Raw, Ledger_Clean, Categories, Monthly_Summary)
================================================================
```

### 2. Jalankan Manual Backfill Sync
Jika sebelumnya ada transaksi yang tersimpan saat offline:
```bash
python -m finance_hub.cli sync-sheets --all
```
Semua transaksi pending di DuckDB akan di-batch insert sekaligus ke Google Sheets dan statusnya otomatis ditandai `synced`.

### 3. Cek Status via API HTTP
Anda juga bisa memantau status secara langsung melalui endpoint:
```bash
curl -s http://127.0.0.1:8000/api/sheets-status?verify=true | jq .
```

---

## 5. Pemecahan Masalah (Troubleshooting)

### Kasus 1: Error `Permission denied (403)` / `The caller does not have permission`
- **Penyebab:** Google Spreadsheet belum di-share ke email Service Account, atau email yang di-share salah.
- **Solusi:** Buka spreadsheet di browser > Klik **Share** > Pastikan email Service Account (`...iam.gserviceaccount.com`) terdaftar sebagai **Editor**.

### Kasus 2: Error `SpreadsheetNotFound (404)`
- **Penyebab:** Nilai `GOOGLE_SPREADSHEET_ID` salah atau spreadsheet telah dihapus.
- **Solusi:** Periksa kembali karakter string di antara `/d/` dan `/edit` pada tautan Google Sheets Anda.

### Kasus 3: Error `WorksheetNotFound`
- **Penyebab:** Tab `Transactions_Raw` atau `Ledger_Clean` tidak ditemukan di spreadsheet.
- **Solusi:** Pastikan nama tab persis sama (case-sensitive):
  - `Transactions_Raw`
  - `Ledger_Clean`

### Kasus 4: Server Offline atau Jaringan Drop
- **Perilaku Sistem:** Sistem dirancang **resilient**. Webhook tetap merespons status sukses 200 ke smartphone (<50ms) dan data aman tercatat di DuckDB lokal. Transaksi yang belum terunggah diberi tanda `sheets_synced = FALSE`. Setelah jaringan kembali normal, jalankan `sync-sheets --all` atau panggil `POST /api/sync-sheets`.

---

## 6. Keamanan & Best Practices

1. **JANGAN PERNAH** melakukan commit file JSON kredensial ke Git repository. Pastikan `credentials/` dan `*.json` tercantum di `.gitignore`.
2. Gunakan permission file ketat: `chmod 600 credentials/google_service_account.json`.
3. Service account hanya memiliki akses ke spreadsheet yang dibagikan secara eksplisit; tidak memiliki akses ke berkas Google Drive pribadi lainnya.
