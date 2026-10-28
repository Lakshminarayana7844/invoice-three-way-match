"""Generate synthetic SAP MM-style procurement data with labeled invoices.

Mimics the shape of an EKKO/EKPO (purchase order), goods receipt and RBKP
(invoice) extract. Labels are kept so the matcher can be evaluated honestly;
a real deployment would not have them.

Issue types injected into roughly 30% of invoices:
  price_variance   unit price above PO price beyond tolerance
  qty_variance     invoiced quantity above goods-receipt quantity
  no_receipt       no goods receipt posted for the PO line
  duplicate        near-copy of another invoice from the same vendor
  unknown_po       purchase order does not exist
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

VENDORS = [f"V{i:04d}" for i in range(1, 31)]
MATERIALS = [
    ("MAT-1001", 12.0), ("MAT-1002", 8.5), ("MAT-2001", 140.0),
    ("MAT-2002", 220.0), ("MAT-3001", 450.0), ("MAT-3002", 780.0),
]


def generate(n_pos: int = 400, seed: int = 42, issue_rate: float = 0.30):
    rng = np.random.default_rng(seed)

    pos, grs, invoices = [], [], []
    start = np.datetime64("2025-01-01")
    for i in range(n_pos):
        po = f"PO-{4500000 + i}"
        vendor = VENDORS[rng.integers(0, len(VENDORS))]
        mat, price = MATERIALS[rng.integers(0, len(MATERIALS))]
        qty = int(rng.lognormal(3.0, 0.6)) + 1
        price = round(price * float(rng.uniform(0.9, 1.1)), 2)  # per-PO price variation
        po_date = start + rng.integers(0, 300).astype("timedelta64[D]")
        pos.append({"po_number": po, "vendor_id": vendor, "material": mat,
                    "po_price": price, "po_qty": qty, "po_date": str(po_date)})

        has_issue = rng.random() < issue_rate
        issue = None
        received = qty
        if has_issue:
            issue = ["price_variance", "qty_variance", "no_receipt",
                     "duplicate", "unknown_po"][rng.integers(0, 5)]

        if issue != "no_receipt":
            gr_date = po_date + rng.integers(2, 20).astype("timedelta64[D]")
            if issue == "qty_variance":
                received = max(1, int(qty * float(rng.uniform(0.5, 0.85))))
            grs.append({"po_number": po, "gr_qty": received, "gr_date": str(gr_date)})

        inv_price = round(price * (1 + float(rng.uniform(0.08, 0.30))), 2) if issue == "price_variance" else price
        inv_qty = qty if issue != "qty_variance" else qty  # invoice full PO qty
        inv_date = po_date + rng.integers(5, 40).astype("timedelta64[D]")
        inv_po = po if issue != "unknown_po" else f"PO-{9999000 + i}"
        invoices.append({
            "invoice_id": f"INV-{5100000 + i}",
            "po_number": inv_po,
            "vendor_id": vendor,
            "material": mat,
            "quantity": inv_qty,
            "unit_price": inv_price,
            "invoice_date": str(inv_date),
            "label": ("clean" if issue == "duplicate" else issue) or "clean",
        })

        if issue == "duplicate":
            dup_date = inv_date + rng.integers(3, 25).astype("timedelta64[D]")
            invoices.append({
                "invoice_id": f"INV-{6100000 + i}",
                "po_number": po,
                "vendor_id": vendor,
                "material": mat,
                "quantity": inv_qty,
                "unit_price": round(inv_price * float(rng.uniform(0.995, 1.005)), 2),
                "invoice_date": str(dup_date),
                "label": "duplicate",
            })

    return (pd.DataFrame(pos), pd.DataFrame(grs),
            pd.DataFrame(invoices).sample(frac=1.0, random_state=seed).reset_index(drop=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pos", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="data")
    args = parser.parse_args()
    pos, grs, invoices = generate(args.pos, args.seed)
    pos.to_csv(f"{args.out_dir}/purchase_orders.csv", index=False, lineterminator="\n")
    grs.to_csv(f"{args.out_dir}/goods_receipts.csv", index=False, lineterminator="\n")
    invoices.to_csv(f"{args.out_dir}/invoices.csv", index=False, lineterminator="\n")
    labels = invoices["label"].value_counts().to_dict()
    print(f"wrote {len(pos)} POs, {len(grs)} GRs, {len(invoices)} invoices: {labels}")


if __name__ == "__main__":
    main()
