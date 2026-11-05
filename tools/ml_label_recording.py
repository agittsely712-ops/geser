"""Ubah rekaman HP sungguhan (CSV dari record_telemetry.py) menjadi data latih berlabel.

Cara kumpulkan data nyata (lakukan untuk tiap kondisi, mis. 2-3 menit per kondisi):
  1. geser-edge --role body  (HP di saku dada)   dan   geser-edge --role desk  (HP di meja)
  2. python tools/record_telemetry.py --out recordings/tegak.csv --duration 120
     (selama merekam: duduk TEGAK / CONDONG / BERGERAK / ketuk MEJA sesuai label)
  3. python tools/ml_label_recording.py --in recordings/tegak.csv --label TEGAK \\
         --out data/real_tegak.csv
  4. python tools/ml_make_dataset.py --per-class 0 --extra data/real_tegak.csv ... 
     lalu latih ulang: python tools/ml_train.py
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from geser.domain.models import Role
from geser.messaging.recording import read_telemetry_csv
from geser.ml.live import PAIR_GAP_MS
from geser.ml.schema import FEATURE_NAMES, LABELS, features_vector


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--label", required=True, choices=LABELS)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    rows = list(read_telemetry_csv(Path(args.src).read_text(encoding="utf-8")))
    desk = None
    out_rows = []
    for received_ms, tele in rows:
        if tele.device is Role.DESK:
            desk = (received_ms, tele.features)
        elif tele.features.calibrated:  # tanpa kalibrasi, body_tilt_deg kosong
            ok = desk is not None and received_ms - desk[0] <= PAIR_GAP_MS
            vec = features_vector(tele.features, desk[1] if ok and desk else None)
            out_rows.append(["" if v != v else f"{v:.5f}" for v in vec] + [args.label])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([*FEATURE_NAMES, "label"])
        w.writerows(out_rows)
    print(f"{len(out_rows)} baris berlabel {args.label} -> {out}")


if __name__ == "__main__":
    main()
