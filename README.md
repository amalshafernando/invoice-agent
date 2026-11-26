# Governed Invoice-to-PO Agent (Xitricon MVP)

Quick start (no API key needed — FakeLLM):
```
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
bash scripts/run_all.sh          # ERP :8001, MCP :8002, API :8000
cd ../frontend && npm install && npm run dev     # UI :5173
python -m evals.run_eval         # writes data/eval_report.json
python -m pytest -q              # 25 passed
```
Docker: `docker compose up --build` -> UI on http://localhost:8080 (compose file not tested in the authoring sandbox).
Real LLMs: `LLM_PROVIDER=langchain MODEL_CHEAP=... MODEL_STRONG=...` + provider key (adapter untested).
