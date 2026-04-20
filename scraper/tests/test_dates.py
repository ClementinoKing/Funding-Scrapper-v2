from __future__ import annotations

from scraper.utils.dates import parse_deadline_info


def test_parse_fixed_deadline() -> None:
    result = parse_deadline_info("Applications close on 15 May 2026.")
    assert result["deadline_type"] == "FixedDate"
    assert str(result["deadline_date"]) == "2026-05-15"
    assert result["confidence"] > 0.7


def test_parse_rolling_deadline() -> None:
    result = parse_deadline_info("Applications are considered on a rolling basis.")
    assert result["deadline_type"] == "Rolling"
    assert result["deadline_date"] is None


def test_parse_open_deadline() -> None:
    result = parse_deadline_info("This fund is open year-round and applicants may apply anytime.")
    assert result["deadline_type"] == "Open"
    assert result["deadline_date"] is None


def test_parse_deadline_ignores_percentages_in_eligibility_text() -> None:
    result = parse_deadline_info("Funding requirements: Minimum of 51% black female ownership.")
    assert result["deadline_type"] == "Unknown"
    assert result["deadline_date"] is None
