import pytest
from conftest import make_blank_pdf_bytes, make_docx_bytes
from knowledge_service.errors import UnsupportedContentTypeError
from knowledge_service.extraction import DOCX_CONTENT_TYPE, PDF_CONTENT_TYPE, extract_text


def test_extract_text_from_docx():
    content = make_docx_bytes(["First paragraph.", "Second paragraph."])
    text = extract_text(content, DOCX_CONTENT_TYPE)
    assert "First paragraph." in text
    assert "Second paragraph." in text


def test_extract_text_from_blank_pdf_is_empty():
    content = make_blank_pdf_bytes()
    text = extract_text(content, PDF_CONTENT_TYPE)
    assert text.strip() == ""


def test_extract_text_rejects_unsupported_content_type():
    with pytest.raises(UnsupportedContentTypeError):
        extract_text(b"whatever", "text/plain")
