"""Halaman Timeline: grafik kemiringan, getaran body dan desk dengan garis ambang."""
from __future__ import annotations

import streamlit as st

from geser.dashboard.charts import events_frame, telemetry_frame
from geser.dashboard.feed import DashboardFeed, FeedSnapshot


def render_timeline(feed: DashboardFeed, snap: FeedSnapshot) -> None:
    cfg = feed.runtime.settings
    st.subheader("Grafik Pergerakan & Kemiringan Body (HP Saku Dada)")
    df_body = telemetry_frame(snap.body_history, cfg.stillness.accel_dev_max)
    if df_body.empty:
        st.info("Belum ada paket telemetry dari perangkat body.")
    else:
        st.caption("Kemiringan terhadap baseline (`tilt_deg`) dan perubahan antar jendela (`tilt_step_deg`)")
        st.line_chart(df_body.set_index("waktu")[["tilt_deg", "tilt_step_deg"]])
        st.caption(f"Getaran Body (`accel_dev_rms`) dan garis ambang awal ({cfg.stillness.accel_dev_max} m/s^2)")
        st.line_chart(df_body.set_index("waktu")[["accel_dev_rms", "ambang_rms"]])

    st.subheader("Grafik Referensi Gangguan Meja (HP Desk)")
    df_desk = telemetry_frame(snap.desk_history, cfg.fusion.desk_disturb_accel_rms)
    if df_desk.empty:
        st.info("Belum ada paket telemetry dari perangkat desk.")
    else:
        st.caption(f"Getaran Meja (`accel_dev_rms`) dan garis ambang gangguan ({cfg.fusion.desk_disturb_accel_rms} m/s^2)")
        st.line_chart(df_desk.set_index("waktu")[["accel_dev_rms", "ambang_rms"]])

    st.subheader("Pita Riwayat Transisi Status & Event")
    df_events = events_frame(snap.events)
    if df_events.empty:
        st.write("Belum ada transisi status yang tercatat.")
    else:
        st.dataframe(df_events, use_container_width=True, hide_index=True)
