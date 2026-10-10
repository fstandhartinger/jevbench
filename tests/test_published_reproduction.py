"""Pin the published v1.4.2.1 / v1.4.2.2 aggregates to the published scoring code.

Every number checked here is recomputed from fields stored in the same
results file, with the composite version the file names (``jevbench::v1.4``
-> ``composite_v14``, which reuses the v1.3 speed, cost and tier helpers).
What cannot be recomputed from stored fields is listed in
docs/REPRODUCIBILITY.md.
"""

import json
from pathlib import Path

import pytest

from jevbench import composite_v13 as V13
from jevbench import composite_v14 as C

ROOT = Path(__file__).resolve().parents[1]
RESULTS = [
    ROOT / "results" / "v1.4.2.2" / "jevbench-v1.4.2.2-results.json",
    ROOT / "results" / "v1.4.2.2" / "base-live-v1.4.2.1-results.json",
    ROOT / "results" / "v1.4.2.1" / "jevbench-v1.4.2.1-results.json",
    ROOT / "results" / "v1.4.2.1" / "base-live-v1.4.2-results.json",
]
# Published scores are shown to one decimal; 0.01 is the stated tolerance.
# The files currently reproduce to ~1e-14.
TOL = 0.01
# Hard tier sizes (public, held out) from the published "hard_tier" description.
HARD_PUBLIC_N, HARD_HELDOUT_N = 111, 109


def load(path):
    return json.loads(path.read_text())


@pytest.fixture(params=RESULTS, ids=lambda p: f"{p.parent.name}/{p.name}")
def published(request):
    data = load(request.param)
    assert data["protocol"] == "jevbench::v1.4"
    return data


def scored(data):
    return [r for r in data["systems"] if r["jevbench_score"] is not None]


def test_published_constants_match_the_v14_scorer(published):
    assert published["axis_weights"] == C.WEIGHTS
    assert published["tier_weights"] == V13.TIER_WEIGHTS
    assert published["sealed_chance"] == C.SEALED_CHANCE
    assert published["sealed_weight"] == C.SEALED_WEIGHT
    assert published["presets"][published["main"]] == C.WEIGHTS
    for name, weights in V13.PRESETS.items():
        assert published["presets"][name] == pytest.approx(dict(zip(C.AXES, weights)))


def test_jevbench_score_and_presets_recompute_from_axes(published):
    rows = scored(published)
    assert len(rows) >= 90
    for row in rows:
        assert row["jevbench_score"] == pytest.approx(C.harmonic(row["axes"]), abs=TOL), row["key"]
        for name, weights in published["presets"].items():
            assert row["presets"][name] == pytest.approx(C.harmonic(row["axes"], weights), abs=TOL), (row["key"], name)
        assert row["presets"][published["main"]] == row["jevbench_score"]


def test_unscored_rows_are_label_only_and_unranked(published):
    for row in published["systems"]:
        if row["jevbench_score"] is None:
            assert row["axes"] is None and not row["has_distribution"], row["key"]
            assert not row["ranked"] and row["rank"] is None


def test_intelligence_recomputes_from_tiers_and_sealed_accuracy(published):
    for row in scored(published):
        tiers = row["tiers"]
        hard = tiers.get("hard")
        if hard is None:
            hard = (tiers["hard_public"] * HARD_PUBLIC_N + tiers["hard_heldout"] * HARD_HELDOUT_N) / (
                HARD_PUBLIC_N + HARD_HELDOUT_N)
        old = V13.intelligence({"easy": tiers["easy"], "standard": tiers["standard"],
                                "judge": tiers["judge"], "hard": hard})
        expected = C.intelligence(old, row["sealed_accuracy"], row["public_accuracy"])
        assert row["axes"]["intelligence"] == pytest.approx(expected, abs=TOL), row["key"]
        gap = 100 * (row["public_accuracy"] - row["sealed_accuracy"])
        assert row["public_minus_sealed_gap_pp"] == pytest.approx(gap, abs=TOL), row["key"]


def test_speed_recomputes_from_latency_where_latency_is_published(published):
    checked = 0
    for row in scored(published):
        s = row["speed"]
        for q in ("p50", "p95"):
            if s.get(f"{q}_s_raw") is not None:
                adjusted = V13.adjusted_latency(s[f"{q}_s_raw"], row["endpoint_kind"])
                assert s[f"{q}_s_adjusted"] == pytest.approx(adjusted, abs=1e-9), row["key"]
        if s.get("p50_s_adjusted") is None:
            continue  # documented gap: speed axis carried forward without latency fields
        expected = (V13.speed_point(s["p50_s_adjusted"]) + V13.speed_point(s["p95_s_adjusted"])) / 2
        assert row["axes"]["speed"] == pytest.approx(expected, abs=TOL), row["key"]
        checked += 1
    assert checked >= len(scored(published)) - 4


def test_cost_axis_recomputes_from_published_price(published):
    for row in scored(published):
        assert row["axes"]["cost"] == pytest.approx(V13.cost(row["cost"]["usd_per_1000"]), abs=TOL), row["key"]


def test_calibration_axis_equals_published_calibration_score(published):
    # The v1.3 calibration that composite_v14.calibration blends from is not
    # published, so only the identity between the two published fields is checked.
    for row in scored(published):
        assert row["axes"]["calibration"] == pytest.approx(row["calibration"]["score"], abs=TOL), row["key"]


def assert_ranks_consistent(rows, score, rank):
    """Ranks are 1..n and agree with scores; exactly tied scores may be in either order."""
    assert sorted(rank(r) for r in rows) == list(range(1, len(rows) + 1))
    for row in rows:
        above = sum(score(o) > score(row) + 1e-9 for o in rows)
        at_or_above = sum(score(o) >= score(row) - 1e-9 for o in rows)
        assert above < rank(row) <= at_or_above, row["key"]


def test_ranks_follow_recomputed_scores(published):
    ranked = [r for r in published["systems"] if r["ranked"]]
    assert all(r["jevbench_score"] is not None for r in ranked)
    assert [r["rank"] for r in ranked] == list(range(1, len(ranked) + 1))
    assert_ranks_consistent(ranked, lambda r: C.harmonic(r["axes"]), lambda r: r["rank"])
    for name, weights in published["presets"].items():
        assert_ranks_consistent(ranked, lambda r: C.harmonic(r["axes"], weights), lambda r: r["rank_under"][name])
    for row in published["systems"]:
        if not row["ranked"]:
            assert row["rank"] is None and row["rank_under"] == {}, row["key"]
