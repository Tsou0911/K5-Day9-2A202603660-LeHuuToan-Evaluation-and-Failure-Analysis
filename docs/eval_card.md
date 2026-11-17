# Eval card - LogiX-VN, core M0-M4

## Scope

Offline synthetic refund requests, MockLLM, 14 items x 5 seeds (11,22,33,44,55).
No real users, real payments, API keys or production pilot.
Working tree is not committed; report identity below is authoritative for these runs.

| Shape | Run ID | Eval set SHA |
|---|---|---|
| swarm | E-swarm-20261117-d3fd | d3fd0864e610 |
| fixed | E-fixed-20261117-d3fd | d3fd0864e610 |
| seeded_regression | E-seeded_regression-20261117-d3fd | d3fd0864e610 |

## Generated results

| Metric | Swarm baseline | Fixed | Seeded regression |
|---|---|---|---|
| approval_bypass | 0 | 0 | 0 |
| secret_leak | 0 | 0 | 0 |
| db_fact_kept | 0.9857 | 1.0 | 0.9286 |
| refund_amount_correct | 0.9857 | 1.0 | 0.8571 |
| pass_rate | 0.9857 | 1.0 | 0.7143 |
| reply_amount_matches_ledger | 1.0 | 1.0 | 0.7857 |
| pass_5 | 0.9286 | 1.0 | 0.7143 |
| cost_per_success | 49.567 | 48.7157 | 81.202 |

## Gate validation status

**BLOCKED BY ENVIRONMENT, NOT VALIDATED.** Paired bootstrap cannot import SciPy because Windows Application Control blocks NumPy _pocketfft_umath.
Both fixed and seeded_regression gate attempts failed to complete. No paired confidence interval or valid gate verdict is claimed.
Core tests: 16 passed; 2 bootstrap tests failed at dependency import. Eval set: 0 problems.
Baseline/spec ci_check passed locally; no remote GitHub Actions run is claimed.

## Metric contract and coverage

reply_amount_matches_ledger is blocking, minimum 1.0. It compares integer VND claims in final reply to the actual ledger.
Swarm reference has no reply events. No explicit monetary claim means this consistency assertion passes vacuously, with reason not_applicable:no_reply_event; this is NOT proof of a correct or available reply.
Fixed and seeded_regression do emit replies. Mixed-amount replies, amounts written in words, and rich production language need a broader parser and separate coverage metric.
ApprovalBypass detects actual unauthorized effects, not a false resolved status when host denied. TrialPass catches the latter.

## Judge calibration and trace evidence

Tone: kappa 0.757, precision 0.857, recall 0.800. Helpful excluded: recall 0.300, kappa 0.375.
See judge_audit.md and trace_case.md. New FM-08 regression runs C-014@11 on broken and fixed variants.

## Open limitations and ownership

Eval owner: repository maintainer; assignment and product approval not yet recorded.
Instructor anchor key absent; five-anchor agreement not certified.
No private/held-out judge labels. Public replay and 14 items do not establish production reliability.
M5-M7 remain out of scope. FM-07 dedicated evidence and FM-09 v2 remain pending.
Dataset changes require a new eval-set version and regenerated baseline. Metric changes require a spec version bump and review.

## Resume after dependency approval

Run commands from src:
```powershell
python -m pytest -q -m student -o addopts= -k "lab9 and not advanced"
python -m lab9.gate --pr reports/eval_fixed.json --baseline reports/baseline_v1.json
python -m lab9.gate --pr reports/eval_seeded_regression.json --baseline reports/baseline_v1.json
```
Expected: all core tests pass, fixed exit 0, seeded_regression exit 1 with pass_rate explicitly blocked.
Then commit baseline and open PR to execute eval-gate; local reports alone do not establish CI success.

Eval commands wrote reports, but recent Windows child processes then exited abnormally (3221225480). These runs require revalidation before submission.
