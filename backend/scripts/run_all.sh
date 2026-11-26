#!/usr/bin/env bash
# From backend/ :  bash scripts/run_all.sh   (ERP 8001, MCP 8002, API 8000)
# Always move to the backend directory
cd "$(dirname "$0")/.."

# ERP: 8001
# MCP: 8002
# API: 8000

set -e
#python scripts/prepare_data.py --n 16 --synthetic >/dev/null
#python scripts/seed_erp.py && python scripts/render_invoices.py



#!/usr/bin/env bash



echo "Starting Invoice Agent services..."

# Start ERP
python -m uvicorn app.mock_erp.main:app --host 127.0.0.1 --port 8001 &

# Start MCP
python -m uvicorn app.mcp_server.server:app --host 127.0.0.1 --port 8002 &

# Start API
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &

wait

