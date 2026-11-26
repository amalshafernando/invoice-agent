from types import SimpleNamespace
from unittest.mock import Mock

import httpx

from app.agent.llm import LangChainLLM
from app.config import settings
from app.schemas import InvoiceExtraction, LineItem


def test_docling_service_returns_markdown(monkeypatch):
    monkeypatch.setattr(settings, "docling_url", "http://docling:5001/")
    monkeypatch.setattr(settings, "docling_api_key", "docling-test-key")
    monkeypatch.setattr(settings, "docling_timeout_s", 45)
    response = httpx.Response(
        200,
        json={"status": "success", "document": {"md_content": "# Invoice"}},
        request=httpx.Request("POST", "http://docling:5001/v1/convert/file"),
    )
    post = Mock(return_value=response)
    monkeypatch.setattr("app.agent.llm.httpx.post", post)

    llm = LangChainLLM.__new__(LangChainLLM)
    assert llm._extract_pdf_text(b"%PDF") == "# Invoice"

    args, kwargs = post.call_args
    assert args == ("http://docling:5001/v1/convert/file",)
    assert kwargs["files"]["files"] == ("invoice.pdf", b"%PDF", "application/pdf")
    assert kwargs["data"] == {"from_formats": "pdf", "to_formats": "md"}
    assert kwargs["headers"] == {"X-Api-Key": "docling-test-key"}
    assert kwargs["timeout"] == 45


def test_langchain_receives_docling_text_not_pdf(monkeypatch):
    extraction = InvoiceExtraction(
        invoice_no="INV-1",
        supplier_name="Acme",
        items=[LineItem(description="Part", quantity=1, unit_price=10)],
        total=10,
    )

    class Model:
        def with_structured_output(self, *_args, **_kwargs):
            return self

        def invoke(self, messages):
            self.messages = messages
            return {
                "parsed": extraction,
                "raw": SimpleNamespace(usage_metadata={
                    "input_tokens": 25, "output_tokens": 10
                }),
            }

    model = Model()
    llm = LangChainLLM.__new__(LangChainLLM)
    llm.m = {"cheap": model}
    monkeypatch.setattr(llm, "_extract_pdf_text", lambda _pdf: "# Extracted invoice")

    parsed, usage = llm.extract(b"%PDF", "cheap")

    assert parsed is extraction
    assert usage.input_tokens == 25
    assert usage.output_tokens == 10
    assert "# Extracted invoice" in model.messages[1].content
    assert "untrusted document text" in model.messages[1].content
    assert "%PDF" not in model.messages[1].content


def test_docling_http_error_is_reported(monkeypatch):
    response = httpx.Response(
        503,
        text="unavailable",
        request=httpx.Request("POST", "http://127.0.0.1:5001/v1/convert/file"),
    )
    monkeypatch.setattr("app.agent.llm.httpx.post", Mock(return_value=response))
    llm = LangChainLLM.__new__(LangChainLLM)

    try:
        llm._extract_pdf_text(b"%PDF")
    except RuntimeError as exc:
        assert str(exc) == "Docling service returned HTTP 503"
    else:
        raise AssertionError("Expected a Docling service error")
