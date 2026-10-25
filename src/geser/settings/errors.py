"""Exception khusus konfigurasi."""
from __future__ import annotations


class ConfigError(Exception):
    """Konfigurasi tidak valid atau tidak ditemukan."""


class ProjectIdError(ConfigError):
    """PROJECT_ID kosong, masih placeholder, atau formatnya salah."""
