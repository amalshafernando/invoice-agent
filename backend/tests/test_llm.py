from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.agent.llm import DocumentExtractionError, LangChainLLM
from app.agent.pdfgen import render_invoice_pdf
from app.config import settings
from app.schemas import InvoiceExtraction, LineItem


def _make_text_pdf() -> bytes:
    """Create a simple PDF with a text layer for pypdf to extract."""
    return render_invoice_pdf({
        "invoice_no": "TEST-001", "supplier_name": "Test Corp",
        "po_number": "PO-999", "currency": "USD",
        "items": [{"description": "Widget", "quantity": 1, "unit_price": 10.0}],
        "total": 10.0, "notes": "test note",
    })


def test_docling_service_returns_markdown(monkeypatch):
    monkeypatch.setattr(settings, "docling_url", "http://docling:5001/")
    monkeypatch.setattr(settings, "hf_token", "")
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
    assert kwargs["data"] == {
        "from_formats": "pdf", "to_formats": "md", "do_ocr": "true"
    }
    assert kwargs["headers"] == {"X-Api-Key": "docling-test-key"}
    assert kwargs["timeout"] == 45


def test_docling_huggingface_endpoint_uses_bearer_token(monkeypatch):
    monkeypatch.setattr(
        settings, "docling_url", "https://docling.example.endpoints.huggingface.cloud"
    )
    monkeypatch.setattr(settings, "hf_token", "hf-test-token")
    monkeypatch.setattr(settings, "docling_api_key", "")
    response = httpx.Response(
        200,
        json={"status": "success", "document": {"md_content": "# Invoice"}},
        request=httpx.Request(
            "POST",
            "https://docling.example.endpoints.huggingface.cloud/v1/convert/file",
        ),
    )
    post = Mock(return_value=response)
    monkeypatch.setattr("app.agent.llm.httpx.post", post)

    llm = LangChainLLM.__new__(LangChainLLM)
    assert llm._extract_pdf_text(b"%PDF") == "# Invoice"
    assert post.call_args.kwargs["headers"] == {
        "Authorization": "Bearer hf-test-token"
    }


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


def test_docling_http_error_falls_back_to_pypdf(monkeypatch):
    """When Docling returns HTTP 503, the extractor should fall back to pypdf
    instead of raising an error, as long as the PDF has a text layer."""
    response = httpx.Response(
        503,
        text="unavailable",
        request=httpx.Request("POST", "http://127.0.0.1:5001/v1/convert/file"),
    )
    monkeypatch.setattr("app.agent.llm.httpx.post", Mock(return_value=response))
    llm = LangChainLLM.__new__(LangChainLLM)

    pdf_bytes = _make_text_pdf()
    text = llm._extract_pdf_text(pdf_bytes)
    # pypdf should have extracted text from the PDF's text layer
    assert "TEST-001" in text
    assert "Test Corp" in text


def test_docling_connection_error_falls_back_to_pypdf(monkeypatch):
    """When Docling is unreachable, extraction falls back to pypdf."""
    monkeypatch.setattr(
        "app.agent.llm.httpx.post",
        Mock(side_effect=httpx.ConnectError("Connection refused")),
    )
    llm = LangChainLLM.__new__(LangChainLLM)

    pdf_bytes = _make_text_pdf()
    text = llm._extract_pdf_text(pdf_bytes)
    assert "TEST-001" in text


def test_both_docling_and_pypdf_fail_raises_error(monkeypatch):
    """When Docling fails AND pypdf can't extract text, we get an error."""
    monkeypatch.setattr(
        "app.agent.llm.httpx.post",
        Mock(side_effect=httpx.ConnectError("Connection refused")),
    )
    llm = LangChainLLM.__new__(LangChainLLM)

    # Empty/corrupt bytes — pypdf won't be able to read this either
    with pytest.raises(DocumentExtractionError):
        llm._extract_pdf_text(b"not-a-pdf")
