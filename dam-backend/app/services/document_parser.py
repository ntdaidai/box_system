"""Document text extraction for knowledge indexing."""

from __future__ import annotations

import io
import re
from pathlib import Path


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_document_bytes(data: bytes, filename: str) -> str:
    """Extract plain text from common office/document formats.

    Optional parsers are imported lazily so the API still works for txt/md even
    if PDF/XLSX dependencies are not installed in a development environment.
    """
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix in {"txt", "md", "csv", "json", "log"}:
        return normalize_text(_decode_text(data))
    if suffix == "docx":
        return normalize_text(_parse_docx(data))
    if suffix == "pdf":
        return normalize_text(_parse_pdf(data))
    if suffix in {"xlsx", "xls"}:
        return normalize_text(_parse_xlsx(data))
    return normalize_text(_decode_text(data))


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _parse_docx(data: bytes) -> str:
    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("缺少 python-docx，无法解析 DOCX") from exc

    doc = Document(io.BytesIO(data))
    parts: list[str] = []
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _parse_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("缺少 pypdf，无法解析 PDF") from exc

    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"\n\n[第{index}页]\n{text}")
    return "\n".join(pages)


def _parse_xlsx(data: bytes) -> str:
    try:
        from openpyxl import load_workbook
    except Exception as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("缺少 openpyxl，无法解析 Excel") from exc

    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts: list[str] = []
    for sheet in workbook.worksheets:
        parts.append(f"[工作表] {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(value).strip() for value in row if value not in (None, "")]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)
