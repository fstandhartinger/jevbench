"""Adapter conformance kit: run an adapter on synthetic tasks, report contract violations.

The checks mirror what jevbench/runner.py and jevbench/scoring.py actually do
with an adapter (see docs/ADAPTERS.md for the rule-by-rule citations). Nothing
here is scored or published, and nothing here changes scoring: distributions
are judged with the same scoring.score_task / scoring.score_label the runner
uses.

    from jevbench.adapters.conformance import check_adapter
    report = check_adapter(MyAdapter())
    print(report.summary())
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..scoring import score_label, score_task
from ..tasks import Task
from .base import DecisionResult

LABEL_ONLY = "label_only_no_calibrated_distribution"  # runner.py:244, needle_local.py:36

# ---------------------------------------------------------------------------
# TEST FIXTURES ONLY. These are invented smoke-test inputs for the adapter
# contract. They are NOT benchmark items, are not part of any split's scoring,
# and must never be copied into datasets/.
# ---------------------------------------------------------------------------
_FIXTURES = [
    {"id": "conformance-fixture-noul", "family": "policy",
     "state": "Fixture text: the parcel weighs 2 kg; the limit is 5 kg.",
     "question": {"type": "noul", "instructions": "Fixture: is the parcel within the limit?",
                  "criteria": {"true": "Within the limit", "false": "Over the limit"}},
     "labels": ["no", "yes"], "expected": "yes"},
    {"id": "conformance-fixture-choice", "family": "intent",
     "state": "Fixture text: please send me a copy of last month's invoice.",
     "question": {"type": "choice", "instructions": "Fixture: which intent?",
                  "criteria": {"billing": "About invoices or payments",
                               "shipping": "About delivery", "other": "Anything else"}},
     "labels": ["billing", "shipping", "other"], "expected": "billing"},
    {"id": "conformance-fixture-score", "family": "ordinal",
     "state": {"fixture_note": "Structured state", "reply": "Thanks, fixed."},
     "question": {"type": "score", "instructions": "Fixture: how complete is the reply?",
                  "criteria": ["Empty", "Partial", "Complete"]},
     "labels": ["0", "1", "2"], "expected": 2},
    {"id": "conformance-fixture-unmeasured", "family": "routing",
     "state": "Fixture text with no ground truth.",
     "question": {"type": "choice", "instructions": "Fixture: which queue?", "criteria": None},
     "labels": ["a", "b"], "expected": None},
]


def fixture_tasks() -> list:
    """Fresh Task objects for the synthetic fixtures (validated like real records)."""
    return [Task.from_dict({**d, "split": "public", "group": None,
                            "provenance": {"source": "conformance test fixture",
                                           "exclude_reason": "not a benchmark item"}})
            for d in _FIXTURES]


@dataclass
class ConformanceReport:
    adapter: str
    violations: list = field(default_factory=list)  # [(task_id or "-", message)]
    warnings: list = field(default_factory=list)  # scored, but worth fixing
    checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.violations

    def add(self, where: str, msg: str) -> None:
        self.violations.append((where, msg))

    def summary(self) -> str:
        head = (f"{self.adapter}: {self.checked} fixture tasks, {len(self.violations)} violation(s), "
                f"{len(self.warnings)} warning(s)")
        return "\n".join([head] + [f"  [{w}] {m}" for w, m in self.violations]
                         + [f"  warning [{w}] {m}" for w, m in self.warnings])


def check_adapter(adapter, tasks=None) -> ConformanceReport:
    """Run `adapter` on fixture tasks (or `tasks`) and collect contract violations.

    Calls adapter.prepare(task) when present, then adapter.run(task), exactly
    once per task and without retries. Network, ledger and raw-evidence files
    are not touched; the adapter itself decides whether it talks to anything.
    """
    rep = ConformanceReport(adapter=str(getattr(adapter, "name", type(adapter).__name__)))
    name = getattr(adapter, "name", None)
    if not isinstance(name, str) or not name:
        rep.add("-", "missing str attribute `name` (runner.py:216)")
    for attr in ("price_input_per_m", "price_output_per_m"):
        if not hasattr(adapter, attr):
            rep.add("-", f"missing attribute `{attr}`; use None when unknown (runner.py:232)")
    for meth in ("run", "reserve_estimate"):
        if not callable(getattr(adapter, meth, None)):
            rep.add("-", f"missing method `{meth}(task)` (runner.py:215,226)")
    if not callable(getattr(adapter, "run", None)):
        return rep

    for t in tasks if tasks is not None else fixture_tasks():
        rep.checked += 1
        _check_one(adapter, t, rep)
    return rep


def _check_one(adapter, t, rep) -> None:
    if callable(getattr(adapter, "reserve_estimate", None)):
        try:
            est = adapter.reserve_estimate(t)
            if est is not None and (isinstance(est, bool) or not isinstance(est, (int, float))
                                    or not est >= 0 or est == float("inf")):
                rep.add(t.id, f"reserve_estimate returned {est!r}; need None or a finite float >= 0 (budget.py:147)")
        except Exception as e:  # noqa: BLE001
            rep.add(t.id, f"reserve_estimate raised {type(e).__name__} (runner.py:215 does not catch it)")
    if callable(getattr(adapter, "prepare", None)):
        try:
            adapter.prepare(t)
        except Exception as e:  # noqa: BLE001
            rep.add(t.id, f"prepare raised {type(e).__name__}: {str(e)[:120]}")
    try:
        r = adapter.run(t)
    except Exception as e:  # noqa: BLE001
        rep.add(t.id, f"run raised {type(e).__name__}; the runner records this as a failed attempt "
                      "(runner.py:227) - return DecisionResult(ok=False, error=...) instead")
        return
    if not isinstance(r, DecisionResult):
        rep.add(t.id, f"run returned {type(r).__name__}, not DecisionResult (base.py:16)")
        return
    try:
        json.dumps({"request": r.request_body, "response": r.raw, "http_status": r.status},
                   ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as e:
        rep.add(t.id, f"request_body/raw not JSON-safe ({e}); the runner would crash (runner.py:229)")
    if r.usage is not None and not isinstance(r.usage, dict):
        rep.add(t.id, "usage must be a dict (runner.py:239)")
    if not r.ok:
        if not r.error:
            rep.add(t.id, "ok=False without an `error` message")
        return
    if r.probs is None and r.probs_source == LABEL_ONLY:
        s = score_label(r.label, t)
        if r.label is not None and not s["valid"]:
            rep.add(t.id, f"label {r.label!r} not in labels {t.labels} (scoring.py:134)")
        return
    if r.probs is None:
        rep.add(t.id, "ok=True but probs is None; label-only systems must set "
                      f"probs_source={LABEL_ONLY!r} (runner.py:244)")
        return
    s = score_task(r.probs, t)
    if not s["valid"]:
        rep.add(t.id, f"invalid distribution: {s.get('error')} (scoring.py:27)")
    elif not s["strict_valid"]:
        rep.warnings.append((t.id, "distribution only valid after renormalisation (sum outside SUM_TOL, "
                      "inside RENORM_TOL; scoring.py:11-20); headline-valid but not strict-valid"))
    if r.probs_source not in ("native", "verbalized"):
        rep.add(t.id, f"probs_source {r.probs_source!r}; expected 'native' or 'verbalized' (base.py:20)")
