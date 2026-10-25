"""Titik masuk Dashboard Streamlit GESER."""
from __future__ import annotations

import streamlit as st

from geser.dashboard.feed import DashboardFeed
from geser.dashboard.views.about import render_about
from geser.dashboard.views.live import render_live
from geser.dashboard.views.logs import render_logs
from geser.dashboard.views.summary import render_summary
from geser.dashboard.views.timeline import render_timeline
from geser.settings import ConfigError, load_runtime

st.set_page_config(page_title="GESER - Geser dikit, yuk", layout="wide")


@st.cache_resource
def get_dashboard_feed() -> DashboardFeed:
    runtime = load_runtime()
    feed = DashboardFeed(runtime)
    feed.start()
    return feed


def main() -> None:
    st.title("GESER: Gravity-tilt Estimation for Sedentary Event Reminders")
    st.caption("Tagline: Geser dikit, yuk.")
    st.info("Perkiraan berdasarkan gerakan perangkat, bukan pengukuran postur atau alat medis.")

    try:
        feed = get_dashboard_feed()
    except ConfigError as exc:
        st.error(f"Konfigurasi belum siap: {exc}")
        st.code("python tools/suggest_project_id.py", language="bash")
        st.stop()

    with st.sidebar:
        st.subheader("Identitas & Broker")
        st.write(f"**PROJECT_ID:** `{feed.runtime.project_id}`")
        st.write(f"**Broker:** `{feed.runtime.settings.broker.host}:{feed.runtime.settings.broker.port}`")
        st.divider()
        st.subheader("Mode Replay Rekaman")
        uploaded = st.file_uploader("Unggah CSV / JSONL hasil record_telemetry.py", type=["csv", "jsonl", "json"])
        if uploaded is not None and st.button("Muat Rekaman Replay", use_container_width=True):
            content = uploaded.getvalue().decode("utf-8", errors="replace")
            total = feed.load_replay(uploaded.name, content)
            st.success(f"Memuat {total} baris rekaman ke mode replay.")
        if st.button("Kembali ke Mode Live MQTT", use_container_width=True):
            feed.clear_replay()

    @st.fragment(run_every="2s")
    def render_panels() -> None:
        snap = feed.snapshot()
        status_teks = "MODE REPLAY" if snap.replay_mode else ("TERHUBUNG" if snap.connected else "MENYAMBUNGKAN...")
        st.caption(f"Status Aliran Data: **{status_teks}**")
        tabs = st.tabs(["Live", "Timeline", "Ringkasan Sesi", "Log", "Tentang"])
        with tabs[0]:
            render_live(feed, snap)
        with tabs[1]:
            render_timeline(feed, snap)
        with tabs[2]:
            render_summary(snap)
        with tabs[3]:
            render_logs(snap)
        with tabs[4]:
            render_about(feed)

    render_panels()


if __name__ == "__main__":
    main()
