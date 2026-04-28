"""Shared utilities for Customer Acquisition Skill scripts."""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print_error("python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

# Project root (auto-detected from script location)
PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = PROJECT_ROOT / ".env"


def load_env():
    """Load environment variables from .env file."""
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        print_error(f".env file not found at {ENV_FILE}")
        print_error("Copy .env.example to .env and fill in your API keys.")
        sys.exit(1)


def read_json(filepath):
    """Read and return JSON data from a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath, data):
    """Write JSON data to a file with pretty formatting."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def print_progress(phase, message):
    """Print structured progress message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{phase}] {message}", flush=True)


def print_error(message):
    """Print error message to stderr."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [ERROR] {message}", file=sys.stderr, flush=True)


def extract_domain(url):
    """Extract root domain from a URL for deduplication."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url


# Patterns for non-company URLs to filter out
BLOCKED_DOMAINS = {
    "facebook.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "youtube.com", "tiktok.com", "reddit.com",
    "wikipedia.org", "yelp.com", "tripadvisor.com", "amazon.com",
    "alibaba.com", "aliexpress.com", "made-in-china.com",
    "globalsources.com", "dhgate.com", "ebay.com",
    "crunchbase.com", "zoominfo.com", "bloomberg.com",
    "yellowpages.com", "hotfrog.com", "foursquare.com",
    "mapquest.com", "waze.com",
    "pinterest.com", "quora.com", "medium.com",
}

BLOCKED_PATH_PATTERNS = [
    r"/news/", r"/blog/", r"/article/", r"/press-release/",
    r"/wiki/", r"/forum/", r"/review/", r"/coupon/",
    r"/jobs/", r"/career/", r"/wikipedia",
]


def is_company_url(url):
    """Check if a URL is likely a company website (not a directory/B2B platform/social/news)."""
    url_lower = url.lower()
    domain = extract_domain(url)

    # Check blocked domains
    for blocked in BLOCKED_DOMAINS:
        if blocked in domain:
            return False

    # Check blocked path patterns
    for pattern in BLOCKED_PATH_PATTERNS:
        if re.search(pattern, url_lower):
            return False

    # Must have a real domain (not a file extension)
    if re.search(r"\.(pdf|jpg|jpeg|png|gif|svg|css|js|zip)(\?|$)", url_lower):
        return False

    return True


# ---------------------------------------------------------------------------
# Unified record schema — shared across all 4 phases
# Each phase fills its own fields; the rest stay as empty defaults.
# ---------------------------------------------------------------------------

RECORD_SCHEMA = {
    "company_name": "",          # Phase 1 (from title) → Phase 3 (AI confirmed)
    "website": "",               # Phase 1 (url)
    "country": "",               # Phase 3 (AI judgement)
    "industry": "",              # Phase 3 (AI keywords)
    "company_role": "",          # Phase 3 (AI judgement)
    "contact_name": "",          # Phase 3 (AI guess)
    "email": "",                 # Phase 2 (regex extract)
    "phone": "",                 # Phase 2 (regex extract)
    "ai_summary": "",            # Phase 3 (AI 7-section summary)
    "business_match_points": "", # Phase 3 (AI match analysis)
    "outreach_content": "",      # Phase 3 (AI outreach suggestion)
    "email_sent": False,         # Phase 4 (tracking)
    "sent_time": "",             # Phase 4 (tracking)
    "replied": False,            # Phase 4 (tracking)
    "reply_summary": "",         # Phase 4 (tracking)
    "notes": "",                 # Free-form notes
}


def create_empty_records(count):
    """Create *count* empty records based on RECORD_SCHEMA."""
    return [dict(RECORD_SCHEMA) for _ in range(count)]
