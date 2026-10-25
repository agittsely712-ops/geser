"""Halaman Log: daftar pesan MQTT mentah terbaru."""
from __future__ import annotations

import streamlit as st

from geser.dashboard.charts import logs_frame
from geser.dashboard.feed import FeedSnapshot


def render_logs(snap: FeedSnapshot) -> None:
    st.subheader("Log Lalu Lintas Pesan MQTT")
    df = logs_frame(snap.logs)
    if df.empty:
        st.info("Belum ada lalu lintas pesan yang tercatat.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
