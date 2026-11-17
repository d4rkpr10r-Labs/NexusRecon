"""urlscan.io historical scan correlation tool."""
from __future__ import annotations

from typing import Any

import httpx

from nexusrecon.tools.base import Category, OSINTTool, Tier, ToolResult, make_http_client
from nexusrecon.tools.registry import register_tool
from nexusrecon.opsec.context import proxy_kwargs


@register_tool
class URLScanTool(OSINTTool):
    name = "urlscan"
    tier = Tier.T0
    category = Category.INFRASTRUCTURE
    requires_keys = []
    optional_keys = ["urlscan_api_key"]
    description = "urlscan.io historical scan data and screenshot correlation"
    target_types = ["domain"]
    dynamic_trigger_hints = ["malicious url found", "phishing page detected"]

    async def run(self, target: str, **kwargs: Any) -> ToolResult:
        key = self.config.get_secret("urlscan_api_key")
        try:
            headers = {}
            if key:
                headers["API-Key"] = key

            client = make_http_client(
                base_url="https://urlscan.io/api/v1",
                headers=headers,
                timeout=15.0,
                **proxy_kwargs()
            )

            # Search scans for domain
            resp = await client.get("/search/", params={"q": f"domain:{target}", "size": 50})

            data = {}
            if resp.status_code == 200:
                r = resp.json()
                results = []
                for hit in r.get("results", [])[:20]:
                    hit.get("task", {})
                    page = hit.get("page", {})
                    results.append({
                        "scan_url": page.get("url"),
                        "scan_date": hit.get("task", {}).get("time"),
                        "screenshot_url": hit.get("screenshot"),
                        "ip": page.get("ip"),
                        "country": page.get("country"),
                        "server": page.get("server"),
                        "title": page.get("title"),
                        "status": page.get("status"),
                    })
                data = {"total": r.get("total", 0), "scans": results}

            await client.aclose()
            return ToolResult(
                success=True, source=self.name, data=data,
                result_count=len(data.get("scans", [])),
            )
        except Exception as e:
            return ToolResult(success=False, source=self.name, error=str(e))
