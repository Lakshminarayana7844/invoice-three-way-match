"""FastAPI service for the 3-way match.

Loads the bundled CSVs at startup. Endpoints:
  GET  /health                     liveness
  POST /match                      match submitted invoices against POs/GRs
  GET  /invoices/exceptions?top=N  held invoices from the bundled data,
                                   REVIEW first, then BLOCK, both with reasons
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

from .matching import BLOCK, REVIEW, Tolerances, match_all

DATA_DIR = os.environ.get("DATA_DIR", "data")


class Invoice(BaseModel):
    invoice_id: Optional[str] = None
    po_number: str
    vendor_id: str
    material: str
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    invoice_date: str = Field(..., examples=["2025-06-01"])


class MatchRequest(BaseModel):
    invoices: list[Invoice]
    price_tolerance_pct: Optional[float] = None


app = FastAPI(title="Invoice Three-Way Match", version="1.0.0")
POS = pd.read_csv(f"{DATA_DIR}/purchase_orders.csv")
GRS = pd.read_csv(f"{DATA_DIR}/goods_receipts.csv")
INVOICES = pd.read_csv(f"{DATA_DIR}/invoices.csv")


def _to_frame(invoices: list[Invoice]) -> pd.DataFrame:
    df = pd.DataFrame([i.model_dump() for i in invoices])
    df["invoice_id"] = df["invoice_id"].fillna(
        pd.Series([f"SUB-{i}" for i in range(len(df))]))
    return df


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "pos": len(POS), "grs": len(GRS)}


@app.post("/match")
def match(req: MatchRequest) -> dict:
    tol = Tolerances()
    if req.price_tolerance_pct is not None:
        tol.price_pct = req.price_tolerance_pct
    df = _to_frame(req.invoices)
    results = match_all(df, POS, GRS, tol)
    return {"results": [
        {"invoice_id": r.invoice_id, "outcome": r.outcome, "reasons": r.reasons}
        for r in results]}


@app.get("/invoices/exceptions")
def exceptions(top: int = 10) -> dict:
    results = match_all(INVOICES, POS, GRS)
    held = [r for r in results if r.outcome in (REVIEW, BLOCK)]
    held.sort(key=lambda r: 0 if r.outcome == REVIEW else 1)
    top = max(1, min(top, 100))
    return {"count": len(held), "results": [
        {"invoice_id": r.invoice_id, "outcome": r.outcome, "reasons": r.reasons}
        for r in held[:top]]}
