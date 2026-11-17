# Judge audit

| Criterion | n | Kappa | Precision | Recall | Floors | Decision |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | PASS | Calibrated for tone on public replay |
| helpful | 100 | 0.375 | 1.000 | 0.300 | FAIL | Exclude from release gate |

## Disagreement review

| Case | Human | Judge | Review | Rubric correction |
|---|---|---|---|---|
| H-008 | FAIL | PASS | Agree with human per dataset CS tone convention: overly familiar wording. | Specify acceptable address forms and informal particles. |
| H-017 | FAIL | PASS | Agree with human under supplied context; age/context is not inferable from reply alone. | Provide recipient context and explicit address policy. |
| H-029 | FAIL | PASS | Agree with human: discourages further contact. | Judge whole sentence, not just polite opening words. |
| H-042 | PASS | FAIL | Agree with human: concise, polite and sufficient for tone. | Do not require apology in every reply. |
| H-051 | PASS | FAIL | Agree with human: dataset explicitly permits refund as a loanword. | List allowed terminology; do not reject English automatically. |

## Decision and limitations

Tone confusion: TP=24, FP=4, FN=6, TN=66. Helpful: TP=9, FP=0, FN=21, TN=70.
Helpful finds only 9 of 30 failures and misses 21, despite perfect precision. Kappa and recall fail floors.
Observed failure rates: tone 0.28, helpful 0.09; Rogan-Gladen corrects both to 0.30 on this calibration set.
Reviews above are analysis against the supplied CSV notes, not new independently collected human labels.
Money correctness must use ledger code checks, never politeness as a proxy. New held-out human labels are still needed.
