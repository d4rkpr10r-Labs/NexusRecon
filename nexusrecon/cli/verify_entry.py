"""Console entry for ``nexusrecon-verify`` (NEX-16 / P3.11).

Exposes the packaged standalone Ed25519 STIX verifier
(``nexusrecon/assets/nexusrecon-verify.py``) on PATH after
``pip install``. The asset depends only on ``cryptography`` —
same contract as ``scripts/nexusrecon-verify.py`` for auditors
without a NexusRecon install.

Usage after install::

    nexusrecon-verify --bundle … --receipt … --public-key …
    nexusrecon-verify --extract [PATH]   # write the standalone script
"""
from __future__ import annotations

import importlib.util
import sys
from importlib.resources import as_file, files
from pathlib import Path

_ASSET = "assets/nexusrecon-verify.py"


def packaged_verifier_path():
    """Traversable handle for the packaged verifier asset."""
    return files("nexusrecon").joinpath(_ASSET)


def packaged_verifier_text() -> str:
    """Return the standalone verifier source from package data."""
    return packaged_verifier_path().read_text(encoding="utf-8")


def extract_verifier(dest: Path | str = "nexusrecon-verify.py") -> Path:
    """Write the packaged verifier to ``dest`` for redistribution."""
    out = Path(dest)
    out.write_text(packaged_verifier_text(), encoding="utf-8")
    try:
        out.chmod(out.stat().st_mode | 0o111)
    except OSError:
        pass
    return out.resolve()


def run_verifier(argv: list[str] | None = None) -> int:
    """Execute the packaged verifier's ``main(argv)``; return exit code."""
    ref = packaged_verifier_path()
    with as_file(ref) as path:
        spec = importlib.util.spec_from_file_location(
            "_nexusrecon_verify_asset", path,
        )
        if spec is None or spec.loader is None:
            sys.stderr.write(
                "ERROR: could not load packaged nexusrecon-verify asset\n"
            )
            return 1
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return int(mod.main(argv))


def main(argv: list[str] | None = None) -> None:
    """Console-script entry point (setuptools ``nexusrecon-verify``)."""
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] == "--extract":
        dest = Path(args[1]) if len(args) > 1 else Path("nexusrecon-verify.py")
        out = extract_verifier(dest)
        sys.stdout.write(f"Wrote standalone verifier to {out}\n")
        raise SystemExit(0)

    if args and args[0] in ("-h", "--help"):
        sys.stdout.write(
            "nexusrecon-verify — packaged standalone STIX receipt verifier\n\n"
            "  nexusrecon-verify --bundle B --receipt R --public-key K\n"
            "  nexusrecon-verify --extract [PATH]\n\n"
            "Depends only on the `cryptography` package (same as\n"
            "scripts/nexusrecon-verify.py). Use --extract to copy the\n"
            "script for auditors without a NexusRecon install.\n\n"
        )
        # Also show the asset's argparse help (bundle/receipt flags).
        raise SystemExit(run_verifier(["--help"]))

    raise SystemExit(run_verifier(args))


if __name__ == "__main__":  # pragma: no cover
    main()
