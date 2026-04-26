# Changelog

## 2026-04-26

### Added
- Document-aware AI enrichment for linked PDFs, DOCX, XLSX, and image documents.
- Program-context document reading so document summaries stay tied to the right funding programme.
- Final-record merge logic so document evidence now flows into `raw_documents_data`, `required_documents`, `application_url`, `contact_email`, `contact_phone`, and related trace fields.
- Context-aware document-link filtering so site-wide PDFs do not mix into unrelated programmes.
- Provider-name inference that prefers the actual funder name from the page title instead of a raw domain label.

### Fixed
- Spaza Shop Support Fund pages no longer pick up unrelated NEF documents such as Tourism Transformation Fund checklists.
- Funder names no longer render as `www.nefcorp.co.za`-style domain text when a proper provider name is available.

### Notes
- The crawler remains site-agnostic and scalable for non-NEF funders.
- Document reading is still conservative: document evidence can fill gaps, but it should not override clear page facts.
- Existing JSON and CSV outputs remain unchanged in shape.
