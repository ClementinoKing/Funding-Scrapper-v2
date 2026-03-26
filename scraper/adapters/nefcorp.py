"""NEFCorp adapter configuration for the shared scraper framework."""

from __future__ import annotations

from scraper.adapters.base import SiteAdapter


class NefcorpSiteAdapter:
    """Factory for the NEF site adapter and NEF-specific merge hints."""

    domain = "nefcorp.co.za"
    key = "nefcorp"
    primary_seed_url = "https://www.nefcorp.co.za/products-services/"

    @classmethod
    def build(cls) -> SiteAdapter:
        return SiteAdapter(
            key=cls.key,
            domain=cls.domain,
            allowed_path_prefixes=("/products-services/",),
            default_seed_urls=(cls.primary_seed_url,),
            include_url_terms=(
                "fund",
                "funding",
                "finance",
                "programme",
                "product",
                "transformation",
                "capital",
                "venture",
                "acquisition",
                "expansion",
                "entrepreneurship",
                "procurement",
                "franchise",
                "tourism",
                "furniture",
                "bakubung",
                "spaza",
                "film",
                "arts",
            ),
            exclude_url_terms=(
                "/news/",
                "/media/",
                "/resources/",
                "/about/",
                "/careers/",
                "/contact/",
                "/search",
                "/archive",
            ),
            strict_path_prefixes=False,
            allow_root_url=True,
            discovery_terms=(
                "fund",
                "funding",
                "finance",
                "programme",
                "product",
                "capital",
                "venture",
                "apply",
            ),
            content_selectors=(
                "article.single-page-article .single-page-content",
                "article.single-page-article .entry-content",
                "article.single-page-article",
                ".single-page-content",
                ".entry-content",
            ),
            candidate_selectors=("article", "section", "div.card", ".card", ".programme-card", ".content-block"),
            parent_page_terms=(
                "iMbewu Fund",
                "uMnotho Fund",
                "Rural, Township and Community Development Fund",
                "Strategic Projects Fund",
                "Arts and Culture Venture Capital Fund",
                "Tourism Transformation Fund",
                "Furniture Fund",
                "Bakubung Fund",
                "Spaza Shop Support Fund",
                "Television and Film Fund",
            ),
            child_page_terms=(
                "funding criteria",
                "eligibility criteria",
                "how to apply",
                "non-financial business support",
                "programme guidelines",
                "ttf checklist",
                "empowerment objectives",
            ),
            support_page_terms=(
                "funding criteria",
                "eligibility criteria",
                "how to apply",
                "funding instruments",
                "non-financial business support",
                "checklist",
                "guidelines",
                "brochure",
                "application portal",
                "portal",
                "empowerment objectives",
            ),
            merge_aliases={
                "how to apply": "",
                "programme guidelines": "",
                "funding criteria": "",
                "overview": "",
                "support fund": "fund",
            },
            notes=(
                "Only crawl the /products-services/ funding tree.",
                "Use supporting documents and child pages to enrich parent programmes.",
            ),
        )
