"""Numerical and publication checks for Florian's approved v1.4 settings."""

import json
from pathlib import Path

import pytest

from jevbench import composite_v14 as C

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "v1.4"


def read(name):
    return json.loads((DATA / name).read_text())


@pytest.mark.parametrize("key,rank,expected", [
    ("jev-1.13.0", 1, 63.29205745601932),
    ("jevk5-v02", 2, 62.04446598579722),
    ("hopper", 3, 59.433442874809664),
    ("gpt-6-luna-low", 24, 35.11224166817657),
    ("semif-qwen3.5-4b", 8, 47.69091838825422),
])
def test_lab_examples(key, rank, expected):
    source = next(x for x in read("measurement-aggregates.json")["systems"] if x["key"] == key)
    published = next(x for x in read("jevbench-v1.4-results.json")["systems"] if x["key"] == key)
    axes, score = C.score_from_comparison(source)
    assert score == pytest.approx(expected, abs=1e-9)
    assert published["jevbench_score"] == pytest.approx(expected, abs=1e-9)
    assert published["axes"] == pytest.approx(axes)
    assert published["rank"] == rank


def test_every_row_recomputes_and_only_aggregates_publish():
    sources = read("measurement-aggregates.json")["systems"]
    published = read("jevbench-v1.4-results.json")
    rows = {x["key"]: x for x in published["systems"]}
    assert len(rows) == len(sources) == 76
    for source in sources:
        row = rows[source["key"]]
        axes, expected = C.score_from_comparison(source)
        if expected is None:
            assert row["jevbench_score"] is None
        else:
            assert row["jevbench_score"] == pytest.approx(expected)
        if axes:
            assert row["axes"] == pytest.approx(axes)
        if row["api_flag"]:
            assert "operator's endpoint received sealed item text" in row["api_exposure_note"]
    assert [r["key"] for r in published["systems"][:5]] == [
        "jev-1.13.0", "jevk5-v02", "hopper", "winnow-12b", "reflex-4b"]
    assert rows["swanone"]["rank"] is None
    assert rows["swanone"]["not_ranked_because"].startswith("No completed sealed")
    assert rows["open-jev-json-canvas-joshuasp"]["jevbench_score"] == 0
    for forbidden in ('"results_file"', '"gold"', '"gold_probs"', '"task_text"', '"prompt_text"'):
        assert forbidden not in (DATA / "jevbench-v1.4-results.json").read_text()


def test_separate_gates_and_no_missing_measurement_as_zero():
    axes = dict(intelligence=60.0, calibration=60.0, speed=40.0, cost=30.0)
    base = 4 / sum(1 / x for x in axes.values())
    assert C.harmonic(axes) == pytest.approx(base * (40 / 50) ** 2 * (30 / 50) ** 2)
    assert C.harmonic({**axes, "calibration": 0}) == 0
    assert C.score_from_comparison({"v130": {"axes": axes}, "v14": {"axes": {"calibration": 40}},
                                    "public_acc": .8, "sealed_acc": None}) == (None, None)
