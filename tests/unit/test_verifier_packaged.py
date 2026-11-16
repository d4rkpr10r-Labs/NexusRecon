"""Packaging: standalone verifier ships inside the installed package."""
from __future__ import annotations

from importlib.resources import files


def test_nexusrecon_verify_asset_packaged():
    asset = files("nexusrecon").joinpath("assets/nexusrecon-verify.py")
    assert asset.is_file()
    text = asset.read_text(encoding="utf-8")
    assert "Standalone verifier" in text
    assert "Ed25519" in text or "ed25519" in text.lower()
