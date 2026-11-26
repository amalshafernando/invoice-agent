FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DATA_DIR=/app/data ERP_DB=/app/data/erp.sqlite CHECKPOINT_DB=/app/data/checkpoints.sqlite
RUN python scripts/prepare_data.py --n 16 --synthetic && python scripts/seed_erp.py && python scripts/render_invoices.py
