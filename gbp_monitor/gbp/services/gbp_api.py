"""
gbp_api.py — Service untuk autentikasi dan pengambilan data dari Google Business Profile API.
Dimigrasikan dari fetch_status.py.

Penggunaan:
    from gbp.services.gbp_api import fetch_records
    records = fetch_records(account_id=None)
"""

import logging
import os

import certifi
import requests as req_lib
from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

log = logging.getLogger("gbp.services.gbp_api")

# ── Konfigurasi ──────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/business.manage"]

API_ACCOUNT = "https://mybusinessaccountmanagement.googleapis.com/v1"
API_LOCATIONS = "https://mybusinessbusinessinformation.googleapis.com/v1"

LOCATION_FIELDS = (
    "name,title,storefrontAddress,metadata,"
    "storeCode,websiteUri,latlng"
)


# ── Autentikasi ───────────────────────────────────────────────────────

def get_credentials() -> Credentials:
    """
    OAuth2 dengan certificate eksplisit dari certifi.
    Path credentials dan token dibaca dari Django settings
    (GBP_CREDENTIALS_PATH dan GBP_TOKEN_PATH).
    """
    # Override certificate agar tidak terganggu environment variable lain
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
    os.environ["SSL_CERT_FILE"] = certifi.where()

    credentials_file = getattr(settings, "GBP_CREDENTIALS_PATH", "credentials.json")
    token_file = getattr(settings, "GBP_TOKEN_PATH", "token.json")

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Token expired, me-refresh otomatis...")
            session = req_lib.Session()
            session.verify = certifi.where()
            creds.refresh(Request(session=session))
        else:
            log.info("Login Google pertama kali — browser akan terbuka...")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, "w") as f:
            f.write(creds.to_json())
        log.info(f"Token disimpan ke {token_file}")

    return creds


def make_headers(creds: Credentials) -> dict:
    """Buat HTTP headers dengan Authorization Bearer token."""
    session = req_lib.Session()
    session.verify = certifi.where()
    creds.refresh(Request(session=session))
    return {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }


# ── Fungsi API ────────────────────────────────────────────────────────

def get_accounts(headers: dict) -> list[dict]:
    """Ambil semua akun GBP yang dapat diakses."""
    url = f"{API_ACCOUNT}/accounts"
    resp = req_lib.get(url, headers=headers, verify=certifi.where())
    resp.raise_for_status()
    accounts = resp.json().get("accounts", [])
    log.info(f"Ditemukan {len(accounts)} akun GBP.")
    return accounts


def get_locations(account_name: str, headers: dict) -> list[dict]:
    """
    Ambil semua lokasi dari satu akun GBP dengan paginasi otomatis.

    Args:
        account_name: Nama akun GBP (format: "accounts/123456789")
        headers: HTTP headers dengan Authorization Bearer token
    """
    url = f"{API_LOCATIONS}/{account_name}/locations"
    params = {"readMask": LOCATION_FIELDS, "pageSize": 100}

    all_locations: list[dict] = []
    page_token = None
    page_num = 0

    while True:
        page_num += 1
        if page_token:
            params["pageToken"] = page_token

        resp = req_lib.get(url, headers=headers, params=params, verify=certifi.where())
        resp.raise_for_status()
        data = resp.json()

        locations = data.get("locations", [])
        all_locations.extend(locations)
        log.info(f"  Halaman {page_num}: {len(locations)} lokasi (total: {len(all_locations)})")

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return all_locations


# ── Fetch Utama ───────────────────────────────────────────────────────

def fetch_records(account_id: str | None = None) -> list[dict]:
    """
    Ambil dan parse semua lokasi GBP dari API.

    Args:
        account_id: Account ID spesifik (format: "accounts/123456789").
                    Jika None, ambil dari semua akun yang tersedia.

    Returns:
        List of dict berisi data lokasi yang sudah diparsing.
    """
    from gbp.services.status_parser import parse_location  # avoid circular import

    log.info("Memulai autentikasi Google...")
    creds = get_credentials()
    headers = make_headers(creds)

    if account_id:
        accounts = [{"name": account_id}]
    else:
        accounts = get_accounts(headers)

    all_records: list[dict] = []
    for account in accounts:
        acct_name = account["name"]
        log.info(f"Mengambil lokasi dari akun: {acct_name}")
        try:
            locations = get_locations(acct_name, headers)
            for loc in locations:
                record = parse_location(loc)
                record["account_name"] = acct_name
                all_records.append(record)
        except req_lib.HTTPError as e:
            log.error(f"Gagal mengambil lokasi dari {acct_name}: {e}")

    log.info(f"Total {len(all_records)} lokasi berhasil diambil.")
    return all_records
