"""Publication checks for the JevBench v1.4.3 point release."""

import hashlib
import json
from pathlib import Path

import pytest

from jevbench import composite_v13 as C13
from jevbench import composite_v14 as C

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "v1.4.3"
PREVIOUS = ROOT / "results" / "v1.4.2" / "jevbench-v1.4.2-results.json"
# Update together with Florian's preview approval whenever appended rows change the top five.
EXPECTED_TOP_FIVE = ["decision-4b-v12", "decision-4b-v11", "plumb-4b", "imajev-4b", "decider-4b-v2"]
FIRST_WAVE = {"imajev-2b", "imajev-4b", "imajev-9b", "blink-4b", "ryotide-gemma", "ryotide-qwen",
              "decision-4b-v12", "decision-4b-v11", "plumb-4b", "nemotron-diffusion-8b", "apus-openjev-4b", "jpt-4b",
              "eikos-4b", "eikos-27b", "autojev-27b", "vtx-jev-1"}
PARTIAL = {"gliner25-decide"}
HELD = {"bonsai-2-27b-pq2-0", "bonsai-llama-jev"}


def read(name):
    return json.loads((DATA / name).read_text())


@pytest.fixture(scope="module")
def published():
    return read("jevbench-v1.4.3-results.json")


@pytest.fixture(scope="module")
def rows(published):
    return {r["key"]: r for r in published["systems"]}


def test_inputs_are_pinned():
    assert hashlib.sha256(PREVIOUS.read_bytes()).hexdigest().startswith("ac14e206")
    assert hashlib.sha256((ROOT / "jevbench" / "composite_v14.py").read_bytes()).hexdigest().startswith("33177d06")


def test_every_addition_recomputes_with_the_pinned_v14_scorer(published, rows):
    sources = read("addition-sources.json")["systems"]
    assert FIRST_WAVE | PARTIAL <= {s["key"] for s in sources}
    assert len(rows) == 93 + len(sources)
    for source in sources:
        axes, expected = C.score_from_comparison(source)
        row = rows[source["key"]]
        if source["ranked"]:
            assert row["jevbench_score"] == pytest.approx(expected, abs=1e-12)
            assert row["axes"] == pytest.approx(axes, abs=1e-12)
        else:
            assert expected is None and row["jevbench_score"] is None and row["rank"] is None
    ranked = [r for r in published["systems"] if r["ranked"]]
    assert [r["rank"] for r in ranked] == list(range(1, len(ranked) + 1))
    assert all(a["jevbench_score"] >= b["jevbench_score"] for a, b in zip(ranked, ranked[1:]))
    assert all(r["rank"] is None for r in published["systems"] if not r["ranked"])


def test_v142_rows_are_unchanged_except_rank(rows):
    previous = json.loads(PREVIOUS.read_text())["systems"]
    assert len(previous) == 93
    for old in previous:
        new = rows[old["key"]]
        strip = lambda r: {k: v for k, v in r.items() if k not in ("rank", "rank_under")}  # noqa: E731
        assert strip(old) == strip(new), old["key"]
        assert new["jevbench_score"] == old["jevbench_score"]


def test_additions_are_labelled(rows):
    for key in FIRST_WAVE:
        row = rows[key]
        assert row["new_in"] == "v1.4.3" and row["ranked"] and row["api_flag"] is False, key
        assert row["cost"]["kind"] == "estimate" and row["cost"]["usd_per_1000"] > 0, key
        assert row["cost"]["basis"].startswith("ESTIMATE") and "ESTIMATE: ESTIMATE" not in row["cost"]["basis"], key
        assert row["speed"]["p50_s_adjusted"] == pytest.approx(row["speed"]["p50_s_raw"] * 2 + 0.15), key
        assert row["sealed_aggregate"]["n"] == 308 and row["sealed_aggregate"]["answered_valid"] == 308, key
        assert all(isinstance(v, float) for v in row["sealed_aggregate"]["by_family"].values()), key
        assert all(isinstance(row.get(f), str) and row[f] for f in ("display", "class", "author")), key
        assert row["release_evidence"]["aggregate_source_sha256"] and row["release_evidence"]["row_sha256"], key
    gliner = rows["gliner25-decide"]
    assert not gliner["ranked"] and gliner["listing"] == "partial" and "120 s" in gliner["not_ranked_because"]
    for key in HELD:
        assert key not in rows


def test_apus_is_repriced_to_the_qwen35_4b_basis(rows):
    apus = rows["apus-openjev-4b"]
    usd = 389142 * 0.03 / 1e6 / 534 * 1000
    assert apus["cost"]["usd_per_1000"] == pytest.approx(usd, rel=1e-12)
    assert apus["axes"]["cost"] == pytest.approx(C13.cost(usd), abs=1e-12)
    assert "$0.03/M" in apus["cost"]["basis"] and "Qwen/Qwen3.5-4B" in apus["cost"]["basis"]
    assert apus["cost"]["repriced_from"]["input_usd_per_m"] == 0.1
    for key in ("decider-4b-v2", "typecastlm", "decision-4b-v12", "imajev-4b", "eikos-4b"):
        assert "$0.03/M" in rows[key]["cost"]["basis"], key


def test_instinct_keeps_its_base_model_estimate(rows):
    inst = rows["instinct"]
    assert inst["cost"]["kind"] == "estimate" and "0.42" in inst["cost"]["basis"]
    assert inst["cost"]["usd_per_1000"] == pytest.approx(0.3253253932584269)


def test_decision_4b_disclosure_is_corrected(published):
    for key in ("decision-4b-v12", "decision-4b-v11"):
        note = published["footnotes"][key]
        assert "used for training, tuning or model selection" not in note
        assert "reports/gates.json" in note and "public split was used for model selection" in note


def test_top_five_and_fairness_note_are_true(published, rows):
    ranked = [r for r in published["systems"] if r["ranked"]]
    assert [r["key"] for r in ranked[:5]] == EXPECTED_TOP_FIVE
    note = published["top_five_note"]
    for r in ranked[:5]:
        assert f"{r['display'].split(' (')[0]} {r['axes']['intelligence']:.1f}" in note
    jev = rows["jev-1.13.0"]["axes"]["intelligence"]
    above = sum(r["axes"]["intelligence"] > jev for r in ranked[:5])
    assert f"out-reasoned by {['no', 'one', 'two', 'three', 'four', 'five'][above]} of them" in note
    assert "strongest reasoner" not in note and "out-reasons" not in note
    best = max(ranked, key=lambda r: r["axes"]["intelligence"])
    assert f"up to {best['axes']['intelligence']:.1f}" in note


def test_no_private_fields_are_published():
    for name in ("jevbench-v1.4.3-results.json", "addition-sources.json", "addition-rows.json", "input-manifest.json"):
        text = (DATA / name).read_text()
        for forbidden in ('"results_file"', '"gold"', '"gold_probs"', '"task_text"', '"prompt_text"', "/home/",
                          "jevbench-sealed"):
            assert forbidden not in text, (name, forbidden)
