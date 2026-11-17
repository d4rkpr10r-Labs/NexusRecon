"""Shared NDJSON / JSON-array parsing for ingest adapters."""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from nexusrecon.ingest.types import ImportReport


def iter_json_records(
    body: str,
    report: ImportReport,
) -> Iterator[dict[str, Any]]:
    """Yield dict records from a JSON array or JSON-lines body.

    Malformed lines/items increment ``report.skipped`` and append
    warnings — never raises.
    """
    body = (body or "").strip()
    if not body:
        return

    if body.startswith("["):
        try:
            items = json.loads(body)
        except json.JSONDecodeError as exc:
            report.warnings.append(f"invalid JSON array: {exc}")
            return
        if not isinstance(items, list):
            report.warnings.append("top-level value is not a list")
            return
        for item in items:
            if isinstance(item, dict):
                yield item
            else:
                report.skipped += 1
        return

    for lineno, line in enumerate(body.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            report.warnings.append(f"line {lineno}: invalid JSON ({exc})")
            report.skipped += 1
            continue
        if isinstance(item, dict):
            yield item
        else:
            report.skipped += 1
