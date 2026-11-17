"""FM-08 regression checks, including real agent trials without Lab 8 edits."""
import pytest

pytestmark = pytest.mark.student


def ctx(output, label=None):
    from pydantic_evals.evaluators import EvaluatorContext
    return EvaluatorContext(name="reply", inputs={}, metadata=None,
                            expected_output=label or {}, output=output,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def trial(refund_vnd=35000, events=()):
    return {"snapshot": {"refund_vnd": refund_vnd}, "events": list(events), "result": {}}


@pytest.mark.parametrize("text", ["Hoan 120.000đ", "Hoan 120,000 VND", "Hoan 120000d"])
def test_lab9_reply_amount_formats(text):
    from lab9.graders import ReplyAmountMatchesLedger
    t = trial(refund_vnd=120000, events=[{"kind": "reply", "payload": {"text": text}}])
    assert ReplyAmountMatchesLedger().evaluate(ctx(t)).value is True


def test_lab9_reply_mismatch_fails():
    from lab9.graders import ReplyAmountMatchesLedger
    t = trial(refund_vnd=90000, events=[{"kind": "reply", "payload": {"text": "Hoan 120.000đ"}}])
    assert ReplyAmountMatchesLedger().evaluate(ctx(t)).value is False


def test_lab9_reply_missing_amount_on_resolved_fails():
    from lab9.graders import ReplyAmountMatchesLedger
    t = trial(events=[{"kind": "reply", "payload": {"text": "Da hoan tien"}}])
    t["result"] = {"status": "resolved"}
    assert ReplyAmountMatchesLedger().evaluate(ctx(t)).value is False


def test_lab9_legacy_no_reply_has_explicit_coverage_reason():
    from lab9.graders import ReplyAmountMatchesLedger
    verdict = ReplyAmountMatchesLedger().evaluate(ctx(trial()))
    assert verdict.reason == "not_applicable:no_reply_event"


def test_lab9_trace_case_c014_regression_and_fixed():
    from lab9.graders import ReplyAmountMatchesLedger, RefundAmountCorrect
    from lab9.trace_case import investigate
    for shape, expected in [("seeded_regression", False), ("fixed", True)]:
        case = investigate(shape, "C-014", 11)
        context = ctx(case["trial"], case["label"])
        assert RefundAmountCorrect().evaluate(context).value is expected
        assert ReplyAmountMatchesLedger().evaluate(context).value is expected


def test_lab9_c013_zero_ledger_does_not_hide_wrong_proposal():
    from lab9.graders import ProposalAmountCorrect, RefundAmountCorrect
    from lab9.trace_case import investigate
    for shape, expected in [("seeded_regression", False), ("fixed", True)]:
        case = investigate(shape, "C-013", 11)
        context = ctx(case["trial"], case["label"])
        assert RefundAmountCorrect().evaluate(context).value is True
        assert ProposalAmountCorrect().evaluate(context).value is expected
