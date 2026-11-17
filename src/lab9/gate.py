"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    for entry in [*spec.get("metrics", []), *spec.get("slices", [])]:
        threshold = entry.get("threshold", entry)
        for key in ("min", "max", "max_increase"):
            if key in threshold and (type(threshold[key]) not in (int, float)
                                      or not math.isfinite(threshold[key])):
                problems.append(f"invalid spec threshold {entry.get('id', entry.get('name'))}/{key}")
    row_metrics = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]
    pairs = {}
    for name, report in (("PR", pr), ("baseline", base)):
        manifest = report.get("manifest", {})
        rows = report.get("rows", [])
        if not isinstance(manifest, dict) or not isinstance(rows, list) or not isinstance(report.get("metrics"), dict):
            return [f"{name}: malformed manifest, rows or metrics"]
        if any(not isinstance(row, dict) for row in rows):
            return [f"{name}: malformed row"]
        seeds = manifest.get("seeds", [])
        items = manifest.get("items", 0)
        if not rows or not seeds or len(set(seeds)) != len(seeds):
            problems.append(f"{name}: empty rows/seeds or duplicate manifest seeds")
        if len(rows) != items * len(seeds):
            problems.append(f"{name}: row count != items x seeds")
        keys = [(r.get("item_id"), r.get("seed")) for r in rows]
        if len(set(keys)) != len(keys):
            problems.append(f"{name}: duplicate item/seed rows")
        ids = {r.get("item_id") for r in rows}
        if len(ids) != items or set(keys) != {(i, s) for i in ids for s in seeds}:
            problems.append(f"{name}: incomplete item x seed grid")
        pairs[name] = {key: row for key, row in zip(keys, rows)}
        if report.get("evaluator_failures"):
            problems.append(f"{name}: evaluator failures")
        metrics = report.get("metrics", {})
        for mid, value in metrics.items():
            if type(value) not in (int, float) or not math.isfinite(value):
                problems.append(f"{name}: non-finite/missing metric {mid}")
        for m in spec.get("metrics", []):
            if m["id"] not in metrics:
                problems.append(f"{name}: missing metric {m['id']}")
        for row in rows:
            for mid in row_metrics:
                if type(row.get(mid)) is not bool:
                    problems.append(f"{name}: invalid grader value {mid} at {row.get('item_id')}@{row.get('seed')}")
            if "cost" in row and (not isinstance(row["cost"], (int, float))
                                   or not math.isfinite(row["cost"]) or row["cost"] < 0):
                problems.append(f"{name}: invalid cost")
        # Do not trust a polished headline that disagrees with its evidence.
        for mid in row_metrics:
            values = [r.get(mid) for r in rows]
            if values and all(type(v) is bool for v in values):
                actual = sum(values) if mid in {"secret_leak", "approval_bypass"} else round(sum(values) / len(values), 4)
                value = metrics.get(mid)
                if isinstance(value, (int, float)) and math.isfinite(value) and abs(value - actual) > 1e-9:
                    problems.append(f"{name}: aggregate {mid} disagrees with rows")
        if rows and all(type(r.get("pass_rate")) is bool for r in rows):
            counts = {i: [r["pass_rate"] for r in rows if r.get("item_id") == i] for i in ids}
            for mid, value in metrics.items():
                if mid == "pass_5":
                    expected = sum(all(v) for v in counts.values()) / len(counts)
                elif mid.startswith(("pass_at_", "pass_hat_")) and mid.rsplit("_", 1)[-1].isdigit():
                    k = int(mid.rsplit("_", 1)[-1])
                    fn = stats.pass_at_k if mid.startswith("pass_at_") else stats.pass_hat_k
                    if any(len(v) < k for v in counts.values()):
                        problems.append(f"{name}: insufficient seeds for {mid}")
                        continue
                    expected = sum(fn(len(v), sum(v), k) for v in counts.values()) / len(counts)
                else:
                    continue
                if isinstance(value, (int, float)) and math.isfinite(value) and abs(value - round(expected, 4)) > 1e-9:
                    problems.append(f"{name}: aggregate {mid} disagrees with rows")
    if set(pairs["PR"]) != set(pairs["baseline"]):
        problems.append("PR item/seed set differs from baseline")
    if set(pr.get("manifest", {}).get("seeds", [])) != set(base.get("manifest", {}).get("seeds", [])):
        problems.append("manifest seeds differ from baseline")
    if "seeds" in spec and set(pr.get("manifest", {}).get("seeds", [])) != set(spec["seeds"]):
        problems.append("manifest seeds differ from spec")
    for key in set(pairs["PR"]) & set(pairs["baseline"]):
        if set(pairs["PR"][key].get("slices", [])) != set(pairs["baseline"][key].get("slices", [])):
            problems.append(f"slice relabeling at {key}")
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        def ratchet(old, new, label):
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"ratchet: {label} became non-blocking")
            for key, value in old.items():
                if key == "min" and (key not in new or new[key] < value):
                    problems.append(f"ratchet: {label} lowered/removed min")
                if key in {"max", "max_increase"} and (key not in new or new[key] > value):
                    problems.append(f"ratchet: {label} raised/removed {key}")
                if key == "no_significant_drop" and value and not new.get(key):
                    problems.append(f"ratchet: {label} removed significance check")
        current = {m["id"]: m for m in spec.get("metrics", [])}
        for old in base_spec.get("metrics", []):
            new = current.get(old["id"])
            if new is None:
                problems.append(f"ratchet: removed metric {old['id']}")
                continue
            ratchet({**old.get("threshold", {}), "blocking": old.get("blocking", False)},
                    {**new.get("threshold", {}), "blocking": new.get("blocking", False)}, old["id"])
            for key in ("kind", "level", "grader"):
                if key in old and new.get(key) != old[key]:
                    problems.append(f"ratchet: changed {old['id']} {key}")
        current_slices = {(s["name"], s["metric"]): s for s in spec.get("slices", [])}
        for old in base_spec.get("slices", []):
            key = (old["name"], old["metric"])
            if key not in current_slices:
                problems.append(f"ratchet: removed slice {key}")
            else:
                ratchet(old, current_slices[key], f"slice:{key}")
    return list(dict.fromkeys(problems))


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for entry in spec.get("slices", []):
        name, metric = entry["name"], entry["metric"]
        mid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, name), per_item(base, metric, name)
        failed, note = False, ""
        if not a or set(a) != set(b):
            value, failed, note = None, True, "missing/mismatched slice items"
        else:
            value = sum(a.values()) / len(a)
            failed = "min" in entry and value < entry["min"]
            if entry.get("no_significant_drop"):
                keys = sorted(a)
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95))
                failed |= hi < 0
                note = f"delta {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
        if failed and entry.get("blocking"):
            blocked.append(mid)
        verdict = "BLOCK" if failed and entry.get("blocking") else "warn" if failed else "ok"
        lines.append(f"  {mid} {value} {note} {verdict}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                               confidence=bs.get("confidence", 0.95))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
