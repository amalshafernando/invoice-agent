"""Mock IFS-Cloud-style ERP: OData-like endpoints + OAuth2 + scoped RBAC."""
import sqlite3
from fastapi import Depends, FastAPI, Form, HTTPException

from .. import schemas as S
from ..security import Principal, issue_token, require_scope
from . import audit, store

app = FastAPI(title="Mock IFS ERP", version="1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/oauth/token")
def token(grant_type: str = Form(...), client_id: str = Form(...),
          client_secret: str = Form(...), scope: str = Form(...)):
    if grant_type != "client_credentials":
        raise HTTPException(400, "unsupported_grant_type")
    t = issue_token(client_id, client_secret, scope.split())
    return {"access_token": t, "token_type": "Bearer", "expires_in": 900, "scope": scope}


@app.get("/odata/PurchaseOrderSet/{po_number}", response_model=S.PurchaseOrder)
def get_po(po_number: str, p: Principal = Depends(require_scope("read:po"))):
    with store.conn() as c:
        po = c.execute("SELECT * FROM purchase_orders WHERE po_number=?",
                       (po_number,)).fetchone()
        if not po:
            raise HTTPException(404, "PO not found")
        lines = c.execute("SELECT * FROM po_lines WHERE po_number=? ORDER BY line_no",
                          (po_number,)).fetchall()
    out = S.PurchaseOrder(
        po_number=po["po_number"], supplier_id=po["supplier_id"],
        currency=po["currency"], status=po["status"], note=po["note"] or "",
        lines=[S.POLine(**{k: l[k] for k in ("line_no", "description", "qty_ordered",
                                             "qty_received", "unit_price")}) for l in lines],
        total=round(sum(l["qty_ordered"] * l["unit_price"] for l in lines), 2))
    audit.append(p.sub, "read_po", {"po_number": po_number})
    return out


@app.get("/odata/SupplierSet/{supplier_id}", response_model=S.Supplier)
def get_supplier(supplier_id: str, p: Principal = Depends(require_scope("read:supplier"))):
    with store.conn() as c:
        s = c.execute("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)).fetchone()
    if not s:
        raise HTTPException(404, "Supplier not found")
    audit.append(p.sub, "read_supplier", {"supplier_id": supplier_id})
    return S.Supplier(supplier_id=s["supplier_id"], name=s["name"], status=s["status"],
                      payment_terms=s["payment_terms"] or "NET30", note=s["note"] or "")


@app.get("/odata/InvoiceDraftSet")
def find_invoice(invoice_no: str, supplier_id: str,
                 p: Principal = Depends(require_scope("read:invoice"))):
    with store.conn() as c:
        rows = c.execute("SELECT draft_id, invoice_no, total FROM invoice_drafts "
                         "WHERE lower(trim(invoice_no))=lower(trim(?)) AND supplier_id=?",
                         (invoice_no, supplier_id)).fetchall()
    return {"@odata.context": "InvoiceDraftSet", "value": [dict(r) for r in rows]}


@app.post("/odata/InvoiceDraftSet", response_model=S.InvoiceDraftOut)
def create_draft(body: S.InvoiceDraftIn,
                 p: Principal = Depends(require_scope("write:invoice_draft"))):
    with store.conn() as c:
        prior = c.execute("SELECT draft_id FROM invoice_drafts WHERE idempotency_key=?",
                          (body.idempotency_key,)).fetchone()
        if prior:                                           # safe retry, no double posting
            return S.InvoiceDraftOut(draft_id=prior["draft_id"], idempotent_replay=True)
        sup = c.execute("SELECT status FROM suppliers WHERE supplier_id=?",
                        (body.supplier_id,)).fetchone()
        po = c.execute("SELECT status FROM purchase_orders WHERE po_number=?",
                       (body.po_number,)).fetchone()
        if not po:
            raise HTTPException(404, "PO not found")
        if not sup or sup["status"] != "ACTIVE":           # ERP-side guard (defence in depth)
            raise HTTPException(409, "Supplier not ACTIVE")
        draft_id = store.new_id("DRF")
        try:
            c.execute("INSERT INTO invoice_drafts(draft_id,invoice_no,supplier_id,po_number,"
                      "total,currency,idempotency_key,created_by) VALUES(?,?,?,?,?,?,?,?)",
                      (draft_id, body.invoice_no, body.supplier_id, body.po_number,
                       body.total, body.currency, body.idempotency_key, p.sub))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Duplicate invoice for this supplier")
    audit.append(p.sub, "create_invoice_draft", {"draft_id": draft_id, **body.model_dump()})
    return S.InvoiceDraftOut(draft_id=draft_id)


@app.post("/itsm/tickets", response_model=S.TicketOut)
def create_ticket(body: S.TicketIn, p: Principal = Depends(require_scope("write:ticket"))):
    tid = store.new_id("EXC")
    with store.conn() as c:
        c.execute("INSERT INTO tickets(ticket_id,title,severity,po_number,details,created_by) "
                  "VALUES(?,?,?,?,?,?)",
                  (tid, body.title, body.severity, body.po_number, body.details, p.sub))
    audit.append(p.sub, "create_ticket", {"ticket_id": tid, **body.model_dump()})
    return S.TicketOut(ticket_id=tid)


@app.get("/audit/verify")
def verify(p: Principal = Depends(require_scope("admin:audit"))):
    return audit.verify_chain()
