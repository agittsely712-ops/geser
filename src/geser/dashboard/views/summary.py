"""Halaman Ringkasan Sesi: metrik agregat dan unduh CSV telemetry."""
from __future__ import annotations

import streamlit as st

from geser.dashboard.feed import FeedSnapshot
from geser.messaging.recording import telemetry_csv


def render_summary(snap: FeedSnapshot) -> None:
    s = snap.session
    st.subheader("Ringkasan Metrik Sesi")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Movement Score", f"{s.score if s else 100} / 100")
    m2.metric("Jumlah Pengingat", s.reminders_count if s else len(snap.reminders))
    m3.metric("Jumlah Ganti Posisi (Reposition)", s.repositions if s else 0)
    longest_min = (s.longest_still_s / 60.0) if s else 0.0
    m4.metric("Durasi Diam Terpanjang (Skala)", f"{longest_min:.1f} menit")

    combined = sorted([*snap.body_history, *snap.desk_history], key=lambda item: item[0])
    st.subheader("Ekspor Rekaman Telemetry (CSV)")
    if not combined:
        st.info("Belum ada data telemetry untuk diunduh.")
        return
    csv_text = telemetry_csv(combined)
    st.download_button(
        label=f"Unduh CSV Telemetry ({len(combined)} baris)",
        data=csv_text.encode("utf-8"),
        file_name="geser_telemetry.csv",
        mime="text/csv",
    )
