from src.generate_data import generate


def test_deterministic():
    a = generate(100, seed=1)
    b = generate(100, seed=1)
    assert all(x.equals(y) for x, y in zip(a, b))


def test_shapes_and_labels():
    pos, grs, invoices = generate(200, seed=2)
    assert len(pos) == 200
    assert not grs.empty
    labels = set(invoices["label"].unique())
    assert "clean" in labels
    assert labels <= {"clean", "price_variance", "qty_variance",
                      "no_receipt", "duplicate", "unknown_po"}
    assert invoices["invoice_id"].is_unique


def test_every_non_no_receipt_po_has_gr():
    pos, grs, invoices = generate(150, seed=3)
    no_gr_labels = invoices[invoices["label"] == "no_receipt"]["po_number"].unique()
    for po in no_gr_labels:
        assert po not in set(grs["po_number"])
