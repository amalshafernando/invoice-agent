import pytest
from pathlib import Path

from app.agent.llm import DocumentExtractionError, FakeLLM, Usage
from app.agent.pdfgen import render_invoice_pdf
from app.agent.policy import decide
from app.agent.runtime import build_runtime
from app.config import settings
from app.mock_erp import store
from app.schemas import InvoiceExtraction, LineItem
from evals.run_eval import run_eval

PO = {"po_number": "PO-1", "supplier_id": "S1", "currency": "USD", "status": "OPEN", "total": 1000.0,
      "lines": [{"line_no": 1, "description": "Pump", "qty_ordered": 10, "qty_received": 10, "unit_price": 100.0}]}
SUP = {"supplier_id": "S1", "name": "Acme", "status": "ACTIVE"}


def inv(price=100.0, qty=10.0, total=None, conf=1.0):
    return InvoiceExtraction(invoice_no="I1", supplier_name="Acme", po_number="PO-1",
                             items=[LineItem(description="Pump", quantity=qty, unit_price=price)],
                             total=total if total is not None else round(qty * price, 2),
                             extraction_confidence=conf)


def test_policy_precedence_and_tolerance():
    assert decide(inv(), PO, SUP, False).action == "AUTO_DRAFT"
    assert decide(inv(101), PO, SUP, False).action == "AUTO_DRAFT"          # 1% ok
    assert decide(inv(108), PO, SUP, False).action == "ESCALATE"            # 8% variance
    assert decide(inv(), PO, {**SUP, "status": "SUSPENDED"}, False).action == "BLOCK"
    assert decide(inv(108), PO, SUP, True).action == "BLOCK"                # BLOCK > ESCALATE
    assert decide(inv(), None, None, False).reasons == ["PO_NOT_FOUND"]
    assert "QTY_OVER_RECEIVED" in decide(inv(qty=11), PO, SUP, False).reasons
    assert decide(inv(conf=0.3), PO, SUP, False).action == "ESCALATE"
    assert decide(inv(total=999), PO, SUP, False).action == "ESCALATE"      # arithmetic


def test_high_value_goes_to_hitl():
    big = {**PO, "total": 20000, "lines": [{**PO["lines"][0], "qty_ordered": 200, "qty_received": 200}]}
    assert decide(inv(qty=200), big, SUP, False).action == "HITL_REVIEW"


@pytest.fixture()
def rt(tmp_path):
    settings.erp_db = str(tmp_path / "erp.sqlite")
    store.init_db(Path(settings.data_dir) / "erp_seed.json", reset=True)
    return build_runtime(inproc=True)


def pdf_of(case_id):
    import json
    for l in (Path(settings.data_dir) / "cases.jsonl").read_text().splitlines():
        c = json.loads(l)
        if c["case_id"] == case_id:
            return render_invoice_pdf(c["invoice"])


def test_auto_draft_and_idempotent_rerun(rt):
    a = rt.start(pdf_of("C01"))
    assert a["status"] == "DRAFT_CREATED" and a["draft_id"]
    assert any(s["attrs"].get("mcp.tool.name") == "submit_invoice_draft" for s in a["spans"])
    assert any("gen_ai.usage.input_tokens" in s["attrs"] for s in a["spans"])


def test_reprocessing_same_invoice_is_blocked(rt):
    pdf = pdf_of("C01")
    first = rt.start(pdf)
    second = rt.start(pdf)

    assert first["status"] == "DRAFT_CREATED"
    assert second["status"] == "BLOCKED_TICKET"
    assert second["decision"]["reasons"] == ["DUPLICATE_INVOICE"]
    assert sum(call["tool"] == "submit_invoice_draft" for call in rt.mcp.log) == 1


def test_docling_failure_is_visible_in_case_events(rt):
    class DoclingUnavailable:
        name = "langchain"

        def extract(self, _pdf, _tier):
            raise DocumentExtractionError("Unable to reach the Docling service")

        def explain(self, facts, _tier):
            return "Extraction failed", Usage(1, 1)

    rt2 = build_runtime(inproc=True, llm=DoclingUnavailable())
    snapshot = rt2.start(pdf_of("C01"))

    assert snapshot["status"] == "ESCALATED_TICKET"
    assert any(
        "extract_failed: Unable to reach the Docling service" in event
        for event in snapshot["events"]
    )


def test_hitl_pause_then_approve_and_reject(rt):
    a = rt.start(pdf_of("C08"))
    assert a["status"] == "AWAITING_REVIEW" and "draft_id" not in a
    b = rt.resume(a["case_id"], "approve")
    assert b["status"] == "DRAFT_CREATED_AFTER_APPROVAL" and b["draft_id"]
    c = rt.start(pdf_of("C11"))
    d = rt.resume(c["case_id"], "reject", comment="not ordered")
    assert d["status"] == "REJECTED_TICKET" and d["ticket_id"]


def test_injection_never_reaches_tool_args(rt):
    s = rt.start(pdf_of("C10"))
    assert s["status"] == "ESCALATED_TICKET"
    assert "50,000" not in str(rt.mcp.log)


class FlakyLLM(FakeLLM):
    def extract(self, pdf, tier):
        ex, u = super().extract(pdf, tier)
        if tier == "cheap":
            ex.extraction_confidence = 0.2
        return ex, u


def test_low_confidence_retries_with_strong_model(rt):
    rt2 = build_runtime(inproc=True, llm=FlakyLLM())
    s = rt2.start(pdf_of("C01"))
    models = [x["attrs"]["gen_ai.request.model"] for x in s["spans"] if "extract" in x["name"]]
    assert models == ["fake-llm:cheap", "fake-llm:strong"] and s["status"] == "DRAFT_CREATED"


def test_budget_cap_forces_safe_escalation(tmp_path, rt):
    rt3 = build_runtime(inproc=True, cap_usd=0.0)
    s = rt3.start(pdf_of("C01"))
    assert s["status"] == "ESCALATED_TICKET" and "EXTRACTION_FAILED" in s["decision"]["reasons"]


def test_eval_passes_and_is_sensitive(tmp_path):
    settings.erp_db = str(tmp_path / "e.sqlite")
    r = run_eval()
    assert r["passed"] and r["decision_accuracy"] == 1.0 and r["false_approve_rate"] == 0
    old = settings.price_tolerance_pct
    settings.price_tolerance_pct = 50.0               # break the policy on purpose
    try:
        bad = run_eval()
    finally:
        settings.price_tolerance_pct = old
    assert bad["decision_accuracy"] < 1.0 and bad["false_approve_rate"] > 0
