"""Demo AI tanpa HP dan tanpa internet: Input (A) -> model -> Output (B).

  python tools/ml_demo.py
  python tools/ml_demo.py --model models/posture_mlp.json --seed 7
"""
from __future__ import annotations

import argparse
import random

from geser.ml import FEATURE_NAMES, LABELS, PostureModel
from geser.ml.schema import LABEL_TEXT
from geser.ml.synthetic import make_example


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="models/posture_mlp.json")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--rows", type=int, default=2, help="contoh per kondisi")
    args = p.parse_args()

    model = PostureModel.load(args.model)
    rng = random.Random(args.seed)
    print("INPUT (A) = " + ", ".join(FEATURE_NAMES))
    print("OUTPUT (B) = " + " | ".join(LABELS) + "\n")
    benar = total = 0
    for true in LABELS:
        for _ in range(args.rows):
            vec = make_example(true, rng)
            pred = model.predict(vec)
            ok = pred.label == true
            benar, total = benar + ok, total + 1
            nums = " ".join(f"{v:6.2f}" for v in vec)
            print(f"A=[{nums}]  ->  B={pred.label:<15} ({pred.confidence:5.1%})  "
                  f"asli={true:<15} {'OK' if ok else 'SALAH'}")
            print(f"    {LABEL_TEXT[pred.label]}")
    print(f"\n{benar}/{total} benar pada contoh demo ini.")


if __name__ == "__main__":
    main()
