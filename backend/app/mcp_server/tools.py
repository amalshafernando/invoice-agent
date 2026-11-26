"""Typed MCP tools. Each tool = scope + input model + output model + handler."""
from dataclasses import dataclass
from typing import Callable, Optional
from pydantic import BaseModel

from .. import schemas as S
from .erp_client import ErpClient


class ToolError(Exception):
    pass


class PoArgs(S.Strict):
    po_number: str


class SupplierArgs(S.Strict):
    supplier_id: str


class DupArgs(S.Strict):
    invoice_no: str
    supplier_id: str


class DupOut(S.Strict):
    exists: bool
    draft_id: Optional[str] = None


@dataclass
class Tool:
    name: str
    description: str
    scope: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[ErpClient, BaseModel], BaseModel]


def _ok(r, what: str):
    if r.status_code >= 400:
        raise ToolError(f"{what}: HTTP {r.status_code} {r.json().get('detail', '')}")
    return r.json()


def get_open_purchase_order(erp: ErpClient, a: PoArgs) -> S.PurchaseOrder:
    po = S.PurchaseOrder(**_ok(erp.get(f"/odata/PurchaseOrderSet/{a.po_number}"), "get_po"))
    return po


def check_supplier_status(erp: ErpClient, a: SupplierArgs) -> S.Supplier:
    return S.Supplier(**_ok(erp.get(f"/odata/SupplierSet/{a.supplier_id}"), "get_supplier"))


def find_existing_invoice(erp: ErpClient, a: DupArgs) -> DupOut:
    rows = _ok(erp.get("/odata/InvoiceDraftSet", invoice_no=a.invoice_no,
                       supplier_id=a.supplier_id), "find_invoice")["value"]
    return DupOut(exists=bool(rows), draft_id=rows[0]["draft_id"] if rows else None)


def create_itsm_exception_ticket(erp: ErpClient, a: S.TicketIn) -> S.TicketOut:
    return S.TicketOut(**_ok(erp.post("/itsm/tickets", a.model_dump()), "create_ticket"))


def submit_invoice_draft(erp: ErpClient, a: S.InvoiceDraftIn) -> S.InvoiceDraftOut:
    return S.InvoiceDraftOut(**_ok(erp.post("/odata/InvoiceDraftSet", a.model_dump()),
                                   "submit_draft"))


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("get_open_purchase_order", "Fetch a purchase order with received quantities.",
         "read:po", PoArgs, S.PurchaseOrder, get_open_purchase_order),
    Tool("check_supplier_status", "Return supplier status (ACTIVE/SUSPENDED/ON_HOLD).",
         "read:supplier", SupplierArgs, S.Supplier, check_supplier_status),
    Tool("find_existing_invoice", "Check whether an invoice number already exists.",
         "read:invoice", DupArgs, DupOut, find_existing_invoice),
    Tool("create_itsm_exception_ticket", "Open an exception ticket for a human owner.",
         "write:ticket", S.TicketIn, S.TicketOut, create_itsm_exception_ticket),
    Tool("submit_invoice_draft", "Create an invoice DRAFT (never posts/pays).",
         "write:invoice_draft", S.InvoiceDraftIn, S.InvoiceDraftOut, submit_invoice_draft),
]}
