"""Tests for contact_extractor module."""

import pytest

from app.utils.profile_beta2.contact_extractor import (
    Contacts,
    extract_contacts,
    rank_emails,
)


class _FakePage:
    """Minimal fake page for testing."""
    def __init__(self, url="https://testcorp.com", title="", clean_text="", html="", base_url=None):
        self.url = url
        self.title = title
        self.clean_text = clean_text
        self.html = html
        self.base_url = base_url or url


class TestExtractEmails:
    def test_normal_emails(self):
        contacts = extract_contacts([
            _FakePage(clean_text="Contact us at sales@testcorp.com or info@testcorp.com"),
        ], "testcorp.com")
        assert "sales@testcorp.com" in contacts.emails
        assert "info@testcorp.com" in contacts.emails

    def test_filters_noreply(self):
        contacts = extract_contacts([
            _FakePage(clean_text="noreply@testcorp.com and sales@testcorp.com"),
        ], "testcorp.com")
        assert "noreply@testcorp.com" not in contacts.ranked_emails
        assert "sales@testcorp.com" in contacts.ranked_emails

    def test_filters_privacy(self):
        contacts = extract_contacts([
            _FakePage(clean_text="privacy@testcorp.com and export@testcorp.com"),
        ], "testcorp.com")
        assert "privacy@testcorp.com" not in contacts.ranked_emails


class TestRankEmails:
    def test_sales_first(self):
        emails = ["info@test.com", "sales@test.com", "admin@test.com"]
        ranked = rank_emails(emails, "test.com")
        assert ranked[0] == "sales@test.com"

    def test_export_higher_than_info(self):
        emails = ["info@test.com", "export@test.com"]
        ranked = rank_emails(emails, "test.com")
        assert ranked[0] == "export@test.com"

    def test_company_domain_boost(self):
        emails = ["sales@other.com", "info@testcorp.com"]
        ranked = rank_emails(emails, "testcorp.com")
        # Company domain should boost
        assert "info@testcorp.com" == ranked[0]

    def test_deduplication(self):
        emails = ["sales@test.com", "sales@test.com", "info@test.com"]
        ranked = rank_emails(emails, "test.com")
        assert len(ranked) == 2


class TestExtractSocial:
    def test_linkedin(self):
        contacts = extract_contacts([
            _FakePage(html='<a href="https://www.linkedin.com/company/testcorp">LinkedIn</a>'),
        ], "testcorp.com")
        assert "linkedin" in contacts.social_links

    def test_facebook(self):
        contacts = extract_contacts([
            _FakePage(html='<a href="https://www.facebook.com/testcorp">Facebook</a>'),
        ], "testcorp.com")
        assert "facebook" in contacts.social_links

    def test_excludes_share_links(self):
        contacts = extract_contacts([
            _FakePage(html='<a href="https://www.facebook.com/sharer/sharer.php?u=http://testcorp.com">Share</a>'),
        ], "testcorp.com")
        assert "facebook" not in contacts.social_links

    def test_multiple_socials(self):
        contacts = extract_contacts([
            _FakePage(html='<a href="https://www.linkedin.com/company/testcorp">LI</a>'
                       '<a href="https://www.youtube.com/@testcorp">YT</a>'
                       '<a href="https://www.facebook.com/testcorp">FB</a>'),
        ], "testcorp.com")
        assert "linkedin" in contacts.social_links
        assert "youtube" in contacts.social_links
        assert "facebook" in contacts.social_links


class TestExtractMessaging:
    def test_whatsapp(self):
        contacts = extract_contacts([
            _FakePage(clean_text="WhatsApp: +1 234 567 8900"),
        ], "testcorp.com")
        assert contacts.whatsapp != ""

    def test_wechat(self):
        contacts = extract_contacts([
            _FakePage(clean_text="WeChat: test_wechat_id"),
        ], "testcorp.com")
        assert contacts.wechat == "test_wechat_id"


class TestExtractPhones:
    def test_normal_phones(self):
        contacts = extract_contacts([
            _FakePage(clean_text="Call us at +1 (234) 567-8900"),
        ], "testcorp.com")
        assert len(contacts.phones) >= 1

    def test_multiple_phones_dedup(self):
        contacts = extract_contacts([
            _FakePage(clean_text="Phone: +1 234 567 8900 and also +1 234 567 8900"),
        ], "testcorp.com")
        # Should deduplicate same-digit phones
        assert len(contacts.phones) == 1
