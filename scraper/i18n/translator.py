"""Translation provider abstraction for multi-language support."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from scraper.utils.text import clean_text


class TranslationProvider(ABC):
    """Abstract base for translation providers."""

    def __init__(self, config: Optional[Dict[str, str]] = None) -> None:
        self.config = config or {}
        self._initialize()

    @abstractmethod
    def _initialize(self) -> None:
        """Initialize the translation provider."""
        pass

    @abstractmethod
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str:
        """Translate text from source language to target language."""
        pass

    @abstractmethod
    def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
    ) -> List[str]:
        """Translate multiple texts in batch."""
        pass

    @abstractmethod
    def detect_language(self, text: str) -> str:
        """Detect the language of text."""
        pass

    @property
    @abstractmethod
    def supported_languages(self) -> List[str]:
        """Return list of supported language codes."""
        pass


class NoOpTranslationProvider(TranslationProvider):
    """No-op translation provider that returns text unchanged."""

    def _initialize(self) -> None:
        """No initialization needed."""
        pass

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Return text unchanged."""
        return text

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
    ) -> List[str]:
        """Return texts unchanged."""
        return texts

    def detect_language(self, text: str) -> str:
        """Return default language."""
        return "en"

    @property
    def supported_languages(self) -> List[str]:
        """Return empty list."""
        return []


class OpenAITranslationProvider(TranslationProvider):
    """Translation provider using OpenAI API."""

    def _initialize(self) -> None:
        """Initialize OpenAI client."""
        self.api_key = self.config.get("api_key")
        self.model = self.config.get("model", "gpt-4o-mini")
        self.enabled = bool(self.api_key)

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text using OpenAI."""
        if not self.enabled:
            return text

        try:
            import openai

            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"Translate the following text from {source_lang} to {target_lang}. Return only the translation, no explanations.",
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
            )
            return clean_text(response.choices[0].message.content) or text
        except Exception:
            return text

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
    ) -> List[str]:
        """Translate multiple texts."""
        return [self.translate(text, source_lang, target_lang) for text in texts]

    def detect_language(self, text: str) -> str:
        """Detect language using OpenAI."""
        if not self.enabled:
            return "en"

        try:
            import openai

            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Detect the language of the following text. Return only the ISO 639-1 language code (e.g., 'en', 'fr', 'es').",
                    },
                    {"role": "user", "content": text[:500]},
                ],
                temperature=0.1,
            )
            return clean_text(response.choices[0].message.content).lower() or "en"
        except Exception:
            return "en"

    @property
    def supported_languages(self) -> List[str]:
        """Return supported languages."""
        return [
            "en",
            "es",
            "fr",
            "de",
            "it",
            "pt",
            "nl",
            "pl",
            "ru",
            "ja",
            "ko",
            "zh",
            "ar",
            "hi",
            "af",
            "zu",
            "xh",
        ]


class TranslationRegistry:
    """Registry for managing translation providers."""

    def __init__(self) -> None:
        self._providers: Dict[str, TranslationProvider] = {}
        self._default_provider: Optional[str] = None

    def register(
        self,
        name: str,
        provider: TranslationProvider,
        set_as_default: bool = False,
    ) -> None:
        """Register a translation provider."""
        self._providers[name] = provider
        if set_as_default or self._default_provider is None:
            self._default_provider = name

    def get(self, name: Optional[str] = None) -> Optional[TranslationProvider]:
        """Get a translation provider by name."""
        if name:
            return self._providers.get(name)
        if self._default_provider:
            return self._providers.get(self._default_provider)
        return None

    def list_providers(self) -> List[str]:
        """List all registered providers."""
        return list(self._providers.keys())


# Global registry
_global_translation_registry: Optional[TranslationRegistry] = None


def get_global_translation_registry() -> TranslationRegistry:
    """Get or create the global translation registry."""
    global _global_translation_registry
    if _global_translation_registry is None:
        _global_translation_registry = TranslationRegistry()
        # Register default no-op provider
        _global_translation_registry.register(
            "noop",
            NoOpTranslationProvider(),
            set_as_default=True,
        )
    return _global_translation_registry
