"""Tests for NullspanLocalAdapter (offline, no network or weight downloads)."""

from __future__ import annotations

from pathlib import Path
import tomllib

import pytest

from jevbench import cli
from jevbench.adapters import NullspanLocalAdapter
from jevbench.adapters.conformance import check_adapter, fixture_tasks
from jevbench.tasks import Task


def _task(qtype, criteria, labels, state="The item state.", expected="sentinel"):
    exp = labels[0] if expected == "sentinel" else expected
    return Task(
        id="t-nullspan",
        family="policy",
        state=state,
        labels=labels,
        expected=exp,
        split="public",
        question={"type": qtype, "instructions": "Decide this.", "criteria": criteria},
    )


class _FakeEngine:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = []

    def decide(self, state, questions, max_length=None):
        self.calls.append((state, questions))
        if self.fail:
            raise RuntimeError("synthetic engine failure")
        q = questions["decision"]
        qtype = q["type"]
        if qtype == "noul":
            return {
                "model": "gnumanth/nullspan",
                "answers": {
                    "decision": {
                        "type": "noul",
                        "noul": 0.75,
                        "probabilities": {"yes": 0.75, "no": 0.25},
                    }
                },
                "usage": {"input_tokens": 42, "output_tokens": 0},
            }
        if qtype == "score":
            crit = q["criteria"]
            n = len(crit)
            p = 1.0 / n
            probs = {str(i): p for i in range(n)}
            return {
                "model": "gnumanth/nullspan",
                "answers": {
                    "decision": {
                        "type": "score",
                        "score": sum(i * p for i in range(n)),
                        "probabilities": probs,
                    }
                },
                "usage": {"input_tokens": 54, "output_tokens": 0},
            }
        crit = q["criteria"]
        keys = list(crit.keys())
        probs = {k: (0.7 if idx == 0 else 0.3 / max(1, len(keys) - 1)) for idx, k in enumerate(keys)}
        if len(keys) == 1:
            probs = {keys[0]: 1.0}
        return {
            "model": "gnumanth/nullspan",
            "answers": {
                "decision": {
                    "type": "choice",
                    "choice": keys[0],
                    "probabilities": probs,
                }
            },
            "usage": {"input_tokens": 38, "output_tokens": 0},
        }


def test_nullspan_build_request_covers_all_primitives_and_excludes_gold():
    c = NullspanLocalAdapter.build_request(
        _task("choice", {"billing": "Invoices", "other": None}, ["billing", "other"])
    )
    assert c == {
        "state": "The item state.",
        "questions": {
            "decision": {
                "type": "choice",
                "instructions": "Decide this.",
                "criteria": {"billing": "Invoices", "other": "other"},
            }
        },
    }
    assert "expected" not in str(c)

    c_nocrit = NullspanLocalAdapter.build_request(
        _task("choice", None, ["a", "b"], expected=None)
    )
    assert c_nocrit["questions"]["decision"]["criteria"] == {"a": "a", "b": "b"}

    n = NullspanLocalAdapter.build_request(
        _task("noul", {"true": "Within limit", "false": "Over limit"}, ["no", "yes"])
    )
    assert n["questions"]["decision"] == {
        "type": "noul",
        "instructions": "Decide this.",
        "criteria": {"true": "Within limit", "false": "Over limit"},
    }

    s = NullspanLocalAdapter.build_request(
        _task("score", ["Empty", "Partial", "Complete"], ["0", "1", "2"])
    )
    assert s["questions"]["decision"] == {
        "type": "score",
        "instructions": "Decide this.",
        "criteria": ["Empty", "Partial", "Complete"],
    }


def test_nullspan_conformance_and_token_accounting(monkeypatch):
    adapter = NullspanLocalAdapter()
    assert adapter.name == "nullspan_local"
    assert adapter.cost_basis == "self_hosted_gpu"
    assert adapter.endpoint == "gnumanth/nullspan"
    assert adapter.revision == "51acf9e097ade3fb1068b3511490ef2756485927"

    fake = _FakeEngine()
    monkeypatch.setattr(adapter, "load", lambda: fake)

    rep = check_adapter(adapter)
    assert rep.ok, rep.summary()
    assert rep.checked == len(fixture_tasks())
    assert rep.warnings == []

    res = adapter.run(_task("noul", {"true": "Yes", "false": "No"}, ["no", "yes"]))
    assert res.ok
    assert res.probs == {"yes": 0.75, "no": 0.25}
    assert res.probs_source == "native"
    assert res.usage == {"input_tokens": 42, "output_tokens": 0}


def test_nullspan_errors_return_decision_result_without_raising(monkeypatch):
    adapter = NullspanLocalAdapter()
    monkeypatch.setattr(adapter, "load", lambda: _FakeEngine(fail=True))
    res = adapter.run(_task("choice", {"a": "Alpha", "b": "Beta"}, ["a", "b"]))
    assert not res.ok
    assert "RuntimeError: synthetic engine failure" in (res.error or "")


def test_cli_accepts_nullspan_local_without_endpoint(tmp_path, monkeypatch):
    tasks_path = tmp_path / "tasks.jsonl"
    tasks_path.write_text(
        '{"id":"t1","family":"f","split":"public","state":"ok","labels":["no","yes"],'
        '"expected":"yes","question":{"type":"noul","instructions":"Is it ok?","criteria":{"true":"Yes","false":"No"}}}\n',
        encoding="utf-8",
    )
    out_path = tmp_path / "res.jsonl"
    ledger_path = tmp_path / "ledger.jsonl"
    raw_dir = tmp_path / "raw"

    monkeypatch.setattr(NullspanLocalAdapter, "load", lambda self: _FakeEngine())
    rc = cli.main([
        "run",
        "--tasks", str(tasks_path),
        "--adapter", "nullspan_local",
        "--results", str(out_path),
        "--ledger", str(ledger_path),
        "--raw-dir", str(raw_dir),
    ])
    assert rc == 0
    assert out_path.exists()


def test_pyproject_pins_exact_nullspan_version():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert data["project"]["optional-dependencies"]["nullspan"] == ["nullspan[hf]==1.3.1"]

