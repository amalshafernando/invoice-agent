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
Real LLMs: `LLM_PROVIDER=langchain MODEL_CHEAP=... MODEL_STRONG=...` + provider key.

PDF extraction with Docling Serve:
1. Start the Docling Serve CPU container (the image includes Docling and its model assets):
   `docker run --rm -p 5001:5001 ghcr.io/docling-project/docling-serve-cpu:latest`
2. Set `LLM_PROVIDER=langchain`, the two LangChain model settings, and the provider API key in the root `.env`.
3. For a locally running backend, `DOCLING_URL` defaults to `http://127.0.0.1:5001`. With Docker Compose, it defaults to `http://host.docker.internal:5001` so the API container can reach the service running on the host.
4. Optionally set `DOCLING_API_KEY` and `DOCLING_TIMEOUT_S` if the Docling service requires an API key or more conversion time.

`docling-project/docling-models` contains model assets, not an HTTP service. Docling Serve exposes the `/v1/convert/file` API; the application sends the returned Markdown to LangChain for structured invoice extraction. The CPU image is several gigabytes and downloads on first use.
