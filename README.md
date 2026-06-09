# GBP Verification Status — Setup & Panduan Lengkap

Toolset ini mengambil status verifikasi dari **Google Business Profile API** 
secara otomatis dan melakukan lookup ke database kios yang sudah ada.

---

## Struktur File

```
gbp_verification/
│
├── fetch_status.py      → Ambil data dari GBP API → simpan ke CSV
├── update_database.py   → Lookup CSV hasil ke database kios
├── scheduler.py         → Jalankan keduanya otomatis setiap hari
├── requirements.txt     → Library yang dibutuhkan
│
├── credentials.json     ← Kamu download dari Google Cloud Console (langkah 3)
├── token.json           ← Dibuat otomatis saat login pertama kali
│
├── gbp_status_YYYYMMDD.csv   ← Hasil harian fetch
├── logs/                     ← Log otomatis per hari
└── report_*.txt              ← Laporan singkat per run
```

---

## LANGKAH 1 — Buat Google Cloud Project

1. Buka https://console.cloud.google.com
2. Klik **"New Project"** → beri nama (contoh: `gbp-fifgroup`)
3. Pastikan project baru ini sudah dipilih (pojok kiri atas)

---

## LANGKAH 2 — Aktifkan Business Profile APIs

Di Google Cloud Console, buka **APIs & Services → Library**, 
cari dan aktifkan **ketiga API** berikut:

| API | Nama di Library |
|-----|----------------|
| Account Management | `Business Profile Account Management API` |
| Business Information | `My Business Business Information API` |
| Verifications | `My Business Verifications API` |

Klik **"Enable"** untuk masing-masing.

> ⚠️ **PENTING:** Business Profile API adalah **restricted API**.
> Google memerlukan approval sebelum bisa digunakan untuk akun production.
> Ajukan akses di: https://developers.google.com/my-business/content/prereqs
> Proses approval biasanya **3–7 hari kerja**.

---

## LANGKAH 3 — Buat OAuth 2.0 Credentials

Sebelum membuat client ID, Google biasanya akan meminta kamu menyiapkan **OAuth consent screen** dulu.

1. Di Google Cloud Console → **APIs & Services → OAuth consent screen**
2. Pilih tipe **External** jika ini untuk akun pribadi / testing
3. Isi **App name**, **User support email**, dan **Developer contact information**
4. Jika diminta, tambahkan akun Google kamu ke daftar **Test users**
5. Simpan perubahan

Setelah consent screen selesai, lanjut ke pembuatan credential:

1. Di Google Cloud Console → **APIs & Services → Credentials**
2. Klik **"Create Credentials" → "OAuth 2.0 Client ID"**
3. Pilih **Application type: Desktop app**
4. Beri nama (contoh: `gbp-script`)
5. Klik **Download JSON**
6. Rename file yang didownload menjadi **`credentials.json`**
7. Letakkan di folder yang sama dengan script ini

---

## LANGKAH 4 — Install Python Dependencies

```bash
# Pastikan Python 3.9+ sudah terinstall
# Untuk Python 3.13, pakai pin dependency yang sudah disesuaikan di requirements ini
python --version

# Install semua library
pip install -r requirements.txt
```

---

## LANGKAH 5 — Login Pertama Kali (OAuth)

```bash
python fetch_status.py
```

Saat pertama kali dijalankan:
- Browser akan terbuka otomatis
- Login dengan akun Google yang jadi **admin di Business Profile Manager**
- Izinkan akses → browser akan redirect ke localhost
- Token disimpan otomatis ke `token.json` (tidak perlu login lagi ke depannya)

---

## LANGKAH 6 — Jalankan Fetch Status

```bash
# Fetch semua lokasi dari semua akun
python fetch_status.py

# Atau dengan output file custom
python fetch_status.py --output hasil_verifikasi.csv

# Atau spesifik satu akun
python fetch_status.py --account-id accounts/123456789
```

Hasilnya: file CSV dengan kolom:

| Kolom | Keterangan |
|-------|-----------|
| `location_name` | ID internal GBP |
| `store_code` | Kode kios (untuk lookup ke DB) |
| `business_name` | Nama bisnis di GBP |
| `address` | Alamat lengkap |
| `status` | `Verified` / `Verification Required` / `Duplicate` |
| `has_vom` | True jika sudah punya Voice of Merchant |
| `is_duplicate` | True jika terdeteksi duplikat |
| `has_pending_edits` | True jika ada edit yang belum disimpan |
| `maps_uri` | Link ke Google Maps |
| `fetched_at` | Waktu pengambilan data |

---

## LANGKAH 7 — Update Database Kios

### Jika database kamu berupa CSV:

```bash
python update_database.py \
    --gbp-file gbp_status_20260511.csv \
    --db-file database_kios.csv \
    --mode csv \
    --db-key-col kode_kios
```

### Jika database kamu berupa SQLite:

```bash
python update_database.py \
    --gbp-file gbp_status_20260511.csv \
    --db-file kios.db \
    --mode sqlite \
    --table kios \
    --db-key-col kode_kios
```

Script akan otomatis:
- Membuat backup database sebelum update
- Menambah kolom `gbp_status` dan `gbp_fetched_at` jika belum ada
- Melakukan lookup berdasarkan `store_code` ↔ `kode_kios`
- Menyimpan laporan ringkas ke file `report_*.txt`

> **Syarat:** Nilai `store_code` di GBP **harus sama** dengan 
> nilai `kode_kios` di database kios (contoh: `x90104`).
> Pastikan shop code di GBP sudah diisi dengan benar.

---

## LANGKAH 8 — Otomasi Harian

### Opsi A: Pakai scheduler.py (paling mudah)

Edit bagian `CONFIG` di `scheduler.py` sesuai setup kamu:

```python
CONFIG = {
    "db_file"    : "database_kios.csv",   # path ke database
    "db_mode"    : "csv",                 # "csv" atau "sqlite"
    "db_key_col" : "kode_kios",           # kolom kunci di database
    "account_id" : "",                    # kosongkan = semua akun
}
```

Lalu jalankan:

```bash
# Jalankan loop — otomatis fetch + update setiap hari jam 08:00
python scheduler.py --schedule 08:00
```

### Opsi B: Windows Task Scheduler

1. Buka **Task Scheduler** → "Create Basic Task"
2. Trigger: Daily, jam yang kamu mau
3. Action: Start a program
   - Program: `python`
   - Arguments: `C:\path\ke\scheduler.py --run-now`
   - Start in: `C:\path\ke\folder\gbp_verification`

### Opsi C: Linux/Mac Cron

```bash
# Edit crontab
crontab -e

# Tambahkan baris ini (jalankan setiap hari jam 08:00)
0 8 * * * cd /path/ke/gbp_verification && python scheduler.py --run-now >> logs/cron.log 2>&1
```

---

## Troubleshooting

| Error | Solusi |
|-------|--------|
| `credentials.json not found` | Download credentials dari Google Cloud Console (Langkah 3) |
| `403 ACCESS_DENIED` | API belum dapat approval dari Google, atau akun bukan admin GBP |
| `store_code tidak cocok` | Cek shop code di GBP Manager — harus identik dengan kode di database |
| `Token expired` | Hapus `token.json`, jalankan ulang, login kembali |
| `ModuleNotFoundError` | Jalankan `pip install -r requirements.txt` |

---

## Catatan Quota & Biaya

- ✅ **Gratis** — Business Profile API tidak dikenakan biaya per request
- Quota default: **100 request/detik**, **cukup untuk 2000+ lokasi**
- Jika kena quota limit, script otomatis akan error — ajukan peningkatan quota 
  di Google Cloud Console → APIs & Services → Quotas
