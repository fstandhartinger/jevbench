"""Conformance kit: a well-behaved mock adapter passes, broken ones are caught."""

from jevbench.adapters.base import DecisionResult
from jevbench.adapters.conformance import LABEL_ONLY, check_adapter, fixture_tasks


class GoodAdapter:
    """Uniform distribution over the exact labels; no network."""
    name = "mock_good"
    price_input_per_m = None
    price_output_per_m = None

    def reserve_estimate(self, task):
        return 0.0

    def run(self, task):
        p = 1.0 / len(task.labels)
        return DecisionResult(adapter=self.name, ok=True, probs={lab: p for lab in task.labels},
                              probs_source="native", model="mock", raw={"runtime": {}},
                              usage={"input_tokens": 1, "output_tokens": 0})


class LabelOnlyAdapter(GoodAdapter):
    name = "mock_label_only"

    def run(self, task):
        return DecisionResult(adapter=self.name, ok=True, probs=None, probs_source=LABEL_ONLY,
                              label=task.labels[0])


class BadAdapter:
    """Breaks one rule per question type and forgets price attributes."""
    name = "mock_bad"

    def reserve_estimate(self, task):
        return float("nan")

    def run(self, task):
        qtype = task.question["type"]
        if qtype == "noul":
            return DecisionResult(adapter=self.name, ok=True, probs={"true": 0.7, "false": 0.3},
                                  probs_source="native")
        if qtype == "score":
            return DecisionResult(adapter=self.name, ok=True, probs={0: 0.2, 1: 0.3, 2: 0.5},
                                  probs_source="logprobs", raw={"x": float("nan")})
        if task.expected is None:
            raise RuntimeError("boom")
        return DecisionResult(adapter=self.name, ok=True, probs=None, label="billing")


def test_fixtures_are_marked_and_cover_all_types():
    tasks = fixture_tasks()
    assert 3 <= len(tasks) <= 6
    assert {t.question["type"] for t in tasks} == {"noul", "choice", "score"}
    assert all(t.id.startswith("conformance-fixture-") for t in tasks)
    assert all(t.provenance["exclude_reason"] for t in tasks)


def test_good_adapter_passes():
    rep = check_adapter(GoodAdapter())
    assert rep.ok, rep.summary()
    assert rep.checked == len(fixture_tasks())


def test_label_only_adapter_passes():
    rep = check_adapter(LabelOnlyAdapter())
    assert rep.ok, rep.summary()


def test_bad_adapter_violations_reported():
    rep = check_adapter(BadAdapter())
    assert not rep.ok
    text = rep.summary()
    assert "price_input_per_m" in text and "price_output_per_m" in text
    assert "reserve_estimate returned nan" in text
    assert "label keys mismatch" in text            # noul with true/false keys
    assert "not JSON-safe" in text                  # NaN in raw
    assert "probs_source 'logprobs'" in text        # score: int keys + bad source
    assert "probs is None" in text                  # choice without label-only marker
    assert "run raised RuntimeError" in text        # unmeasured fixture


def test_renormalised_distribution_is_warning_not_violation():
    class Rounded(GoodAdapter):
        def run(self, task):
            r = super().run(task)
            r.probs = {k: v * 1.01 for k, v in r.probs.items()}
            return r
    rep = check_adapter(Rounded())
    assert rep.ok and len(rep.warnings) == len(fixture_tasks())
