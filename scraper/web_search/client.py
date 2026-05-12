"""OpenAI Responses API Web Search client."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

from scraper.web_search.models import WebSearchExtractionResponse, WebSearchFunder, WebSearchSource
from scraper.web_search.queries import normalized_search_domain
from scraper.utils.text import clean_text


class OpenAIWebSearchExtractor:
    """Run one domain-filtered OpenAI Web Search extraction query."""

    def __init__(
        self,
        *,
        model: str,
        api_key: Optional[str] = None,
        client: Any = None,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = client
        if self.client is None:
            if not self.api_key:
                raise RuntimeError("OPENAI_API_KEY is required when SCRAPER_MODE=web_search.")
            self.client = OpenAI(api_key=self.api_key, max_retries=0)

    def extract(self, funder: WebSearchFunder, query: str) -> tuple[WebSearchExtractionResponse, List[WebSearchSource]]:
        domain = normalized_search_domain(funder.website_url)
        response = self.client.responses.create(
            model=self.model,
            tools=[
                {
                    "type": "web_search",
                    "filters": {"allowed_domains": [domain]},
                }
            ],
            tool_choice="auto",
            include=["web_search_call.action.sources"],
            input=[
                {
                    "role": "system",
                    "content": self._system_prompt(),
                },
                {
                    "role": "user",
                    "content": self._user_prompt(funder, domain, query),
                },
            ],
        )
        raw_text = self._response_text(response)
        payload = self._parse_json(raw_text)
        parsed = WebSearchExtractionResponse.model_validate(payload)
        for programme in parsed.programmes:
            if not programme.query:
                programme.query = query
        return parsed, self._response_sources(response, domain)

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You extract funding programme records from reliable web sources. "
            "Return strict JSON only. Do not guess. Do not include records without a source_url. "
            "Extract main programmes and sub-programmes as separate records. "
            "Classify funding_type only as Grant, Loan, Equity, Guarantee, Hybrid, Other, or Unknown. "
            "Use null for unknown scalar values and [] for unknown lists."
        )

    @staticmethod
    def _user_prompt(funder: WebSearchFunder, domain: str, query: str) -> str:
        return json.dumps(
            {
                "task": "Use OpenAI Web Search for the query and extract funding programme data.",
                "query": query,
                "source_priority": [
                    "Official funder website",
                    "Official PDFs, brochures, annual reports, or product documents from the funder website",
                    "Government or official partner pages",
                    "Other sources only as supporting references",
                ],
                "funder": {
                    "funder_name": funder.funder_name,
                    "website_url": funder.website_url,
                    "domain": domain,
                    "country": funder.country,
                    "currency": funder.currency,
                },
                "required_output_shape": {
                    "funder_name": "",
                    "website_url": "",
                    "country": "",
                    "currency": "",
                    "status": "ok",
                    "notes": None,
                    "programmes": [
                        {
                            "program_name": "",
                            "parent_program_name": None,
                            "is_sub_programme": False,
                            "funding_type": None,
                            "funding_lines": [],
                            "ticket_min": None,
                            "ticket_max": None,
                            "ideal_range": None,
                            "currency": "",
                            "raw_eligibility_criteria": [],
                            "raw_repayment_terms": [],
                            "sector_focus": [],
                            "required_documents": [],
                            "application_process": None,
                            "target_applicants": [],
                            "geographic_focus": None,
                            "source_url": "",
                            "source_title": "",
                            "source_type": "",
                            "confidence_score": "integer from 0 to 100, not a 0-1 decimal",
                            "extraction_notes": "",
                        }
                    ],
                },
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _response_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return str(output_text)
        output = getattr(response, "output", None) or []
        chunks: List[str] = []
        for item in output:
            content = getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else None) or []
            for part in content:
                text = getattr(part, "text", None) or (part.get("text") if isinstance(part, dict) else None)
                if text:
                    chunks.append(str(text))
        return "\n".join(chunks)

    @staticmethod
    def _parse_json(raw_text: str) -> Dict[str, Any]:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw_text or "")
            if not match:
                raise ValueError("OpenAI Web Search response did not contain JSON.")
            payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            raise ValueError("OpenAI Web Search response JSON must be an object.")
        return payload

    @staticmethod
    def _response_sources(response: Any, domain: str) -> List[WebSearchSource]:
        sources: List[WebSearchSource] = []
        output = getattr(response, "output", None) or []
        for item in output:
            action = getattr(item, "action", None) or (item.get("action") if isinstance(item, dict) else None)
            action_sources = getattr(action, "sources", None) or (action.get("sources") if isinstance(action, dict) else None) or []
            for source in action_sources:
                url = getattr(source, "url", None) or (source.get("url") if isinstance(source, dict) else None)
                title = getattr(source, "title", None) or (source.get("title") if isinstance(source, dict) else None)
                if not url:
                    continue
                sources.append(
                    WebSearchSource(
                        url=str(url),
                        title=clean_text(str(title or "")) or None,
                        source_type=_source_type_for_url(str(url)),
                        official_rank=1 if domain in str(url).lower() else 4,
                    )
                )
        deduped: Dict[str, WebSearchSource] = {}
        for source in sources:
            deduped.setdefault(source.url, source)
        return list(deduped.values())


def _source_type_for_url(url: str) -> str:
    lowered = url.lower()
    if lowered.endswith(".pdf") or ".pdf?" in lowered:
        return "official_document"
    if any(term in lowered for term in ["annual-report", "brochure", "guideline", "application-form"]):
        return "official_document"
    return "official_website"
