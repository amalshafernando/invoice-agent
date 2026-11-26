"""Agent API consumed by the React UI.  uvicorn app.api.main:app --port 8000"""
import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..agent.runtime import build_runtime
from ..config import settings

app = FastAPI(title="Invoice Agent API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:8080"],
                   allow_methods=["*"], allow_headers=["*"])
rt = build_runtime(inproc=False, checkpoint_path=settings.checkpoint_db)
DATA = Path(settings.data_dir)


def _cases() -> list[dict]:
    return [json.loads(l) for l in (DATA / "cases.jsonl").read_text().splitlines()]


def _brief(s: dict) -> dict:
    ex, d = s.get("extraction") or {}, s.get("decision") or {}
    return {"case_id": s["case_id"], "label": s["label"], "status": s["status"],
            "invoice_no": ex.get("invoice_no"), "supplier": ex.get("supplier_name"),
            "total": ex.get("total"), "action": d.get("action"), "reasons": d.get("reasons", []),
            "cost_usd": s["cost_usd"], "latency_s": s["latency_s"], "created_at": s["created_at"]}


@app.get("/api/health")
def health():
    return {"status": "ok", "llm": rt.gateway.llm.name}


@app.get("/api/samples")
def samples():
    return [{"case_id": c["case_id"], "scenario": c["scenario"],
             "invoice_no": c["invoice"]["invoice_no"], "total": c["invoice"]["total"]} for c in _cases()]


@app.post("/api/cases/sample/{sample_id}")
def from_sample(sample_id: str):
    f = DATA / "pdfs" / f"{sample_id}.pdf"
    if not f.exists():
        raise HTTPException(404, "unknown sample")
    return rt.start(f.read_bytes(), source="sample", label=sample_id)


@app.post("/api/cases/upload")
async def upload(file: UploadFile = File(...)):
    return rt.start(await file.read(), source="upload", label=file.filename or "upload")


@app.get("/api/cases")
def list_cases():
    return sorted((_brief(rt.get(c)) for c in rt.cases), key=lambda x: -x["created_at"])


@app.get("/api/cases/{cid}")
def get_case(cid: str):
    if cid not in rt.cases:
        raise HTTPException(404, "case not found")
    return rt.get(cid)


class Review(BaseModel):
    decision: str            # approve | reject
    reviewer: str = "finance-officer"
    comment: str = ""


@app.post("/api/cases/{cid}/review")
def review(cid: str, body: Review):
    if cid not in rt.cases or rt.get(cid)["status"] != "AWAITING_REVIEW":
        raise HTTPException(409, "case is not awaiting review")
    if body.decision not in ("approve", "reject"):
        raise HTTPException(422, "decision must be approve|reject")
    return rt.resume(cid, body.decision, body.reviewer, body.comment)


@app.get("/api/metrics")
def metrics():
    rows = [_brief(rt.get(c)) for c in rt.cases]
    n = len(rows) or 1
    by = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    return {"cases": len(rows), "by_status": by,
            "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 6),
            "avg_cost_usd": round(sum(r["cost_usd"] for r in rows) / n, 6),
            "avg_latency_s": round(sum((r["latency_s"] or 0) for r in rows) / n, 4),
            "budget_cap_usd": settings.budget_usd_per_invoice,
            "touchless_rate": round(by.get("DRAFT_CREATED", 0) / n, 3)}


@app.get("/api/eval")
def eval_report():
    f = DATA / "eval_report.json"
    return json.loads(f.read_text()) if f.exists() else {"rows": [], "note": "run: python -m evals.run_eval"}


@app.get("/api/audit")
def audit():
    import httpx
    c = httpx.Client(base_url=settings.erp_url)
    t = c.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": "finance-ui",
                                     "client_secret": "ui-secret", "scope": "admin:audit"}).json()["access_token"]
    return c.get("/audit/verify", headers={"Authorization": f"Bearer {t}"}).json()
