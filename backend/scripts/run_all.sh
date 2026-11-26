#!/usr/bin/env bash
# From backend/ :  bash scripts/run_all.sh   (ERP 8001, MCP 8002, API 8000)
set -e
python scripts/prepare_data.py --n 16 --synthetic >/dev/null
python scripts/seed_erp.py && python scripts/render_invoices.py
uvicorn app.mock_erp.main:app --port 8001 & 
uvicorn app.mcp_server.server:app --port 8002 &
uvicorn app.api.main:app --port 8000 &
wait
