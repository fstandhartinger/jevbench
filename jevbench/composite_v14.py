"""JevBench v1.4 official scoring from published aggregate measurements.

No sealed task, answer, or per-item result is needed by this module.
"""

from . import composite_v13 as previous

AXES = previous.AXES
WEIGHTS = previous.WEIGHTS
SEALED_WEIGHT = 0.20
SEALED_CHANCE = 0.293
CALIBRATION_REFERENCE_WEIGHT = 0.35
GAP_ALLOWANCE_POINTS = 25.0
GAP_PENALTY_K = 1.0
JEV_CLASS_THRESHOLD = 50.0


def chance_corrected_sealed(accuracy):
    if accuracy is None:
        return None
    return previous.clamp(100 * max(0.0, (accuracy - SEALED_CHANCE) / (1 - SEALED_CHANCE)))


def intelligence(old_intelligence, sealed_accuracy, public_accuracy):
    if None in (old_intelligence, sealed_accuracy, public_accuracy):
        return None
    combined = (1 - SEALED_WEIGHT) * old_intelligence + SEALED_WEIGHT * chance_corrected_sealed(sealed_accuracy)
    gap_points = 100 * (public_accuracy - sealed_accuracy)
    penalty = max(0.0, gap_points - GAP_ALLOWANCE_POINTS) * GAP_PENALTY_K / 100
    return combined * max(0.0, 1 - penalty)


def calibration(old_calibration, candidate_calibration):
    # A label-only answer has no distribution and has always contributed zero.
    old = 0.0 if old_calibration is None else old_calibration
    new = 0.0 if candidate_calibration is None else candidate_calibration
    return old + (new - old) * min(1.0, SEALED_WEIGHT / CALIBRATION_REFERENCE_WEIGHT)


def harmonic(axes, weights=WEIGHTS):
    """Weighted power mean p=-1, followed by all three official gates."""
    selected = [(axes.get(axis), weights[axis]) for axis in AXES if weights[axis] > 0]
    if not selected or any(value is None for value, _ in selected):
        return None
    if any(value <= 0 for value, _ in selected):
        score = 0.0
    else:
        score = sum(weight for _, weight in selected) / sum(weight / value for value, weight in selected)
    i = axes.get("intelligence")
    if i is not None and i < JEV_CLASS_THRESHOLD:
        score *= (max(0.0, i) / JEV_CLASS_THRESHOLD) ** 2
    for axis in ("speed", "cost"):
        value = axes.get(axis)
        if value is not None and value < JEV_CLASS_THRESHOLD:
            score *= (max(0.0, value) / JEV_CLASS_THRESHOLD) ** 2
    return score


def score_from_comparison(row):
    """Return official axes and score from a private comparison's aggregate fields."""
    old = row["v130"]["axes"]
    v14 = row["v14"]["axes"] if row.get("v14") else None
    if row.get("sealed_acc") is None or v14 is None:
        return None, None
    axes = {
        "intelligence": intelligence(old["intelligence"], row["sealed_acc"], row["public_acc"]),
        "calibration": calibration(old["calibration"], v14["calibration"]),
        "speed": old["speed"],
        "cost": old["cost"],
    }
    return axes, harmonic(axes)
