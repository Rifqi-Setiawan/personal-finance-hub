# Panduan Setup Otomasi Notifikasi HP (Samsung Galaxy A54 / Android) via MacroDroid

**Proyek:** Personal Finance Hub  
**Target:** Ingesti Otomatis Notifikasi Transaksi m-Banking & e-Wallet ke VPS Webhook  
**Perangkat:** Samsung Galaxy A54 5G (One UI / Android 13/14)  
**Aplikasi Pendukung:** MacroDroid (Gratis di Google Play Store)  
**Webhook URL Publik:** `https://your-domain-or-tunnel-url/webhook/transaction`  

---

## 1. Instalasi Aplikasi
1. Buka **Google Play Store** di Samsung A54 Anda.
2. Cari dan instal aplikasi **MacroDroid - Device Automation** (oleh ArloSoft).
3. Buka aplikasi MacroDroid dan selesaikan panduan awal.
4. Berikan izin:
   - **Notification Access (Akses Notifikasi)**: Wajib diizinkan agar MacroDroid bisa membaca teks notifikasi transaksi bank.
   - **Battery Optimization (Optimasi Baterai)**: Pilih *Don't optimize* / *Tidak dibatasi* agar MacroDroid tidak dimatikan paksa oleh One UI Samsung saat layar mati.

---

## 2. Membuat Makro Baru di MacroDroid (Hanya 2 Menit)

Di menu utama MacroDroid, klik tombol **"Add Macro"** (Tambah Makro), lalu atur 3 bagian berikut:

### 🟢 A. Bagian TRIGGER (Pemicu)
1. Klik tombol **`+`** warna merah pada kotak *Triggers*.
2. Pilih kategori **Device Events** ➔ pilih **Notification** ➔ pilih **Notification Received**.
3. Pilih opsi **Select Application(s)** ➔ klik **OK**.
4. Centang aplikasi keuangan yang ingin Anda pantau, misalnya:
   - **BCA mobile / myBCA**
   - **Livin' by Mandiri**
   - **GoPay / Gojek**
   - **DANA**
   - **OVO**
   - **ShopeePay / Shopee**
   - **Bank Jago / SeaBank / BRImo / BNI Mobile**
5. Klik **OK**.
6. Pada opsi *Text Content*, pilih **Any content** ➔ klik **OK**.

---

### 🔵 B. Bagian ACTION (Tindakan Kirim ke VPS)
1. Klik tombol **`+`** warna biru pada kotak *Actions*.
2. Pilih kategori **Connectivity** ➔ pilih **HTTP Request**.
3. Atur parameter HTTP Request:
   - **Request Method**: Pilih `POST`.
   - **URL**: Masukkan alamat webhook server Anda:
     ```text
     https://your-domain-or-tunnel-url/webhook/transaction
     ```
   - **Content-Type**: Pilih `application/json`.
   - **Request Body (Content Body)**:
     Ketik template JSON persis seperti berikut:
     ```json
     {
       "package_name": "[package_name]",
       "title": "[not_title]",
       "text": "[not_body]",
       "timestamp": "[year]-[month_digit]-[day_digit]T[hour]:[minute]:[second]",
       "source_device": "Samsung A54"
     }
     ```
     *(Catatan: Teks di dalam tanda kurung siku seperti `[package_name]`, `[not_title]`, dan `[not_body]` adalah variabel bawaan MacroDroid yang otomatis mengambil data notifikasi aktual).*
4. Klik **OK** / Centang simpan.

---

### ⚪ C. Simpan & Aktifkan Makro
1. Beri nama makro di bagian atas, misalnya: `Finance Hub Ingestion`.
2. Klik tombol centang / simpan di pojok kanan bawah.
3. Pastikan switch MacroDroid di halaman utama berstatus **ON** (Aktif).

---

## 3. Cara Pengujian (Live Testing)
1. Buka salah satu aplikasi (misal GoPay atau m-BCA).
2. Lakukan transaksi nyata (misal beli Kopi QRIS Rp 15.000 atau transfer Rp 10.000).
3. Saat notifikasi sukses muncul di layar Samsung A54 Anda:
   - MacroDroid akan menangkap teks tersebut dalam 0.1 detik.
   - Mengirimkannya ke webhook VPS.
   - DuckDB mencatat transaksi dan melakukan deduplikasi SHA-256.
   - Google Sheets Anda di tab `Ledger_Clean` langsung terisi baris baru otomatis!
