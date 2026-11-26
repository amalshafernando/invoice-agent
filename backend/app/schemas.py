"""Shared Pydantic contracts: ERP <-> MCP tools <-> LangGraph state (Part 2)."""
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")      # unknown fields => validation error


class LineItem(Strict):
    description: str = Field(max_length=300)
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)


class InvoiceExtraction(Strict):
    """What the quarantined extractor LLM must return (Part 2)."""
    invoice_no: str
    supplier_name: str
    po_number: Optional[str] = None
    currency: str = "USD"
    items: list[LineItem]
    total: float = Field(ge=0)
    notes: str = ""                                  # free text = UNTRUSTED
    extraction_confidence: float = Field(default=1.0, ge=0, le=1)


class POLine(Strict):
    line_no: int
    description: str
    qty_ordered: float
    qty_received: float
    unit_price: float


class PurchaseOrder(Strict):
    po_number: str
    supplier_id: str
    currency: str
    status: Literal["OPEN", "CLOSED", "CANCELLED"]
    lines: list[POLine]
    total: float
    note: str = ""


class Supplier(Strict):
    supplier_id: str
    name: str
    status: Literal["ACTIVE", "SUSPENDED", "ON_HOLD"]
    payment_terms: str = "NET30"
    note: str = ""


class InvoiceDraftIn(Strict):
    invoice_no: str
    supplier_id: str
    po_number: str
    total: float = Field(ge=0)
    currency: str = "USD"
    idempotency_key: str = Field(min_length=8, max_length=80)


class InvoiceDraftOut(Strict):
    draft_id: str
    status: Literal["DRAFT"] = "DRAFT"
    idempotent_replay: bool = False


class TicketIn(Strict):
    title: str = Field(max_length=200)
    severity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    po_number: Optional[str] = None
    details: str = Field(default="", max_length=2000)


class TicketOut(Strict):
    ticket_id: str
    status: Literal["OPEN"] = "OPEN"
