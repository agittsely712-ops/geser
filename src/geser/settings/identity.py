"""Identitas proyek: validasi PROJECT_ID dan saran nilai unik."""
from __future__ import annotations

import re
import secrets
import string

from .errors import ProjectIdError

PLACEHOLDER_PROJECT_ID = "geser-kelompok-GANTI"
_VALID_ID = re.compile(r"^[A-Za-z0-9_-]{6,48}$")
_SUFFIX_LENGTH = 4
_ALPHABET = string.ascii_lowercase + string.digits


def suggest_project_id() -> str:
    """Saran PROJECT_ID dengan sufiks acak 4 karakter."""
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(_SUFFIX_LENGTH))
    return f"geser-kelompok-{suffix}"


def validate_project_id(value: str | None) -> str:
    """Kembalikan PROJECT_ID bila layak; tolak placeholder atau format salah."""
    text = (value or "").strip()
    if not text or text == PLACEHOLDER_PROJECT_ID or text.upper().endswith("GANTI"):
        raise ProjectIdError(
            "PROJECT_ID masih kosong atau placeholder. Broker HiveMQ bersifat publik, "
            "jadi PROJECT_ID harus unik per kelompok.\n"
            f"Saran nilai: PROJECT_ID={suggest_project_id()}\n"
            "Isi di berkas .env (salin dari .env.example)."
        )
    if not _VALID_ID.match(text):
        raise ProjectIdError(
            "PROJECT_ID hanya boleh huruf, angka, '-' dan '_' (6 sampai 48 karakter). "
            f"Saran nilai: {suggest_project_id()}"
        )
    return text
