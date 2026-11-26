"""SQLite store for the mock IFS ERP (prod: PostgreSQL/Supabase)."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from ..config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers(
  supplier_id TEXT PRIMARY KEY, name TEXT, status TEXT, payment_terms TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS purchase_orders(
  po_number TEXT PRIMARY KEY, supplier_id TEXT, currency TEXT, status TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS po_lines(
  po_number TEXT, line_no INTEGER, description TEXT,
  qty_ordered REAL, qty_received REAL, unit_price REAL,
  PRIMARY KEY(po_number, line_no));
CREATE TABLE IF NOT EXISTS invoice_drafts(
  draft_id TEXT PRIMARY KEY, invoice_no TEXT, supplier_id TEXT, po_number TEXT,
  total REAL, currency TEXT, idempotency_key TEXT UNIQUE,
  created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(invoice_no, supplier_id));
CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_drafts_supplier_invoice_normalized
  ON invoice_drafts(supplier_id, lower(trim(invoice_no)));
CREATE TABLE IF NOT EXISTS tickets(
  ticket_id TEXT PRIMARY KEY, title TEXT, severity TEXT, po_number TEXT,
  details TEXT, created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, action TEXT,
  payload TEXT, prev_hash TEXT, hash TEXT);
"""


@contextmanager
def conn():
    Path(settings.erp_db).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(settings.erp_db)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db(seed_path: str | Path | None = None, reset: bool = False) -> None:
    if reset and Path(settings.erp_db).exists():
        Path(settings.erp_db).unlink()
    with conn() as c:
        c.executescript(SCHEMA)
    if seed_path:
        load_seed(seed_path)


def load_seed(seed_path: str | Path) -> None:
    seed = json.loads(Path(seed_path).read_text())
    with conn() as c:
        for s in seed["suppliers"]:
            c.execute("INSERT OR REPLACE INTO suppliers VALUES(?,?,?,?,?)",
                      (s["supplier_id"], s["name"], s["status"],
                       s.get("payment_terms", "NET30"), s.get("note", "")))
        for po in seed["purchase_orders"]:
            c.execute("INSERT OR REPLACE INTO purchase_orders VALUES(?,?,?,?,?)",
                      (po["po_number"], po["supplier_id"], po["currency"],
                       po["status"], po.get("note", "")))
            for ln in po["lines"]:
                c.execute("INSERT OR REPLACE INTO po_lines VALUES(?,?,?,?,?,?)",
                          (po["po_number"], ln["line_no"], ln["description"],
                           ln["qty_ordered"], ln["qty_received"], ln["unit_price"]))
        for d in seed.get("invoice_drafts", []):     # pre-existing invoices (duplicates)
            c.execute("INSERT OR REPLACE INTO invoice_drafts"
                      "(draft_id,invoice_no,supplier_id,po_number,total,currency,"
                      "idempotency_key,created_by) VALUES(?,?,?,?,?,?,?,?)",
                      (d["draft_id"], d["invoice_no"], d["supplier_id"], d["po_number"],
                       d["total"], d["currency"], d["draft_id"], "seed"))


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"
