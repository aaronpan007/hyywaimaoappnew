"""Tests for completeness module."""

import pytest

from app.utils.profile_beta2.completeness import calculate_completeness


def _full_profile() -> dict:
    return {
        "company_name": "Test Company Inc.",
        "industry": "Manufacturing",
        "products": [{"name": "Widget A"}, {"name": "Widget B"}],
        "cooperation_models": [{"model": "OEM"}],
        "target_customer_types": [{"type": "Distributors"}],
        "core_competencies": [{"competency": "Quality"}],
        "unique_selling_points": ["Fast delivery"],
        "case_studies": [
            {"project": "Project Alpha", "country": "USA", "products_used": ["Widget A"]},
            {"project": "Project Beta", "country": "UK", "products_used": ["Widget B"]},
            {"project": "Project Gamma", "country": "Germany", "products_used": ["Widget A"]},
        ],
        "certifications": ["ISO 9001", "CE"],
        "location": "123 Main St, City, Country",
        "metadata": {"source_documents": ["catalog.pdf"]},
    }


class TestCalculateCompleteness:
    def test_full_profile_high_score(self):
        profile = _full_profile()
        result = calculate_completeness(profile)
        assert result.score >= 80
        assert len(result.missing_items) <= 2

    def test_empty_profile(self):
        result = calculate_completeness({})
        assert result.score == 0
        assert len(result.missing_items) >= 8

    def test_partial_profile(self):
        profile = {
            "company_name": "Test Corp",
            "products": [{"name": "Product 1"}],
        }
        result = calculate_completeness(profile)
        assert 0 < result.score < 50
        assert "company_name" not in result.missing_items
        assert "main_products" not in result.missing_items
        assert "industry" in result.missing_items

    def test_breakdown_all_present(self):
        profile = _full_profile()
        result = calculate_completeness(profile)
        assert "company_name" in result.breakdown
        assert "industry" in result.breakdown
        assert "main_products" in result.breakdown
        assert result.breakdown["company_name"] == 10

    def test_missing_name(self):
        profile = _full_profile()
        profile["company_name"] = ""
        result = calculate_completeness(profile)
        assert result.score < 100
        assert "company_name" in result.missing_items
        assert result.breakdown["company_name"] == 0

    def test_missing_industry(self):
        profile = _full_profile()
        profile["industry"] = ""
        result = calculate_completeness(profile)
        assert "industry" in result.missing_items
        assert result.breakdown["industry"] == 0

    def test_missing_products(self):
        profile = _full_profile()
        profile["products"] = []
        result = calculate_completeness(profile)
        assert "main_products" in result.missing_items
        assert result.breakdown["main_products"] == 0

    def test_few_case_studies_partial_score(self):
        profile = _full_profile()
        profile["case_studies"] = [{"project": "One project"}]
        result = calculate_completeness(profile)
        # Should get partial score, not full
        assert 0 < result.breakdown["case_studies"] < 10

    def test_no_case_studies(self):
        profile = _full_profile()
        profile["case_studies"] = []
        result = calculate_completeness(profile)
        assert result.breakdown["case_studies"] == 0
        assert any("case_studies" in item for item in result.missing_items)

    def test_contacts_from_location(self):
        profile = _full_profile()
        profile["location"] = "123 Business Ave, City"
        result = calculate_completeness(profile)
        assert "contacts" not in result.missing_items

    def test_no_contacts(self):
        profile = _full_profile()
        profile["location"] = ""
        del profile["location"]
        result = calculate_completeness(profile)
        assert "contacts" in result.missing_items

    def test_downloads_from_metadata(self):
        profile = _full_profile()
        profile["metadata"] = {"source_documents": ["brochure.pdf"]}
        result = calculate_completeness(profile)
        assert "downloads" not in result.missing_items

    def test_no_downloads(self):
        profile = _full_profile()
        profile["metadata"] = {}
        result = calculate_completeness(profile)
        assert "downloads" in result.missing_items

    def test_max_score_100(self):
        profile = _full_profile()
        result = calculate_completeness(profile)
        assert result.score <= 100
