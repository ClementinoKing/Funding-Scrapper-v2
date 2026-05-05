"""Language detection for multi-language content."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from scraper.utils.text import clean_text


class LanguageDetector:
    """Simple language detector based on character patterns and common words."""

    # Common words for basic language detection
    LANGUAGE_PATTERNS = {
        "en": {
            "words": ["the", "and", "for", "are", "with", "this", "that", "from", "have", "will"],
            "chars": set("abcdefghijklmnopqrstuvwxyz"),
        },
        "af": {
            "words": ["die", "van", "en", "is", "vir", "met", "wat", "het", "word", "sal"],
            "chars": set("abcdefghijklmnopqrstuvwxyzêëïôûáéíóú"),
        },
        "zu": {
            "words": ["ukuthi", "futhi", "ngoba", "uma", "ukuba", "noma", "kodwa", "ngakho"],
            "chars": set("abcdefghijklmnopqrstuvwxyz"),
        },
        "xh": {
            "words": ["ukuba", "kwaye", "okanye", "kodwa", "ngoba", "ukuze", "xa", "ukuba"],
            "chars": set("abcdefghijklmnopqrstuvwxyz"),
        },
        "fr": {
            "words": ["le", "la", "les", "de", "et", "pour", "dans", "avec", "que", "qui"],
            "chars": set("abcdefghijklmnopqrstuvwxyzàâäæçéèêëïîôùûüÿœ"),
        },
        "es": {
            "words": ["el", "la", "los", "las", "de", "y", "para", "con", "que", "por"],
            "chars": set("abcdefghijklmnopqrstuvwxyzáéíóúüñ¿¡"),
        },
        "pt": {
            "words": ["o", "a", "os", "as", "de", "e", "para", "com", "que", "por"],
            "chars": set("abcdefghijklmnopqrstuvwxyzáàâãéêíóôõúüç"),
        },
        "de": {
            "words": ["der", "die", "das", "und", "für", "mit", "von", "zu", "auf", "ist"],
            "chars": set("abcdefghijklmnopqrstuvwxyzäöüß"),
        },
        "ar": {
            "words": ["في", "من", "على", "إلى", "هذا", "التي", "أن", "كان"],
            "chars": set("ابتثجحخدذرزسشصضطظعغفقكلمنهوي"),
        },
        "zh": {
            "words": ["的", "是", "在", "和", "有", "了", "人", "我", "他", "这"],
            "chars": set(),  # Will use Unicode range
        },
    }

    def __init__(self) -> None:
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for language detection."""
        self.word_patterns: Dict[str, re.Pattern] = {}
        for lang, data in self.LANGUAGE_PATTERNS.items():
            words = data["words"]
            pattern = r"\b(" + "|".join(re.escape(word) for word in words) + r")\b"
            self.word_patterns[lang] = re.compile(pattern, re.IGNORECASE)

    def detect(self, text: str, top_n: int = 3) -> List[Tuple[str, float]]:
        """
        Detect language(s) in text.

        Returns list of (language_code, confidence) tuples.
        """
        if not text or len(text.strip()) < 10:
            return [("en", 0.5)]  # Default to English for short text

        cleaned = clean_text(text).lower()
        scores: Dict[str, float] = {}

        # Score based on common words
        for lang, pattern in self.word_patterns.items():
            matches = pattern.findall(cleaned)
            if matches:
                # Weight by frequency and uniqueness
                word_score = len(matches) / max(len(cleaned.split()), 1)
                scores[lang] = scores.get(lang, 0.0) + word_score * 10

        # Score based on character sets
        char_counter = Counter(cleaned)
        for lang, data in self.LANGUAGE_PATTERNS.items():
            chars = data["chars"]
            if chars:
                matching_chars = sum(count for char, count in char_counter.items() if char in chars)
                total_chars = sum(char_counter.values())
                if total_chars > 0:
                    char_score = matching_chars / total_chars
                    scores[lang] = scores.get(lang, 0.0) + char_score * 5

        # Check for Chinese characters
        if re.search(r"[\u4e00-\u9fff]", text):
            scores["zh"] = scores.get("zh", 0.0) + 10

        # Check for Arabic script
        if re.search(r"[\u0600-\u06ff]", text):
            scores["ar"] = scores.get("ar", 0.0) + 10

        # Normalize scores
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {lang: score / max_score for lang, score in scores.items()}

        # Sort by score and return top N
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_n] if sorted_scores else [("en", 0.5)]

    def detect_primary(self, text: str) -> str:
        """Detect the primary language in text."""
        results = self.detect(text, top_n=1)
        return results[0][0] if results else "en"

    def is_multilingual(self, text: str, threshold: float = 0.3) -> bool:
        """Check if text contains multiple languages."""
        results = self.detect(text, top_n=3)
        if len(results) < 2:
            return False
        # Check if second language has significant presence
        return results[1][1] >= threshold
