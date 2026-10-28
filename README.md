# Invoice Three-Way Match

Automated three-way match for procurement invoices, the check an SAP MM
invoice-verification step (MIRO) performs: match each invoice against its
purchase order and goods receipts, within configurable tolerances, and decide
whether it can post automatically, needs review, or must be blocked.

Built as a portfolio project. The bundled data is fully synthetic.

## What it does

- Matches invoices against PO and goods-receipt extracts (EKKO/EKPO/RBKP
  shape) and assigns an outcome:
  - **AUTO_POST**: quantity and price within tolerance
  - **REVIEW**: price above PO price, invoiced quantity above received
    quantity, or no goods receipt posted
  - **BLOCK**: unknown purchase order, or a suspected duplicate invoice
- Every held invoice comes with reason codes an accountant can act on, for
  example "unit price 155.00 is 24.1% above the PO price 125.00 (tolerance
  5%)" or "possible duplicate of INV-5100007 (same vendor, material and
  amount within 1%)".
- Ships with a REST API, an evaluation CLI, tests, a Dockerfile and CI.

## Quick start

```bash
pip install -r requirements.txt
python -m pytest -q                      # 17 tests
uvicorn src.api:app --port 8000
```

Score an invoice:

```bash
curl -X POST http://localhost:8000/match -H 'Content-Type: application/json' -d '{
  "invoices": [{
    "po_number": "PO-4500001",
    "vendor_id": "V0007",
    "material": "MAT-2001",
    "quantity": 12,
    "unit_price": 181.0,
    "invoice_date": "2025-06-01"
  }]
}'
```

With Docker:

```bash
docker build -t invoice-three-way-match .
docker run -p 8000:8000 invoice-three-way-match
```

## Evaluation (honest numbers)

The synthetic invoice CSV carries labels, so the matcher can be evaluated
honestly (`python -m src.evaluate --data-dir data`, also run in CI):

| Outcome   | Precision | Recall |
| --------- | --------- | ------ |
| AUTO_POST | 0.987     | 1.000  |
| REVIEW    | 1.000     | 0.952  |
| BLOCK     | 1.000     | 1.000  |

Overall accuracy: 0.991 on 427 invoices.

The misses are price variances that fall inside the tolerance: for
low-priced materials the absolute tolerance (2.00 over the PO price) is
larger than the percentage one, so a +15% price increase on a cheap item
legitimately auto-posts. That is a tolerance design choice, surfaced in the
report, not a hidden failure.

## Design notes and limits

- **Tolerances are explicit**: `Tolerances` (price %, price absolute,
  quantity over-receipt %, duplicate amount % and window) can be tuned per
  call. The API accepts a price-tolerance override.
- **Duplicate detection** flags a later invoice from the same vendor for the
  same material and quantity with a total within 1% and within 30 days of an
  earlier one. It deliberately needs the full combination, so repeat orders
  of the same item do not false-fire.
- **Line-level, single-line invoices**: real invoices have multiple lines and
  partial receipts across many GR documents. The engine matches at invoice
  level against one PO; extending it to line-level matching is the natural
  next step.
- **No ML here, on purpose**: the 3-way match is a deterministic control and
  should stay auditable. The synthetic labels exist to prove the rules behave
  as specified.
- **Synthetic data**: the generator mimics the shape of MM extracts. Real
  data needs currency conversion, tax handling, credit memos and tolerance
  keys per company code.

## Project layout

```
src/generate_data.py   synthetic MM-style PO/GR/invoice generator (labeled)
src/matching.py        match engine, tolerances, duplicate detection
src/evaluate.py        precision/recall report against labels
src/api.py             FastAPI service (/match, /invoices/exceptions, /health)
data/                  400 POs, 371 GRs, 427 invoices (30% with issues)
tests/                 17 tests: data, matching, evaluation, API
```

## License

MIT
