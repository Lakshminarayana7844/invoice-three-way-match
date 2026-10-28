import pandas as pd

from src.matching import (AUTO_POST, BLOCK, REVIEW, Tolerances,
                          find_duplicates, match_all, match_invoice)


def _inv(**kw):
    base = {"invoice_id": "INV-1", "po_number": "PO-1", "vendor_id": "V1",
            "material": "M1", "quantity": 10, "unit_price": 100.0,
            "invoice_date": "2025-06-01", "label": "clean"}
    base.update(kw)
    return pd.Series(base)


POS = pd.DataFrame([{"po_number": "PO-1", "vendor_id": "V1", "material": "M1",
                     "po_price": 100.0, "po_qty": 10, "po_date": "2025-05-01"}])
GRS = pd.DataFrame([{"po_number": "PO-1", "gr_qty": 10, "gr_date": "2025-05-10"}])
TOL = Tolerances()


def test_clean_auto_posts():
    r = match_invoice(_inv(), POS, GRS, TOL)
    assert r.outcome == AUTO_POST and r.reasons == []


def test_unknown_po_blocks():
    r = match_invoice(_inv(po_number="PO-9"), POS, GRS, TOL)
    assert r.outcome == BLOCK
    assert "does not exist" in r.reasons[0]


def test_price_variance_reviews():
    r = match_invoice(_inv(unit_price=120.0), POS, GRS, TOL)
    assert r.outcome == REVIEW
    assert any("above the PO price" in x for x in r.reasons)


def test_price_within_tolerance_auto_posts():
    r = match_invoice(_inv(unit_price=103.0), POS, GRS, TOL)
    assert r.outcome == AUTO_POST


def test_qty_over_receipt_reviews():
    r = match_invoice(_inv(quantity=15), POS, GRS, TOL)
    assert r.outcome == REVIEW
    assert any("exceeds goods receipt" in x for x in r.reasons)


def test_no_goods_receipt_reviews():
    empty_grs = GRS.iloc[0:0]
    r = match_invoice(_inv(), POS, empty_grs, TOL)
    assert r.outcome == REVIEW
    assert any("no goods receipt" in x for x in r.reasons)


def test_duplicate_blocks():
    invoices = pd.DataFrame([
        _inv(invoice_id="A", invoice_date="2025-06-01"),
        _inv(invoice_id="B", invoice_date="2025-06-10"),
    ])
    dup = find_duplicates(invoices, TOL)
    assert dup == {"B": "A"}
    results = {r.invoice_id: r for r in match_all(invoices, POS, GRS, TOL)}
    assert results["B"].outcome == BLOCK
    assert results["A"].outcome == AUTO_POST


def test_different_vendor_not_duplicate():
    invoices = pd.DataFrame([
        _inv(invoice_id="A", invoice_date="2025-06-01"),
        _inv(invoice_id="B", invoice_date="2025-06-10", vendor_id="V2"),
    ])
    assert find_duplicates(invoices, TOL) == {}
