"""Property tests for metric and composite helpers on synthetic numbers only.

A seeded ``random.Random`` stands in for a property-testing library so the
suite keeps its single test dependency (pytest).
"""

import math
import random

import pytest

from jevbench import composite_v13 as V13
from jevbench import composite_v14 as C
from jevbench import metrics as M

RNG_SEED = 20261010
TRIALS = 300
GATE = 50.0  # documented gate threshold (results "scoring.jevbench_score")


@pytest.fixture
def rng():
    return random.Random(RNG_SEED)


def random_axes(rng, lo=0.0, hi=100.0):
    return {axis: rng.uniform(lo, hi) for axis in C.AXES}


# --- metrics.py -------------------------------------------------------------

def test_ece_is_bounded_and_counts_every_pair(rng):
    for _ in range(TRIALS):
        pairs = [(rng.uniform(-0.2, 1.2), rng.random() < 0.5) for _ in range(rng.randint(1, 60))]
        out = M.ece_top_label(pairs)
        assert 0.0 <= out["ece"] <= 1.0
        assert out["n"] == len(pairs) == sum(b["n"] for b in out["bins"])


def test_ece_is_zero_when_each_bin_accuracy_equals_its_confidence():
    pairs = []
    for conf, n, n_correct in ((0.25, 4, 1), (0.55, 20, 11), (0.95, 20, 19)):
        pairs += [(conf, i < n_correct) for i in range(n)]
    assert M.ece_top_label(pairs)["ece"] == pytest.approx(0.0, abs=1e-12)


def test_ece_is_maximal_for_confident_wrong_answers():
    assert M.ece_top_label([(1.0, False)] * 5)["ece"] == pytest.approx(1.0)
    assert M.ece_top_label([(1.0, True)] * 5)["ece"] == pytest.approx(0.0)


def test_brier_is_bounded_and_zero_only_for_certain_correct(rng):
    labels = ["a", "b", "c", "d"]
    for _ in range(TRIALS):
        raw = [rng.random() for _ in labels]
        probs = {lab: v / sum(raw) for lab, v in zip(labels, raw)}
        expected = rng.choice(labels)
        assert 0.0 <= M.brier_score(probs, expected, labels) <= 2.0 + 1e-12
    assert M.brier_score({"a": 1.0, "b": 0, "c": 0, "d": 0}, "a", labels) == 0.0
    assert M.brier_score({"a": 0.0, "b": 1, "c": 0, "d": 0}, "a", labels) == 2.0


def test_percentile_stays_within_range_and_is_monotone_in_q(rng):
    for _ in range(TRIALS):
        values = [rng.uniform(0, 10) for _ in range(rng.randint(1, 30))]
        qs = sorted(rng.random() for _ in range(5))
        ps = [M.percentile(values, q) for q in qs]
        assert all(min(values) <= p <= max(values) for p in ps)
        assert all(a <= b + 1e-12 for a, b in zip(ps, ps[1:]))


# --- composite_v13.calibration / speed / cost --------------------------------

def test_calibration_score_bounds_and_zero_at_documented_ece_cap(rng):
    for _ in range(TRIALS):
        ece = rng.uniform(0, 1)
        score = V13.calibration(ece)
        assert 0.0 <= score <= 100.0
        assert score <= V13.calibration(ece * 0.9) + 1e-12
    assert V13.calibration(0.0) == 100.0
    assert V13.calibration(0.5) == 0.0 and V13.calibration(0.9) == 0.0
    assert V13.calibration(None) is None


def test_speed_and_cost_points_hit_documented_anchors_and_are_clipped():
    assert V13.speed_point(0.1) == pytest.approx(100.0)
    assert V13.speed_point(1.0) == pytest.approx(80.0)
    assert V13.speed_point(10.0) == pytest.approx(60.0)
    assert V13.speed_point(0.001) == 100.0 and V13.speed_point(1e9) == 0.0
    for usd, points in ((0.001, 100), (0.01, 70), (0.1, 40), (1.0, 10)):
        assert V13.cost(usd) == pytest.approx(points)
    assert V13.cost(1e6) == 0.0
    with pytest.raises(ValueError):
        V13.cost(0)


# --- composite_v14 -----------------------------------------------------------

def test_harmonic_lies_between_min_and_arithmetic_mean_without_gates(rng):
    for _ in range(TRIALS):
        axes = random_axes(rng, GATE, 100)
        score = C.harmonic(axes)
        values = list(axes.values())
        assert min(values) - 1e-9 <= score <= sum(values) / len(values) + 1e-9


def test_harmonic_is_monotone_in_every_axis(rng):
    for _ in range(TRIALS):
        axes = random_axes(rng, 0.5, 100)
        axis = rng.choice(C.AXES)
        better = dict(axes, **{axis: min(100.0, axes[axis] + rng.uniform(0, 20))})
        assert C.harmonic(better) >= C.harmonic(axes) - 1e-12


def test_harmonic_is_zero_when_any_weighted_axis_is_zero_and_none_when_missing(rng):
    axes = random_axes(rng, GATE, 100)
    for axis in C.AXES:
        assert C.harmonic(dict(axes, **{axis: 0.0})) == 0.0
        assert C.harmonic({k: v for k, v in axes.items() if k != axis}) is None
    # A zero-weight axis is ignored by the mean (but intelligence still gates).
    no_cal = dict(zip(C.AXES, (1 / 3, 0.0, 1 / 3, 1 / 3)))
    assert C.harmonic(dict(axes, calibration=0.0), no_cal) > 0


@pytest.mark.parametrize("axis", ["intelligence", "speed", "cost"])
def test_gates_start_exactly_below_the_documented_threshold(axis):
    base = {a: 80.0 for a in C.AXES}
    at = C.harmonic(dict(base, **{axis: GATE}))
    ungated = 4 / (3 / 80 + 1 / GATE)
    assert at == pytest.approx(ungated)
    for value in (49.999, 40.0, 25.0, 10.0):
        mean = 4 / (3 / 80 + 1 / value)
        assert C.harmonic(dict(base, **{axis: value})) == pytest.approx(mean * (value / GATE) ** 2)
    # The gate is continuous at the threshold.
    assert C.harmonic(dict(base, **{axis: GATE - 1e-9})) == pytest.approx(at, rel=1e-8)


def test_calibration_has_no_gate():
    base = {a: 80.0 for a in C.AXES}
    assert C.harmonic(dict(base, calibration=10.0)) == pytest.approx(4 / (3 / 80 + 1 / 10))


def test_gates_multiply(rng):
    for _ in range(TRIALS):
        axes = random_axes(rng, 1, GATE)
        mean = 4 / sum(1 / v for v in axes.values())
        gates = math.prod((axes[a] / GATE) ** 2 for a in ("intelligence", "speed", "cost"))
        assert C.harmonic(axes) == pytest.approx(mean * gates)


def test_sealed_chance_correction_anchors_and_clipping(rng):
    assert C.chance_corrected_sealed(0.293) == 0.0  # documented sealed chance
    assert C.chance_corrected_sealed(0.0) == 0.0
    assert C.chance_corrected_sealed(1.0) == pytest.approx(100.0)
    assert C.chance_corrected_sealed(None) is None
    xs = sorted(rng.random() for _ in range(TRIALS))
    ys = [C.chance_corrected_sealed(x) for x in xs]
    assert all(0.0 <= y <= 100.0 for y in ys)
    assert all(a <= b for a, b in zip(ys, ys[1:]))


def test_gap_penalty_starts_above_the_documented_allowance():
    old, sealed = 70.0, 0.6
    combined = 0.8 * old + 0.2 * C.chance_corrected_sealed(sealed)
    allowance = 0.25  # documented 25 percentage-point allowance
    assert C.intelligence(old, sealed, sealed) == pytest.approx(combined)
    assert C.intelligence(old, sealed, sealed + allowance) == pytest.approx(combined)
    assert C.intelligence(old, sealed, sealed + allowance + 0.10) == pytest.approx(combined * 0.90)
    # A sealed score above public is never penalised.
    assert C.intelligence(old, sealed, sealed - 0.3) == pytest.approx(combined)
    assert C.intelligence(None, sealed, sealed) is None


def test_calibration_blend_moves_at_most_the_documented_fraction(rng):
    frac = 0.2 / 0.35  # documented min(1, 0.2/0.35)
    for _ in range(TRIALS):
        old, new = rng.uniform(0, 100), rng.uniform(0, 100)
        out = C.calibration(old, new)
        assert out == pytest.approx(old + (new - old) * frac)
        assert min(old, new) - 1e-9 <= out <= max(old, new) + 1e-9
    assert C.calibration(None, None) == 0.0
