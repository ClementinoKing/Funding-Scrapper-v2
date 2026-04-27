from __future__ import annotations

from scraper.classifiers.repayment import extract_payback_details
from scraper.schemas import RepaymentFrequency


def test_extract_payback_details_parses_years_grace_and_monthly_frequency() -> None:
    details = extract_payback_details(
        "Loan term of up to 5 years. A 3 month grace period applies and the facility is repaid in monthly instalments."
    )

    assert details.raw_text is not None
    assert "5 years" in details.raw_text
    assert details.term_min_months is None
    assert details.term_max_months == 60
    assert details.grace_period_months == 3
    assert details.repayment_frequency == RepaymentFrequency.MONTHLY
    assert details.structure == "monthly instalments"
    assert details.confidence > 0


def test_extract_payback_details_parses_range_and_quarterly_frequency() -> None:
    details = extract_payback_details("Repayment period between 12 and 36 months with quarterly repayments.")

    assert details.term_min_months == 12
    assert details.term_max_months == 36
    assert details.repayment_frequency == RepaymentFrequency.QUARTERLY
    assert details.structure == "quarterly repayments"
    assert details.confidence > 0
