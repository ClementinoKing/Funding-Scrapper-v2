"""OpenAI Web Search extraction pipeline."""

from scraper.web_search.models import WebSearchFunder
from scraper.web_search.pipeline import WebSearchPipeline

__all__ = ["WebSearchFunder", "WebSearchPipeline"]
