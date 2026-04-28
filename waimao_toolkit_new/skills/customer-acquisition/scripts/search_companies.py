"""Phase 1: Search companies via Serper Google Search API."""

import argparse
import os
import sys
import time
import random
from pathlib import Path

# Add scripts dir to path for utils import
sys.path.insert(0, str(Path(__file__).parent))
from utils import load_env, write_json, print_progress, print_error, is_company_url, extract_domain, create_empty_records

try:
    import requests
except ImportError:
    print_error("requests not installed. Run: pip install requests")
    sys.exit(1)

SERPER_URL = "https://google.serper.dev/search"
RESULTS_PER_PAGE = 10


def generate_queries(industry, country, keywords_list):
    """Generate multiple search query combinations."""
    queries = []
    roles = keywords_list if keywords_list else ["company", "supplier"]

    for role in roles:
        # Pattern 1: industry + country + role
        queries.append(f'{industry} {role} in {country}')
        # Pattern 2: "top" modifier
        queries.append(f'top {industry} {role} {country}')
        # Pattern 3: "best" modifier
        queries.append(f'best {industry} {role} {country}')
        # Pattern 4: manufacturer/distributor specific
        for suffix in ["manufacturer", "distributor", "wholesaler", "supplier"]:
            if suffix not in role.lower():
                queries.append(f'{industry} {suffix} {country}')

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower not in seen:
            seen.add(q_lower)
            unique.append(q.strip())
    return unique


def serper_search(query, api_key, num_results=10):
    """Call Serper API and return organic results."""
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "num": num_results,
        "gl": "us",  # Default to US geolocation
        "hl": "en",
    }

    try:
        resp = requests.post(SERPER_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("organic", [])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401 or e.response.status_code == 403:
            print_error(f"Serper API authentication failed: {e}")
            print_error("Check your SERPER_API_KEY in .env file.")
            sys.exit(1)
        print_error(f"Serper API error for query '{query}': {e}")
        return []
    except requests.exceptions.RequestException as e:
        print_error(f"Network error for query '{query}': {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Phase 1: Search companies via Serper API")
    parser.add_argument("--industry", required=True, help="Target industry (e.g. 'LED', 'solar panel')")
    parser.add_argument("--country", required=True, help="Target country (e.g. 'USA', 'Germany')")
    parser.add_argument("--keywords", default="", help="Comma-separated role keywords (e.g. 'wholesale,distributor')")
    parser.add_argument("--num", type=int, default=30, help="Target number of companies")
    parser.add_argument("--output", default="search_results.json", help="Output JSON file path")
    args = parser.parse_args()

    load_env()

    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        print_error("SERPER_API_KEY not set in .env file.")
        sys.exit(1)

    keywords_list = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else []
    queries = generate_queries(args.industry, args.country, keywords_list)

    print_progress("SEARCH", f"Searching for {args.num} companies in {args.industry} ({args.country})")
    print_progress("SEARCH", f"Generated {len(queries)} search queries")

    companies = []
    seen_domains = set()
    queries_used = []
    start_time = time.time()

    for i, query in enumerate(queries):
        if len(companies) >= args.num:
            break

        print_progress("SEARCH", f"Query {i + 1}/{len(queries)}: {query}")
        results = serper_search(query, api_key, RESULTS_PER_PAGE)
        queries_used.append({"query": query, "results_found": len(results)})

        for result in results:
            if len(companies) >= args.num:
                break

            url = result.get("link", "")
            if not url or not is_company_url(url):
                continue

            domain = extract_domain(url)
            if domain in seen_domains:
                continue

            seen_domains.add(domain)
            record = create_empty_records(1)[0]
            record["company_name"] = result.get("title", "")
            record["website"] = url
            record["_domain"] = domain
            record["_snippet"] = result.get("snippet", "")
            record["_query"] = query
            companies.append(record)

        elapsed = time.time() - start_time
        eta = elapsed / (i + 1) * (len(queries) - i - 1) if i + 1 < len(queries) else 0
        print_progress("SEARCH", f"  Collected {len(companies)}/{args.num} companies | elapsed {elapsed:.0f}s, ETA {eta:.0f}s")

        # Rate limiting: delay between queries
        if i < len(queries) - 1 and len(companies) < args.num:
            delay = random.uniform(1.0, 2.5)
            time.sleep(delay)

    # Build output
    output = {
        "metadata": {
            "industry": args.industry,
            "country": args.country,
            "keywords": args.keywords,
            "target_count": args.num,
            "actual_count": len(companies),
            "queries_used": queries_used,
        },
        "companies": companies,
    }

    write_json(args.output, output)

    print_progress("SEARCH", f"Done. Found {len(companies)} companies, saved to {args.output}")
    if len(companies) < args.num:
        print_progress("SEARCH", f"WARNING: Only found {len(companies)}/{args.num} target companies")

    return output


if __name__ == "__main__":
    main()
