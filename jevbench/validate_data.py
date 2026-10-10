"""Read-only checks over JevBench task files (`jevbench validate-data`).

Loads each JSONL file with the canonical loader in jevbench.tasks (which runs
Task.validate() on every record) and then checks, across all given files:

  * every id is unique
  * question.type is an allowed kind (jevbench.tasks.QUESTION_TYPES)
  * the expected answer has the type its kind needs: int level index for
    score (bool rejected), "no"/"yes" for noul, a label string for choice
  * group consistency: all items sharing a group share one expected answer
    (the same check tests/test_protocol.py makes on the public suite)

Never writes anything. Returns a list of problem strings; empty means clean.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from .tasks import QUESTION_TYPES, Task


def _load(path: str, problems: list) -> list:
    """Like tasks.load_jsonl, but keeps going past a bad line so every
    problem in the file is reported, not just the first."""
    tasks = []
    try:
        fh = open(path, "r", encoding="utf-8")
    except OSError as e:
        problems.append(f"{path}: cannot open: {e}")
        return tasks
    with fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                tasks.append(Task.from_dict(json.loads(line)))
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                kind = type(e).__name__
                problems.append(f"{path}:{lineno}: {kind}: {e}")
    return tasks


def _check_expected(t: Task) -> str | None:
    kind = t.question.get("type")
    exp = t.expected
    if exp is None:
        return None  # unmeasured ground truth is allowed
    if kind == "score":
        if isinstance(exp, bool) or not isinstance(exp, int):
            return f"score expected must be int, got {type(exp).__name__}"
    elif kind == "noul":
        if exp not in ("no", "yes"):
            return f"noul expected must be 'no' or 'yes', got {exp!r}"
    elif kind == "choice":
        if not isinstance(exp, str):
            return f"choice expected must be a label string, got {type(exp).__name__}"
    return None


def validate_paths(paths: list) -> tuple:
    """Return (tasks_by_path, problems)."""
    problems: list = []
    by_path = {}
    for p in paths:
        by_path[p] = _load(p, problems)

    seen: dict = {}
    groups: dict = defaultdict(set)
    for p, tasks in by_path.items():
        for t in tasks:
            where = f"{p}: {t.id}"
            if t.id in seen:
                problems.append(f"{where}: duplicate id (first in {seen[t.id]})")
            else:
                seen[t.id] = p
            if t.question.get("type") not in QUESTION_TYPES:
                problems.append(f"{where}: kind {t.question.get('type')!r} not in {QUESTION_TYPES}")
            msg = _check_expected(t)
            if msg:
                problems.append(f"{where}: {msg}")
            if t.group is not None:
                groups[t.group].add(str(t.expected))
    for g, answers in sorted(groups.items()):
        if len(answers) > 1:
            problems.append(f"group {g!r}: members disagree on expected {sorted(answers)}")
    return by_path, problems


def report(paths: list, out) -> int:
    by_path, problems = validate_paths(paths)
    for p, tasks in by_path.items():
        kinds = Counter(t.question.get("type") for t in tasks)
        n_groups = len({t.group for t in tasks if t.group is not None})
        kind_s = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())) or "-"
        print(f"{p}: {len(tasks)} tasks ({kind_s}); {n_groups} groups", file=out)
    for msg in problems:
        print(f"PROBLEM {msg}", file=out)
    total = sum(len(t) for t in by_path.values())
    status = "OK" if not problems else "FAIL"
    print(f"{status}: {len(paths)} files, {total} tasks, {len(problems)} problems", file=out)
    return 0 if not problems else 1
