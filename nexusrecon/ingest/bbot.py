"""BBOT scan JSON / NDJSON → Living Graph.

Maps BBOT Stable ``DNS_NAME`` / ``IP_ADDRESS`` events into the
EntityGraph with provenance. Does **not** reimplement BBOT's
event engine — operators run BBOT externally and ingest
``output.json`` / ``-om json`` (NEX-21 / P4.16).

Event shape (NDJSON)::

  {"type": "DNS_NAME", "data": "www.example.com",
   "resolved_hosts": ["1.2.3.4"], "module": "certspotter",
   "tags": ["subdomain"]}
  {"type": "IP_ADDRESS", "data": "1.2.3.4", "module": "A"}
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from nexusrecon.ingest._json_stream import iter_json_records
from nexusrecon.ingest.types import ImportReport
from nexusrecon.models.entities import RelationshipType

log = structlog.get_logger(__name__)

_ALLOWED_TYPES = frozenset({"DNS_NAME", "IP_ADDRESS"})


def _parent_domain(name: str) -> str:
    parts = name.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return name


def _is_ip(value: str) -> bool:
    if not value:
        return False
    if value.count(".") == 3 and all(
        p.isdigit() and 0 <= int(p) <= 255 for p in value.split(".")
    ):
        return True
    return ":" in value


class BBOTImporter:
    """BBOT NDJSON / JSON array → EntityGraph."""

    name: str = "bbot"

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
        # First pass: index event ids → host values for parent edges.
        events = list(iter_json_records(body, report))
        id_to_host: dict[str, str] = {}
        for item in events:
            etype = str(item.get("type") or "")
            if etype not in _ALLOWED_TYPES:
                continue
            data = item.get("data")
            if isinstance(data, str) and data.strip():
                eid = str(item.get("id") or "")
                if eid:
                    id_to_host[eid] = data.strip().lower()

        for item in events:
            self._import_event(item, graph, report, id_to_host)
        return report

    def _import_event(
        self,
        item: dict[str, Any],
        graph: Any,
        report: ImportReport,
        id_to_host: dict[str, str],
    ) -> None:
        etype = str(item.get("type") or "")
        if etype not in _ALLOWED_TYPES:
            report.skipped += 1
            return

        data = item.get("data")
        if not isinstance(data, str) or not data.strip():
            report.skipped += 1
            return
        value = data.strip().lower()
        module = str(item.get("module") or "").strip()

        if etype == "IP_ADDRESS" or _is_ip(value):
            self._add_ip(graph, report, value, module=module)
            return

        host_id = self._add_dns_name(graph, report, value, module=module)
        if host_id is None:
            return

        # resolved_hosts → RESOLVES_TO
        for rh in item.get("resolved_hosts") or []:
            ip = str(rh).strip().lower()
            if not _is_ip(ip):
                continue
            ip_id = self._add_ip(graph, report, ip, module=module)
            if ip_id is None:
                continue
            try:
                graph.relate(
                    host_id, ip_id, RelationshipType.RESOLVES_TO,
                    source_tool=self.source_label,
                )
                report.relationships_added += 1
            except Exception as exc:
                report.warnings.append(f"resolves_to {value}->{ip}: {exc}")

        # parent DNS_NAME → HAS_SUBDOMAIN when both are names
        parent_id = str(item.get("parent") or "")
        parent_host = id_to_host.get(parent_id, "")
        if parent_host and parent_host != value and not _is_ip(parent_host):
            parent_node = self._add_dns_name(
                graph, report, parent_host, module=module, count=False,
            )
            if parent_node and parent_node != host_id:
                # Prefer parent as apex → child subdomain
                try:
                    if value.endswith("." + parent_host) or value.count(".") > parent_host.count("."):
                        graph.relate(
                            parent_node, host_id,
                            RelationshipType.HAS_SUBDOMAIN,
                            source_tool=self.source_label,
                        )
                    else:
                        graph.relate(
                            host_id, parent_node,
                            RelationshipType.HAS_SUBDOMAIN,
                            source_tool=self.source_label,
                        )
                    report.relationships_added += 1
                except Exception as exc:
                    report.warnings.append(f"parent edge: {exc}")

    def _add_dns_name(
        self,
        graph: Any,
        report: ImportReport,
        name: str,
        *,
        module: str = "",
        count: bool = True,
    ) -> str | None:
        parent = _parent_domain(name)
        try:
            before = graph.graph.number_of_nodes()
            if name.count(".") >= 2 and name != parent:
                host_id = graph.add_subdomain(
                    name, parent=parent, source=self.source_label,
                )
                etype = "subdomain"
            else:
                host_id = graph.add_domain(name, source=self.source_label)
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
            if module:
                # Secondary provenance: BBOT module that emitted the event.
                if etype == "subdomain":
                    graph.add_subdomain(
                        name, parent=parent, source=f"bbot:{module}",
                    )
                else:
                    graph.add_domain(name, source=f"bbot:{module}")
            if etype == "subdomain":
                before_p = graph.graph.number_of_nodes()
                did = graph.add_domain(parent, source=self.source_label)
                after_p = graph.graph.number_of_nodes()
                if count and after_p > before_p:
                    report.entities_added += 1
                    report.counts_by_type["domain"] = (
                        report.counts_by_type.get("domain", 0) + 1
                    )
                if did and did != host_id:
                    graph.relate(
                        did, host_id, RelationshipType.HAS_SUBDOMAIN,
                        source_tool=self.source_label,
                    )
                    if count:
                        report.relationships_added += 1
            return host_id
        except Exception as exc:
            report.warnings.append(f"dns_name {name}: {exc}")
            return None

    def _add_ip(
        self,
        graph: Any,
        report: ImportReport,
        ip: str,
        *,
        module: str = "",
    ) -> str | None:
        try:
            before = graph.graph.number_of_nodes()
            ip_id = graph.add_ip(ip, source=self.source_label)
            after = graph.graph.number_of_nodes()
            if after > before:
                report.entities_added += 1
                report.counts_by_type["ip_address"] = (
                    report.counts_by_type.get("ip_address", 0) + 1
                )
            else:
                report.entities_merged += 1
            if module:
                graph.add_ip(ip, source=f"bbot:{module}")
            return ip_id
        except Exception as exc:
            report.warnings.append(f"ip {ip}: {exc}")
            return None
