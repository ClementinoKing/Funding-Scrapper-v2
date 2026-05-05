"""OCR providers for image-based document extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union

from scraper.utils.text import clean_text


class OCRProvider(ABC):
    """Abstract base for OCR providers."""

    @abstractmethod
    def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract text from image or PDF using OCR."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if OCR provider is available."""
        pass


class TesseractOCRProvider(OCRProvider):
    """OCR provider using Tesseract."""

    def __init__(self, language: str = "eng") -> None:
        self.language = language
        self._available: Optional[bool] = None

    def extract_text(self, file_path: Union[str, Path]) -> str:
        """Extract text using Tesseract OCR."""
        if not self.is_available():
            return ""

        try:
            import pytesseract
            from PIL import Image

            path = Path(file_path)

            # Handle PDF files
            if path.suffix.lower() == ".pdf":
                try:
                    from pdf2image import convert_from_path

                    images = convert_from_path(str(path))
                    text_parts = []
                    for image in images:
                        text = pytesseract.image_to_string(image, lang=self.language)
                        if text:
                            text_parts.append(text)
                    return clean_text("\n".join(text_parts))
                except Exception:
                    return ""

            # Handle image files
            image = Image.open(path)
            text = pytesseract.image_to_string(image, lang=self.language)
            return clean_text(text)
        except Exception:
            return ""

    def is_available(self) -> bool:
        """Check if Tesseract is available."""
        if self._available is not None:
            return self._available

        try:
            import pytesseract

            # Try to get version to verify installation
            pytesseract.get_tesseract_version()
            self._available = True
        except Exception:
            self._available = False

        return self._available


class NoOpOCRProvider(OCRProvider):
    """No-op OCR provider that returns empty text."""

    def extract_text(self, file_path: Union[str, Path]) -> str:
        """Return empty text."""
        return ""

    def is_available(self) -> bool:
        """Always return False."""
        return False
