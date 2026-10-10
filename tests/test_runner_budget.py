"""Offline unit tests for jevbench/runner.py and jevbench/budget.py.

Mock adapters in this file return fixed typed answers, raise, "time out" or
overrun their reservation. The tests pin what the runner and ledger record
today; they make no network calls and write only under tmp_path.
"""
import json
import math
from types import SimpleNamespace

import pytest

from jevbench import runner as runner_mod
from jevbench.adapters.base import DecisionResult
from jevbench.budget import BudgetExceeded, Ledger, PriceTable, finite
from jevbench.runner import Runner
from jevbench.tasks import Task


def task(tid, expected="yes", qtype="noul", labels=("no", "yes")):
    return Task(id=tid, family="fam", state={"x": 1},
                question={"type": qtype, "instructions": "decide"},
                labels=list(labels), expected=expected, split="public", group="g1")


class FakeClock:
    """Deterministic stand-in for the runner's `time` module."""

    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def perf_counter(self):
        return self.now

    def time(self):
        return 1_700_000_000.0

    def sleep(self, s):
        self.sleeps.append(s)


@pytest.fixture
def clock(monkeypatch):
    c = FakeClock()
    monkeypatch.setattr(runner_mod, "time", SimpleNamespace(
        perf_counter=c.perf_counter, time=c.time, sleep=c.sleep))
    return c


class MockAdapter:
    """Returns scripted outcomes in order: a DecisionResult or an exception."""

    name = "mock"
    price_input_per_m = None
    price_output_per_m = None

    def __init__(self, outcomes, clock=None, elapsed=0.0, estimate=None):
        self.outcomes = list(outcomes)
        self.clock = clock
        self.elapsed = elapsed
        self.estimate = estimate
        self.calls = []

    def reserve_estimate(self, t):
        return self.estimate

    def run(self, t):
        self.calls.append(t.id)
        if self.clock is not None:
            self.clock.now += self.elapsed
        out = self.outcomes.pop(0)
        if isinstance(out, BaseException):
            raise out
        return out


def ok(probs=None, **kw):
    kw.setdefault("model", "m-1")
    kw.setdefault("status", 200)
    return DecisionResult("mock", True, probs=probs, probs_source="native", **kw)


def failed(status, error="http_error"):
    return DecisionResult("mock", False, status=status, error=error)


def make(tmp_path, adapter, cap=1.0, **kw):
    ledger = Ledger(tmp_path / "ledger.jsonl", cap_usd=cap)
    return Runner(adapter, ledger, tmp_path / "raw", **kw), ledger


def ledger_rows(tmp_path):
    return [json.loads(l) for l in (tmp_path / "ledger.jsonl").read_text().splitlines()]


# ---------------------------------------------------------------- budget.py


@pytest.mark.parametrize("bad", [-0.01, math.nan, math.inf, -math.inf])
def test_finite_rejects_negative_and_nonfinite(bad):
    with pytest.raises(BudgetExceeded):
        finite(bad)


def test_finite_coerces_to_float():
    assert finite(0) == 0.0 and isinstance(finite(3), float)
    assert finite("0.5") == 0.5


def test_price_table_estimate_and_unknown():
    assert PriceTable(2.0, 10.0).estimate(1000, 100) == pytest.approx(0.003)
    assert not PriceTable(2.0, None).known
    with pytest.raises(BudgetExceeded):
        PriceTable(None, 1.0).estimate(1, 1)


def test_ledger_reserve_settle_and_charged(tmp_path):
    led = Ledger(tmp_path / "l.jsonl", cap_usd=1.0)
    assert led.charged == 0
    rid = led.reserve(0.4, {"task_id": "a"})
    assert led.charged == pytest.approx(0.4)  # unsettled reservation stays charged
    led.settle(rid, 0.1)
    assert led.charged == pytest.approx(0.1)
    rows = [json.loads(l) for l in (tmp_path / "l.jsonl").read_text().splitlines()]
    assert [r["event"] for r in rows] == ["cap", "reserve", "settle"]
    assert rows[0]["cap_usd"] == 1.0
    assert rows[1]["meta"] == {"task_id": "a"} and rows[2]["charged_usd"] == 0.1


def test_ledger_refuses_reservation_over_cap_without_writing(tmp_path):
    led = Ledger(tmp_path / "l.jsonl", cap_usd=1.0)
    led.reserve(0.7)
    with pytest.raises(BudgetExceeded, match="request not sent"):
        led.reserve(0.31)
    assert led.charged == pytest.approx(0.7)
    led.reserve(0.3)  # exactly at the cap is allowed
    assert led.charged == pytest.approx(1.0)


def test_ledger_first_written_cap_wins_unless_lower(tmp_path):
    p = tmp_path / "l.jsonl"
    Ledger(p, cap_usd=1.0).reserve(0.5)
    with pytest.raises(BudgetExceeded):  # a higher cap later cannot raise the stored one
        Ledger(p, cap_usd=20).reserve(0.6)
    with pytest.raises(BudgetExceeded):  # a lower cap applies for that instance
        Ledger(p, cap_usd=0.6).reserve(0.2)
    caps = [json.loads(l) for l in p.read_text().splitlines() if '"cap"' in l]
    assert len(caps) == 1


def test_ledger_settle_errors(tmp_path):
    led = Ledger(tmp_path / "l.jsonl", cap_usd=1.0)
    with pytest.raises(BudgetExceeded, match="Missing"):
        led.settle("nope", 0.0)
    rid = led.reserve(0.2)
    led.settle(rid, 0.2)
    with pytest.raises(BudgetExceeded, match="duplicate"):
        led.settle(rid, 0.1)


def test_ledger_overcharge_is_recorded_then_raises(tmp_path):
    led = Ledger(tmp_path / "l.jsonl", cap_usd=1.0)
    rid = led.reserve(0.1)
    with pytest.raises(BudgetExceeded, match="exceeded reserved maximum"):
        led.settle(rid, 0.25)
    assert led.charged == pytest.approx(0.25)


def test_ledger_rejects_invalid_settlement_history(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps({"event": "settle", "reservation_id": "x", "charged_usd": 0}) + "\n")
    with pytest.raises(BudgetExceeded, match="Invalid settlement history"):
        Ledger(p).charged


# ---------------------------------------------------------------- runner.py


def test_runner_refuses_raw_dir_inside_repo(tmp_path):
    repo = runner_mod.Path(runner_mod.__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="outside public repository"):
        Runner(MockAdapter([]), Ledger(tmp_path / "l"), repo / "raw_should_not_exist")
    assert not (repo / "raw_should_not_exist").exists()


def test_run_task_records_typed_answer_timing_and_raw(tmp_path, clock):
    a = MockAdapter([ok({"no": 0.2, "yes": 0.8}, usage={"input_tokens": 10},
                        raw={"runtime": "cpu", "out": "yes"}, request_body={"q": 1})],
                    clock=clock, elapsed=1.5)
    r, led = make(tmp_path, a)
    rec = r.run_task(task("t1"))
    assert rec["status"] == "ok" and rec["ok"] is True
    assert rec["valid"] is True and rec["strict_valid"] is True and rec["renormalized"] is False
    assert rec["predicted"] == "yes" and rec["correct"] is True
    assert rec["probs"] == {"no": 0.2, "yes": 0.8}
    assert rec["probs_as_returned"] == {"no": 0.2, "yes": 0.8}
    assert rec["latency_s"] == 1.5 and rec["ts"] == 1_700_000_000.0
    assert rec["model"] == "m-1" and rec["status_code"] == 200 and rec["error"] is None
    assert rec["runtime"] == "cpu" and rec["usage"] == {"input_tokens": 10}
    assert (rec["family"], rec["split"], rec["group"]) == ("fam", "public", "g1")
    assert "prepare_s" not in rec
    # unknown price: cost stays null and the reservation is kept as the charge
    assert rec["cost_usd"] is None and rec["cost_basis"] == "unknown"
    assert rec["reserved_usd"] == 0.02 and rec["charged_usd"] == 0.02
    assert led.charged == pytest.approx(0.02)
    raw_files = list((tmp_path / "raw").iterdir())
    assert len(raw_files) == 1
    raw = raw_files[0].read_bytes()
    assert json.loads(raw) == {"request": {"q": 1}, "response": {"runtime": "cpu", "out": "yes"},
                               "http_status": 200}
    assert rec["raw_sha256"] == runner_mod.hashlib.sha256(raw).hexdigest()


def test_run_task_wrong_and_renormalized_answer(tmp_path, clock):
    a = MockAdapter([ok({"no": 0.6, "yes": 0.41})])
    rec = make(tmp_path, a)[0].run_task(task("t1"))
    assert rec["valid"] is True and rec["strict_valid"] is False and rec["renormalized"] is True
    assert rec["predicted"] == "no" and rec["correct"] is False


def test_run_task_invalid_distribution_counts_wrong(tmp_path, clock):
    a = MockAdapter([ok({"no": 0.9, "yes": 0.9})])
    rec = make(tmp_path, a)[0].run_task(task("t1"))
    assert rec["ok"] is True and rec["valid"] is False and rec["correct"] is False
    assert rec["predicted"] is None and rec["schema_error"]


def test_run_task_label_only_answer(tmp_path, clock):
    res = DecisionResult("mock", True, label="yes", status=200,
                         probs_source="label_only_no_calibrated_distribution")
    rec = make(tmp_path, MockAdapter([res]))[0].run_task(task("t1"))
    assert rec["valid"] is True and rec["correct"] is True and rec["predicted"] == "yes"
    assert rec["probs"] is None and rec["probs_as_returned"] is None


@pytest.mark.parametrize("exc", [RuntimeError("boom"), TimeoutError("slow"), ConnectionError("x")])
def test_run_task_adapter_exception_becomes_failed_record(tmp_path, clock, exc):
    a = MockAdapter([exc], clock=clock, elapsed=30.0)
    r, led = make(tmp_path, a)
    rec = r.run_task(task("t1"))
    assert rec["status"] == "failed" and rec["ok"] is False
    assert rec["error"] == type(exc).__name__ and rec["status_code"] is None
    assert rec["valid"] is False and rec["correct"] is False and rec["predicted"] is None
    assert rec["latency_s"] == 30.0  # timing is kept even for a failure
    assert rec["charged_usd"] == 0.02 and led.charged == pytest.approx(0.02)
    raw = json.loads(next((tmp_path / "raw").iterdir()).read_text())
    assert raw == {"request": None, "response": None, "http_status": None}


def test_run_task_cost_from_usage_and_tariff(tmp_path, clock):
    a = MockAdapter([ok({"no": 0.0, "yes": 1.0}, usage={"input_tokens": 1000, "output_tokens": 100})])
    a.price_input_per_m, a.price_output_per_m = 2.0, 10.0
    r, led = make(tmp_path, a)
    rec = r.run_task(task("t1"))
    assert rec["cost_usd"] == pytest.approx(0.003)
    assert rec["cost_basis"] == "derived_usage_times_tariff"
    assert rec["charged_usd"] == pytest.approx(0.003) and rec["reserved_usd"] == 0.02
    assert led.charged == pytest.approx(0.003)
    assert ledger_rows(tmp_path)[-1]["meta"] == {"task_id": "t1", "basis": "derived_usage_times_tariff"}


def test_run_task_zero_price_route_is_zero_even_on_failure(tmp_path, clock):
    a = MockAdapter([failed(500)])
    a.price_input_per_m = a.price_output_per_m = 0
    rec = make(tmp_path, a)[0].run_task(task("t1"))
    assert rec["cost_usd"] == 0.0 and rec["cost_basis"] == "zero_route_fee_compute_excluded"


def test_run_task_reserve_estimate_raises_reservation(tmp_path, clock):
    a = MockAdapter([failed(500)], estimate=0.5)
    r, led = make(tmp_path, a)
    rec = r.run_task(task("t1"))
    assert rec["reserved_usd"] == 0.5 and rec["charged_usd"] == 0.5
    assert ledger_rows(tmp_path)[1]["reserved_usd"] == 0.5
    # an estimate below the default reserve does not lower it
    a2 = MockAdapter([failed(500)], estimate=0.001)
    rec2 = Runner(a2, led, tmp_path / "raw").run_task(task("t2"))
    assert rec2["reserved_usd"] == 0.02


def test_run_task_prepare_timed_and_failure_swallowed(tmp_path, clock, capsys):
    a = MockAdapter([ok({"no": 0.0, "yes": 1.0})])

    def prepare(t):
        clock.now += 4.0
        raise OSError("no program")

    a.prepare = prepare
    rec = make(tmp_path, a)[0].run_task(task("t1"))
    assert rec["prepare_s"] == 4.0 and rec["latency_s"] == 0.0 and rec["ok"] is True
    assert "prepare failed: OSError no program" in capsys.readouterr().out


def test_run_all_writes_stream_and_returns_records(tmp_path, clock):
    a = MockAdapter([ok({"no": 0.1, "yes": 0.9}), ok({"no": 0.9, "yes": 0.1})])
    r, _ = make(tmp_path, a)
    out = tmp_path / "runs" / "results.jsonl"
    recs = r.run_all([task("a"), task("b")], results_path=out, delay_s=0.5)
    assert [x["task_id"] for x in recs] == ["a", "b"]
    assert [x["correct"] for x in recs] == [True, False]
    assert [json.loads(l) for l in out.read_text().splitlines()] == recs
    assert clock.sleeps == [0.5]  # no delay before the first task
    with pytest.raises(FileExistsError):  # results files are never overwritten
        make(tmp_path / "again", MockAdapter([]))[0].run_all([], results_path=out)


def test_run_all_refuses_results_inside_repo(tmp_path):
    repo = runner_mod.Path(runner_mod.__file__).resolve().parents[1]
    r, _ = make(tmp_path, MockAdapter([]))
    with pytest.raises(ValueError, match="outside public repo"):
        r.run_all([], results_path=repo / "results" / "should_not_exist.jsonl")


def test_run_all_stops_when_budget_exhausted(tmp_path, clock, capsys):
    a = MockAdapter([ok({"no": 0, "yes": 1})] * 5)
    r, led = make(tmp_path, a, cap=0.05)  # room for two 0.02 reservations
    recs = r.run_all([task(str(i)) for i in range(5)])
    assert len(recs) == 2 and a.calls == ["0", "1"]
    assert "STOP: Shared job budget exhausted; request not sent" in capsys.readouterr().out
    assert led.charged == pytest.approx(0.04)


def test_run_all_overcharge_stops_and_drops_that_record(tmp_path, clock, capsys):
    a = MockAdapter([ok({"no": 0, "yes": 1}, usage={"input_tokens": 10_000, "output_tokens": 0})] * 2)
    a.price_input_per_m, a.price_output_per_m = 5.0, 5.0  # 0.05 actual vs 0.02 reserved
    r, led = make(tmp_path, a)
    out = tmp_path / "res.jsonl"
    recs = r.run_all([task("a"), task("b")], results_path=out)
    assert recs == [] and a.calls == ["a"]
    assert out.read_text() == ""
    assert "exceeded reserved maximum" in capsys.readouterr().out
    assert led.charged == pytest.approx(0.05)  # the ledger keeps the real charge
    assert len(list((tmp_path / "raw").iterdir())) == 1  # raw evidence kept


def test_run_all_three_consecutive_failures_stop(tmp_path, clock, capsys):
    a = MockAdapter([failed(500), RuntimeError("x"), failed(502), ok({"no": 0, "yes": 1})])
    recs = make(tmp_path, a)[0].run_all([task(str(i)) for i in range(4)])
    assert [x["status"] for x in recs] == ["failed"] * 3 and a.calls == ["0", "1", "2"]
    assert "consecutive infrastructure errors" in capsys.readouterr().out


def test_run_all_success_resets_failure_streak(tmp_path, clock):
    outs = [failed(500), failed(500), ok({"no": 0, "yes": 1}), failed(500), failed(500)]
    recs = make(tmp_path, MockAdapter(outs))[0].run_all([task(str(i)) for i in range(5)])
    assert len(recs) == 5


def test_run_all_422_is_not_counted_and_resets_streak(tmp_path, clock):
    # current behaviour: a 422 sets the consecutive-error counter back to 0
    outs = [failed(500), failed(500), failed(422), failed(500), failed(500), failed(422)]
    recs = make(tmp_path, MockAdapter(outs))[0].run_all([task(str(i)) for i in range(6)])
    assert len(recs) == 6 and all(not x["ok"] for x in recs)


@pytest.mark.parametrize("code", [401, 403, 429])
def test_run_all_access_or_rate_limit_stops_immediately(tmp_path, clock, code):
    a = MockAdapter([failed(code), ok({"no": 0, "yes": 1})])
    recs = make(tmp_path, a)[0].run_all([task("a"), task("b")])
    assert [x["status_code"] for x in recs] == [code] and a.calls == ["a"]


def test_run_all_progress_lines(tmp_path, clock, capsys):
    a = MockAdapter([ok({"no": 0, "yes": 1})] * 4)
    make(tmp_path, a)[0].run_all([task(str(i)) for i in range(4)], progress_every=2)
    out = capsys.readouterr().out
    assert "2/4 completed" in out and "4/4 completed" in out


def test_write_results_jsonl_and_no_overwrite(tmp_path):
    p = tmp_path / "out" / "r.jsonl"
    Runner.write_results([{"a": 1}, {"b": None}], p)
    assert p.read_text() == '{"a": 1}\n{"b": null}\n'
    with pytest.raises(FileExistsError):
        Runner.write_results([], p)
