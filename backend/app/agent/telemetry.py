"""OpenTelemetry GenAI-style spans. In-memory exporter feeds the UI; set
OTEL_EXPORTER_OTLP_ENDPOINT to also ship to Jaeger/Grafana/Datadog."""
import os
import time
from contextlib import contextmanager

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    try:
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    except ImportError:
        pass
tracer = _provider.get_tracer("invoice-agent")


@contextmanager
def llm_span(case_id: str, operation: str, model: str):
    t0 = time.perf_counter()
    with tracer.start_as_current_span(f"gen_ai {operation}") as sp:
        sp.set_attribute("app.case_id", case_id)
        sp.set_attribute("gen_ai.operation.name", operation)
        sp.set_attribute("gen_ai.request.model", model)
        box: dict = {}
        yield box                                   # caller fills usage
        sp.set_attribute("gen_ai.usage.input_tokens", box.get("in", 0))
        sp.set_attribute("gen_ai.usage.output_tokens", box.get("out", 0))
        sp.set_attribute("gen_ai.client.operation.duration", time.perf_counter() - t0)
        sp.set_attribute("app.cache_hit", bool(box.get("cache_hit", False)))
        sp.set_attribute("app.cost_usd", float(box.get("cost", 0.0)))


@contextmanager
def tool_span(case_id: str, tool: str):
    with tracer.start_as_current_span(f"mcp tools/call {tool}") as sp:
        sp.set_attribute("app.case_id", case_id)
        sp.set_attribute("mcp.tool.name", tool)
        yield sp


def spans_for(case_id: str) -> list[dict]:
    out = []
    for s in _exporter.get_finished_spans():
        a = dict(s.attributes or {})
        if a.get("app.case_id") == case_id:
            out.append({"name": s.name, "ms": round((s.end_time - s.start_time) / 1e6, 2), "attrs": a})
    return out
