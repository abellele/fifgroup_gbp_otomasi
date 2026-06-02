"""
fetch_status.py
---------------
Mengambil status verifikasi semua lokasi dari Google Business Profile API
dan menyimpan hasilnya ke CSV untuk keperluan lookup ke database kios.

Cara pakai:
    python fetch_status.py
    python fetch_status.py --output hasil_verifikasi.csv
    python fetch_status.py --account-id accounts/123456789
"""

import os
import json
import csv
import argparse
import logging
from datetime import datetime
from pathlib import Path

import requests
import certifi
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

# ──────────────────────────────────────────────
# KONFIGURASI
# ──────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/business.manage",
]

TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"

API_ACCOUNT   = "https://mybusinessaccountmanagement.googleapis.com/v1"
API_LOCATIONS = "https://mybusinessbusinessinformation.googleapis.com/v1"

# [PERUBAHAN 1] Tambah "latlng" ke daftar field yang diminta
LOCATION_FIELDS = (
    "name,title,storefrontAddress,metadata,"
    "storeCode,websiteUri,latlng"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def sanitize_ssl_env() -> None:
    """Bersihkan env SSL yang mengarah ke path CA bundle tidak valid."""
    for env_name in ("REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "SSL_CERT_FILE"):
        env_value = os.environ.get(env_name)
        if env_value and not Path(env_value).exists():
            log.warning("Env %s invalid (%s), diabaikan.", env_name, env_value)
            os.environ.pop(env_name, None)


def build_http_session() -> requests.Session:
    """Session HTTP terstandar agar selalu pakai CA cert valid."""
    sanitize_ssl_env()
    session = requests.Session()
    session.verify = certifi.where()
    session.trust_env = False
    return session


HTTP = build_http_session()


# ──────────────────────────────────────────────
# AUTENTIKASI
# ──────────────────────────────────────────────

def get_credentials() -> Credentials:
    """
    Mengelola token OAuth2.
    - Jika token.json sudah ada dan masih valid → langsung pakai.
    - Jika expired → refresh otomatis.
    - Jika belum ada → buka browser untuk login (hanya sekali).
    """
    def run_oauth_login() -> Credentials:
        log.info("Login Google pertama kali — browser akan terbuka...")
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, SCOPES
        )
        return flow.run_local_server(port=0)

    def build_google_request() -> Request:
        """Buat transport request dengan CA bundle valid (certifi)."""
        session = build_http_session()
        return Request(session=session)

    creds = None

    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Token expired, me-refresh otomatis...")
            try:
                creds.refresh(build_google_request())
            except RefreshError:
                log.warning("Refresh token tidak valid/revoked. Login ulang diperlukan.")
                try:
                    Path(TOKEN_FILE).unlink(missing_ok=True)
                except TypeError:
                    if Path(TOKEN_FILE).exists():
                        Path(TOKEN_FILE).unlink()
                creds = run_oauth_login()
        else:
            creds = run_oauth_login()

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        log.info(f"Token disimpan ke {TOKEN_FILE}")

    return creds


def make_headers(creds: Credentials) -> dict:
    """Buat header Authorization dari credentials."""
    if not creds:
        raise RuntimeError("Credentials kosong. Jalankan autentikasi ulang.")

    if not creds.valid and creds.refresh_token:
        session = build_http_session()
        try:
            creds.refresh(Request(session=session))
        except RefreshError as e:
            raise RuntimeError("Token tidak valid. Hapus token.json lalu login ulang.") from e

    return {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }


# ──────────────────────────────────────────────
# FUNGSI API
# ──────────────────────────────────────────────

def get_accounts(headers: dict) -> list[dict]:
    """Ambil semua akun GBP yang bisa diakses."""
    url = f"{API_ACCOUNT}/accounts"
    resp = HTTP.get(url, headers=headers)
    resp.raise_for_status()
    accounts = resp.json().get("accounts", [])
    log.info(f"Ditemukan {len(accounts)} akun GBP.")
    return accounts


def get_locations(account_name: str, headers: dict) -> list[dict]:
    """
    Ambil semua lokasi dari sebuah akun dengan pagination otomatis.
    account_name contoh: 'accounts/123456789'
    """
    url = f"{API_LOCATIONS}/{account_name}/locations"
    params = {
        "readMask": LOCATION_FIELDS,
        "pageSize": 100,
    }

    all_locations = []
    page_token = None
    page_num = 0

    while True:
        page_num += 1
        if page_token:
            params["pageToken"] = page_token

        resp = HTTP.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

        locations = data.get("locations", [])
        all_locations.extend(locations)
        log.info(f"  Halaman {page_num}: {len(locations)} lokasi (total: {len(all_locations)})")

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return all_locations


# ──────────────────────────────────────────────
# PARSING STATUS
# ──────────────────────────────────────────────

def parse_verification_status(location: dict) -> dict:
    """
    Ekstrak status verifikasi dan koordinat dari objek lokasi.

    Status yang mungkin muncul di metadata:
      - hasVoiceOfMerchant : True  → Verified
      - duplicateLocation  : ada   → Duplicate
      - hasPendingEdits    : True  → ada edit pending
      Jika tidak ada metadata VoM → Verification Required

    Koordinat diambil dari field latlng:
      - latitude  : angka desimal (contoh: -6.2088)
      - longitude : angka desimal (contoh: 106.8456)
      Jika lokasi tidak memiliki koordinat → kedua field dikosongkan ("")
    """
    metadata = location.get("metadata", {})
    address  = location.get("storefrontAddress", {})

    # Susun status
    has_vom        = metadata.get("hasVoiceOfMerchant", False)
    is_duplicate   = "duplicateLocation" in metadata
    has_pending    = metadata.get("hasPendingEdits", False)
    maps_uri       = metadata.get("mapsUri", "")
    new_review_uri = metadata.get("newReviewUri", "")

    if is_duplicate:
        status = "Duplicate"
    elif has_vom:
        status = "Verified"
    else:
        status = "Verification Required"

    # Susun alamat
    addr_lines   = address.get("addressLines", [])
    full_address = ", ".join([
        " ".join(addr_lines),
        address.get("locality", ""),
        address.get("administrativeArea", ""),
        address.get("postalCode", ""),
        address.get("regionCode", ""),
    ]).strip(", ")

    # [PERUBAHAN 2] Ekstrak koordinat dari field latlng
    latlng    = location.get("latlng", {})
    latitude  = latlng.get("latitude", "")
    longitude = latlng.get("longitude", "")

    return {
        "location_name"    : location.get("name", ""),
        "store_code"       : location.get("storeCode", ""),
        "business_name"    : location.get("title", ""),
        "address"          : full_address,
        "latitude"         : latitude,     
        "longitude"        : longitude,   
        "status"           : status,
        "has_vom"          : has_vom,
        "is_duplicate"     : is_duplicate,
        "has_pending_edits": has_pending,
        "maps_uri"         : maps_uri,
        "new_review_uri"   : new_review_uri,
        "fetched_at"       : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ──────────────────────────────────────────────
# SIMPAN HASIL
# ──────────────────────────────────────────────

def save_to_csv(records: list[dict], output_path: str):
    """Simpan hasil ke file CSV."""
    if not records:
        log.warning("Tidak ada data untuk disimpan.")
        return

    fieldnames = list(records[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    log.info(f"✅ Hasil disimpan ke: {output_path} ({len(records)} baris)")


def print_summary(records: list[dict]):
    """Tampilkan ringkasan status ke terminal."""
    from collections import Counter
    counts = Counter(r["status"] for r in records)

    # Hitung berapa lokasi yang punya koordinat
    has_coords = sum(1 for r in records if r["latitude"] != "" and r["longitude"] != "")

    print("\n" + "=" * 50)
    print("RINGKASAN STATUS VERIFIKASI GBP")
    print("=" * 50)
    print(f"  Total lokasi        : {len(records)}")
    print(f"  ✅ Verified          : {counts.get('Verified', 0)}")
    print(f"  ⚠️  Verif. Required   : {counts.get('Verification Required', 0)}")
    print(f"  🔁 Duplicate         : {counts.get('Duplicate', 0)}")
    print(f"  📍 Punya koordinat   : {has_coords} / {len(records)}")
    if has_coords < len(records):
        print(f"  ⚠️  Tanpa koordinat  : {len(records) - has_coords} titik")
    print("=" * 50 + "\n")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch GBP verification status + koordinat")
    parser.add_argument(
        "--output", default=None,
        help="Nama file CSV output (default: gbp_status_YYYYMMDD.csv)"
    )
    parser.add_argument(
        "--account-id", default=None,
        help="Account ID spesifik (contoh: accounts/123456789). "
             "Jika tidak diisi, semua akun akan diproses."
    )
    args = parser.parse_args()

    output_file = args.output or f"gbp_status_{datetime.now().strftime('%Y%m%d')}.csv"

    # 1. Auth
    log.info("Memulai autentikasi Google...")
    creds   = get_credentials()
    headers = make_headers(creds)

    # 2. Ambil daftar akun
    if args.account_id:
        accounts = [{"name": args.account_id}]
    else:
        accounts = get_accounts(headers)

    # 3. Ambil lokasi dari setiap akun
    all_records = []
    for account in accounts:
        acct_name = account["name"]
        log.info(f"Mengambil lokasi dari akun: {acct_name}")
        try:
            locations = get_locations(acct_name, headers)
            for loc in locations:
                record = parse_verification_status(loc)
                all_records.append(record)
        except requests.HTTPError as e:
            log.error(f"Gagal mengambil lokasi dari {acct_name}: {e}")

    # 4. Simpan & tampilkan
    save_to_csv(all_records, output_file)
    print_summary(all_records)


if __name__ == "__main__":
    main()
