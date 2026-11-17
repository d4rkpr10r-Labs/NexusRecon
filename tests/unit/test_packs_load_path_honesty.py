"""NEX-17: packs/burp excluded from wheel; honesty docs present."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_excludes_packs_from_package_data():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "assets/nexusrecon-verify.py" in text
    assert "NEX-17" in text or "checkout dogfood" in text
    # package-data entries are quoted paths — burp must not be one.
    assert '"packs/burp' not in text
    assert '"packs/' not in text


def test_setuptools_packages_find_is_nexusrecon_only():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["nexusrecon*"]' in text


def test_burp_pack_readme_states_not_in_wheel():
    readme = (ROOT / "packs" / "burp" / "README.md").read_text(encoding="utf-8")
    assert "not" in readme.lower()
    assert "wheel" in readme.lower()
    assert "default load path" in readme.lower() or "~/.nexusrecon/packs" in readme


def test_burp_manifest_still_present_for_checkout_dogfood():
    manifest = ROOT / "packs" / "burp" / "manifest.yaml"
    assert manifest.is_file()
    text = manifest.read_text(encoding="utf-8")
    assert "name: burp" in text
