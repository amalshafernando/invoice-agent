import json
from .conftest import token

V = "2026-07-28"


def call(mcp, method, params=None, tok=None, name=None, version=V, header_method=None, id_=1):
    h = {"MCP-Protocol-Version": version, "Mcp-Method": header_method or method}
    if name:
        h["Mcp-Name"] = name
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return mcp.post("/mcp", headers=h, content=json.dumps(
        {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}))


def agent_token(erp, scope="read:po read:supplier read:invoice write:invoice_draft write:ticket"):
    return token(erp, "invoice-agent", scope).json()["access_token"]


def test_discover_is_public_and_stateless(mcp):
    r = call(mcp, "server/discover")
    assert r.status_code == 200 and V in r.json()["result"]["supportedVersions"]
    assert "mcp-session-id" not in {k.lower() for k in r.headers}


def test_header_body_mismatch_rejected(mcp, erp):
    t = agent_token(erp)
    r = call(mcp, "tools/call", {"name": "check_supplier_status", "arguments": {}},
             tok=t, name="get_open_purchase_order")
    assert r.status_code == 400
    assert call(mcp, "tools/list", tok=t, header_method="tools/call").status_code == 400
    assert call(mcp, "tools/list", tok=t, version="2025-11-25").status_code == 400


def test_tools_list_filtered_by_scope(mcp, erp):
    t = agent_token(erp, "read:po")
    names = [x["name"] for x in call(mcp, "tools/list", tok=t).json()["result"]["tools"]]
    assert names == ["get_open_purchase_order"]


def test_call_without_scope_is_forbidden(mcp, erp):
    t = agent_token(erp, "read:po")
    r = call(mcp, "tools/call", {"name": "submit_invoice_draft", "arguments": {}},
             tok=t, name="submit_invoice_draft")
    assert r.json()["error"]["code"] == -32003 and r.status_code == 403


def test_no_token_is_401(mcp):
    assert call(mcp, "tools/list").status_code == 401


def test_get_po_and_injection_redacted(mcp, erp):
    t = agent_token(erp)
    r = call(mcp, "tools/call", {"name": "get_open_purchase_order",
             "arguments": {"po_number": "PO-1"}}, tok=t, name="get_open_purchase_order").json()
    res = r["result"]
    assert res["isError"] is False and res["structuredContent"]["total"] == 1000.0
    assert "50,000" not in json.dumps(res["structuredContent"])
    assert res["_meta"]["untrusted"] is True and res["_meta"]["securityFindings"]


def test_invalid_arguments_and_unknown_tool(mcp, erp):
    t = agent_token(erp)
    r = call(mcp, "tools/call", {"name": "get_open_purchase_order",
             "arguments": {"po": "x"}}, tok=t, name="get_open_purchase_order").json()
    assert r["error"]["code"] == -32602
    r = call(mcp, "tools/call", {"name": "hack", "arguments": {}}, tok=t, name="hack").json()
    assert r["error"]["code"] == -32602


def test_submit_draft_then_erp_error_is_tool_error(mcp, erp):
    t = agent_token(erp)
    args = {"invoice_no": "INV-NEW", "supplier_id": "SUP-OK", "po_number": "PO-1",
            "total": 1000.0, "idempotency_key": "idem-key-9999"}
    ok = call(mcp, "tools/call", {"name": "submit_invoice_draft", "arguments": args},
              tok=t, name="submit_invoice_draft").json()["result"]
    assert ok["structuredContent"]["status"] == "DRAFT"
    bad = call(mcp, "tools/call", {"name": "submit_invoice_draft",
               "arguments": {**args, "supplier_id": "SUP-BAD", "po_number": "PO-2",
                             "idempotency_key": "idem-key-8888"}},
               tok=t, name="submit_invoice_draft").json()["result"]
    assert bad["isError"] is True


def test_find_existing_invoice(mcp, erp):
    t = agent_token(erp)
    r = call(mcp, "tools/call", {"name": "find_existing_invoice",
             "arguments": {"invoice_no": "INV-DUP", "supplier_id": "SUP-OK"}},
             tok=t, name="find_existing_invoice").json()["result"]["structuredContent"]
    assert r["exists"] is True
