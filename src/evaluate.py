"""Evaluate the matcher against the labels in the synthetic invoice CSV.

Usage: python -m src.evaluate --data-dir data
Maps labels to expected outcomes: clean->AUTO_POST, price_variance/
qty_variance/no_receipt->REVIEW, duplicate/unknown_po->BLOCK.
Prints per-class precision/recall and overall accuracy.
"""
from __future__ import annotations

import argparse
from collections import defaultdict

import pandas as pd

from .matching import match_all

EXPECTED = {
    "clean": "AUTO_POST",
    "price_variance": "REVIEW",
    "qty_variance": "REVIEW",
    "no_receipt": "REVIEW",
    "duplicate": "BLOCK",
    "unknown_po": "BLOCK",
}


def evaluate(data_dir: str = "data") -> dict:
    pos = pd.read_csv(f"{data_dir}/purchase_orders.csv")
    grs = pd.read_csv(f"{data_dir}/goods_receipts.csv")
    invoices = pd.read_csv(f"{data_dir}/invoices.csv")
    results = {r.invoice_id: r for r in match_all(invoices, pos, grs)}

    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)
    correct = 0
    per_class = {}
    for label, expected in EXPECTED.items():
        ids = invoices.loc[invoices["label"] == label, "invoice_id"]
        for iid in ids:
            got = results[iid].outcome
            if got == expected:
                correct += 1
                tp[expected] += 1
            else:
                fn[expected] += 1
                fp[got] += 1
        total = max(len(ids), 1)
        per_class[label] = sum(
            1 for iid in ids if results[iid].outcome == expected) / total

    metrics = {}
    for outcome in ["AUTO_POST", "REVIEW", "BLOCK"]:
        p = tp[outcome] / max(tp[outcome] + fp[outcome], 1)
        r = tp[outcome] / max(tp[outcome] + fn[outcome], 1)
        metrics[outcome] = {"precision": round(p, 3), "recall": round(r, 3)}
    metrics["accuracy"] = round(correct / len(invoices), 3)
    metrics["per_class_recall"] = {k: round(v, 3) for k, v in per_class.items()}
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    metrics = evaluate(args.data_dir)
    for outcome in ["AUTO_POST", "REVIEW", "BLOCK"]:
        m = metrics[outcome]
        print(f"{outcome:9s} precision={m['precision']:.3f} recall={m['recall']:.3f}")
    print(f"overall accuracy={metrics['accuracy']:.3f}")
    print(f"per-class recall: {metrics['per_class_recall']}")


if __name__ == "__main__":
    main()
