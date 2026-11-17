"""NEX-16: nexusrecon-verify console entry extracts/runs packaged asset."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from nexusrecon.cli import verify_entry


def test_packaged_verifier_text_matches_asset():
    text = verify_entry.packaged_verifier_text()
    assert "Standalone verifier" in text
    assert "Ed25519" in text or "ed25519" in text.lower()
    assert "def main(" in text


def test_extract_writes_standalone_script(tmp_path: Path):
    dest = tmp_path / "out" / "nexusrecon-verify.py"
    dest.parent.mkdir()
    out = verify_entry.extract_verifier(dest)
    assert out.is_file()
    assert "Standalone verifier" in out.read_text(encoding="utf-8")


def test_main_extract_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    dest = tmp_path / "copied-verify.py"
    with pytest.raises(SystemExit) as exc:
        verify_entry.main(["--extract", str(dest)])
    assert exc.value.code == 0
    assert dest.is_file()
    captured = capsys.readouterr()
    assert "Wrote standalone verifier" in captured.out


def test_run_verifier_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        verify_entry.run_verifier(["--help"])
    assert exc.value.code == 0


def test_run_verifier_missing_args_fails():
    with pytest.raises(SystemExit) as exc:
        verify_entry.run_verifier([])
    assert exc.value.code != 0


def test_pyproject_declares_console_script():
    root = Path(__file__).resolve().parents[2]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'nexusrecon-verify = "nexusrecon.cli.verify_entry:main"' in text


def test_entry_main_help_mentions_extract(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        verify_entry.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--extract" in out
    assert "cryptography" in out
