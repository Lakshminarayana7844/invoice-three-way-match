import pandas as pd
import pytest

from src.generate_data import generate


@pytest.fixture(scope="session")
def data():
    return generate(n_pos=300, seed=7)


@pytest.fixture(scope="session")
def matched(data):
    from src.matching import match_all
    pos, grs, invoices = data
    return {r.invoice_id: r for r in match_all(invoices, pos, grs)}, invoices
