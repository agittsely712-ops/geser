"""Latih AI GESER (supervised learning A -> B) dan ekspor model ke JSON.

  pip install -e ".[ml]"
  python tools/ml_train.py --data data/posture_dataset.csv

Alur sesuai materi "AI for Everyone":
  1. Dataset  : tabel Input (A) fitur 2 HP + Output (B) label kondisi duduk
  2. Split    : training 60% / validation 20% / test 20% (test disentuh sekali di akhir)
  3. Model    : baseline aturan (algoritma lama) vs Decision Tree vs Neural Network (MLP)
  4. Pilih    : berdasarkan akurasi validation, lalu laporkan akurasi test
  5. Kriteria : acceptance criteria akurasi test >= 95% (ubah dengan --target)
  6. Deploy   : bobot jaringan diekspor ke models/posture_mlp.json (inferensi Python murni)
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.tree import DecisionTreeClassifier

from geser.ml.model import SPEC_VERSION
from geser.ml.schema import FEATURE_NAMES, LABELS

# Ambang aturan lama (configs/default.yaml) dipakai sebagai pembanding.
RULE_DESK_DISTURB = 0.60
RULE_GYRO_MAX = 0.15
RULE_ACCEL_MAX = 0.25
RULE_LEAN_DEG = 25.0


def rule_based(x: np.ndarray) -> np.ndarray:
    """Algoritma GESER lama (ambang tetap), dinilai sebagai pengklasifikasi."""
    tilt, _, acc, gyro, d_acc, _ = (np.nan_to_num(x[:, i]) for i in range(6))
    out = np.full(len(x), LABELS.index("TEGAK"))
    out[tilt >= RULE_LEAN_DEG] = LABELS.index("CONDONG")
    out[(gyro >= RULE_GYRO_MAX) | (acc >= RULE_ACCEL_MAX)] = LABELS.index("BERGERAK")
    out[d_acc >= RULE_DESK_DISTURB] = LABELS.index("MEJA_TERGANGGU")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--data", default="data/posture_dataset.csv")
    p.add_argument("--model-out", default="models/posture_mlp.json")
    p.add_argument("--report-dir", default="reports")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--epochs", type=int, default=150)
    p.add_argument("--target", type=float, default=0.95, help="acceptance criteria akurasi test")
    args = p.parse_args()

    df = pd.read_csv(args.data)
    x_all = df[list(FEATURE_NAMES)].to_numpy(dtype=float)
    y_all = df["label"].map(LABELS.index).to_numpy()
    x_tr, x_rest, y_tr, y_rest = train_test_split(
        x_all, y_all, test_size=0.4, stratify=y_all, random_state=args.seed)
    x_va, x_te, y_va, y_te = train_test_split(
        x_rest, y_rest, test_size=0.5, stratify=y_rest, random_state=args.seed)

    impute = np.nanmedian(x_tr, axis=0)  # nilai hilang -> median data training

    def prep(x: np.ndarray) -> np.ndarray:
        return np.where(np.isnan(x), impute, x)

    mean = prep(x_tr).mean(axis=0)
    scale = prep(x_tr).std(axis=0)
    scale[scale == 0] = 1.0

    def z(x: np.ndarray) -> np.ndarray:
        return (prep(x) - mean) / scale

    # --- model 1: aturan lama
    results = {"Aturan (lama)": (accuracy_score(y_va, rule_based(x_va)),
                                 accuracy_score(y_te, rule_based(x_te)))}

    # --- model 2: decision tree
    tree = DecisionTreeClassifier(max_depth=6, random_state=args.seed).fit(z(x_tr), y_tr)
    results["Decision Tree"] = (accuracy_score(y_va, tree.predict(z(x_va))),
                                accuracy_score(y_te, tree.predict(z(x_te))))

    # --- model 3: neural network, simpan bobot epoch dengan akurasi validation terbaik
    mlp = MLPClassifier(hidden_layer_sizes=(16, 8), alpha=1e-3, random_state=args.seed)
    hist = {"train": [], "val": [], "loss": []}
    best, best_acc = None, -1.0
    for _ in range(args.epochs):
        mlp.partial_fit(z(x_tr), y_tr, classes=np.arange(len(LABELS)))
        tr, va = mlp.score(z(x_tr), y_tr), mlp.score(z(x_va), y_va)
        hist["train"].append(tr)
        hist["val"].append(va)
        hist["loss"].append(mlp.loss_)
        if va > best_acc:
            best_acc, best = va, copy.deepcopy(mlp)
    assert best is not None
    best_epoch = int(np.argmax(hist["val"])) + 1
    results["Neural Network (MLP)"] = (accuracy_score(y_va, best.predict(z(x_va))),
                                       accuracy_score(y_te, best.predict(z(x_te))))

    # --- pilih berdasarkan validation (bukan test)
    chosen = max(results, key=lambda k: results[k][0])
    print(f"{'Model':<22}{'Val':>8}{'Test':>8}")
    for name, (va, te) in results.items():
        print(f"{name:<22}{va:>8.3f}{te:>8.3f}" + ("   <- dipilih" if name == chosen else ""))

    # --- laporan model neural network (yang diekspor ke edge)
    pred = best.predict(z(x_te))
    test_acc = accuracy_score(y_te, pred)
    cm = confusion_matrix(y_te, pred, labels=range(len(LABELS)))
    rep = classification_report(y_te, pred, target_names=LABELS, output_dict=True, zero_division=0)
    passed = test_acc >= args.target
    print(f"\nAkurasi test MLP: {test_acc:.3f}  (kriteria {args.target:.0%}: "
          f"{'LULUS' if passed else 'BELUM LULUS'})")
    print(classification_report(y_te, pred, target_names=LABELS, zero_division=0))

    # --- ekspor JSON
    spec = {
        "version": SPEC_VERSION, "kind": "mlp", "classes": list(LABELS),
        "features": list(FEATURE_NAMES), "impute": impute.tolist(), "mean": mean.tolist(),
        "scale": scale.tolist(),
        "layers": [{"w": w.tolist(), "b": b.tolist()}
                   for w, b in zip(best.coefs_, best.intercepts_, strict=True)],
        "meta": {"test_accuracy": round(test_acc, 4), "val_accuracy": round(best_acc, 4),
                 "best_epoch": best_epoch, "n_train": len(y_tr), "n_val": len(y_va),
                 "n_test": len(y_te), "data": Path(args.data).name, "seed": args.seed},
    }
    out = Path(args.model_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec), encoding="utf-8")
    print(f"Model diekspor ke {out} ({out.stat().st_size / 1024:.1f} KB)")

    # --- grafik & metrik
    rdir = Path(args.report_dir)
    rdir.mkdir(parents=True, exist_ok=True)
    ink, soft, accent = "#1f2937", "#9ca3af", "#2563eb"

    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(LABELS)), LABELS, rotation=25, ha="right")
    ax.set_yticks(range(len(LABELS)), LABELS)
    for i in range(len(LABELS)):
        for j in range(len(LABELS)):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else ink)
    ax.set_xlabel("Prediksi AI")
    ax.set_ylabel("Label sebenarnya")
    ax.set_title(f"Confusion matrix (test, akurasi {test_acc:.1%})")
    fig.tight_layout()
    fig.savefig(rdir / "confusion_matrix.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 3.6))
    ep = np.arange(1, len(hist["train"]) + 1)
    ax.plot(ep, hist["train"], color=soft, label="Training")
    ax.plot(ep, hist["val"], color=accent, label="Validation")
    ax.axvline(best_epoch, color=ink, ls=":", lw=1)
    ax.axhline(args.target, color="#dc2626", ls="--", lw=1)
    ax.text(ep[-1], args.target + 0.002, f"kriteria {args.target:.0%}", ha="right", color="#dc2626",
            fontsize=8)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Akurasi")
    ax.set_title("Kurva belajar neural network")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(rdir / "learning_curve.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 3.4))
    names = list(results)
    vals = [results[n][1] for n in names]
    colors = [accent if n == "Neural Network (MLP)" else soft for n in names]
    bars = ax.bar(names, vals, color=colors)
    for b, v in zip(bars, vals, strict=True):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.004, f"{v:.1%}", ha="center", fontsize=9)
    ax.set_ylim(min(vals) - 0.1, 1.0)
    ax.set_ylabel("Akurasi test")
    ax.set_title("Perbandingan model")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(rdir / "model_comparison.png", dpi=200)
    plt.close(fig)

    metrics = {"results": {k: {"val": round(v[0], 4), "test": round(v[1], 4)}
                           for k, v in results.items()},
               "chosen_by_validation": chosen, "exported_model": "Neural Network (MLP)",
               "test_accuracy": round(test_acc, 4), "target": args.target, "passed": bool(passed),
               "confusion_matrix": cm.tolist(), "per_class": {k: rep[k] for k in LABELS},
               "split": {"train": len(y_tr), "val": len(y_va), "test": len(y_te)},
               "best_epoch": best_epoch}
    (rdir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Grafik & metrik di {rdir}/")


if __name__ == "__main__":
    main()
