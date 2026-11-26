"""HTTP routes for the React UI. No app wiring here: see app/main.py."""
import json
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from ..agent.runtime import Runtime
from ..config import settings

router = APIRouter(prefix="/api")
DATA = Path(settings.data_dir)


def get_rt(request: Request) -> Runtime:
    return request.app.state.rt


def _cases() -> list[dict]:
    return [json.loads(l) for l in (DATA / "cases.jsonl").read_text().splitlines()]


def _brief(s: dict) -> dict:
    ex, d = s.get("extraction") or {}, s.get("decision") or {}
    return {"case_id": s["case_id"], "label": s["label"], "status": s["status"],
            "invoice_no": ex.get("invoice_no"), "supplier": ex.get("supplier_name"),
            "total": ex.get("total"), "action": d.get("action"), "reasons": d.get("reasons", []),
            "cost_usd": s["cost_usd"], "latency_s": s["latency_s"], "created_at": s["created_at"]}


class Review(BaseModel):
    decision: str            # approve | reject
    reviewer: str = "finance-officer"
    comment: str = ""


@router.get("/health")
def health(rt: Runtime = Depends(get_rt)):
    return {"status": "ok", "llm": rt.gateway.llm.name}


@router.get("/samples")
def samples():
    return [{"case_id": c["case_id"], "scenario": c["scenario"],
             "invoice_no": c["invoice"]["invoice_no"], "total": c["invoice"]["total"]} for c in _cases()]


@router.post("/cases/sample/{sample_id}")
def from_sample(sample_id: str, rt: Runtime = Depends(get_rt)):
    f = DATA / "pdfs" / f"{sample_id}.pdf"
    if not f.exists():
        raise HTTPException(404, "unknown sample")
    return rt.start(f.read_bytes(), source="sample", label=sample_id)


@router.post("/cases/upload")
async def upload(file: UploadFile = File(...), rt: Runtime = Depends(get_rt)):
    return rt.start(await file.read(), source="upload", label=file.filename or "upload")


@router.get("/cases")
def list_cases(rt: Runtime = Depends(get_rt)):
    return sorted((_brief(rt.get(c)) for c in rt.cases), key=lambda x: -x["created_at"])


@router.get("/cases/{cid}")
def get_case(cid: str, rt: Runtime = Depends(get_rt)):
    if cid not in rt.cases:
        raise HTTPException(404, "case not found")
    return rt.get(cid)


@router.post("/cases/{cid}/review")
def review(cid: str, body: Review, rt: Runtime = Depends(get_rt)):
    if cid not in rt.cases or rt.get(cid)["status"] != "AWAITING_REVIEW":
        raise HTTPException(409, "case is not awaiting review")
    if body.decision not in ("approve", "reject"):
        raise HTTPException(422, "decision must be approve|reject")
    return rt.resume(cid, body.decision, body.reviewer, body.comment)


@router.get("/metrics")
def metrics(rt: Runtime = Depends(get_rt)):
    rows = [_brief(rt.get(c)) for c in rt.cases]
    n = len(rows) or 1
    by: dict[str, int] = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    return {"cases": len(rows), "by_status": by,
            "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 6),
            "avg_cost_usd": round(sum(r["cost_usd"] for r in rows) / n, 6),
            "avg_latency_s": round(sum((r["latency_s"] or 0) for r in rows) / n, 4),
            "budget_cap_usd": settings.budget_usd_per_invoice,
            "touchless_rate": round(by.get("DRAFT_CREATED", 0) / n, 3)}


@router.get("/roi")
def roi(rt: Runtime = Depends(get_rt)):
    """Part 3: Business ROI & Financial Impact Telemetry for non-technical stakeholders."""
    cases = [rt.get(c) for c in rt.cases]
    n = len(cases)
    total_llm_cost = sum(c.get("cost_usd", 0.0) for c in cases)
    manual_cost = n * settings.manual_cost_per_invoice
    processing_savings = max(0.0, manual_cost - total_llm_cost)
    prevented_leakage = sum(
        float((c.get("decision") or {}).get("invoice_total") or 0.0)
        for c in cases
        if (c.get("decision") or {}).get("action") in ("BLOCK", "ESCALATE")
    )
    auto_drafts = sum(1 for c in cases if c.get("status") == "DRAFT_CREATED")
    hours_saved = round(n * 0.25, 2)  # ~15 min manual 3-way match per invoice
    precedents_learned = rt.memory.count() if getattr(rt, "memory", None) is not None else 0
    return {
        "invoices_processed": n,
        "manual_benchmark_usd": round(manual_cost, 2),
        "ai_total_cost_usd": round(total_llm_cost, 6),
        "processing_savings_usd": round(processing_savings, 2),
        "prevented_leakage_usd": round(prevented_leakage, 2),
        "total_business_value_usd": round(processing_savings + prevented_leakage, 2),
        "touchless_rate": round(auto_drafts / max(1, n), 3),
        "hours_saved": hours_saved,
        "precedents_learned": precedents_learned,
        "guardrail_mode": settings.guardrail_mode,
    }


@router.get("/eval")
def eval_report():
    f = DATA / "eval_report.json"
    return json.loads(f.read_text()) if f.exists() else {"rows": [], "note": "run: python -m evals.run_eval"}


@router.get("/audit")
def audit():
    c = httpx.Client(base_url=settings.erp_url)
    t = c.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": "finance-ui",
                                     "client_secret": "ui-secret", "scope": "admin:audit"}).json()["access_token"]
    return c.get("/audit/verify", headers={"Authorization": f"Bearer {t}"}).json()