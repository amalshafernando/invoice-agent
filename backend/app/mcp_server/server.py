"""Stateless Streamable-HTTP MCP server (spec 2026-07-28 style).
No initialize handshake, no session id: every request is self-contained."""
import json
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..config import settings
from ..security import principal_from_header
from .erp_client import ErpClient
from .sanitize import sanitize
from .tools import TOOLS, ToolError

app = FastAPI(title="Governed MCP Server", version="1.0")
erp = ErpClient()          # tests replace: server.erp = ErpClient(TestClient(erp_app))

E_PARSE, E_REQUEST, E_METHOD, E_PARAMS, E_FORBIDDEN = -32700, -32600, -32601, -32602, -32003


def rpc_error(id_, code: int, msg: str, http: int = 200) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": id_,
                         "error": {"code": code, "message": msg}}, status_code=http)


def rpc_ok(id_, result: dict) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": result})


@app.get("/health")
def health():
    return {"status": "ok", "protocol": settings.mcp_protocol_version}


@app.post("/mcp")
async def mcp(request: Request,
              mcp_protocol_version: str | None = Header(default=None, alias="MCP-Protocol-Version"),
              mcp_method: str | None = Header(default=None, alias="Mcp-Method"),
              mcp_name: str | None = Header(default=None, alias="Mcp-Name"),
              authorization: str | None = Header(default=None)):
    try:
        body = json.loads(await request.body())
    except json.JSONDecodeError:
        return rpc_error(None, E_PARSE, "parse error", 400)
    id_, method, params = body.get("id"), body.get("method"), body.get("params") or {}

    # 1) header/body consistency (lets gateways route without parsing JSON)
    if mcp_protocol_version != settings.mcp_protocol_version:
        return rpc_error(id_, E_REQUEST, f"unsupported MCP-Protocol-Version "
                         f"(need {settings.mcp_protocol_version})", 400)
    if mcp_method != method:
        return rpc_error(id_, E_REQUEST, "Mcp-Method header != body method", 400)
    if method == "tools/call" and mcp_name != params.get("name"):
        return rpc_error(id_, E_REQUEST, "Mcp-Name header != params.name", 400)

    # 2) discovery is public; everything else needs a bearer token
    if method == "server/discover":
        return rpc_ok(id_, {
            "supportedVersions": [settings.mcp_protocol_version],
            "serverInfo": {"name": "invoice-governed-mcp", "version": "1.0"},
            "capabilities": {"tools": {}}})
    try:
        who = principal_from_header(authorization)
    except HTTPException as e:
        return rpc_error(id_, E_FORBIDDEN, e.detail, 401)

    if method == "tools/list":                    # least-privilege visibility
        tools = [{"name": t.name, "description": t.description,
                  "inputSchema": t.input_model.model_json_schema(),
                  "requiredScope": t.scope}
                 for t in TOOLS.values() if t.scope in who.scopes]
        return rpc_ok(id_, {"tools": tools, "ttlMs": 60_000})

    if method == "tools/call":
        tool = TOOLS.get(params.get("name", ""))
        if not tool:
            return rpc_error(id_, E_PARAMS, "unknown tool")
        if tool.scope not in who.scopes:          # DENY BY DEFAULT
            return rpc_error(id_, E_FORBIDDEN, f"missing scope {tool.scope}", 403)
        try:
            args = tool.input_model(**(params.get("arguments") or {}))
        except ValidationError as e:
            return rpc_error(id_, E_PARAMS, f"invalid arguments: {e.errors()[0]['msg']}")
        try:
            out = tool.handler(erp, args)
            data = tool.output_model.model_validate(out).model_dump()   # output contract
            clean, findings = sanitize(data)                            # untrusted output
            return rpc_ok(id_, {
                "content": [{"type": "text", "text": json.dumps(clean, ensure_ascii=False)}],
                "structuredContent": clean, "isError": False,
                "_meta": {"untrusted": True, "securityFindings": findings}})
        except ToolError as e:
            clean, _ = sanitize(str(e))
            return rpc_ok(id_, {"content": [{"type": "text", "text": clean}],
                                "isError": True})

    return rpc_error(id_, E_METHOD, f"method not found: {method}")
