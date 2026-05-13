from __future__ import annotations

from scraper.utils.money import extract_amount_evidence, extract_budget_total, extract_money_range


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


def test_extract_money_range_requires_currency_or_funding_context() -> None:
    minimum, maximum, currency, snippet, confidence = extract_money_range(
        "The programme has 2024 participants and 350 applications.",
        default_currency="ZAR",
    )
    assert minimum is None
    assert maximum is None
    assert currency is None
    assert snippet is None
    assert confidence == 0.0


def test_extract_money_range_rejects_non_amount_numeric_contexts() -> None:
    examples = [
        "Call 011 555 0100 for details.",
        "Tender number T2025/004 closes on 12/05/2026.",
        "Applicants need 51% black ownership.",
        "Support is for TRL 4-7 technologies.",
        "Postal code 2001 applies.",
    ]
    for example in examples:
        minimum, maximum, currency, snippet, confidence = extract_money_range(example, default_currency="ZAR")
        assert minimum is None
        assert maximum is None
        assert currency is None
        assert snippet is None
        assert confidence == 0.0


def test_extract_money_range_accepts_scaled_amount_with_funding_context() -> None:
    minimum, maximum, currency, snippet, confidence = extract_money_range(
        "The loan amount is ZAR 1 million for qualifying businesses.",
        default_currency="ZAR",
    )
    assert minimum is None
    assert maximum == 1000000
    assert currency == "ZAR"
    assert "ZAR 1 million" in snippet
    assert confidence >= 0.65


def test_extract_money_range_handles_shared_scale_in_ranges() -> None:
    minimum, maximum, currency, snippet, confidence = extract_money_range(
        "Ideal R300–R500m for strategic expansion opportunities.",
        default_currency="ZAR",
    )
    assert minimum == 300000000
    assert maximum == 500000000
    assert currency == "ZAR"
    assert "R300" in snippet
    assert confidence >= 0.8


def test_extract_money_range_handles_usd_ranges_and_billion_notation() -> None:
    minimum, maximum, currency, snippet, confidence = extract_money_range(
        "The fund targets US$20–US$40m investments and can scale to R1.35 billion in larger mandates.",
        default_currency=None,
    )
    assert minimum == 20000000
    assert maximum == 40000000
    assert currency == "USD"
    assert "US$20" in snippet
    assert confidence >= 0.8


def test_extract_amount_evidence_preserves_ideal_and_minimum_ranges() -> None:
    evidence = extract_amount_evidence(
        "Min R100m. Ideal R300–R500m. Funding is for strategic infrastructure deals.",
        default_currency="ZAR",
    )
    assert evidence["minimum"]["value"] == 100000000
    assert evidence["minimum"]["currency"] == "ZAR"
    assert evidence["ideal_range"]["min"] == 300000000
    assert evidence["ideal_range"]["max"] == 500000000


def test_extract_budget_total() -> None:
    amount, currency, snippet, confidence = extract_budget_total(
        "The programme budget totals ZAR 2 million for the 2026 intake.",
        default_currency="ZAR",
    )
    assert amount == 2000000
    assert currency == "ZAR"
    assert "budget" in snippet.lower()
    assert confidence > 0
