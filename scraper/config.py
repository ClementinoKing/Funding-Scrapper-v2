"""Configuration loading for the funding programme scraper."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
RESOURCE_DIR = PACKAGE_ROOT / "resources"
DEFAULT_OUTPUT_DIR = PACKAGE_ROOT / "output"

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0 Safari/537.36",
]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def bootstrap_env_files() -> None:
    for path in [REPO_ROOT / ".env.local", REPO_ROOT / ".env.scraper", REPO_ROOT / ".env", PACKAGE_ROOT / ".env"]:
        load_env_file(path)


bootstrap_env_files()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_json_resource(filename: str) -> Any:
    path = RESOURCE_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class RuntimeOptions:
    """Run-specific overrides from the CLI layer."""

    output_path: Optional[Path] = None
    max_pages: Optional[int] = None
    depth_limit: Optional[int] = None
    headless: Optional[bool] = None
    browser_fallback: Optional[bool] = None
    respect_robots: Optional[bool] = None
    ai_enrichment: Optional[bool] = None


@dataclass
class ScraperSettings:
    """Global scraper settings loaded from environment variables and resources."""

    output_path: Path = DEFAULT_OUTPUT_DIR
    timeout_seconds: int = 20
    retries: int = 3
    delay_min_seconds: float = 0.8
    delay_max_seconds: float = 2.5
    max_pages: int = 50
    depth_limit: int = 2
    low_confidence_threshold: float = 0.45
    programme_accept_threshold: int = 35
    programme_review_threshold: int = 20
    headless: bool = True
    browser_fallback: bool = True
    respect_robots: bool = True
    application_verification_timeout_seconds: int = 10
    browser_wait_until: str = "networkidle"
    user_agents: List[str] = field(default_factory=lambda: list(DEFAULT_USER_AGENTS))
    relevant_keywords: List[str] = field(default_factory=list)
    irrelevant_url_patterns: List[str] = field(default_factory=list)
    province_list: List[str] = field(default_factory=list)
    municipality_list: List[str] = field(default_factory=list)
    industry_taxonomy: Dict[str, List[str]] = field(default_factory=dict)
    use_of_funds_taxonomy: Dict[str, List[str]] = field(default_factory=dict)
    ownership_target_keywords: Dict[str, List[str]] = field(default_factory=dict)
    entity_type_keywords: Dict[str, List[str]] = field(default_factory=dict)
    certification_keywords: Dict[str, List[str]] = field(default_factory=dict)
    ai_enrichment: bool = False
    ai_provider: str = "openai"
    ai_model: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ScraperSettings":
        output_path = Path(os.getenv("SCRAPER_OUTPUT_PATH", str(DEFAULT_OUTPUT_DIR))).expanduser()
        user_agents_raw = os.getenv("SCRAPER_USER_AGENTS")
        if user_agents_raw:
            user_agents = [agent.strip() for agent in user_agents_raw.split("||") if agent.strip()]
        else:
            user_agents = list(DEFAULT_USER_AGENTS)

        return cls(
            output_path=output_path,
            timeout_seconds=_env_int("SCRAPER_TIMEOUT_SECONDS", 20),
            retries=_env_int("SCRAPER_RETRIES", 3),
            delay_min_seconds=_env_float("SCRAPER_DELAY_MIN_SECONDS", 0.8),
            delay_max_seconds=_env_float("SCRAPER_DELAY_MAX_SECONDS", 2.5),
            max_pages=_env_int("SCRAPER_MAX_PAGES", 50),
            depth_limit=_env_int("SCRAPER_DEPTH_LIMIT", 2),
            low_confidence_threshold=_env_float("SCRAPER_LOW_CONFIDENCE_THRESHOLD", 0.45),
            programme_accept_threshold=_env_int("SCRAPER_PROGRAMME_ACCEPT_THRESHOLD", 35),
            programme_review_threshold=_env_int("SCRAPER_PROGRAMME_REVIEW_THRESHOLD", 20),
            headless=_env_bool("SCRAPER_HEADLESS", True),
            browser_fallback=_env_bool("SCRAPER_BROWSER_FALLBACK", True),
            respect_robots=_env_bool("SCRAPER_RESPECT_ROBOTS", True),
            application_verification_timeout_seconds=_env_int("SCRAPER_APPLICATION_VERIFY_TIMEOUT", 10),
            browser_wait_until=os.getenv("SCRAPER_BROWSER_WAIT_UNTIL", "networkidle"),
            user_agents=user_agents,
            relevant_keywords=load_json_resource("relevant_keywords.json"),
            irrelevant_url_patterns=load_json_resource("irrelevant_url_patterns.json"),
            province_list=load_json_resource("provinces.json"),
            municipality_list=load_json_resource("municipalities.json"),
            industry_taxonomy=load_json_resource("industry_taxonomy.json"),
            use_of_funds_taxonomy=load_json_resource("use_of_funds_taxonomy.json"),
            ownership_target_keywords=load_json_resource("ownership_target_keywords.json"),
            entity_type_keywords=load_json_resource("entity_type_keywords.json"),
            certification_keywords=load_json_resource("certification_keywords.json"),
            ai_enrichment=_env_bool("SCRAPER_AI_ENRICHMENT", False),
            ai_provider=os.getenv("AI_PROVIDER", "openai").strip() or "openai",
            ai_model=os.getenv("SCRAPER_AI_MODEL", "").strip() or None,
        )

    def with_overrides(self, options: RuntimeOptions) -> "ScraperSettings":
        return ScraperSettings(
            output_path=options.output_path or self.output_path,
            timeout_seconds=self.timeout_seconds,
            retries=self.retries,
            delay_min_seconds=self.delay_min_seconds,
            delay_max_seconds=self.delay_max_seconds,
            max_pages=options.max_pages if options.max_pages is not None else self.max_pages,
            depth_limit=options.depth_limit if options.depth_limit is not None else self.depth_limit,
            low_confidence_threshold=self.low_confidence_threshold,
            programme_accept_threshold=self.programme_accept_threshold,
            programme_review_threshold=self.programme_review_threshold,
            headless=options.headless if options.headless is not None else self.headless,
            browser_fallback=(
                options.browser_fallback if options.browser_fallback is not None else self.browser_fallback
            ),
            respect_robots=options.respect_robots if options.respect_robots is not None else self.respect_robots,
            ai_enrichment=options.ai_enrichment if options.ai_enrichment is not None else self.ai_enrichment,
            application_verification_timeout_seconds=self.application_verification_timeout_seconds,
            browser_wait_until=self.browser_wait_until,
            user_agents=list(self.user_agents),
            relevant_keywords=list(self.relevant_keywords),
            irrelevant_url_patterns=list(self.irrelevant_url_patterns),
            province_list=list(self.province_list),
            municipality_list=list(self.municipality_list),
            industry_taxonomy=dict(self.industry_taxonomy),
            use_of_funds_taxonomy=dict(self.use_of_funds_taxonomy),
            ownership_target_keywords=dict(self.ownership_target_keywords),
            entity_type_keywords=dict(self.entity_type_keywords),
            certification_keywords=dict(self.certification_keywords),
            ai_provider=self.ai_provider,
            ai_model=self.ai_model,
        )


@dataclass(frozen=True)
class SupabaseSettings:
    """Supabase connection settings for pushing normalized scraper output."""

    url: str
    anon_key: str
    service_role_key: Optional[str] = None
    rpc_name: str = "ingest_funding_programmes"

    @classmethod
    def from_env(cls) -> "SupabaseSettings":
        url = os.getenv("SUPABASE_URL", "").strip()
        anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or None
        rpc_name = os.getenv("SUPABASE_RPC_NAME", "ingest_funding_programmes").strip() or "ingest_funding_programmes"
        if not url or not anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in the environment, .env.local, or .env.scraper.")
        return cls(
            url=url.rstrip("/"),
            anon_key=anon_key,
            service_role_key=service_role_key,
            rpc_name=rpc_name,
        )

    @property
    def bearer_token(self) -> str:
        return self.service_role_key or self.anon_key
