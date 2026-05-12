"""Tests for page_ranking module."""

import pytest

from app.utils.profile_beta2.page_ranking import classify_url, score_page, select_pages


class TestClassifyUrl:
    def test_homepage_root(self):
        assert classify_url("https://example.com/") == "homepage"
        assert classify_url("https://example.com") == "homepage"
        assert classify_url("https://example.com/index.html") == "homepage"

    def test_about_pages(self):
        assert classify_url("https://example.com/about") == "about"
        assert classify_url("https://example.com/about-us") == "about"
        assert classify_url("https://example.com/company") == "about"
        assert classify_url("https://example.com/who-we-are") == "about"

    def test_products_pages(self):
        assert classify_url("https://example.com/products") == "products"
        assert classify_url("https://example.com/product-category/widgets") == "products"

    def test_services_pages(self):
        assert classify_url("https://example.com/services") == "services"
        assert classify_url("https://example.com/solutions") == "services"

    def test_projects_pages(self):
        assert classify_url("https://example.com/projects") == "projects"
        assert classify_url("https://example.com/portfolio") == "projects"

    def test_cases_pages(self):
        assert classify_url("https://example.com/cases") == "cases"
        assert classify_url("https://example.com/case-studies/success") == "cases"

    def test_certificates_pages(self):
        assert classify_url("https://example.com/certificates") == "certificates"
        assert classify_url("https://example.com/iso-certification") == "certificates"

    def test_downloads_pages(self):
        assert classify_url("https://example.com/downloads") == "downloads"
        assert classify_url("https://example.com/resources/brochure") == "downloads"

    def test_contact_pages(self):
        assert classify_url("https://example.com/contact") == "contact"
        assert classify_url("https://example.com/contact-us") == "contact"
        assert classify_url("https://example.com/inquiry") == "contact"

    def test_factory_pages(self):
        assert classify_url("https://example.com/factory") == "factory"
        assert classify_url("https://example.com/manufacturing") == "factory"

    def test_quality_pages(self):
        assert classify_url("https://example.com/quality-control") == "quality"

    def test_news_pages(self):
        assert classify_url("https://example.com/news/latest") == "news"

    def test_blog_pages(self):
        assert classify_url("https://example.com/blog/post-1") == "blog"

    def test_other_pages(self):
        assert classify_url("https://example.com/some-random-page") == "other"

    def test_link_text_fallback(self):
        # Chinese about text
        assert classify_url("https://example.com/page1", "关于我们") == "about"
        # Chinese products text
        assert classify_url("https://example.com/page2", "产品中心") == "products"
        # Japanese about text
        assert classify_url("https://example.com/page3", "会社概要") == "about"


class TestScorePage:
    def test_high_value_products(self):
        score = score_page("https://example.com/products", "Products", set(), set())
        assert score >= 10

    def test_high_value_cases(self):
        score = score_page("https://example.com/cases", "Case Studies", set(), set())
        assert score >= 10

    def test_certificates_high(self):
        score = score_page("https://example.com/certificates", "Certificates", set(), set())
        assert score >= 10

    def test_contact_moderate(self):
        score = score_page("https://example.com/contact", "Contact Us", set(), set())
        assert 0 < score < 10

    def test_blog_penalty(self):
        score = score_page("https://example.com/blog/post-1", "Blog Post", set(), set())
        assert score < 0

    def test_news_penalty(self):
        score = score_page("https://example.com/news/latest", "Latest News", set(), set())
        assert score < 0

    def test_tag_penalty(self):
        score = score_page("https://example.com/tag/widget", "Tag: Widget", set(), set())
        assert score <= -5

    def test_login_penalty(self):
        score = score_page("https://example.com/login", "Login", set(), set())
        assert score <= -8

    def test_duplicate_url_penalty(self):
        """Duplicate high-value page should still be positive but lower than original."""
        seen = {"https://example.com/products"}
        score = score_page("https://example.com/products", "Products", seen, set())
        # products=12, duplicate=-8 → score=4, still positive but less than original
        assert score == 4

    def test_duplicate_title_penalty(self):
        seen_titles = {"products page"}
        score = score_page("https://example.com/products", "Products Page", set(), seen_titles)
        # Same: products=12, duplicate title=-8 → 4
        assert score == 4

    def test_paginated_penalty(self):
        score = score_page("https://example.com/products?page=2", "Page 2", set(), set())
        # products=12, page param=-5 → 7 (still positive but reduced)
        assert score == 7


class TestSelectPages:
    def _make_page(self, url, title, category, score):
        return {"url": url, "title": title, "category": category, "score": score}

    def test_diversity_ensured(self):
        """Each diversity group should have at least one representative."""
        pages = [
            self._make_page("https://example.com/products", "Products", "products", 12),
            self._make_page("https://example.com/services", "Services", "services", 10),
            self._make_page("https://example.com/about", "About", "about", 8),
            self._make_page("https://example.com/cases", "Cases", "cases", 12),
            self._make_page("https://example.com/contact", "Contact", "contact", 6),
            self._make_page("https://example.com/blog/1", "Blog 1", "blog", -3),
            self._make_page("https://example.com/blog/2", "Blog 2", "blog", -3),
            self._make_page("https://example.com/blog/3", "Blog 3", "blog", -3),
            self._make_page("https://example.com/blog/4", "Blog 4", "blog", -3),
            self._make_page("https://example.com/blog/5", "Blog 5", "blog", -3),
        ]
        selected = select_pages(pages, max_default=8)
        categories = {p["category"] for p in selected}
        assert "products" in categories
        assert "about" in categories
        assert "contact" in categories
        # Blogs should be lower priority (maybe included if slots remain)

    def test_max_default_limit(self):
        pages = [self._make_page(f"https://example.com/page/{i}", f"Page {i}", "other", 5) for i in range(20)]
        selected = select_pages(pages, max_default=8, hard_max=8)
        assert len(selected) <= 8

    def test_hard_max_limit(self):
        pages = [self._make_page(f"https://example.com/page/{i}", f"Page {i}", "other", 5) for i in range(20)]
        selected = select_pages(pages, max_default=5, hard_max=7)
        assert len(selected) <= 7

    def test_empty_pages(self):
        assert select_pages([]) == []

    def test_single_page(self):
        pages = [self._make_page("https://example.com/about", "About", "about", 8)]
        selected = select_pages(pages, max_default=8)
        assert len(selected) == 1
        assert selected[0]["category"] == "about"
