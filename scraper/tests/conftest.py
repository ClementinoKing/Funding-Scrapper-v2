from __future__ import annotations

from pathlib import Path

import pytest

from scraper.config import RuntimeOptions, ScraperSettings


@pytest.fixture()
def settings(tmp_path: Path) -> ScraperSettings:
    base = ScraperSettings.from_env()
    return base.with_overrides(
        RuntimeOptions(
            output_path=tmp_path / "output",
            max_pages=10,
            depth_limit=2,
            headless=True,
            browser_fallback=False,
            respect_robots=False,
        )
    )


@pytest.fixture()
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"

