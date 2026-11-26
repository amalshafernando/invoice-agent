"""Deterministic Policy Gateway. NO LLM here. Pure function => unit-testable.
Precedence: BLOCK > ESCALATE > HITL_REVIEW > AUTO_DRAFT."""
from typing import Literal, Optional
from pydantic import BaseModel

from ..config import settings
from ..schemas import InvoiceExtraction
from .memory import cosine_sim, embed_text

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


def align_lines(inv_items, po_lines: list[dict]) -> list[tuple[object, dict, float]]:
    """Order-independent semantic 1-to-1 alignment between invoice items and PO lines."""
    if not inv_items or not po_lines:
        return []
    inv_vecs = [embed_text(it.description) for it in inv_items]
    po_vecs = [embed_text(ln["description"]) for ln in po_lines]
    used: set[int] = set()
    aligned: list[tuple[object, dict, float]] = []
    for i, it in enumerate(inv_items):
        best_j, best_sim = -1, -1.0
        for j, ln in enumerate(po_lines):
            if j in used:
                continue
            sim = 1.0 if _norm(it.description) == _norm(ln["description"]) else cosine_sim(inv_vecs[i], po_vecs[j])
            if sim > best_sim:
                best_j, best_sim = j, sim
        if best_j >= 0:
            used.add(best_j)
            aligned.append((it, po_lines[best_j], max(0.0, best_sim)))
    return aligned


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
        for it, ln, sim in align_lines(inv.items, po["lines"]):
            if _norm(it.description) != _norm(ln["description"]) and sim < settings.semantic_match_threshold:
                reasons.append("LINE_DESC_MISMATCH")
            pv = (it.unit_price - ln["unit_price"]) / ln["unit_price"] * 100 if ln["unit_price"] else 100.0
            qv_limit = ln["qty_received"] * (1 + settings.qty_tolerance_pct / 100)
            over_qty = it.quantity > qv_limit + 1e-9
            if abs(pv) > settings.price_tolerance_pct:
                reasons.append("PRICE_VARIANCE")
            if over_qty:
                reasons.append("QTY_OVER_RECEIVED")
            worst = max(worst, abs(pv))
            checks.append({"description": it.description, "po_description": ln["description"],
                           "match_score": round(sim, 2), "inv_qty": it.quantity,
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
