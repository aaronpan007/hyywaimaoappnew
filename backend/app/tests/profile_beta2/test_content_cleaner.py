"""Tests for content_cleaner module."""

import pytest

from app.utils.profile_beta2.content_cleaner import clean_content


class TestCleanContent:
    def test_basic_html(self):
        html = """
        <html>
        <head><title>Test Company</title></head>
        <body>
            <h1>Welcome to Test Company</h1>
            <p>We make great products.</p>
            <p>Contact us at info@test.com</p>
        </body>
        </html>
        """
        result = clean_content(html)
        assert result.title == "Test Company"
        assert "Welcome to Test Company" in result.clean_text
        assert "great products" in result.clean_text

    def test_removes_nav(self):
        html = """
        <html><body>
            <nav>
                <a href="/home">Home</a>
                <a href="/about">About</a>
                <a href="/products">Products</a>
            </nav>
            <h1>Main Content</h1>
            <p>This is the actual content.</p>
        </body></html>
        """
        result = clean_content(html)
        assert "Main Content" in result.clean_text
        assert "actual content" in result.clean_text

    def test_removes_script_and_style(self):
        html = """
        <html><body>
            <script>alert('hello')</script>
            <style>body { color: red; }</style>
            <h1>Real Title</h1>
            <p>Real paragraph.</p>
        </body></html>
        """
        result = clean_content(html)
        assert "alert" not in result.clean_text
        assert "color: red" not in result.clean_text
        assert "Real Title" in result.clean_text

    def test_removes_footer(self):
        html = """
        <html><body>
            <h1>Page Content</h1>
            <p>Important text here.</p>
            <footer>
                <p>Copyright 2024. All rights reserved.</p>
                <p>Privacy Policy | Terms of Service</p>
            </footer>
        </body></html>
        """
        result = clean_content(html)
        assert "Page Content" in result.clean_text
        assert "Important text" in result.clean_text

    def test_extracts_headings(self):
        html = """
        <html><body>
            <h1>Main Title</h1>
            <h2>Section One</h2>
            <p>Content for section one.</p>
            <h2>Section Two</h2>
            <p>Content for section two.</p>
        </body></html>
        """
        result = clean_content(html)
        assert "Main Title" in result.headings
        assert "Section One" in result.headings
        assert "Section Two" in result.headings
        assert len(result.headings) == 3

    def test_extracts_meta_description(self):
        html = """
        <html><head>
            <title>Test</title>
            <meta name="description" content="This is a test company description.">
        </head><body><p>Content</p></body></html>
        """
        result = clean_content(html)
        assert result.meta_description == "This is a test company description."

    def test_removes_cookie_banner(self):
        html = """
        <html><body>
            <div class="cookie-banner">We use cookies to improve your experience.</div>
            <h1>Real Heading</h1>
            <p>Real content.</p>
        </body></html>
        """
        result = clean_content(html)
        assert "Real Heading" in result.clean_text
        assert "cookies" not in result.clean_text.lower()

    def test_removes_modal_overlay(self):
        html = """
        <html><body>
            <div class="newsletter-modal">Subscribe to our newsletter!</div>
            <h1>Page Title</h1>
            <p>Page content.</p>
        </body></html>
        """
        result = clean_content(html)
        assert "newsletter" not in result.clean_text.lower()

    def test_empty_html(self):
        result = clean_content("")
        assert result.title == ""
        assert result.clean_text == ""
        assert result.headings == []

    def test_invalid_html(self):
        result = clean_content("<<<not html>>>")
        assert result.clean_text != ""

    def test_none_html(self):
        result = clean_content(None)
        assert result.title == ""
        assert result.clean_text == ""
