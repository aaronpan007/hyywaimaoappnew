"""Email Craft — CSV I/O wrappers.

Provides CSV read/write functions specific to email-craft's needs,
building on the shared csv_utils module.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Import shared csv_utils
_SHARED_DIR = Path(__file__).resolve().parents[2] / "_shared"
sys.path.insert(0, str(_SHARED_DIR))
from csv_utils import read_pipeline_csv, read_all_pipeline_csv, write_pipeline_csv  # noqa: E402


def read_csv_records(csv_path: str, skip_with_draft: bool = True) -> list[dict]:
    """Read customer records from pipeline CSV for email generation.

    Sets ``_record_id = str(_row_index)`` for compatibility with
    generate_emails.py (which uses _record_id to identify records).

    Args:
        csv_path: Path to CSV file.
        skip_with_draft: If True, skip rows with existing email_draft.

    Returns:
        List of dicts with English keys + ``_record_id`` + ``_row_index``.
    """
    records = read_pipeline_csv(csv_path, skip_with_draft=skip_with_draft)
    for r in records:
        r["_record_id"] = str(r["_row_index"])
    return records


def write_csv_emails(csv_path: str, results: list[dict], dry_run: bool = False) -> int:
    """Merge generated emails back into the pipeline CSV.

    For each successful result, writes email_subject and email_draft
    to the corresponding row (matched by record_id → row_index).

    Args:
        csv_path: Path to CSV file.
        results: Output from generate_emails().
        dry_run: If True, don't write anything.

    Returns:
        Number of rows written.
    """
    if dry_run:
        return 0

    csv_path_p = Path(csv_path)
    if not csv_path_p.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        return 0

    # Read all existing rows
    all_records = read_all_pipeline_csv(csv_path)
    row_map = {r["_row_index"]: r for r in all_records}

    # Merge results into existing records
    written = 0
    for result in results:
        if not result.get("success"):
            continue
        record_id = result.get("record_id", "")
        try:
            row_index = int(record_id)
        except (ValueError, TypeError):
            continue

        if row_index in row_map:
            row_map[row_index]["email_subject"] = result.get("email_subject", "")
            row_map[row_index]["email_draft"] = result.get("email_body", "")
            written += 1

    if written > 0:
        write_pipeline_csv(csv_path, all_records)

    return written


def print_csv_records_table(records: list[dict]) -> None:
    """Print a formatted table of customer records for selection.

    Shows: #, company_name, country, industry, email, has_draft
    """
    if not records:
        print("No customer records found.")
        return

    # Column widths
    col_w = [4, 25, 15, 20, 30, 8]
    header = f"{'#':<4} {'公司名称':<25} {'国家/地区':<15} {'行业':<20} {'邮箱':<30} {'开发信':<8}"
    sep = "-" * len(header.encode("gbk", errors="replace"))

    print()
    print(header)
    print(sep)
    for r in records:
        idx = r.get("_row_index", 0)
        company = (r.get("company_name", "") or "")[:24]
        country = (r.get("country", "") or "")[:14]
        industry = (r.get("industry", "") or "")[:19]
        email = (r.get("email", "") or "")[:29]
        draft = "有" if r.get("email_draft", "").strip() else "-"
        print(f"{idx:<4} {company:<25} {country:<15} {industry:<20} {email:<30} {draft:<8}")
    print(sep)
    print(f"共 {len(records)} 条记录\n")
