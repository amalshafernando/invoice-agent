"""Tamper-evident audit log: every row hashes (prev_hash + content)."""
import hashlib
import json
from datetime import datetime, timezone

from .store import conn

GENESIS = "0" * 64


def _digest(prev: str, ts: str, actor: str, action: str, payload: str) -> str:
    raw = json.dumps([prev, ts, actor, action, payload], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def append(actor: str, action: str, payload: dict) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    with conn() as c:
        row = c.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
        prev = row["hash"] if row else GENESIS
        h = _digest(prev, ts, actor, action, body)
        c.execute("INSERT INTO audit(ts,actor,action,payload,prev_hash,hash) "
                  "VALUES(?,?,?,?,?,?)", (ts, actor, action, body, prev, h))
    return h


def verify_chain() -> dict:
    with conn() as c:
        rows = c.execute("SELECT * FROM audit ORDER BY id").fetchall()
    prev = GENESIS
    for r in rows:
        if r["prev_hash"] != prev or r["hash"] != _digest(
                prev, r["ts"], r["actor"], r["action"], r["payload"]):
            return {"ok": False, "broken_at": r["id"], "rows": len(rows)}
        prev = r["hash"]
    return {"ok": True, "rows": len(rows)}
