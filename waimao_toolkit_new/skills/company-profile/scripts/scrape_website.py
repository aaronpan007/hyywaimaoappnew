"""
Company Website Scraper
Scrapes key pages from a company website for profile building.

Supports two modes:
  1. Browser mode (Playwright) — supports SPA/JS-rendered sites
  2. Fallback mode (requests + BeautifulSoup) — static HTML sites only

Usage:
    python scrape_website.py --url "https://example.com" --output "output.md"
    python scrape_website.py --url "https://example.com" --output "output.md" --pages "about,products,contact"
    python scrape_website.py --url "https://example.com" --output "output.md" --max-pages 10

Dependencies:
    Base:     pip install requests beautifulsoup4
    Enhanced: pip install playwright && python -m playwright install chromium
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

# --- Dependency detection ---
HAS_PLAYWRIGHT = False
HAS_REQUESTS = False
HAS_BS4 = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    pass

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    pass

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    pass


def print_dependency_status():
    """Print clear dependency status at startup."""
    print("=" * 55)
    print("[依赖状态]")
    if HAS_PLAYWRIGHT:
        print("  Playwright:      可用 -> 使用浏览器模式（支持 SPA）")
    else:
        print("  Playwright:      不可用 -> 降级到 requests 模式（仅静态页面）")
        print("                   安装方法: pip install playwright && python -m playwright install chromium")
    if HAS_REQUESTS and HAS_BS4:
        print("  requests+bs4:    可用 -> 降级模式可用")
    else:
        missing = []
        if not HAS_REQUESTS:
            missing.append("requests")
        if not HAS_BS4:
            missing.append("beautifulsoup4")
        print(f"  requests+bs4:    不可用 -> 请安装: pip install {' '.join(missing)}")
    print("=" * 55)

    if not HAS_PLAYWRIGHT and not (HAS_REQUESTS and HAS_BS4):
        print("ERROR: 没有可用的抓取依赖。请至少安装一组：")
        print("  基础: pip install requests beautifulsoup4")
        print("  增强: pip install playwright && python -m playwright install chromium")
        sys.exit(1)


# Keywords to identify important pages
PAGE_PATTERNS = {
    "about": [
        "about", "about-us", "company", "who-we-are", "our-story",
        "introduction", "profile", "corporate", "overview",
        "关于我们", "公司简介", "企业介绍", "关于", "公司概况"
    ],
    "products": [
        "products", "product", "services", "service", "solutions",
        "catalog", "catalogue", "portfolio", "what-we-do", "offerings",
        "产品", "产品中心", "服务", "解决方案", "业务范围", "产品展示"
    ],
    "cases": [
        "cases", "case-studies", "case-study", "projects", "project",
        "portfolio", "work", "clients", "testimonials", "success-stories",
        "project-gallery", "gallery", "applications", "application",
        "reference", "references", "installations", "installation",
        "customer-story", "customer-stories", "our-work", "special",
        "案例", "成功案例", "项目案例", "客户案例", "工程案例"
    ],
    "contact": [
        "contact", "contact-us", "get-in-touch", "reach-us",
        "联系我们", "联系方式", "联系"
    ],
    "certifications": [
        "certifications", "certificates", "quality", "compliance",
        "认证", "资质", "证书", "品质"
    ],
    "factory": [
        "factory", "facilities", "manufacturing", "production",
        "workshop", "plant", "tour",
        "工厂", "厂房", "生产线", "车间", "制造"
    ],
}

# Selectors to remove for text extraction
REMOVE_SELECTORS = [
    'script', 'style', 'nav', 'footer', 'header',
    'iframe', 'noscript', '.cookie-banner', '.popup',
    '.modal', '.chat-widget', '.sidebar',
    '[role="navigation"]', '[role="banner"]',
    '.advertisement', 'aside'
]


def clean_text(text: str) -> str:
    """Clean up extracted text."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
    return text.strip()


def find_relevant_links_from_html(soup, base_url: str) -> dict:
    """Find links to important pages from parsed HTML."""
    relevant = {}
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        text = (a_tag.get_text() or '').strip().lower()
        href_lower = href.lower()

        for category, keywords in PAGE_PATTERNS.items():
            if category in relevant:
                continue
            for kw in keywords:
                if kw in href_lower or kw in text:
                    full_url = urljoin(base_url, href)
                    if urlparse(full_url).netloc != urlparse(base_url).netloc:
                        continue
                    relevant[category] = full_url
                    break

    return relevant


def find_sub_links_from_html(soup, base_url: str, max_links: int) -> list:
    """Find sub-page links from product/case listing pages."""
    seen = set()
    unique_links = []
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if href in seen or href.startswith('javascript:'):
            continue
        full_url = urljoin(base_url, href)
        if urlparse(full_url).netloc != urlparse(base_url).netloc:
            continue
        if full_url.rstrip("/") != base_url.rstrip("/"):
            seen.add(href)
            unique_links.append(full_url)
            if len(unique_links) >= max_links:
                break
    return unique_links


def score_case_link(url: str) -> int:
    """Rank links that are more likely to be real case/project detail pages."""
    value = url.lower()
    strong = [
        "case", "project", "portfolio", "gallery", "application",
        "reference", "installation", "customer", "success", "special",
    ]
    weak = ["product", "solution", "service", "work"]
    score = 0
    for token in strong:
        if token in value:
            score += 3
    for token in weak:
        if token in value:
            score += 1
    if re.search(r"/\d{4}/|-\d+\.|_\d+\.", value):
        score += 1
    return score


def prioritize_case_links(links: list) -> list:
    """Put likely case/project detail pages first without dropping fallback links."""
    return sorted(links, key=lambda item: score_case_link(item), reverse=True)


# ============ Playwright mode ============

def extract_text_from_page(page, url: str) -> dict:
    """Extract visible text and metadata from a page using Playwright."""
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    title = page.title() or ""

    text_content = page.evaluate("""() => {
        const removeSelectors = """ + json.dumps(REMOVE_SELECTORS) + """;
        removeSelectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(el => el.remove());
        });
        const body = document.body;
        if (!body) return '';
        let text = body.innerText || body.textContent || '';
        text = text.replace(/\\n{3,}/g, '\\n\\n');
        text = text.replace(/[ \\t]+/g, ' ');
        text = text.split('\\n').map(line => line.trim()).filter(line => line).join('\\n');
        return text;
    }""")

    return {
        "url": url,
        "title": title,
        "text": clean_text(text_content),
    }


def find_relevant_links_pw(page, base_url: str) -> list:
    """Find links to important pages using Playwright."""
    links = page.evaluate("""() => {
        const anchors = Array.from(document.querySelectorAll('a[href]'));
        return anchors.map(a => ({
            href: a.href,
            text: (a.textContent || '').trim().toLowerCase()
        })).filter(a => a.href && !a.href.startsWith('javascript:'));
    }""")

    relevant = {}
    for link in links:
        href = link["href"]
        text = link["text"]
        href_lower = href.lower()

        for category, keywords in PAGE_PATTERNS.items():
            if category in relevant:
                continue
            for kw in keywords:
                if kw in href_lower or kw in text:
                    full_url = urljoin(base_url, href)
                    if urlparse(full_url).netloc != urlparse(base_url).netloc:
                        continue
                    relevant[category] = full_url
                    break

    return relevant


def find_sub_links_pw(page, base_url: str, max_links: int) -> list:
    """Find sub-page links from product/case listing pages using Playwright."""
    links = page.evaluate("""() => {
        const anchors = Array.from(document.querySelectorAll('a[href]'));
        return anchors
            .map(a => a.href)
            .filter(href => href && !href.startsWith('javascript:') && href !== window.location.href);
    }""")

    seen = set()
    unique_links = []
    for link in links:
        if link in seen:
            continue
        if urlparse(link).netloc != urlparse(base_url).netloc:
            continue
        if link.rstrip("/") != base_url.rstrip("/"):
            seen.add(link)
            unique_links.append(link)
            if len(unique_links) >= max_links:
                break
    return unique_links


def scrape_website_playwright(url: str, max_pages: int = 15, extra_pages: list = None) -> list:
    """Scrape using Playwright (browser mode)."""
    pages_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = context.new_page()

        print(f"\n[浏览器模式] 抓取首页: {url}")

        try:
            page.goto(url, timeout=30000)
            homepage_data = extract_text_from_page(page, url)
            pages_data.append({"category": "homepage", **homepage_data})
            print(f"    获取 {len(homepage_data['text'])} 字符")

            relevant_links = find_relevant_links_pw(page, url)
            print(f"    发现 {len(relevant_links)} 个关键页面: {list(relevant_links.keys())}")

            pages_scraped = 1
            for category, link_url in relevant_links.items():
                if pages_scraped >= max_pages:
                    print(f"    已达到页面上限 ({max_pages})")
                    break

                print(f"    抓取 {category}: {link_url}")
                try:
                    page.goto(link_url, timeout=20000)
                    page_data = extract_text_from_page(page, link_url)
                    pages_data.append({"category": category, **page_data})
                    pages_scraped += 1
                    print(f"    获取 {len(page_data['text'])} 字符")

                    if category in ("products", "cases") and pages_scraped < max_pages:
                        sub_links = find_sub_links_pw(page, link_url, max_pages - pages_scraped)
                        if category == "cases":
                            sub_links = prioritize_case_links(sub_links)
                            detail_limit = max_pages - pages_scraped
                        else:
                            detail_limit = min(3, max_pages - pages_scraped)
                        for sub_url in sub_links[:detail_limit]:
                            print(f"    抓取子页面: {sub_url}")
                            try:
                                page.goto(sub_url, timeout=15000)
                                sub_data = extract_text_from_page(page, sub_url)
                                pages_data.append({"category": f"{category}-detail", **sub_data})
                                pages_scraped += 1
                                print(f"    获取 {len(sub_data['text'])} 字符")
                            except Exception as e:
                                print(f"    失败: {e}")
                                pages_scraped += 1

                except Exception as e:
                    print(f"    失败: {e}")

            if extra_pages:
                for ep in extra_pages:
                    if pages_scraped >= max_pages:
                        break
                    full_url = urljoin(url, ep)
                    print(f"    抓取额外页面: {full_url}")
                    try:
                        page.goto(full_url, timeout=20000)
                        ep_data = extract_text_from_page(page, full_url)
                        pages_data.append({"category": "extra", **ep_data})
                        pages_scraped += 1
                        print(f"    获取 {len(ep_data['text'])} 字符")
                    except Exception as e:
                        print(f"    失败: {e}")

        except Exception as e:
            print(f"    首页抓取失败: {e}")

        browser.close()

    return pages_data


# ============ Requests + BeautifulSoup mode (fallback) ============

def extract_text_from_html(html: str, url: str) -> dict:
    """Extract visible text and metadata from HTML using BeautifulSoup."""
    soup = BeautifulSoup(html, 'html.parser')

    # Get title
    title_tag = soup.find('title')
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Remove unwanted elements
    for selector in REMOVE_SELECTORS:
        # Handle both tag names and CSS class selectors
        for el in soup.select(selector):
            el.decompose()

    body = soup.find('body')
    if not body:
        return {"url": url, "title": title, "text": ""}

    text = body.get_text(separator='\n', strip=True)
    text = clean_text(text)

    return {
        "url": url,
        "title": title,
        "text": text,
    }


def scrape_website_requests(url: str, max_pages: int = 15, extra_pages: list = None) -> list:
    """Scrape using requests + BeautifulSoup (fallback mode)."""
    pages_data = []
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    print(f"\n[requests模式] 抓取首页: {url}")

    # Scrape homepage
    try:
        resp = session.get(url, timeout=20)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        homepage_data = extract_text_from_html(resp.text, url)
        pages_data.append({"category": "homepage", **homepage_data})
        print(f"    获取 {len(homepage_data['text'])} 字符")

        # Find relevant sub-pages
        soup = BeautifulSoup(resp.text, 'html.parser')
        relevant_links = find_relevant_links_from_html(soup, url)
        print(f"    发现 {len(relevant_links)} 个关键页面: {list(relevant_links.keys())}")

        pages_scraped = 1
        for category, link_url in relevant_links.items():
            if pages_scraped >= max_pages:
                print(f"    已达到页面上限 ({max_pages})")
                break

            print(f"    抓取 {category}: {link_url}")
            try:
                resp2 = session.get(link_url, timeout=15)
                resp2.encoding = resp2.apparent_encoding or 'utf-8'
                page_data = extract_text_from_html(resp2.text, link_url)
                pages_data.append({"category": category, **page_data})
                pages_scraped += 1
                print(f"    获取 {len(page_data['text'])} 字符")

                # For products/cases pages, find sub-links
                if category in ("products", "cases") and pages_scraped < max_pages:
                    soup2 = BeautifulSoup(resp2.text, 'html.parser')
                    sub_links = find_sub_links_from_html(soup2, link_url, max_pages - pages_scraped)
                    if category == "cases":
                        sub_links = prioritize_case_links(sub_links)
                        detail_limit = max_pages - pages_scraped
                    else:
                        detail_limit = min(3, max_pages - pages_scraped)
                    for sub_url in sub_links[:detail_limit]:
                        print(f"    抓取子页面: {sub_url}")
                        try:
                            resp3 = session.get(sub_url, timeout=15)
                            resp3.encoding = resp3.apparent_encoding or 'utf-8'
                            sub_data = extract_text_from_html(resp3.text, sub_url)
                            pages_data.append({"category": f"{category}-detail", **sub_data})
                            pages_scraped += 1
                            print(f"    获取 {len(sub_data['text'])} 字符")
                        except Exception as e:
                            print(f"    失败: {e}")
                            pages_scraped += 1

            except Exception as e:
                print(f"    失败: {e}")

        # Scrape extra pages
        if extra_pages:
            for ep in extra_pages:
                if pages_scraped >= max_pages:
                    break
                full_url = urljoin(url, ep)
                print(f"    抓取额外页面: {full_url}")
                try:
                    resp_ep = session.get(full_url, timeout=15)
                    resp_ep.encoding = resp_ep.apparent_encoding or 'utf-8'
                    ep_data = extract_text_from_html(resp_ep.text, full_url)
                    pages_data.append({"category": "extra", **ep_data})
                    pages_scraped += 1
                    print(f"    获取 {len(ep_data['text'])} 字符")
                except Exception as e:
                    print(f"    失败: {e}")

    except Exception as e:
        print(f"    首页抓取失败: {e}")

    return pages_data


# ============ Output formatting ============

def format_as_markdown(pages_data: list) -> str:
    """Convert scraped data to a clean Markdown document."""
    md_lines = []
    md_lines.append("# Website Scraping Results")
    md_lines.append(f"Scraped {len(pages_data)} pages at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    md_lines.append("")

    for page_info in pages_data:
        category = page_info.get("category", "unknown")
        title = page_info.get("title", "Untitled")
        url = page_info.get("url", "")
        text = page_info.get("text", "")

        md_lines.append("---")
        md_lines.append(f"## [{category.upper()}] {title}")
        md_lines.append(f"Source: {url}")
        md_lines.append("")

        if text:
            if len(text) > 8000:
                text = text[:8000] + "\n\n[... truncated ...]"
            md_lines.append(text)
        else:
            md_lines.append("(No text content extracted)")
        md_lines.append("")

    return "\n".join(md_lines)


# ============ Main ============

def main():
    parser = argparse.ArgumentParser(description="Scrape company website for profile building")
    parser.add_argument("--url", required=True, help="Company website URL")
    parser.add_argument("--output", required=True, help="Output Markdown file path")
    parser.add_argument("--pages", default=None, help="Comma-separated list of page categories to scrape (about,products,cases,contact)")
    parser.add_argument("--max-pages", type=int, default=15, help="Maximum number of pages to scrape")
    parser.add_argument("--json", action="store_true", help="Also output raw JSON data")

    args = parser.parse_args()

    # Print dependency status
    print_dependency_status()

    # Normalize URL
    url = args.url.rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url

    print(f"\n[*] 开始抓取: {url}")

    # Choose scraping mode
    if HAS_PLAYWRIGHT:
        pages_data = scrape_website_playwright(url, max_pages=args.max_pages, extra_pages=args.pages.split(",") if args.pages else None)
    else:
        print("[*] 提示: Playwright 不可用，使用 requests 模式（无法抓取 SPA 页面）")
        pages_data = scrape_website_requests(url, max_pages=args.max_pages, extra_pages=args.pages.split(",") if args.pages else None)

    if not pages_data:
        print("[!] 没有成功抓取任何页面")
        sys.exit(1)

    # Format and save
    markdown = format_as_markdown(pages_data)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    print(f"\n[+] 抓取完成!")
    print(f"    页面数量: {len(pages_data)}")
    print(f"    总字符数: {sum(len(p['text']) for p in pages_data):,}")
    print(f"    输出文件: {output_path}")

    # Also save raw JSON if requested
    if args.json:
        json_path = output_path.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(pages_data, f, ensure_ascii=False, indent=2)
        print(f"    JSON: {json_path}")


if __name__ == "__main__":
    main()
