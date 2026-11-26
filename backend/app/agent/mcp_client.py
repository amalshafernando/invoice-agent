"""Agent-side MCP client (stateless: every call carries its own headers)."""
import json
import time
from dataclasses import dataclass, field

import httpx

from ..config import settings
from . import telemetry

SCOPES = "read:po read:supplier read:invoice write:invoice_draft write:ticket"


@dataclass
class ToolResult:
    ok: bool
    data: dict = field(default_factory=dict)
    error: str = ""
    findings: list = field(default_factory=list)


class McpClient:
    def __init__(self, mcp_http: httpx.Client, erp_http: httpx.Client):
        self.mcp, self.erp = mcp_http, erp_http
        self._tok, self._exp = "", 0.0
        self.log: list[dict] = []          # every tool call (args included) for eval/audit

    def _token(self) -> str:
        if time.time() > self._exp - 30:
            r = self.erp.post("/oauth/token", data={
                "grant_type": "client_credentials", "client_id": "invoice-agent",
                "client_secret": "agent-secret", "scope": SCOPES})
            r.raise_for_status()
            self._tok, self._exp = r.json()["access_token"], time.time() + 900
        return self._tok

    def call(self, case_id: str, name: str, args: dict) -> ToolResult:
        self.log.append({"case_id": case_id, "tool": name, "args": args})
        with telemetry.tool_span(case_id, name) as sp:
            r = self.mcp.post("/mcp", headers={
                "MCP-Protocol-Version": settings.mcp_protocol_version,
                "Mcp-Method": "tools/call", "Mcp-Name": name,
                "Authorization": f"Bearer {self._token()}"},
                content=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                    "params": {"name": name, "arguments": args}}))
            body = r.json()
            if "error" in body:
                sp.set_attribute("app.error", body["error"]["message"])
                return ToolResult(False, error=body["error"]["message"])
            res = body["result"]
            sp.set_attribute("app.untrusted_findings", len(res.get("_meta", {}).get("securityFindings", [])))
            if res.get("isError"):
                return ToolResult(False, error=res["content"][0]["text"])
            return ToolResult(True, res["structuredContent"], findings=res["_meta"]["securityFindings"])
