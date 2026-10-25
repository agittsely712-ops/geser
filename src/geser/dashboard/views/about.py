"""Halaman Tentang: kepanjangan GESER, penafian non-medis, dan daftar topic."""
from __future__ import annotations

import streamlit as st

from geser.dashboard.feed import DashboardFeed


def render_about(feed: DashboardFeed) -> None:
    st.subheader("Tentang Proyek GESER")
    st.markdown(
        """
        **GESER** adalah singkatan dari **G**ravity-tilt **E**stimation for **S**edentary **E**vent **R**eminders
        (*G Gravity-tilt, E Estimation, S Sedentary, E Event, R Reminders*).

        Kata *geser* dalam Bahasa Indonesia berarti berpindah sedikit dari posisi semula.
        Tagline: **"Geser dikit, yuk."**

        ### Penafian Penting (Disclaimer)
        Perkiraan berdasarkan gerakan perangkat, bukan pengukuran postur atau alat medis.
        Sistem ini hanya menghitung perubahan kemiringan vektor gravitasi dan tingkat getaran
        dari dua telepon pintar (HP `body` di saku baju dada dan HP `desk` di atas meja).

        ### Jenis Algoritma
        Sistem menggunakan **algoritma lain: rule-based dengan state machine** serta perhitungan
        noise floor adaptif berbasis rata-rata dan simpangan baku pada 60 detik pertama sesi.
        """
    )
    st.subheader("Daftar Topic MQTT Aktif")
    st.code("\n".join(feed.topics.all_topics()), language="text")
