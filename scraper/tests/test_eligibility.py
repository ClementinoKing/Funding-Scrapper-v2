from __future__ import annotations

from scraper.classifiers.eligibility import extract_eligibility_criteria


def test_extract_eligibility_criteria_splits_and_filters_noise() -> None:
    text = (
        "Eligibility Criteria: The business must be majority black-owned; the applicant must submit a completed application form. "
        "The enterprise must demonstrate commercial viability and sustainability. Shareholders must be operationally involved in the business. "
        "The applicant must provide valid registration documents and tax clearance. Loan term of up to 60 months. Contact us by email."
    )

    criteria = extract_eligibility_criteria(text)

    assert criteria == [
        "The business must be majority black-owned",
        "the applicant must submit a completed application form.",
        "The enterprise must demonstrate commercial viability and sustainability.",
        "Shareholders must be operationally involved in the business.",
        "The applicant must provide valid registration documents and tax clearance.",
    ]
