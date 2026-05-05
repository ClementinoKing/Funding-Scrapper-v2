"""Enhanced document processing for multiple formats."""

from scraper.documents.extractors import (
    DocumentExtractor,
    PDFExtractor,
    WordExtractor,
    ExcelExtractor,
    get_extractor_for_file,
)
from scraper.documents.ocr import OCRProvider, TesseractOCRProvider

__all__ = [
    "DocumentExtractor",
    "PDFExtractor",
    "WordExtractor",
    "ExcelExtractor",
    "get_extractor_for_file",
    "OCRProvider",
    "TesseractOCRProvider",
]
