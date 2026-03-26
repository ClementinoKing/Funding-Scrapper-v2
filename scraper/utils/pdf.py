"""Helpers for extracting text from PDF documents."""

from __future__ import annotations

import io
import re
from typing import List, Optional

try:  # pragma: no cover - optional dependency
    from pypdf import PdfReader
except Exception:  # pragma: no cover - dependency may not be installed yet
    PdfReader = None  # type: ignore[assignment]


TEXT_OBJECT_RE = re.compile(r"\((.*?)\)\s*Tj", re.S)
ARRAY_TEXT_RE = re.compile(r"\[(.*?)\]\s*TJ", re.S)
STRING_RE = re.compile(r"\(([^()]*)\)")


def _unescape_pdf_text(value: str) -> str:
    text = value.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    text = text.replace(r"\r", "\n").replace(r"\n", "\n").replace(r"\t", "\t")
    return text


def _fallback_extract_pdf_text(pdf_bytes: bytes) -> str:
    if not pdf_bytes:
        return ""
    decoded = pdf_bytes.decode("latin-1", errors="ignore")
    chunks: List[str] = []

    for match in TEXT_OBJECT_RE.finditer(decoded):
        text = _unescape_pdf_text(match.group(1))
        if text.strip():
            chunks.append(text)

    for match in ARRAY_TEXT_RE.finditer(decoded):
        text = " ".join(_unescape_pdf_text(part) for part in STRING_RE.findall(match.group(1)))
        if text.strip():
            chunks.append(text)

    if chunks:
        return "\n".join(chunks).strip()

    return ""


def extract_pdf_text(pdf_bytes: bytes) -> str:
    if not pdf_bytes:
        return ""

    if PdfReader is not None:
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            chunks: List[str] = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    chunks.append(page_text)
            text = "\n".join(chunks).strip()
            if text:
                return text
        except Exception:
            pass

    return _fallback_extract_pdf_text(pdf_bytes)
