import io

from docx import Document as DocxDocument
from pypdf import PdfReader

from .errors import UnsupportedContentTypeError

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def extract_text(content: bytes, content_type: str) -> str:
    if content_type == PDF_CONTENT_TYPE:
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if content_type == DOCX_CONTENT_TYPE:
        document = DocxDocument(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    raise UnsupportedContentTypeError(
        f"Unsupported content type {content_type!r}; only PDF and DOCX are supported"
    )
