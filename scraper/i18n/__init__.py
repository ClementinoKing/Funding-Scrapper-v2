"""Internationalization and multi-language support."""

from scraper.i18n.detector import LanguageDetector
from scraper.i18n.translator import TranslationProvider, TranslationRegistry

__all__ = [
    "LanguageDetector",
    "TranslationProvider",
    "TranslationRegistry",
]
