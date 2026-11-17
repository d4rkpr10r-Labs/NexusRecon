"""OWASP Amass enum JSON / JSONL → Living Graph.

Maps ``amass enum -json`` records into subdomain/domain + IP
entities with ``RESOLVES_TO`` edges. Does **not** reimplement
Amass recursion — operators run Amass externally and ingest
the export (NEX-21 / P4.16).

Record shape (one object per line)::

  {"name": "www.example.com", "domain": "example.com",
   "addresses": [{"ip": "93.184.216.34"}], "source": "crtsh"}
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from nexusrecon.ingest._json_stream import iter_json_records
from nexusrecon.ingest.types import ImportReport
from nexusrecon.models.entities import RelationshipType

log = structlog.get_logger(__name__)


def _parent_domain(name: str) -> str:
    parts = name.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return name


def _is_ip(value: str) -> bool:
    # Minimal v4/v6 check — full validation left to EntityGraph.
    if not value:
        return False
    if value.count(".") == 3 and all(
        p.isdigit() and 0 <= int(p) <= 255 for p in value.split(".")
    ):
        return True
    return ":" in value  # IPv6-ish


class AmassImporter:
    """Amass enum JSONL / JSON array → EntityGraph."""

    name: str = "amass"

    def __init__(self, *, source_label: str | None = None):
        self.source_label = source_label or f"imported_from:{self.name}"

    def import_file(self, path: Path | str, graph: Any) -> ImportReport:
        p = Path(path).expanduser()
        report = ImportReport(importer=self.name, source_path=str(p))
        if not p.exists():
            report.warnings.append(f"file not found: {p}")
            return report
        try:
            body = p.read_text(encoding="utf-8")
        except Exception as exc:
            report.warnings.append(f"read failed: {exc}")
            return report
        return self.import_text(body, graph, source_path=str(p))

    def import_text(
        self,
        body: str,
        graph: Any,
        *,
        source_path: str = "",
    ) -> ImportReport:
        report = ImportReport(importer=self.name, source_path=source_path)
        for item in iter_json_records(body, report):
            self._import_record(item, graph, report)
        return report

    def _import_record(
        self,
        item: dict[str, Any],
        graph: Any,
        report: ImportReport,
    ) -> None:
        name = str(item.get("name") or item.get("subdomain") or "").strip().lower()
        if not name:
            report.skipped += 1
            return

        amass_src = str(item.get("source") or "").strip()
        host_id = self._add_host(graph, report, name)
        if host_id is None:
            report.skipped += 1
            return

        # Secondary provenance: Amass's own collector label when present.
        if amass_src:
            try:
                self._add_host(
                    graph, report, name,
                    source=f"amass:{amass_src}",
                    count=False,
                )
            except Exception as exc:
                report.warnings.append(f"secondary source {amass_src}: {exc}")

        addresses = item.get("addresses") or []
        if isinstance(addresses, list):
            for addr in addresses:
                ip = ""
                if isinstance(addr, dict):
                    ip = str(addr.get("ip") or "").strip()
                elif isinstance(addr, str):
                    ip = addr.strip()
                if not ip or not _is_ip(ip):
                    continue
                try:
                    before = (graph.graph.number_of_nodes()
                              if hasattr(graph, "graph") else 0)
                    ip_id = graph.add_ip(ip, source=self.source_label)
                    after = (graph.graph.number_of_nodes()
                             if hasattr(graph, "graph") else before)
                    if after > before:
                        report.entities_added += 1
                        report.counts_by_type["ip_address"] = (
                            report.counts_by_type.get("ip_address", 0) + 1
                        )
                    else:
                        report.entities_merged += 1
                    graph.relate(
                        host_id, ip_id, RelationshipType.RESOLVES_TO,
                        source_tool=self.source_label,
                    )
                    report.relationships_added += 1
                except Exception as exc:
                    report.warnings.append(f"ip {ip}: {exc}")

    def _add_host(
        self,
        graph: Any,
        report: ImportReport,
        name: str,
        *,
        source: str | None = None,
        count: bool = True,
    ) -> str | None:
        src = source or self.source_label
        parent = _parent_domain(name)
        try:
            before = graph.graph.number_of_nodes()
            if name.count(".") >= 2 and name != parent:
                host_id = graph.add_subdomain(name, parent=parent, source=src)
                etype = "subdomain"
            else:
                host_id = graph.add_domain(name, source=src)
                etype = "domain"
            after = graph.graph.number_of_nodes()
            if count:
                if after > before:
                    report.entities_added += 1
                    report.counts_by_type[etype] = (
                        report.counts_by_type.get(etype, 0) + 1
                    )
                else:
                    report.entities_merged += 1
            # Ensure parent domain exists for subdomain hosts.
            if etype == "subdomain":
                before_p = graph.graph.number_of_nodes()
                did = graph.add_domain(parent, source=src)
                after_p = graph.graph.number_of_nodes()
                if count and after_p > before_p:
                    report.entities_added += 1
                    report.counts_by_type["domain"] = (
                        report.counts_by_type.get("domain", 0) + 1
                    )
                if did and did != host_id:
                    graph.relate(
                        did, host_id, RelationshipType.HAS_SUBDOMAIN,
                        source_tool=src,
                    )
                    if count:
                        report.relationships_added += 1
            return host_id
        except Exception as exc:
            report.warnings.append(f"host {name}: {exc}")
            return None
