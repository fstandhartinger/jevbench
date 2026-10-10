"""`jevbench validate-data` on tiny invented fixtures.

Every record below is fake (ids start with "fake-", text is placeholder);
none of them is or paraphrases a benchmark item.
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from jevbench.cli import main
from jevbench.validate_data import validate_paths


def rec(id, qtype="choice", expected="a", labels=None, group=None):
    if labels is None:
        labels = {"noul": ["no", "yes"], "score": ["0", "1"]}.get(qtype, ["a", "b"])
    return {"id": id, "family": "intent", "state": "FAKE STATE",
            "question": {"type": qtype, "instructions": "FAKE?"},
            "labels": labels, "expected": expected, "split": "public",
            "group": group, "provenance": {"source": "test fixture"}}


class ValidateData(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.dir = Path(self._d.name)

    def tearDown(self):
        self._d.cleanup()

    def write(self, name, rows):
        p = self.dir / name
        p.write_text("".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows))
        return str(p)

    def run_cli(self, *paths):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["validate-data", *paths])
        return code, buf.getvalue()

    def test_clean_file_passes(self):
        p = self.write("ok.jsonl", [rec("fake-1", group="g"), rec("fake-2", group="g"),
                                    rec("fake-3", "noul", "yes"), rec("fake-4", "score", 1),
                                    rec("fake-5", expected=None)])
        code, out = self.run_cli(p)
        self.assertEqual(code, 0, out)
        self.assertIn("OK: 1 files, 5 tasks, 0 problems", out)

    def test_duplicate_id_across_files(self):
        a = self.write("a.jsonl", [rec("fake-1")])
        b = self.write("b.jsonl", [rec("fake-1")])
        code, out = self.run_cli(a, b)
        self.assertEqual(code, 1)
        self.assertIn("duplicate id", out)

    def test_bad_kind_and_bad_line_are_reported_and_loading_continues(self):
        p = self.write("bad.jsonl", [rec("fake-1", qtype="vibes"), "{not json", rec("fake-2")])
        by_path, problems = validate_paths([p])
        self.assertEqual([t.id for t in by_path[p]], ["fake-2"])
        self.assertEqual(len(problems), 2, problems)
        self.assertIn(":1:", problems[0]); self.assertIn("bad question type", problems[0])
        self.assertIn(":2:", problems[1])

    def test_expected_type_must_match_kind(self):
        # Each passes Task.validate() (expected is in labels) but has the wrong type.
        rows = [rec("fake-1", "score", True, labels=["0", "True"]),
                rec("fake-2", "noul", "maybe", labels=["no", "maybe"]),
                rec("fake-3", "choice", 1, labels=[1, 2])]
        _, problems = validate_paths([self.write("t.jsonl", rows)])
        self.assertEqual(len(problems), 3, problems)
        self.assertIn("score expected must be int", problems[0])
        self.assertIn("noul expected must be", problems[1])
        self.assertIn("choice expected must be a label string", problems[2])

    def test_group_members_must_share_expected(self):
        p = self.write("g.jsonl", [rec("fake-1", group="fake-g"), rec("fake-2", expected="b", group="fake-g")])
        code, out = self.run_cli(p)
        self.assertEqual(code, 1)
        self.assertIn("group 'fake-g': members disagree", out)

    def test_missing_file(self):
        code, out = self.run_cli(str(self.dir / "nope.jsonl"))
        self.assertEqual(code, 1)
        self.assertIn("cannot open", out)


if __name__ == "__main__":
    unittest.main()
