"""Publication checks for the JevBench v1.4.2 point release."""

import json
from pathlib import Path

import pytest

from jevbench import composite_v14 as C

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "v1.4.2"
PREVIOUS = ROOT / "results" / "v1.4.1" / "jevbench-v1.4.1-results.json"
ADDED = {"decider-4b-v2", "cygnet", "malkuth-4b", "malkuth-2b", "standardone-8b", "typecastlm", "clm-8b",
         "instinct", "jevact", "verdict-small", "kushal-gemma4-31b-it-autoloops"}


def read(name):
    return json.loads((DATA / name).read_text())


def test_every_row_recomputes_with_the_pinned_v14_scorer():
    sources = read("measurement-aggregates.json")["systems"]
    published = read("jevbench-v1.4.2-results.json")
    rows = {x["key"]: x for x in published["systems"]}
    assert len(rows) == len(sources) == 93
    for source in sources:
        axes, expected = C.score_from_comparison(source)
        row = rows[source["key"]]
        if expected is None:
            assert row["jevbench_score"] is None
        else:
            assert row["jevbench_score"] == pytest.approx(expected, abs=1e-12)
            assert row["axes"] == pytest.approx(axes, abs=1e-12)
    ranked = [r for r in published["systems"] if r["ranked"]]
    assert [r["rank"] for r in ranked] == list(range(1, len(ranked) + 1))
    assert all(a["jevbench_score"] >= b["jevbench_score"] for a, b in zip(ranked, ranked[1:]))


def test_approved_top_five_and_fairness_note():
    published = read("jevbench-v1.4.2-results.json")
    assert [r["key"] for r in published["systems"][:5]] == [
        "decider-4b-v2", "jev-1.13.0", "jevk5-v02", "cygnet", "hopper"]
    assert published["top_five_note"].startswith("Jev 1.13.0 out-reasons decider-4b v2 (Intelligence 53.1 vs 49.4)")
    rows = {x["key"]: x for x in published["systems"]}
    jev, decider = rows["jev-1.13.0"]["axes"], rows["decider-4b-v2"]["axes"]
    assert round(jev["intelligence"], 1) == 53.1 and round(decider["intelligence"], 1) == 49.4
    assert jev["calibration"] > decider["calibration"]
    assert decider["speed"] > jev["speed"] and decider["cost"] > jev["cost"]


def test_v141_rows_are_unchanged_and_additions_are_labelled():
    previous = {r["key"]: r for r in json.loads(PREVIOUS.read_text())["systems"]}
    backfill = read("v141-hard-family-backfill.json")["rows"]
    assert len(backfill) == 7
    for key, hard in backfill.items():
        assert previous[key]["hard"] != hard and sum(f["n"] for f in hard["by_family"].values()) == 220
        previous[key] = {**previous[key], "hard": hard}
    published = read("jevbench-v1.4.2-results.json")
    for row in published["systems"]:
        if row["key"] in previous and row["key"] != "swanone":
            old = {k: v for k, v in previous[row["key"]].items() if k not in ("rank", "rank_under")}
            assert old == {k: v for k, v in row.items() if k not in ("rank", "rank_under")}, row["key"]
    rows = {r["key"]: r for r in published["systems"]}
    assert ADDED | {"swanone"} == {r["key"] for r in published["systems"] if r.get("new_in") == "v1.4.2"}
    assert rows["swanone"]["ranked"] and rows["swanone"]["rank"] is not None
    for key in ("instinct", "jevact", "kushal-gemma4-31b-it-autoloops"):
        assert rows[key]["api_flag"] is True
        assert "operator's endpoint received sealed item text" in rows[key]["api_exposure_note"]
    for key in ADDED - {"kushal-gemma4-31b-it-autoloops"}:
        assert rows[key]["cost"]["kind"] == "estimate", key
    for key in ADDED | {"swanone"}:
        row = rows[key]
        assert isinstance(row["cost"].get("basis"), str) and row["cost"]["usd_per_1000"] > 0, key
        assert all(isinstance(row.get(f), str) and row[f] for f in ("display", "class", "author")), key
        assert row["speed"].get("p50_s_adjusted") is not None, key
    assert "0.42" in rows["instinct"]["cost"]["basis"] and "qwen3.8-27b" in rows["instinct"]["cost"]["basis"]
    for held in ("imajev-4b", "blink-4b", "ryotide-qwen", "jpt-4b", "apus-openjev-4b"):
        assert held not in rows


def test_no_private_fields_are_published():
    text = (DATA / "jevbench-v1.4.2-results.json").read_text()
    for forbidden in ('"results_file"', '"gold"', '"gold_probs"', '"task_text"', '"prompt_text"', "/home/"):
        assert forbidden not in text
