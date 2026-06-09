"""
dashboard.py
------------
Dashboard monitoring status verifikasi Google Business Profile.
Membaca data dari gbp_history.db yang diisi oleh fetch_status.py.

Cara menjalankan:
    streamlit run dashboard.py

Fitur:
  - Summary cards (Total / Verified / Duplicate / Suspended)
  - Tren status 30 hari
  - Tabel dengan search, filter, sort, pagination
  - Export CSV & Excel
  - Detail lokasi (klik dari tabel)
  - Peta interaktif dengan marker berwarna per status
"""

import io
from datetime import datetime

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import history_db as db

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="GBP Monitor",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# KONSTANTA
# ──────────────────────────────────────────────

STATUS_META = {
    "Verified":              {"icon": "🟢", "color": "#22c55e", "map_color": "green"},
    "Duplicate":             {"icon": "🟡", "color": "#eab308", "map_color": "orange"},
    "Suspended":             {"icon": "🔴", "color": "#ef4444", "map_color": "red"},
    "Verification Required": {"icon": "⚪", "color": "#94a3b8", "map_color": "gray"},
}

PAGE_SIZE = 50


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def status_label(status: str) -> str:
    meta = STATUS_META.get(status, {"icon": "❓"})
    return f"{meta['icon']} {status}"


@st.cache_data(ttl=120, show_spinner=False)
def load_snapshots(run_id: int, statuses: tuple, search: str) -> pd.DataFrame:
    """Load + cache snapshot dari DB. Cache invalidasi tiap 2 menit."""
    rows = db.get_snapshots(
        run_id,
        status_filter=list(statuses) if statuses else None,
        search=search or None,
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_trend(days: int = 30) -> pd.DataFrame:
    rows = db.get_status_trend(days)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("run_date")


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="GBP Status")
    return buf.getvalue()


def build_map(df_map: pd.DataFrame) -> folium.Map:
    """Buat folium map dengan marker berwarna sesuai status."""
    center = [df_map["latitude"].mean(), df_map["longitude"].mean()]
    m = folium.Map(location=center, zoom_start=6, tiles="CartoDB positron")

    for _, row in df_map.iterrows():
        color = STATUS_META.get(row["status"], {}).get("map_color", "gray")
        popup = folium.Popup(
            f"""
            <div style="font-family:sans-serif;min-width:220px;font-size:13px">
                <b>{row['business_name']}</b><br>
                <span style="color:#666">{row['store_code']}</span>
                <hr style="margin:5px 0">
                📍 {row['address']}<br>
                🔵 {row['latitude']:.7f}, {row['longitude']:.7f}<br>
                <hr style="margin:5px 0">
                <b>Status:</b> {row['status']}
            </div>
            """,
            max_width=300,
        )
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=7,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            popup=popup,
            tooltip=f"{row['business_name']} — {row['status']}",
        ).add_to(m)

    # Legend
    legend = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:9999;
                background:white;padding:12px 16px;border-radius:8px;
                box-shadow:0 2px 10px rgba(0,0,0,0.15);font-family:sans-serif;font-size:13px">
        <b>Status</b><br>
        <span style="color:#22c55e;font-size:16px">●</span> Verified<br>
        <span style="color:#f59e0b;font-size:16px">●</span> Duplicate<br>
        <span style="color:#ef4444;font-size:16px">●</span> Suspended<br>
        <span style="color:#94a3b8;font-size:16px">●</span> Unverified
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    return m


# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────

db.init_db()
all_runs = db.get_all_runs()

st.sidebar.title("📍 GBP Monitor")
st.sidebar.caption("FIFGROUP — Business Profile Dashboard")
st.sidebar.markdown("---")

if not all_runs:
    st.error("Belum ada data. Jalankan `python fetch_status.py` terlebih dahulu.")
    st.stop()

# Run selector
run_labels = {
    f"#{r['run_id']} · {r['run_date']} ({r['total']:,} lokasi)": r["run_id"]
    for r in all_runs
}
sel_label  = st.sidebar.selectbox("📅 Pilih Run", list(run_labels.keys()))
sel_run_id = run_labels[sel_label]
sel_run    = db.get_run_by_id(sel_run_id)

st.sidebar.markdown("---")

# Filter status
st.sidebar.subheader("Filter Status")
all_statuses   = list(STATUS_META.keys())
sel_statuses   = []
for s in all_statuses:
    if st.sidebar.checkbox(status_label(s), value=True, key=f"cb_{s}"):
        sel_statuses.append(s)

st.sidebar.markdown("---")

# Search
search_text = st.sidebar.text_input(
    "🔍 Cari",
    placeholder="Nama bisnis / kode kios / location ID",
)

st.sidebar.markdown("---")

# Navigasi
page = st.sidebar.radio(
    "Halaman",
    ["📊 Overview", "📋 Data Table", "🗺️ Map View"],
    label_visibility="collapsed",
)


# ──────────────────────────────────────────────
# LOAD DATA
# ──────────────────────────────────────────────

df = load_snapshots(sel_run_id, tuple(sel_statuses), search_text)


# ══════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ══════════════════════════════════════════════

if page == "📊 Overview":
    st.title("📊 Overview")
    st.caption(
        f"Run #{sel_run_id} · {sel_run['run_timestamp']} · "
        f"{sel_run['total']:,} total lokasi"
    )

    # ── Summary Cards ───────────────────────
    c1, c2, c3, c4 = st.columns(4)

    total = sel_run["total"] or 1   # hindari division by zero

    c1.metric(
        "📍 Total Lokasi",
        f"{sel_run['total']:,}",
    )
    c2.metric(
        "🟢 Verified",
        f"{sel_run['verified']:,}",
        f"{sel_run['verified']/total*100:.1f}% dari total",
    )
    c3.metric(
        "🟡 Duplicate",
        f"{sel_run['duplicate']:,}",
        f"{sel_run['duplicate']/total*100:.1f}% dari total",
        delta_color="inverse",
    )
    c4.metric(
        "🔴 Suspended",
        f"{sel_run['suspended']:,}",
        f"{sel_run['suspended']/total*100:.1f}% dari total",
        delta_color="inverse",
    )

    st.markdown("---")

    # ── Tren & Distribusi ───────────────────
    col_trend, col_dist = st.columns([3, 1])

    with col_trend:
        st.subheader("Tren Status — 30 Hari Terakhir")
        df_trend = load_trend(30)
        if not df_trend.empty:
            st.line_chart(
                df_trend[["verified", "duplicate", "suspended", "unverified"]],
                color=["#22c55e", "#eab308", "#ef4444", "#94a3b8"],
            )
        else:
            st.info("Belum cukup data historis untuk tren. Jalankan fetch beberapa hari.")

    with col_dist:
        st.subheader("Distribusi")
        dist = {
            "🟢 Verified":    sel_run["verified"],
            "🟡 Duplicate":   sel_run["duplicate"],
            "🔴 Suspended":   sel_run["suspended"],
            "⚪ Unverified":   sel_run["unverified"],
        }
        df_dist = pd.DataFrame.from_dict(dist, orient="index", columns=["Jumlah"])
        st.bar_chart(df_dist)

    # ── Riwayat Run ─────────────────────────
    st.markdown("---")
    st.subheader("Riwayat Semua Run")
    df_runs = pd.DataFrame(all_runs)[[
        "run_id","run_date","run_timestamp",
        "total","verified","duplicate","suspended","unverified"
    ]]
    df_runs.columns = [
        "Run ID","Tanggal","Timestamp",
        "Total","Verified","Duplicate","Suspended","Unverified"
    ]
    st.dataframe(df_runs, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════
# PAGE 2 — DATA TABLE
# ══════════════════════════════════════════════

elif page == "📋 Data Table":
    st.title("📋 Data Lokasi")
    st.caption(
        f"{len(df):,} lokasi ditampilkan"
        + (f" dari {sel_run['total']:,} total" if search_text or len(sel_statuses) < 4 else "")
    )

    if df.empty:
        st.warning("Tidak ada data yang cocok dengan filter saat ini.")
        st.stop()

    # ── Sort ────────────────────────────────
    sort_col = st.selectbox(
        "Urutkan berdasarkan",
        ["business_name", "store_code", "status", "fetched_at"],
        format_func=lambda x: {
            "business_name": "Nama Bisnis",
            "store_code":    "Kode Kios",
            "status":        "Status",
            "fetched_at":    "Waktu Update",
        }.get(x, x),
        horizontal=True,
    )
    sort_asc = st.radio("Urutan", ["A → Z", "Z → A"], horizontal=True) == "A → Z"
    df = df.sort_values(sort_col, ascending=sort_asc)

    # ── Tabel utama ─────────────────────────
    display_cols = {
        "store_code":    "Kode Kios",
        "business_name": "Nama Bisnis",
        "address":       "Alamat",
        "latitude":      "Latitude",
        "longitude":     "Longitude",
        "status":        "Status",
        "fetched_at":    "Diperbarui",
    }

    df_show = df[list(display_cols.keys())].copy()
    df_show.columns = list(display_cols.values())
    df_show["Status"] = df_show["Status"].map(status_label)

    # Format koordinat: 7 desimal, "-" jika kosong
    df_show["Latitude"]  = df_show["Latitude"].map(
        lambda v: f"{v:.7f}" if pd.notna(v) else "—"
    )
    df_show["Longitude"] = df_show["Longitude"].map(
        lambda v: f"{v:.7f}" if pd.notna(v) else "—"
    )

    # Pagination
    total_pages  = max(1, (len(df_show) - 1) // PAGE_SIZE + 1)
    _, col_pnum, _ = st.columns([2, 1, 2])
    with col_pnum:
        cur_page = st.number_input(
            f"Halaman (dari {total_pages})",
            min_value=1, max_value=total_pages, value=1,
        )
    start    = (cur_page - 1) * PAGE_SIZE
    df_page  = df_show.iloc[start : start + PAGE_SIZE]

    st.dataframe(df_page, use_container_width=True, hide_index=True)
    st.caption(f"Menampilkan baris {start+1}–{min(start+PAGE_SIZE, len(df_show))} dari {len(df_show):,}")

    # ── Export ──────────────────────────────
    st.markdown("---")
    col_e1, col_e2, _ = st.columns([1, 1, 3])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    col_e1.download_button(
        "⬇️ Export CSV",
        data=to_csv_bytes(df[list(display_cols.keys())]),
        file_name=f"gbp_export_{ts}.csv",
        mime="text/csv",
    )
    col_e2.download_button(
        "⬇️ Export Excel",
        data=to_excel_bytes(df[list(display_cols.keys())]),
        file_name=f"gbp_export_{ts}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # ── Detail View ─────────────────────────
    st.markdown("---")
    st.subheader("🔍 Detail Lokasi")

    options = ["— Pilih lokasi —"] + df["business_name"].tolist()
    sel_loc = st.selectbox("Pilih atau cari nama bisnis", options)

    if sel_loc != "— Pilih lokasi —":
        row = df[df["business_name"] == sel_loc].iloc[0]
        d1, d2 = st.columns(2)

        with d1:
            st.markdown(f"**Nama Bisnis**   : {row['business_name']}")
            st.markdown(f"**Kode Kios**     : `{row['store_code']}`")
            st.markdown(f"**Location ID**   : `{row['location_name']}`")
            st.markdown(f"**Alamat**         : {row['address']}")
            st.markdown(f"**Status**         : {status_label(row['status'])}")
            st.markdown(f"**Diperbarui**     : {row['fetched_at']}")

        with d2:
            lat_str = f"{row['latitude']:.7f}" if pd.notna(row['latitude']) else "—"
            lng_str = f"{row['longitude']:.7f}" if pd.notna(row['longitude']) else "—"
            st.markdown(f"**Latitude**       : `{lat_str}`")
            st.markdown(f"**Longitude**      : `{lng_str}`")
            st.markdown(f"**Has VoM**        : {'✅ Ya' if row['has_vom'] else '❌ Tidak'}")
            st.markdown(f"**Duplicate**      : {'⚠️ Ya' if row['is_duplicate'] else '— Tidak'}")
            st.markdown(f"**Suspended**      : {'🚫 Ya' if row['is_suspended'] else '— Tidak'}")
            st.markdown(f"**Pending Edits**  : {'⏳ Ya' if row['has_pending_edits'] else '— Tidak'}")

        # Copy helpers
        st.markdown("**Salin:**")
        cc1, cc2, cc3 = st.columns(3)
        cc1.markdown("Location ID")
        cc1.code(row["location_name"] or "—", language=None)

        if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
            cc2.markdown("LatLong")
            cc2.code(f"{row['latitude']:.7f},{row['longitude']:.7f}", language=None)

        if row.get("maps_uri"):
            cc3.markdown("Google Maps")
            cc3.link_button("🗺️ Buka Maps", row["maps_uri"])


# ══════════════════════════════════════════════
# PAGE 3 — MAP VIEW
# ══════════════════════════════════════════════

elif page == "🗺️ Map View":
    st.title("🗺️ Peta Persebaran Lokasi")

    df_map = df.dropna(subset=["latitude", "longitude"]).copy()

    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.metric("Ditampilkan di peta", f"{len(df_map):,}")
    col_info2.metric("Tanpa koordinat",     f"{len(df) - len(df_map):,}")
    col_info3.metric("Total filtered",      f"{len(df):,}")

    if df_map.empty:
        st.warning(
            "Tidak ada lokasi dengan koordinat valid untuk ditampilkan. "
            "Pastikan `latlng` sudah diambil dari GBP API."
        )
    else:
        m = build_map(df_map)
        st_folium(m, use_container_width=True, height=620, returned_objects=[])

        # Breakdown koordinat error
        if "coord_status" in df.columns:
            coord_issues = df[df["coord_status"] != "OK"]
            if not coord_issues.empty:
                with st.expander(f"⚠️ {len(coord_issues)} lokasi dengan masalah koordinat"):
                    st.dataframe(
                        coord_issues[["store_code","business_name","coord_status","address"]],
                        use_container_width=True,
                        hide_index=True,
                    )