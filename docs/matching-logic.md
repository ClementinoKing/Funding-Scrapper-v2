# Matching Logic Design

## Rule-Based Scoring (Initial)
- Sector overlap: 35%
- Geography eligibility: 30%
- Funding type preference: 20%
- Amount range overlap: 15%

## Match Status Thresholds
- `high_fit`: score >= 80
- `medium_fit`: score 60-79
- `low_fit`: score < 60
- `manual_review`: score ambiguous or conflicting blockers

## Processing Model
- Trigger matching when profile updates or approved program data changes.
- Cache match results in `match_results` for instant UI retrieval.
- Preserve explanation fields (`reasons`, `blockers`) for transparency.

## Extensibility
- Add rule plug-ins for legal entity type, years operating, gender focus, founder age, and documentation requirements.
- Add optional ML ranking layer after rules as a second-pass reranker.
