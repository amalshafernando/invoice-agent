"""Part 3: Episodic HITL Memory & Semantic Line-Item Matcher using sqlite-vec.

- Stores human-in-the-loop (HITL) exception precedents in a local sqlite-vec
  vector index so the agent learns across cases without paid vector DBs.
- Supports free Hugging Face Inference API embeddings (BAAI/bge-small-en-v1.5)
  with a deterministic local n-gram projection fallback for offline/test runs.
"""
from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import struct
import time
from dataclasses import dataclass

import httpx
import sqlite_vec

from ..config import settings

EMBED_DIM = 384
_WORD_RE = re.compile(r"[a-z0-9]+")


def _pack_f32(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def _local_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic subword + token hashing projection (L2-normalized).
    Preserves lexical and partial-word overlap (e.g. 'Centrifugal Pump' ~ 'Pump')."""
    v = [0.0] * dim
    norm = " ".join(_WORD_RE.findall((text or "").lower()))
    if not norm:
        return v
    tokens = norm.split()
    features: list[tuple[str, float]] = []
    for tok in tokens:
        features.append((f"w:{tok}", 2.5))
        if len(tok) >= 3:
            for i in range(len(tok) - 2):
                features.append((f"c:{tok[i:i+3]}", 1.0))
    for feat, weight in features:
        h = int.from_bytes(hashlib.blake2b(feat.encode(), digest_size=8).digest(), "little")
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0
        v[idx] += sign * weight
    mag = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / mag for x in v]


def embed_text(text: str) -> list[float]:
    """Embed text via free HF Inference API when configured, else local projection."""
    if settings.embedding_provider == "hf" and settings.hf_token:
        try:
            url = f"https://router.huggingface.co/hf-inference/models/{settings.hf_embed_model}/pipeline/feature-extraction"
            r = httpx.post(
                url,
                headers={"Authorization": f"Bearer {settings.hf_token}"},
                json={"inputs": text, "options": {"wait_for_model": True}},
                timeout=10.0,
            )
            if r.status_code == 200:
                data = r.json()
                vec = data[0] if isinstance(data, list) and isinstance(data[0], list) else data
                if isinstance(vec, list) and len(vec) == EMBED_DIM:
                    mag = math.sqrt(sum(float(x) * float(x) for x in vec)) or 1.0
                    return [float(x) / mag for x in vec]
        except Exception:
            pass
    return _local_embed(text)


def cosine_sim(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass
class Precedent:
    id: int
    supplier_id: str
    reason_code: str
    decision: str
    reviewer: str
    comment: str
    summary: str
    similarity: float


class EpisodicMemory:
    """sqlite-vec backed cross-thread episodic memory for HITL precedents."""

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(f"""
            CREATE TABLE IF NOT EXISTS precedents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                decision TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                comment TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_precedents USING vec0(
                embedding float[{EMBED_DIM}]
            );
        """)
        self.conn.commit()

    def record_precedent(
        self,
        supplier_id: str,
        reasons: list[str],
        decision: str,
        reviewer: str,
        comment: str,
        summary: str,
    ) -> int:
        reason_code = ",".join(reasons) if reasons else "GENERAL"
        query_text = f"{supplier_id} {reason_code} {summary} {comment}".strip()
        vec = embed_text(query_text)
        cur = self.conn.execute(
            """INSERT INTO precedents(supplier_id, reason_code, decision, reviewer, comment, summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (supplier_id, reason_code, decision, reviewer, comment, summary, time.time()),
        )
        row_id = cur.lastrowid
        self.conn.execute(
            "INSERT INTO vec_precedents(rowid, embedding) VALUES (?, ?)",
            (row_id, _pack_f32(vec)),
        )
        self.conn.commit()
        return int(row_id)

    def recall(
        self,
        supplier_id: str,
        reasons: list[str],
        summary: str,
        top_k: int = 3,
        min_sim: float = 0.35,
    ) -> list[Precedent]:
        count = self.conn.execute("SELECT COUNT(*) FROM precedents").fetchone()[0]
        if count == 0:
            return []
        k = min(top_k, count)
        query_text = f"{supplier_id} {','.join(reasons)} {summary}".strip()
        vec = embed_text(query_text)
        rows = self.conn.execute(
            """
            SELECT p.id, p.supplier_id, p.reason_code, p.decision, p.reviewer,
                   p.comment, p.summary, v.distance
            FROM vec_precedents v
            JOIN precedents p ON p.id = v.rowid
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance
            """,
            (_pack_f32(vec), k),
        ).fetchall()
        out: list[Precedent] = []
        for r in rows:
            # sqlite-vec L2 distance on unit vectors: cos_sim = 1 - d^2 / 2
            sim = round(max(0.0, 1.0 - (r[7] * r[7]) / 2.0), 3)
            if sim >= min_sim:
                out.append(
                    Precedent(
                        id=r[0],
                        supplier_id=r[1],
                        reason_code=r[2],
                        decision=r[3],
                        reviewer=r[4],
                        comment=r[5],
                        summary=r[6],
                        similarity=sim,
                    )
                )
        return out

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM precedents").fetchone()[0])
