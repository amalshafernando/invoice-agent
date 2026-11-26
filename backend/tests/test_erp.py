from app.mock_erp import audit, store
from .conftest import token


def bearer(erp, who="invoice-agent", scope="read:po"):
    return {"Authorization": "Bearer " + token(erp, who, scope).json()["access_token"]}


def test_token_rejects_scope_not_allowed_for_client(erp):
    assert token(erp, "finance-ui", "write:invoice_draft").status_code == 400


def test_token_rejects_bad_secret(erp):
    r = erp.post("/oauth/token", data={"grant_type": "client_credentials",
                 "client_id": "invoice-agent", "client_secret": "x", "scope": "read:po"})
    assert r.status_code == 401


def test_no_token_is_401_and_wrong_scope_is_403(erp):
    assert erp.get("/odata/PurchaseOrderSet/PO-1").status_code == 401
    h = bearer(erp, scope="read:supplier")
    assert erp.get("/odata/PurchaseOrderSet/PO-1", headers=h).status_code == 403


def test_get_po_total_and_404(erp):
    h = bearer(erp)
    r = erp.get("/odata/PurchaseOrderSet/PO-1", headers=h)
    assert r.status_code == 200 and r.json()["total"] == 1000.0
    assert erp.get("/odata/PurchaseOrderSet/NOPE", headers=h).status_code == 404


def draft(key="idem-key-0001", inv="INV-1", sup="SUP-OK", po="PO-1"):
    return {"invoice_no": inv, "supplier_id": sup, "po_number": po,
            "total": 1000.0, "idempotency_key": key}


def test_draft_idempotent_replay(erp):
    h = bearer(erp, scope="write:invoice_draft")
    a = erp.post("/odata/InvoiceDraftSet", json=draft(), headers=h).json()
    b = erp.post("/odata/InvoiceDraftSet", json=draft(), headers=h).json()
    assert a["draft_id"] == b["draft_id"] and b["idempotent_replay"] is True


def test_draft_duplicate_invoice_and_suspended_supplier(erp):
    h = bearer(erp, scope="write:invoice_draft")
    assert erp.post("/odata/InvoiceDraftSet", json=draft("idem-key-0002", "INV-DUP"),
                    headers=h).status_code == 409
    assert erp.post("/odata/InvoiceDraftSet", json=draft("idem-key-0003", "INV-9", "SUP-BAD", "PO-2"),
                    headers=h).status_code == 409


def test_invoice_number_duplicate_ignores_case_and_outer_whitespace(erp):
    h = bearer(erp, scope="write:invoice_draft")
    first = erp.post("/odata/InvoiceDraftSet",
                      json=draft("idem-key-0010", "INV-NORMALIZED"), headers=h)
    assert first.status_code == 200

    duplicate = erp.post("/odata/InvoiceDraftSet",
                         json=draft("idem-key-0011", " inv-normalized "), headers=h)
    assert duplicate.status_code == 409


def test_invoice_lookup_normalizes_case_and_outer_whitespace(erp):
    writer = bearer(erp, scope="write:invoice_draft")
    reader = bearer(erp, scope="read:invoice")
    created = erp.post("/odata/InvoiceDraftSet",
                       json=draft("idem-key-0012", "INV-LOOKUP"), headers=writer)
    assert created.status_code == 200

    found = erp.get("/odata/InvoiceDraftSet",
                    params={"invoice_no": " inv-lookup ", "supplier_id": "SUP-OK"},
                    headers=reader)
    assert found.status_code == 200
    assert found.json()["value"][0]["draft_id"] == created.json()["draft_id"]


def test_extra_fields_rejected(erp):
    h = bearer(erp, scope="write:invoice_draft")
    bad = {**draft(), "approved": True}
    assert erp.post("/odata/InvoiceDraftSet", json=bad, headers=h).status_code == 422


def test_audit_chain_ok_then_tamper_detected(erp):
    h = bearer(erp)
    erp.get("/odata/PurchaseOrderSet/PO-1", headers=h)
    erp.get("/odata/PurchaseOrderSet/PO-1", headers=h)
    assert audit.verify_chain()["ok"] is True
    with store.conn() as c:
        c.execute("UPDATE audit SET actor='attacker' WHERE id=1")
    assert audit.verify_chain()["ok"] is False
