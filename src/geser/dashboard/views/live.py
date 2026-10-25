"""Halaman Live: status sesi besar, kontrol 2 arah, dan diagnostik bila belum ada data."""
from __future__ import annotations

import streamlit as st

from geser.dashboard.feed import DashboardFeed, FeedSnapshot
from geser.domain.models import ReminderKind, Role
from geser.domain.states import STATE_LABELS, State
from geser.messaging.codec import CommandName, ControlCommand


def render_live(feed: DashboardFeed, snap: FeedSnapshot) -> None:
    session = snap.session
    cfg = feed.runtime.settings

    if session is None and not snap.body_history and not snap.desk_history:
        st.warning(
            "Diagnostik: Belum ada data dari Engine maupun Edge. "
            "Pastikan `geser-engine` dan `geser-edge` sedang berjalan dengan PROJECT_ID yang sama."
        )
        st.code(
            "geser-engine\ngeser-edge --role body --simulate still\ngeser-edge --role desk --simulate still",
            language="bash",
        )

    state = session.state if session else State.IDLE
    reason = session.reason if session else "Menunggu paket status dari geser-engine..."
    still_scaled_s = session.still_scaled_s if session else 0.0
    still_real_s = session.still_real_s if session else 0.0
    time_scale = session.time_scale if session else cfg.engine.time_scale
    score = session.score if session else int(cfg.score.start)

    latest_tilt = None
    if snap.body_history:
        latest_tilt = snap.body_history[-1][1].features.tilt_deg
    elif session and session.anchor_tilt_deg is not None:
        latest_tilt = session.anchor_tilt_deg

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status Sesi", f"{STATE_LABELS[state]} ({state.value})")
    c2.metric(
        f"Timer Diam (Skala x{time_scale:g})",
        f"{still_scaled_s / 60.0:.1f} menit",
        f"Waktu nyata: {still_real_s:.0f} detik",
    )
    c3.metric(
        "Kemiringan Body (Tilt)",
        f"{latest_tilt:.1f} deg" if latest_tilt is not None else "Belum dikalibrasi",
    )
    c4.metric("Movement Score", f"{score} / 100")

    st.caption(f"Alasan status: {reason}")

    p1, p2, p3 = st.columns(3)
    body_up = (session.nodes_online.get("body", False) if session else False) or snap.presence.get(Role.BODY, False)
    desk_up = (session.nodes_online.get("desk", False) if session else False) or snap.presence.get(Role.DESK, False)
    p1.write(f"**HP Body (Saku Dada):** {'ONLINE' if body_up else 'OFFLINE'}")
    p2.write(f"**HP Desk (Meja):** {'ONLINE' if desk_up else 'OFFLINE'}")
    p3.write(f"**Level Pengingat Aktif:** Level {session.reminder_level if session else 0}")

    if snap.reminders:
        latest = snap.reminders[0]
        if latest.event is ReminderKind.REMINDER:
            st.warning(f"Pengingat Level {latest.level} ({latest.still_min:.0f} mnt): {latest.message}")
        else:
            st.success(f"Auto-Clear: {latest.message}")

    st.divider()
    st.subheader("Kontrol Sesi Dua Arah")
    b1, b2, b3, b4, b5, b6, b7 = st.columns(7)
    if b1.button("Start", use_container_width=True):
        feed.send_command(ControlCommand(CommandName.START))
    if b2.button("Pause", use_container_width=True):
        feed.send_command(ControlCommand(CommandName.PAUSE))
    if b3.button("Resume", use_container_width=True):
        feed.send_command(ControlCommand(CommandName.RESUME))
    if b4.button("End", use_container_width=True):
        feed.send_command(ControlCommand(CommandName.END))
    if b5.button("Kalibrasi 5 dtk", use_container_width=True):
        feed.send_command(ControlCommand(CommandName.CALIBRATE, target=Role.BODY))

    snooze_opts = cfg.reminders.snooze_options_min
    if b6.button(f"Snooze {snooze_opts[0]}m", use_container_width=True):
        feed.send_command(ControlCommand(CommandName.SNOOZE, minutes=snooze_opts[0]))
    if len(snooze_opts) > 1 and b7.button(f"Snooze {snooze_opts[1]}m", use_container_width=True):
        feed.send_command(ControlCommand(CommandName.SNOOZE, minutes=snooze_opts[1]))

    sc1, sc2 = st.columns([3, 1])
    scale_val = sc1.slider(
        "Skala Waktu Demo (TIME_SCALE)",
        min_value=float(cfg.engine.time_scale_min),
        max_value=float(cfg.engine.time_scale_max),
        value=float(time_scale),
        step=1.0,
    )
    if sc2.button("Terapkan Skala Waktu", use_container_width=True):
        feed.send_command(ControlCommand(CommandName.TIME_SCALE, value=float(scale_val)))
