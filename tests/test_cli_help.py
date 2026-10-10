"""`--help` works for the main command and every subcommand, and documents every flag."""

import argparse
import os
import subprocess
import sys

import pytest

from jevbench import cli

SUBCOMMANDS = {
    "run": ["--tasks", "--adapter", "--endpoint", "--model", "--key-env", "--results",
            "--ledger", "--raw-dir", "--cap-usd", "--reserve-usd", "--price-in-per-m",
            "--price-out-per-m", "--limit", "--delay-s", "--request-options", "--revision",
            "--run-label", "--cost-basis", "--manifest"],
    "summarize": ["--tasks", "--results", "--ledger", "--public-export", "--include-excluded"],
}


def _help(capsys, argv):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 0
    return capsys.readouterr().out


def test_main_help(capsys):
    out = _help(capsys, ["--help"])
    assert out.startswith("usage: jevbench")
    for name in SUBCOMMANDS:
        assert name in out
    assert "examples:" in out


@pytest.mark.parametrize("name", sorted(SUBCOMMANDS))
def test_subcommand_help(capsys, name):
    out = _help(capsys, [name, "--help"])
    assert out.startswith(f"usage: jevbench {name}")
    assert "example:" in out
    for flag in SUBCOMMANDS[name]:
        assert flag in out, flag


def test_every_option_has_help_text(monkeypatch):
    parser_actions = []

    def capture(self, args=None, namespace=None):
        for action in self._actions:
            if isinstance(action, argparse._SubParsersAction):
                for sub in action.choices.values():
                    parser_actions.extend((sub.prog, a) for a in sub._actions)
        raise SystemExit(0)

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", capture)
    with pytest.raises(SystemExit):
        cli.main([])
    assert parser_actions
    missing = [f"{prog} {a.option_strings}" for prog, a in parser_actions if not a.help]
    assert not missing, missing


def test_module_help_subprocess():
    proc = subprocess.run([sys.executable, "-m", "jevbench.cli", "--help"],
                          capture_output=True, text=True, timeout=60,
                          cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert proc.returncode == 0, proc.stderr
    assert "usage: jevbench" in proc.stdout


def test_missing_subcommand_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2
