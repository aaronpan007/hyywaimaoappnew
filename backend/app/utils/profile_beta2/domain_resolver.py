"""Domain resolver: normalize URLs, try variants, determine access status."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 10  # seconds


@dataclass
class ResolvedDomain:
    domain: str  # bare domain (example.com)
    base_url: str  # first successfully accessed URL
    url_variants: list[str] = field(default_factory=list)
    access_status: str = "unknown"  # ok | timeout | ssl_error | 502 | blocked | unstable | no_content | unknown


def _bare_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = (parsed.hostname or parsed.netloc or "").lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain or ""
    except Exception:
        return ""


def _generate_variants(domain: str) -> list[str]:
    """Generate 4 URL variants to try."""
    return [
        f"https://{domain}",
        f"https://www.{domain}",
        f"http://{domain}",
        f"http://www.{domain}",
    ]


def _classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "ssl" in msg or "certificate" in msg:
        return "ssl_error"
    if any(code in msg for code in ("502", "503", "504")):
        return "502"
    if "403" in msg or "forbidden" in msg:
        return "blocked"
    return "unknown"


async def resolve_domain(url: str) -> ResolvedDomain:
    """Resolve domain: normalize URL, try variants, return first accessible one.

    Does not raise — returns ResolvedDomain with access_status on failure.
    """
    bare = _bare_domain(url)
    if not bare:
        return ResolvedDomain(domain="", base_url="", url_variants=[], access_status="unknown")

    variants = _generate_variants(bare)

    for variant in variants:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(connect=5.0, read=_TIMEOUT, write=5.0, pool=5.0),
                limits=httpx.Limits(max_connections=2),
                headers={"User-Agent": "Mozilla/5.0 (compatible; Bot/1.0)"},
            ) as client:
                resp = await client.get(variant)
                if resp.status_code >= 500:
                    return ResolvedDomain(
                        domain=bare,
                        base_url=variant,
                        url_variants=variants,
                        access_status="502" if resp.status_code in (502, 503, 504) else "blocked",
                    )
                if resp.status_code == 403:
                    return ResolvedDomain(
                        domain=bare, base_url=variant, url_variants=variants, access_status="blocked"
                    )
                if resp.status_code >= 400:
                    continue

                # Check for actual content (not just a redirect landing)
                content_length = len(resp.content or b"")
                if content_length < 100:
                    return ResolvedDomain(
                        domain=bare, base_url=variant, url_variants=variants, access_status="no_content"
                    )

                return ResolvedDomain(
                    domain=bare,
                    base_url=str(resp.url),
                    url_variants=variants,
                    access_status="ok",
                )
        except httpx.TimeoutException:
            logger.debug("Timeout reaching %s", variant)
            continue
        except Exception as exc:
            logger.debug("Error reaching %s: %s", variant, exc)
            continue

    # All variants failed — try HEAD as last resort
    for variant in variants[:2]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0),
                headers={"User-Agent": "Mozilla/5.0 (compatible; Bot/1.0)"},
            ) as client:
                resp = await client.head(variant, follow_redirects=True)
                if resp.status_code < 400:
                    return ResolvedDomain(
                        domain=bare,
                        base_url=str(resp.url),
                        url_variants=variants,
                        access_status="unstable",
                    )
        except Exception:
            continue

    return ResolvedDomain(
        domain=bare,
        base_url=variants[0],
        url_variants=variants,
        access_status="timeout",
    )
