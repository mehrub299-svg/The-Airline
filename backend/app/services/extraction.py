import asyncio
import io
import zipfile
from pathlib import PurePath
from xml.etree import ElementTree

from pypdf import PdfReader

from app.services.exceptions import BadRequestError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_MAX_DOCX_XML_BYTES = 20 * 1024 * 1024

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_CODE_AND_TEXT = (
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".csv", ".html", ".css", ".sql", ".yaml", ".yml",
)

_TYPES = {
    ".pdf": "application/pdf",
    ".docx": DOCX_TYPE,
    ".md": "text/markdown",
    ".txt": "text/plain",
    **{ext: "text/plain" for ext in _CODE_AND_TEXT},
}

SUPPORTED_EXTENSIONS = ", ".join(sorted(_TYPES))

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def detect_content_type(filename: str) -> str:
    """Decided by file extension; the client-supplied Content-Type is not trusted."""
    suffix = PurePath(filename or "").suffix.lower()
    content_type = _TYPES.get(suffix)
    if content_type is None:
        raise BadRequestError(f"Unsupported file type. Supported: {SUPPORTED_EXTENSIONS}")
    return content_type


def _extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise BadRequestError("Encrypted PDFs are not supported")
        pages = [page.extract_text() or "" for page in reader.pages]
    except BadRequestError:
        raise
    except Exception:
        raise BadRequestError("Could not read this PDF file")
    return "\n\n".join(pages)


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == _W + "t" and node.text:
            parts.append(node.text)
        elif node.tag == _W + "tab":
            parts.append("\t")
        elif node.tag in (_W + "br", _W + "cr"):
            parts.append("\n")
    return "".join(parts)


def _extract_docx(data: bytes) -> str:
    """Paragraphs and tables from word/document.xml, using only the standard library."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            with archive.open("word/document.xml") as member:
                xml_bytes = member.read(_MAX_DOCX_XML_BYTES + 1)
        if len(xml_bytes) > _MAX_DOCX_XML_BYTES:
            raise BadRequestError("This Word document is too large to read")
        if b"<!DOCTYPE" in xml_bytes:  # real documents never have one; blocks XML entity tricks
            raise BadRequestError("Could not read this Word document")

        body = ElementTree.fromstring(xml_bytes).find(_W + "body")
        if body is None:
            raise BadRequestError("Could not read this Word document")

        blocks: list[str] = []
        for child in body:
            if child.tag == _W + "p":
                blocks.append(_paragraph_text(child).strip())
            elif child.tag == _W + "tbl":
                rows: list[str] = []
                for row in child.iter(_W + "tr"):
                    cells = [
                        " ".join(_paragraph_text(p).strip() for p in cell.iter(_W + "p")).strip()
                        for cell in row.findall(_W + "tc")
                    ]
                    if any(cells):
                        rows.append(" | ".join(cells))
                blocks.append("\n".join(rows))
    except BadRequestError:
        raise
    except Exception:
        raise BadRequestError("Could not read this Word document")

    return "\n\n".join(block for block in blocks if block)


async def extract_text(data: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        text = await asyncio.to_thread(_extract_pdf, data)  # pypdf is synchronous and CPU-bound
    elif content_type == DOCX_TYPE:
        text = await asyncio.to_thread(_extract_docx, data)
    else:
        text = data.decode("utf-8-sig", errors="replace")

    text = text.replace("\x00", "").strip()  # PostgreSQL text columns reject NUL bytes
    if not text:
        raise BadRequestError("No extractable text found (scanned PDFs are not supported)")
    return text