"""Cetak saran PROJECT_ID unik dengan sufiks acak 4 karakter."""
from __future__ import annotations

from geser.settings.identity import suggest_project_id


def main() -> None:
    saran = suggest_project_id()
    print(f"PROJECT_ID={saran}")


if __name__ == "__main__":
    main()
