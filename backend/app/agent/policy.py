"""Deterministic Policy Gateway. NO LLM here. Pure function => unit-testable.
Precedence: BLOCK > ESCALATE > HITL_REVIEW > AUTO_DRAFT."""
from typing import Literal, Optional
from pydantic import BaseModel

from ..config import settings
from ..schemas import InvoiceExtraction

BLOCK_REASONS = {"SUPPLIER_SUSPENDED", "SUPPLIER_ON_HOLD", "DUPLICATE_INVOICE"}


class Decision(BaseModel):
    action: Literal["BLOCK", "ESCALATE", "HITL_REVIEW", "AUTO_DRAFT"]
    reasons: list[str]
    line_checks: list[dict] = []
    max_price_var_pct: float = 0.0
    invoice_total: float = 0.0
    po_total: Optional[float] = None


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def decide(inv: InvoiceExtraction, po: Optional[dict], supplier: Optional[dict],
           duplicate: bool, lookup_error: bool = False) -> Decision:
    reasons: list[str] = []
    checks: list[dict] = []
    worst = 0.0

    if inv.extraction_confidence < settings.min_confidence:
        reasons.append("LOW_CONFIDENCE")
    if lookup_error:
        reasons.append("TOOL_ERROR")
    if abs(sum(i.quantity * i.unit_price for i in inv.items) - inv.total) > 0.05:
        reasons.append("TOTAL_ARITHMETIC")

    if po is None:
        reasons.append("PO_NOT_FOUND")
    else:
        if po["status"] != "OPEN":
            reasons.append("PO_NOT_OPEN")
        if inv.currency != po["currency"]:
            reasons.append("CURRENCY_MISMATCH")
        if len(inv.items) != len(po["lines"]):
            reasons.append("LINE_COUNT_MISMATCH")
        for it, ln in zip(inv.items, po["lines"]):
            if _norm(it.description) != _norm(ln["description"]):
                reasons.append("LINE_DESC_MISMATCH")
            pv = (it.unit_price - ln["unit_price"]) / ln["unit_price"] * 100 if ln["unit_price"] else 100.0
            qv_limit = ln["qty_received"] * (1 + settings.qty_tolerance_pct / 100)
            over_qty = it.quantity > qv_limit + 1e-9
            if abs(pv) > settings.price_tolerance_pct:
                reasons.append("PRICE_VARIANCE")
            if over_qty:
                reasons.append("QTY_OVER_RECEIVED")
            worst = max(worst, abs(pv))
            checks.append({"description": it.description, "inv_qty": it.quantity,
                           "po_qty_received": ln["qty_received"], "inv_price": it.unit_price,
                           "po_price": ln["unit_price"], "price_var_pct": round(pv, 2),
                           "qty_over": over_qty})
        if supplier is None:
            reasons.append("SUPPLIER_UNKNOWN")
        else:
            if supplier["status"] == "SUSPENDED":
                reasons.append("SUPPLIER_SUSPENDED")
            elif supplier["status"] != "ACTIVE":
                reasons.append("SUPPLIER_ON_HOLD")
            if _norm(supplier["name"]) != _norm(inv.supplier_name):
                reasons.append("SUPPLIER_NAME_MISMATCH")
    if duplicate:
        reasons.append("DUPLICATE_INVOICE")

    reasons = list(dict.fromkeys(reasons))
    if any(r in BLOCK_REASONS for r in reasons):
        action = "BLOCK"
    elif reasons:
        action = "ESCALATE"
    elif inv.total >= settings.hitl_value_threshold:
        action, reasons = "HITL_REVIEW", ["HIGH_VALUE"]
    else:
        action = "AUTO_DRAFT"
    return Decision(action=action, reasons=reasons, line_checks=checks,
                    max_price_var_pct=round(worst, 2), invoice_total=inv.total,
                    po_total=po["total"] if po else None)
