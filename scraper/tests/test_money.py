from __future__ import annotations

from scraper.utils.money import extract_budget_total, extract_money_range


def test_extract_money_range_between() -> None:
    minimum, maximum, currency, snippet, confidence = extract_money_range(
        "Funding ranges between R500k and R5m for qualifying SMEs.",
        default_currency="ZAR",
    )
    assert minimum == 500000
    assert maximum == 5000000
    assert currency == "ZAR"
    assert "R500k" in snippet
    assert confidence >= 0.8


def test_extract_money_range_up_to() -> None:
    minimum, maximum, currency, snippet, _confidence = extract_money_range(
        "Applicants may receive up to R10 million for equipment purchases.",
        default_currency="ZAR",
    )
    assert minimum is None
    assert maximum == 10000000
    assert currency == "ZAR"
    assert "up to" in snippet.lower()


def test_extract_money_range_ignores_year_like_values() -> None:
    minimum, maximum, currency, snippet, confidence = extract_money_range(
        "Applications close in 2020.",
        default_currency="ZAR",
    )
    assert minimum is None
    assert maximum is None
    assert currency is None
    assert snippet is None
    assert confidence == 0.0


def test_extract_budget_total() -> None:
    amount, currency, snippet, confidence = extract_budget_total(
        "The programme budget totals ZAR 2 million for the 2026 intake.",
        default_currency="ZAR",
    )
    assert amount == 2000000
    assert currency == "ZAR"
    assert "budget" in snippet.lower()
    assert confidence > 0
