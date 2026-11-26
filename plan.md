# Governed Autonomous Invoice-to-PO Agent — සම්පූර්ණ ව්‍යාපෘති සැලැස්ම (`plan.md`)

මෙම සැලැස්ම **Xitricon Agentic AI Booklet (කොටස 1 සහ කොටස 2)** ඇසුරෙන්, ව්‍යාපෘතිය ආරම්භයේ සිට **Production** මට්ටම දක්වා පියවරෙන් පියවර ගොඩනැගීම සඳහා සකස් කර ඇත. වත්මන් codebase එක පරීක්ෂා කර එක් එක් පියවරේ තත්ත්වය පහත සලකුණු වලින් දක්වා ඇත:

- ✅ **සම්පූර්ණයෙන් ක්‍රියාත්මකයි** (Codebase හි දැනටමත් ඇත)
- ❓ **අර්ධ වශයෙන් ක්‍රියාත්මකයි / තවදුරටත් සංවර්ධනය හෝ පරීක්ෂා කිරීම අවශ්‍යයි**
- ❌ **තවම ක්‍රියාත්මක කර නැත** (ඉදිරියේදී ක්‍රියාත්මක කළ යුතුය)

---

## අදියර 0: ව්‍යාපෘති ව්‍යුහය සහ පරිසරය සූදානම් කිරීම (Setup & Environment)

- ✅ **ව්‍යාපෘති ෆෝල්ඩර ව්‍යුහය සැකසීම**: `backend/app/` (`mock_erp`, `mcp_server`, `agent`, `api`), `backend/scripts/`, `backend/data/`, `backend/evals/`, `backend/tests/`, සහ `frontend/` නිර්මාණය කර ඇත.
- ✅ **Dependencies ලැයිස්තු සැකසීම**: `backend/requirements.txt` (FastAPI, Pydantic, PyJWT, LangGraph, OpenTelemetry, pypdf, reportlab, pytest) සහ `frontend/package.json` (React, TypeScript, Vite) සකසා ඇත.
- ❌ **දේශීය (Local) පරිසරය ස්ථාපනය කිරීම**:
  - `backend/.venv` virtual environment එක සාදා `pip install -r requirements.txt` ධාවනය කිරීම (මෙම පරිගණකයේ `.venv` තවම සාදා නැත).
  - `.env` ගොනුවක් සාදා `JWT_SECRET`, `LLM_PROVIDER`, `MODEL_CHEAP`, `MODEL_STRONG`, සහ API keys සැකසීම (`.env` තවම නැත).
  - `frontend/` හි `npm install` ධාවනය කර dependencies ස්ථාපනය කිරීම.

---

## අදියර 1: දත්ත සැකසීම සහ Ingestion (Dataset & Data Pipeline)

- ✅ **Data pipeline & Scenario 10 සැකසීම (`backend/scripts/prepare_data.py`)**:
  - Hugging Face `katanaml-org/invoices-donut-data-v1` සහ offline fallback (`synth()`) මගින් invoice දත්ත ලබාගෙන, අවස්ථා 10ක් (`clean`, `small_variance`, `price_variance`, `qty_over_received`, `suspended_supplier`, `duplicate_invoice`, `missing_po`, `high_value`, `injection_clean`, `injection_variance`) සඳහා `backend/data/cases.jsonl` සහ `backend/data/erp_seed.json` සාදා ඇත.
- ✅ **Invoice PDF ගොනු නිර්මාණය (`backend/scripts/render_invoices.py`)**:
  - Mutated invoices සහ prompt-injection පෙළ ඇතුළත් PDF ගොනු 16 (`backend/data/pdfs/C01.pdf` – `C16.pdf`) සාදා ඇත.
- ❓ **Hugging Face සැබෑ dataset schema (`from_donut()`) සත්‍යාපනය කිරීම**:
  - `from_donut()` කේතය ලියා ඇතත්, සැබෑ Hugging Face dataset එක download කර පළමු row එකේ schema ගැළපේදැයි මෙම පරිසරයේ පරීක්ෂා කර නැත.
- ❓ **SQLite ERP දත්ත සමුදාය seed කිරීම (`backend/scripts/seed_erp.py`)**:
  - `seed_erp.py` ස්ක්‍රිප්ට් එක ලියා ඇතත්, මෙම පරිසරයේ `backend/data/erp.sqlite` ගොනුව තවම සාදා නැත (`python scripts/seed_erp.py` ධාවනය කළ යුතුය).

---

## අදියර 2: Mock IFS ERP, OAuth2 ආරක්ෂාව සහ Audit Chain (පැය 1)

- ✅ **මධ්‍යගත සැකසුම් සහ Policy සංඛ්‍යා (`backend/app/config.py`)**:
  - `price_tolerance_pct` (2.0%), `qty_tolerance_pct` (0.0%), `hitl_value_threshold` ($10,000), `budget_usd_per_invoice` ($0.05), `min_confidence` (0.7) සහ `mcp_protocol_version` (`2026-07-28`) ඇතුළත් කර ඇත.
- ✅ **Strict Pydantic Data Contracts (`backend/app/schemas.py`)**:
  - `Strict` base class (`extra="forbid"`) මගින් අනවසර fields ප්‍රතික්ෂේප කිරීම සහ `InvoiceExtraction`, `PurchaseOrder`, `Supplier`, `InvoiceDraftIn/Out`, `TicketIn/Out` සකසා ඇත. *(සටහන: MVP සඳහා `float` භාවිතා කර ඇත.)*
- ✅ **OAuth2 Client-Credentials සහ Scoped RBAC (`backend/app/security.py`)**:
  - `invoice-agent`, `finance-ui`, සහ `mcp-server` සඳහා least-privilege scopes සහ `require_scope(...)` deny-by-default ආරක්ෂාව ක්‍රියාත්මක කර ඇත (MVP සඳහා HS256 shared secret).
- ✅ **SQLite ERP Store (`backend/app/mock_erp/store.py`)**:
  - `suppliers`, `purchase_orders`, `po_lines`, `invoice_drafts` (`UNIQUE(invoice_no, supplier_id)` සහ `idempotency_key UNIQUE`), `tickets`, සහ `audit` වගු සකසා ඇත.
- ✅ **Tamper-evident Hash-Chained Audit Log (`backend/app/mock_erp/audit.py`)**:
  - සෑම පේළියක්ම `SHA256(prev_hash, ts, actor, action, payload)` මගින් සම්බන්ධ කර `verify_chain()` මගින් වෙනස් කිරීම් හඳුනාගැනීම ක්‍රියාත්මක කර ඇත.
- ✅ **Mock IFS ERP FastAPI Endpoints (`backend/app/mock_erp/main.py`)**:
  - `/oauth/token`, `/odata/PurchaseOrderSet/{po}`, `/odata/SupplierSet/{id}`, `/odata/InvoiceDraftSet` (idempotent + suspended/duplicate guards), `/itsm/tickets`, සහ `/audit/verify` ක්‍රියාත්මක කර ඇත.

---

## අදියර 3: Governed Stateless MCP Server (පැය 2)

- ❓ **MCP 2026-07-28 Stateless Streamable-HTTP Server (`backend/app/mcp_server/server.py`)**:
  - `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` header/body ගැළපුම් පරීක්ෂාව, `server/discover`, scope-filtered `tools/list`, සහ `tools/call` FastAPI මගින් ක්‍රියාත්මක කර ඇත.
  - *වැඩිදියුණු කළ යුතු දේ*: Request `_meta` හරහා client capabilities යැවීම වැනි සම්පූර්ණ නිල MCP 2026-07-28 spec විශේෂාංග හෝ නිල MCP Python SDK භාවිතය තවම එක් කර නැත.
- ✅ **MCP Server ස්වකීය OAuth Identity (`backend/app/mcp_server/erp_client.py`)**:
  - Agent ගේ token එක ERP වෙත ඉදිරිපත් නොකර (no token passthrough), `mcp-server` client-credentials token එක cache කර ERP ඇමතීම ක්‍රියාත්මක කර ඇත.
- ✅ **Typed Scoped MCP Tools 5 (`backend/app/mcp_server/tools.py`)**:
  - `get_open_purchase_order`, `check_supplier_status`, `find_existing_invoice`, `create_itsm_exception_ticket`, සහ `submit_invoice_draft` input/output schema validation සමඟ ක්‍රියාත්මක කර ඇත.
- ❓ **Output Sanitizer සහ Untrusted Tagging (`backend/app/mcp_server/sanitize.py`)**:
  - NFKC normalization, zero-width/control chars ඉවත් කිරීම, regex injection redaction, සහ `_meta.untrusted: True` + `securityFindings` ක්‍රියාත්මක කර ඇත.
  - *වැඩිදියුණු කළ යුතු දේ*: මෙය regex පදනම් heuristic ස්ථරයක් පමණි; production සඳහා වඩාත් ශක්තිමත් ML/LLM-based prompt-injection classifier එකක් එක් කළ යුතුය.

---

## අදියර 4: Quarantined Extractor, FinOps Router සහ Telemetry (පැය 2:00 – 2:40)

- ✅ **PDF උත්පාදකය (`backend/app/agent/pdfgen.py`)**:
  - Invoice dict වලින් text layer සහිත A4 PDF නිර්මාණය කිරීම ක්‍රියාත්මකයි.
- ✅ **Offline Deterministic Adapter — `FakeLLM` (`backend/app/agent/llm.py`)**:
  - API key නොමැතිව PDF text layer parse කර `InvoiceExtraction` සහ explanation ලබාදීම ක්‍රියාත්මකයි.
- ❓ **සැබෑ Multimodal LLM Adapter — `LangChainLLM` (`backend/app/agent/llm.py`)**:
  - `init_chat_model` + `with_structured_output(InvoiceExtraction)` සහ Prompt Caching සැකැස්ම (`SYSTEM_PROMPT` පළමුව, PDF අවසානයේ) කේතය ලියා ඇතත්, **API key නොමැතිවීම නිසා පරීක්ෂා කර නැත**.
  - *කළ යුතු දේ*: සැබෑ LLM provider (Gemini / OpenAI / Anthropic) ගේ නවතම model නම් `.env` හි යොදා, PDF `content`-block ආකෘතිය provider docs සමඟ සසඳා සජීවීව පරීක්ෂා කළ යුතුය.
- ❌ **සැබෑ Scanned / Image-only Invoices සඳහා Extraction පරීක්ෂාව**:
  - දැනට පද්ධතිය පරීක්ෂා කර ඇත්තේ `pdfgen.py` මගින් සෑදූ text-layer PDFs සඳහා පමණි; සැබෑ scanned PDFs සඳහා `LangChainLLM` multimodal extraction පරීක්ෂා කර තහවුරු කළ යුතුය.
- ✅ **FinOps Model Router (`backend/app/agent/router.py`)**:
  - Cheap-first routing, confidence < 0.7 නම් එක් වරක් strong model retry, සහ invoice එකකට `$0.05` budget cap (`BudgetExceeded` → safe escalation) ක්‍රියාත්මකයි. *(සැ.යු. `PRICES` අගයන් සැබෑ provider මිල ගණන් අනුව යාවත්කාලීන කළ යුතුය.)*
- ❓ **OpenTelemetry GenAI Spans (`backend/app/agent/telemetry.py`)**:
  - `InMemorySpanExporter` මගින් UI වෙත traces/tokens/cost/latency ලබාදීම ක්‍රියාත්මකයි.
  - *පරීක්ෂා කළ යුතු දේ*: `OTEL_EXPORTER_OTLP_ENDPOINT` සකසා Jaeger / Grafana / Datadog වෙත සජීවීව OTLP spans යැවීම තවම පරීක්ෂා කර නැත.

---

## අදියර 5: Deterministic Policy Gateway, LangGraph සහ Agent API (පැය 2:40 – 4:00)

- ❓ **Deterministic Policy Gateway (`backend/app/agent/policy.py`)**:
  - LLM නොමැතිව පිරිසිදු Python `decide()` ශ්‍රිතය මගින් `BLOCK > ESCALATE > HITL_REVIEW > AUTO_DRAFT` ප්‍රමුඛතාව අනුව 3-way match තීරණ ගැනීම ක්‍රියාත්මකයි.
  - *වැඩිදියුණු කළ යුතු දේ*: දැනට invoice lines ගළපන්නේ අනුපිළිවෙලින් පමණි; real-world අවස්ථා වන **partial deliveries, tax ගණනය, multi-PO matching, සහ line order වෙනස් වීම්** සඳහා policy logic පුළුල් කළ යුතුය.
- ✅ **Agent-side Stateless MCP Client (`backend/app/agent/mcp_client.py`)**:
  - සෑම ඇමතුමකටම MCP 2026-07-28 headers යැවීම සහ eval/audit සඳහා `self.log` පවත්වාගැනීම ක්‍රියාත්මකයි.
- ✅ **LangGraph State Machine (`backend/app/agent/graph.py`)**:
  - `extract` → `retry_or_go` (`bump` retry cycle) → `lookup` (PO ගෙන් `supplier_id` ගැනීම) → `decide` → `explain`/`human` (`interrupt()`) / `draft` (`sha256` idempotency key) / `ticket` (reason codes පමණක්, raw text නැත) ක්‍රියාත්මකයි.
- ✅ **Agent Runtime සහ Checkpointer (`backend/app/agent/runtime.py`)**:
  - `build_runtime(inproc=True/False)`, `SqliteSaver` durable checkpointer, `start()`, `resume(Command(resume=...))`, සහ `get()` ක්‍රියාත්මකයි.
- ✅ **Agent API (`backend/app/api/main.py`)**:
  - `/api/health`, `/api/samples`, `/api/cases/sample/{id}`, `/api/cases/upload`, `/api/cases`, `/api/cases/{id}`, `/api/cases/{id}/review`, `/api/metrics`, `/api/eval`, `/api/audit` ක්‍රියාත්මකයි.

---

## අදියර 6: Frontend UI — React + TypeScript + Vite (පැය 4:00 – 4:40)

- ✅ **App Shell, API Client සහ Styles (`frontend/src/App.tsx`, `api.ts`, `components.tsx`, `styles.css`)**:
  - Hash routing (`#inbox`, `#case/{id}`, `#obs`) සහ ප්‍රවේශ්‍යතා/ආරක්ෂක design මූලධර්ම ක්‍රියාත්මකයි.
- ✅ **තිරය 1 — Inbox / Dashboard (`frontend/src/pages/Inbox.tsx`)**:
  - KPI cards, sample selector, PDF upload, සහ case table ක්‍රියාත්මකයි.
- ✅ **තිරය 2 — Case Review / HITL (`frontend/src/pages/CaseReview.tsx`)**:
  - Evidence table (රතු පැහැති variance), untrusted notes (mono font), Approve/Reject බොත්තම්, සහ Agent trace ක්‍රියාත්මකයි.
- ✅ **තිරය 3 — Observability & Eval (`frontend/src/pages/Observability.tsx`)**:
  - Automated eval metrics, case matrix, live system metrics, සහ audit chain තත්ත්වය ක්‍රියාත්මකයි.
- ❌ **බ්‍රවුසරය තුළ දෘශ්‍යමය (Visual / E2E) UI පරීක්ෂාව**:
  - කේතය `tsc --noEmit` සහ `vite build` සමත් වුවද, සජීවී බ්‍රවුසරයක UI තිර 3 සහ HITL Approve/Reject ප්‍රවාහය දෘශ්‍යමය වශයෙන් තවම පරීක්ෂා කර නැත.

---

## අදියර 7: පරීක්ෂණ, Eval Harness සහ Docker (පැය 4:40 – 5:00)

- ❓ **Unit & Integration Tests (`backend/tests/test_erp.py`, `test_mcp.py`, `test_agent.py`)**:
  - Pytest 25 සඳහා සියලුම test ගොනු ලියා ඇත; නමුත් මෙම පරිසරයේ `.venv` සාදා `python -m pytest -q` ධාවනය කර තහවුරු කළ යුතුය.
- ❓ **Automated Eval Harness (`backend/evals/run_eval.py`)**:
  - `FakeLLM` සමඟ `backend/data/eval_report.json` ජනනය කර ඇත (`decision_accuracy: 1.0`, `false_approve_rate: 0.0`, `injection_block_rate: 1.0`).
  - *කළ යුතු දේ*: සැබෑ LLM (`LLM_PROVIDER=langchain`) සමඟ `python -m evals.run_eval --repeats 3` ධාවනය කර සැබෑ accuracy, latency, සහ cost මැන බැලිය යුතුය.
- ❓ **Docker සහ Compose (`docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`)**:
  - සියලුම Docker ගොනු සකසා ඇතත්, `docker compose up --build` තවම ධාවනය කර පරීක්ෂා කර නැත.
- ❓ **Local Startup Script (`backend/scripts/run_all.sh`)**:
  - Linux/Mac bash සඳහා `run_all.sh` සකසා ඇත; Windows PowerShell පරිසරයක සේවා 3 (`8001`, `8002`, `8000`) වෙනම ධාවනය කිරීම හෝ PowerShell script එකක් (`run_all.ps1`) සැකසීම ප්‍රයෝජනවත් වේ.

---

## අදියර 8: MVP සිට Production දක්වා ගමන (Production Roadmap)

කොටස 2 (පිටුව 27) හි දක්වා ඇති **MVP → Production** සිතියමට අනුව, මෙම පද්ධතිය සැබෑ enterprise (Xitricon / IFS Cloud) පරිසරයකට ගෙන යාම සඳහා පහත අංග **ඉදිරියේදී ක්‍රියාත්මක කළ යුතුය**:

- ❌ **සැබෑ IFS Cloud OData API Integration**:
  - `backend/app/mcp_server/erp_client.py` Mock ERP වෙනුවට IFS Cloud sandbox tenant හි OData APIs වෙත යොමු කිරීම, IFS IAM OAuth2 සම්බන්ධ කිරීම, field mapping සහ contract tests ලිවීම.
- ❌ **Enterprise Identity Provider (IdP) සහ Secrets Management**:
  - `HS256` shared secret (`dev-only-change-me`) වෙනුවට Entra ID හෝ Keycloak වැනි IdP එකකින් **RS256 + JWKS** token validation සැකසීම සහ secrets vault (Azure Key Vault / GCP Secret Manager / AWS Secrets Manager) භාවිතය.
- ❌ **Production Database සහ Postgres Checkpointer**:
  - SQLite (`erp.sqlite`, `checkpoints.sqlite`) වෙනුවට **Supabase / PostgreSQL** සහ **LangGraph Postgres Checkpointer** භාවිතා කිරීම, සහ multi-tenant ආරක්ෂාව සඳහා **Row-Level Security (RLS)** එක් කිරීම.
- ❌ **නිල MCP SDK හෝ Enterprise MCP Gateway**:
  - Custom FastAPI MCP server වෙනුවට නිල **MCP Python SDK (2026-07-28)** හෝ **Workato / Boomi MCP control plane** භාවිතය.
- ❌ **Production Observability සහ Alerting**:
  - `OTEL_EXPORTER_OTLP_ENDPOINT` හරහා **Grafana / Datadog / Jaeger** වෙත traces යැවීම සහ cost ඉක්මවීම් හෝ false-approve අවදානම් සඳහා automated alerts සැකසීම.
- ❌ **Asynchronous Queue + Background Workers**:
  - Sync API endpoints වෙනුවට email / IFS events හරහා එන invoices සැකසීමට message queue + workers සහ `httpx.AsyncClient` භාවිතා කිරීම.
- ❌ **මූල්‍ය ගණනය කිරීම් සඳහා `Decimal` / Minor Units (Cents)**:
  - `schemas.py`, `policy.py`, සහ DB tables හි `float` / `REAL` වෙනුවට `Decimal` හෝ cents (integer) භාවිතා කර floating-point දෝෂ වැළැක්වීම.
- ❌ **වැඩිදියුණු කළ ආරක්ෂාව සහ Procurement Policy RAG**:
  - Regex sanitizer වලට අමතරව **Prompt-injection classifier** සහ **egress allow-lists** එක් කිරීම; අමතරව `pgvector` මගින් Procurement Policy / SOP Q&A සඳහා RAG සේවාවක් එක් කිරීම.
- ❌ **CI/CD Pipeline සහ සම්මුඛ පරීක්ෂණ Demo පුහුණුව**:
  - GitHub Actions මගින් `pytest`, `npm run build`, සහ `evals.run_eval` gate ස්වයංක්‍රීය කිරීම, සහ විනාඩි 6 Demo script (`C01`, `C03`, `C05`, `C08`, `C10`) පුහුණු වීම.

---

## අදියර 9 (කොටස 3): 2026 Enterprise Agentic AI Upgrade (පැය 3කින් ගොඩනැගිය හැකි සැබෑ Agent විශේෂාංග 2)

Part 1 සහ Part 2 මත පදනම්ව, මෙය "toy project" මට්ටමෙන් **Production-Ready Enterprise AI Agent** එකක් බවට පත් කිරීමට 2026 නවතම AI Engineering ප්‍රවණතා 2ක් (100% නොමිලේ සේවා භාවිතයෙන්) එක් කර ඇත:

- ✅ **විශේෂාංගය 1 — `sqlite-vec` Episodic HITL Memory සහ Semantic Line-Item Matching (`backend/app/agent/memory.py`, `policy.py`, `graph.py`, `runtime.py`)**:
  - **2026 Neuro-Symbolic Pattern**: සරල `==` string matching වෙනුවට `align_lines()` මගින් cosine similarity (`BAAI/bge-small-en-v1.5` හෝ local subword-projection fallback) භාවිතයෙන් invoice lines සහ PO lines semantic ලෙස ගැළපීම (line order වෙනස් වුවද, අමතර විස්තර තිබුණද නිවැරදිව ගැළපේ).
  - **Cross-Thread Episodic Memory**: මූල්‍ය නිලධාරියෙකු HITL (`CaseReview`) හරහා approve/reject කරන සෑම තීරණයක්ම `sqlite-vec` (`memory.sqlite`) හි vector precedent එකක් ලෙස සුරැකේ. ඊළඟ සමාන invoice එකේදී agent ස්වයංක්‍රීයව පෙර precedents සිහිපත් කර (`recall`) UI හි පෙන්වයි.
- ✅ **විශේෂාංගය 2 — Hugging Face Prompt-Injection Guardrail සහ Business ROI Engine (`backend/app/mcp_server/guardrail.py`, `sanitize.py`, `api/routes.py`, `frontend/src/pages/Observability.tsx`)**:
  - **Defense-in-Depth Guardrail**: Regex-only filter එක වෙනුවට pre-trained Hugging Face guardrail model (`protectai/deberta-v3-base-prompt-injection-v2` via free HF Inference API + local structural jailbreak scorer) භාවිතයෙන් indirect prompt injection හඳුනාගැනීම.
  - **Executive Business ROI Telemetry (`/api/roi`)**: තාක්ෂණික නොවන සමාගම් හිමිකරුවන්ට සෘජුවම පෙනෙන ලෙස Processing Savings (`$15/invoice` manual benchmark vs AI cost), Prevented Fraud/Leakage (`$`), Hours Saved, සහ HITL Precedents Learned ගණනය කර Observability dashboard හි පෙන්වීම.
- ✅ **කොටස 3 පරීක්ෂණ සහ සිංහල මාර්ගෝපදේශ පොත**:
  - Unit & Integration Tests: `backend/tests/test_part3.py`
  - සිංහල මාර්ගෝපදේශ පොත (PDF): `docs/Agentic_AI_Booklet_Part3_Sinhala.pdf`
