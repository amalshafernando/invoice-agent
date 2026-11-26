"""python scripts/render_invoices.py -> data/pdfs/C01.pdf ... (one per labelled case)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent.pdfgen import render_invoice_pdf  # noqa: E402

data = Path(__file__).resolve().parents[1] / "data"
(data / "pdfs").mkdir(exist_ok=True)
n = 0
for line in (data / "cases.jsonl").read_text().splitlines():
    c = json.loads(line)
    (data / "pdfs" / f"{c['case_id']}.pdf").write_bytes(render_invoice_pdf(c["invoice"]))
    n += 1
print(f"rendered {n} PDFs")
