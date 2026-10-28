from src.evaluate import EXPECTED


def test_synthetic_accuracy_high(matched):
    results, invoices = matched
    expected = invoices["label"].map(EXPECTED)
    got = invoices["invoice_id"].map(lambda i: results[i].outcome)
    accuracy = (expected == got).mean()
    assert accuracy >= 0.9


def test_clean_never_blocked(matched):
    results, invoices = matched
    for iid in invoices.loc[invoices["label"] == "clean", "invoice_id"]:
        assert results[iid].outcome == "AUTO_POST"
