"""Render a canonical invoice dict to a PDF (text layer included)."""
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def render_invoice_pdf(inv: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    def line(text, size=9, font="Helvetica"):
        nonlocal y
        c.setFont(font, size); c.drawString(40, y, text); y -= size + 6
    line("INVOICE", 16, "Helvetica-Bold"); y -= 6
    line(f"Invoice No: {inv['invoice_no']}")
    line(f"Supplier: {inv['supplier_name']}")
    line(f"PO Number: {inv.get('po_number') or ''}")
    line(f"Currency: {inv.get('currency', 'USD')}"); y -= 8
    line("ITEM | description | qty | unit_price", 9, "Helvetica-Bold")
    for it in inv["items"]:
        line(f"ITEM | {it['description']} | {it['quantity']} | {it['unit_price']}")
    y -= 8
    line(f"Total: {inv['total']}", 11, "Helvetica-Bold")
    line(f"Notes: {inv.get('notes', '')}", 8.5)
    c.showPage(); c.save()
    return buf.getvalue()
