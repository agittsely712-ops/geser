"""Buat dataset CSV untuk AI GESER (simulasi), atau gabungkan dengan data nyata berlabel.

  python tools/ml_make_dataset.py --per-class 1500 --seed 42 --out data/posture_dataset.csv
  python tools/ml_make_dataset.py --extra data/real_tegak.csv --extra data/real_condong.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from geser.ml.schema import FEATURE_NAMES
from geser.ml.synthetic import build_dataset


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--per-class", type=int, default=1500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="data/posture_dataset.csv")
    p.add_argument("--extra", action="append", default=[],
                   help="CSV berlabel dari tools/ml_label_recording.py (boleh berulang)")
    args = p.parse_args()

    rows: list[list[object]] = []
    if args.per_class > 0:
        for vec, label in build_dataset(args.per_class, args.seed):
            rows.append([*("" if v != v else f"{v:.5f}" for v in vec), label, "simulasi"])
    for extra in args.extra:
        with open(extra, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows.append([*(r[name] for name in FEATURE_NAMES), r["label"], "nyata"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([*FEATURE_NAMES, "label", "source"])
        w.writerows(rows)
    print(f"{len(rows)} baris -> {out}")


if __name__ == "__main__":
    main()
