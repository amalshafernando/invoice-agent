"""Wires everything together: LLM gateway + MCP client + graph + case registry."""
import sqlite3
import time
import uuid
from dataclasses import dataclass, field

import httpx
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from ..config import settings
from . import telemetry
from .graph import build_graph
from .llm import get_llm
from .mcp_client import McpClient
from .router import Gateway


@dataclass
class Runtime:
    gateway: Gateway
    mcp: McpClient
    graph: object
    docs: dict = field(default_factory=dict)
    cases: dict = field(default_factory=dict)       # case_id -> metadata

    def _cfg(self, cid):
        return {"configurable": {"thread_id": cid}}

    def _snapshot(self, cid) -> dict:
        st = self.graph.get_state(self._cfg(cid))
        v = dict(st.values)
        paused = bool(st.next)
        v["status"] = "AWAITING_REVIEW" if paused else v.get("status", "UNKNOWN")
        meta = self.cases[cid]
        v.update({"case_id": cid, "source": meta["source"], "label": meta["label"],
                  "created_at": meta["created_at"], "latency_s": meta.get("latency_s"),
                  "cost_usd": round(self.gateway.spent.get(cid, 0.0), 6),
                  "tokens": self.gateway.tokens.get(cid, 0),
                  "spans": telemetry.spans_for(cid)})
        return v

    def start(self, pdf: bytes, source: str = "upload", label: str = "") -> dict:
        cid = "RUN-" + uuid.uuid4().hex[:8].upper()
        self.docs[cid] = pdf
        self.cases[cid] = {"source": source, "label": label, "created_at": time.time()}
        t0 = time.perf_counter()
        self.graph.invoke({"case_id": cid, "attempt": 0, "events": []}, self._cfg(cid))
        self.cases[cid]["latency_s"] = round(time.perf_counter() - t0, 4)
        return self._snapshot(cid)

    def resume(self, cid: str, decision: str, reviewer: str = "officer", comment: str = "") -> dict:
        t0 = time.perf_counter()
        self.graph.invoke(Command(resume={"decision": decision, "reviewer": reviewer,
                                          "comment": comment}), self._cfg(cid))
        self.cases[cid]["latency_s"] = round(self.cases[cid].get("latency_s", 0) + time.perf_counter() - t0, 4)
        return self._snapshot(cid)

    def get(self, cid: str) -> dict:
        return self._snapshot(cid)


def build_runtime(inproc: bool = False, llm=None, cap_usd: float | None = None,
                  checkpoint_path: str = ":memory:") -> Runtime:
    if inproc:                                        # tests / eval: no sockets needed
        from fastapi.testclient import TestClient
        from ..mock_erp.main import app as erp_app
        from ..mcp_server import server as mcp_server
        from ..mcp_server.erp_client import ErpClient
        erp_http = TestClient(erp_app)
        mcp_server.erp = ErpClient(erp_http)
        mcp_http = TestClient(mcp_server.app)
    else:
        erp_http = httpx.Client(base_url=settings.erp_url, timeout=15)
        mcp_http = httpx.Client(base_url=settings.mcp_url, timeout=15)
    conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    gw = Gateway(llm or get_llm(), cap_usd)
    mcp = McpClient(mcp_http, erp_http)
    rt = Runtime(gw, mcp, None)
    rt.graph = build_graph(rt, saver)
    return rt
