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
1. Run Docling Serve locally with `docker run --rm -p 5001:5001 ghcr.io/docling-project/docling-serve-cpu:latest`, or deploy Docling Serve as a custom container on a Hugging Face Inference Endpoint.
2. Set `LLM_PROVIDER=langchain`, the two LangChain model settings, and the LLM provider API key in the root `.env`.
3. Set `DOCLING_URL` to the Docling Serve base URL (for example, `http://127.0.0.1:5001` locally, `http://host.docker.internal:5001` from Docker Compose, or the Hugging Face Inference Endpoint URL). The application appends `/v1/convert/file`.
4. For a protected Hugging Face Inference Endpoint, set `HF_TOKEN` in the root `.env`; Docker Compose passes it to the API container and the application sends it as a Bearer token. Set `DOCLING_URL` to the endpoint's URL, for example `https://<your-endpoint>.endpoints.huggingface.cloud` (not the model repository URL). `DOCLING_API_KEY` remains available for Docling Serve instances configured with their own API key. Set `DOCLING_TIMEOUT_S` if conversion needs more time.

`https://huggingface.co/docling-project/docling-models` is a model-assets repository, not a document-conversion API. A Hugging Face endpoint must actually run Docling Serve and expose its `/v1/convert/file` API; setting `DOCLING_URL` to the model-repository page will not work. The application sends converted Markdown to LangChain for structured invoice extraction.
