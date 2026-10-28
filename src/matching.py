"""Core 3-way match engine.

For each invoice: locate the PO, compare quantity against goods receipts and
price against the PO price, within configurable tolerances. Every non-clean
outcome carries human-readable reason codes so an accountant sees why an
invoice was held, mirroring how MIRO blocks surface in SAP MM.

Outcomes:
  AUTO_POST  invoice matches within tolerance
  REVIEW     discrepancy a human should look at (price/quantity variance,
             missing goods receipt)
  BLOCK      hard stop (unknown PO, suspected duplicate)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

AUTO_POST, REVIEW, BLOCK = "AUTO_POST", "REVIEW", "BLOCK"


@dataclass
class Tolerances:
    price_pct: float = 5.0       # allowed unit-price increase over PO price
    price_abs: float = 2.0       # or absolute increase, whichever is larger
    qty_over_pct: float = 2.0    # allowed quantity over-receipt fraction
    duplicate_amount_pct: float = 1.0
    duplicate_window_days: int = 30


@dataclass
class MatchResult:
    invoice_id: str
    outcome: str
    reasons: list[str] = field(default_factory=list)


def _gr_qty_for(po_number: str, grs: pd.DataFrame) -> int:
    rows = grs[grs["po_number"] == po_number]
    return int(rows["gr_qty"].sum()) if not rows.empty else 0


def match_invoice(inv: pd.Series, pos: pd.DataFrame, grs: pd.DataFrame,
                  tol: Tolerances) -> MatchResult:
    po_rows = pos[pos["po_number"] == inv["po_number"]]
    if po_rows.empty:
        return MatchResult(inv["invoice_id"], BLOCK,
                           [f"purchase order {inv['po_number']} does not exist"])
    po = po_rows.iloc[0]
    reasons: list[str] = []

    gr_qty = _gr_qty_for(inv["po_number"], grs)
    if gr_qty == 0:
        reasons.append(f"no goods receipt posted for {inv['po_number']}")
    else:
        allowed_qty = gr_qty * (1 + tol.qty_over_pct / 100)
        if inv["quantity"] > allowed_qty:
            over = inv["quantity"] - gr_qty
            reasons.append(
                f"invoiced quantity {int(inv['quantity'])} exceeds goods receipt "
                f"{gr_qty} by {over} units")

    po_price = float(po["po_price"])
    allowed_price = max(po_price * (1 + tol.price_pct / 100), po_price + tol.price_abs)
    if inv["unit_price"] > allowed_price + 1e-9:
        pct = (inv["unit_price"] - po_price) / po_price * 100
        reasons.append(
            f"unit price {inv['unit_price']:.2f} is {pct:.1f}% above the PO price "
            f"{po_price:.2f} (tolerance {tol.price_pct:.0f}%)")

    if reasons:
        return MatchResult(inv["invoice_id"], REVIEW, reasons)
    return MatchResult(inv["invoice_id"], AUTO_POST, [])


def find_duplicates(invoices: pd.DataFrame, tol: Tolerances) -> dict[str, str]:
    """Map invoice_id -> id of the earlier invoice it duplicates, if any.

    Two invoices from the same vendor for the same material with total amounts
    within tolerance and dates within the window are flagged as duplicates.
    """
    dup: dict[str, str] = {}
    df = invoices.copy()
    df["total"] = df["quantity"] * df["unit_price"]
    df["date"] = pd.to_datetime(df["invoice_date"])
    df = df.sort_values("date")
    seen: list[pd.Series] = []
    for _, inv in df.iterrows():
        for prev in seen:
            if prev["vendor_id"] != inv["vendor_id"]:
                continue
            days = abs((inv["date"] - prev["date"]).days)
            if days > tol.duplicate_window_days:
                continue
            amt_pct = abs(inv["total"] - prev["total"]) / max(prev["total"], 1e-9) * 100
            if (inv["material"] == prev["material"]
                    and inv["quantity"] == prev["quantity"]
                    and amt_pct <= tol.duplicate_amount_pct):
                dup[inv["invoice_id"]] = prev["invoice_id"]
                break
        seen.append(inv)
    return dup


def match_all(invoices: pd.DataFrame, pos: pd.DataFrame, grs: pd.DataFrame,
              tol: Tolerances | None = None) -> list[MatchResult]:
    tol = tol or Tolerances()
    duplicates = find_duplicates(invoices, tol)
    results = []
    for _, inv in invoices.iterrows():
        if inv["invoice_id"] in duplicates:
            results.append(MatchResult(
                inv["invoice_id"], BLOCK,
                [f"possible duplicate of {duplicates[inv['invoice_id']]} "
                 f"(same vendor, material and amount within {tol.duplicate_amount_pct:.0f}%)"]))
            continue
        results.append(match_invoice(inv, pos, grs, tol))
    return results
