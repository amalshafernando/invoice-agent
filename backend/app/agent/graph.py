"""LangGraph orchestration: durable (checkpointed), cyclic (retry), with HITL interrupt."""
import hashlib
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from ..config import settings
from ..schemas import InvoiceExtraction
from .policy import Decision, decide
from .router import BudgetExceeded


class State(TypedDict, total=False):
    case_id: str
    attempt: int
    extraction: dict | None
    po: dict | None
    supplier: dict | None
    duplicate: bool
    lookup_error: bool
    decision: dict
    precedents: list[dict]
    explanation: str
    human: dict
    status: str
    draft_id: str
    ticket_id: str
    events: list[str]


def build_graph(rt, checkpointer):
    gw, mcp, docs = rt.gateway, rt.mcp, rt.docs

    def ev(s, msg):
        return (s.get("events") or []) + [msg]

    # ---- nodes ----------------------------------------------------------
    def extract(s: State):
        try:
            ex = gw.extract(s["case_id"], docs[s["case_id"]], s.get("attempt", 0))
            return {"extraction": ex.model_dump(), "events": ev(s, f"extract attempt={s.get('attempt', 0)} conf={ex.extraction_confidence}")}
        except BudgetExceeded as e:
            return {"extraction": None, "events": ev(s, f"budget: {e}")}
        except Exception as e:                      # schema violation etc.
            return {"extraction": None, "events": ev(s, f"extract_failed: {type(e).__name__}")}

    def retry_or_go(s: State):
        ex = s.get("extraction")
        bad = ex is None or ex["extraction_confidence"] < settings.min_confidence
        return "bump" if (bad and s.get("attempt", 0) < 1) else "lookup"

    def bump(s: State):
        return {"attempt": s.get("attempt", 0) + 1, "events": ev(s, "retry with stronger model")}

    def lookup(s: State):
        cid, ex = s["case_id"], s.get("extraction")
        if ex is None:
            return {"po": None, "supplier": None, "duplicate": False, "lookup_error": False}
        po = sup = None
        dup = err = False
        if ex.get("po_number"):
            r = mcp.call(cid, "get_open_purchase_order", {"po_number": ex["po_number"]})
            if r.ok:
                po = r.data
            elif "404" not in r.error:
                err = True
        if po:
            r = mcp.call(cid, "check_supplier_status", {"supplier_id": po["supplier_id"]})
            sup = r.data if r.ok else None
            err = err or not r.ok
            r = mcp.call(cid, "find_existing_invoice",
                         {"invoice_no": ex["invoice_no"], "supplier_id": po["supplier_id"]})
            dup = bool(r.ok and r.data["exists"])
            err = err or not r.ok
        return {"po": po, "supplier": sup, "duplicate": dup, "lookup_error": err,
                "events": ev(s, f"lookup po={'yes' if po else 'no'} dup={dup}")}

    def decide_node(s: State):
        if s.get("extraction") is None:
            d = Decision(action="ESCALATE", reasons=["EXTRACTION_FAILED"])
        else:
            d = decide(InvoiceExtraction(**s["extraction"]), s.get("po"), s.get("supplier"),
                       s.get("duplicate", False), s.get("lookup_error", False))
        precs = []
        if getattr(rt, "memory", None) is not None and s.get("po"):
            sup_id = s["po"].get("supplier_id", "")
            ex = s.get("extraction") or {}
            summary = f"{ex.get('supplier_name', '')} total={ex.get('total', 0)}"
            precs = [p.__dict__ for p in rt.memory.recall(sup_id, d.reasons, summary)]
        return {"decision": d.model_dump(), "precedents": precs,
                "events": ev(s, f"policy={d.action} {d.reasons} precedents={len(precs)}")}

    def route(s: State):
        return {"AUTO_DRAFT": "draft", "HITL_REVIEW": "human",
                "BLOCK": "explain", "ESCALATE": "explain"}[s["decision"]["action"]]

    def explain(s: State):
        d, ex = s["decision"], s.get("extraction") or {}
        try:
            txt = gw.explain(s["case_id"], {"invoice_no": ex.get("invoice_no", "?"),
                                            "action": d["action"], "reasons": d["reasons"]})
        except BudgetExceeded:
            txt = f"{d['action']}: {', '.join(d['reasons'])}"      # no LLM: still safe
        return {"explanation": txt}

    def ticket(s: State):
        d, ex = s["decision"], s.get("extraction") or {}
        sev = "HIGH" if d["action"] == "BLOCK" else "MEDIUM"
        r = mcp.call(s["case_id"], "create_itsm_exception_ticket", {
            "title": f"Invoice {ex.get('invoice_no', '?')}: {d['action']}", "severity": sev,
            "po_number": ex.get("po_number"),
            "details": (s.get("explanation") or "") + " reasons=" + ",".join(d["reasons"])})
        status = {"BLOCK": "BLOCKED_TICKET", "ESCALATE": "ESCALATED_TICKET"}.get(d["action"], "REJECTED_TICKET")
        if s.get("human", {}).get("decision") == "reject":
            status = "REJECTED_TICKET"
        return {"status": status, "ticket_id": r.data.get("ticket_id", "") if r.ok else "",
                "events": ev(s, f"ticket {status}")}

    def human(s: State):
        resp = interrupt({"case_id": s["case_id"], "reasons": s["decision"]["reasons"],
                          "invoice_total": s["decision"]["invoice_total"]})
        return {"human": resp, "events": ev(s, f"human={resp.get('decision')}")}

    def after_human(s: State):
        return "draft" if s["human"].get("decision") == "approve" else "ticket"

    def draft(s: State):
        ex, po = s["extraction"], s["po"]
        key = hashlib.sha256(f"{po['supplier_id']}|{ex['invoice_no']}".encode()).hexdigest()[:32]
        r = mcp.call(s["case_id"], "submit_invoice_draft", {
            "invoice_no": ex["invoice_no"], "supplier_id": po["supplier_id"],
            "po_number": po["po_number"], "total": ex["total"],
            "currency": ex["currency"], "idempotency_key": key})
        status = "DRAFT_CREATED_AFTER_APPROVAL" if s.get("human") else "DRAFT_CREATED"
        if not r.ok:
            status = "DRAFT_FAILED"
        return {"status": status, "draft_id": r.data.get("draft_id", "") if r.ok else "",
                "events": ev(s, f"draft {status}")}

    # ---- wiring ---------------------------------------------------------
    g = StateGraph(State)
    for n, f in [("extract", extract), ("bump", bump), ("lookup", lookup), ("decide", decide_node),
                 ("explain", explain), ("ticket", ticket), ("human", human), ("draft", draft)]:
        g.add_node(n, f)
    g.add_edge(START, "extract")
    g.add_conditional_edges("extract", retry_or_go, ["bump", "lookup"])
    g.add_edge("bump", "extract")                       # <- the cycle (reflection/retry)
    g.add_edge("lookup", "decide")
    g.add_conditional_edges("decide", route, ["draft", "human", "explain"])
    g.add_edge("explain", "ticket")
    g.add_conditional_edges("human", after_human, ["draft", "ticket"])
    g.add_edge("draft", END)
    g.add_edge("ticket", END)
    return g.compile(checkpointer=checkpointer)
