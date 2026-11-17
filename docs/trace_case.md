# Trace case: C-014@11

Trial: seeded_regression C-014@11; compare fixed C-014@11.

- Event 3: official full entitlement quote = 150000 VND.
- Event 4: prior refund history = 30000 VND. Reading history is valid.
- First wrong step: event 5 proposal = 120000. The agent pre-deducts history (FM-05).
- Host deducts 30000 again, so actual ledger = 90000 instead of expected 120000.
- Event 6 states 120000, inconsistent with ledger (FM-08, a downstream error).
- Fixed: no pre-deduction proposal event; full quote goes to host, ledger=120000 and reply=120000.

Regression: src/tests/test_lab9_reply.py::test_lab9_trace_case_c014_regression_and_fixed
checks both RefundAmountCorrect and ReplyAmountMatchesLedger on real isolated trials.
This existing eval item remains in v1; no additional claim was invented.

Reproduce from src:
```
python -m lab9.trace_case --shape seeded_regression --claim C-014 --seed 11
python -m lab9.trace_case --shape fixed --claim C-014 --seed 11
```

The trace proves arithmetic and reply inconsistencies, not the model's private reasoning.
