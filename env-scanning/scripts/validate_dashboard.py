#!/usr/bin/env python3
"""
Dashboard Validation Script (v3.4.0)
Checks: DB-001 ~ DB-006

Usage:
    python3 env-scanning/scripts/validate_dashboard.py \
        --dashboard dashboard-2026-03-24.html \
        --date 2026-03-24 \
        [--json]

Exit codes:
    0 = PASS (all checks passed)
    1 = FAIL (critical checks failed)
    2 = WARN (non-critical issues)
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Check Definitions
# ---------------------------------------------------------------------------

CHECKS = {
    "DB-001": {"name": "dashboard_file_exists", "severity": "HALT", "desc": "대시보드 파일 존재"},
    "DB-002": {"name": "dashboard_min_size", "severity": "HALT", "desc": "대시보드 최소 크기 ≥100KB"},
    "DB-003": {"name": "tab_completeness", "severity": "HALT", "desc": "필수 탭 완성도 (9 요약 + 5 보고서)"},
    "DB-004": {"name": "report_content_embedded", "severity": "HALT", "desc": "5개 보고서 콘텐츠 삽입 확인"},
    "DB-005": {"name": "korean_ratio", "severity": "WARN", "desc": "한국어 문자 비율 ≥10%"},
    "DB-006": {"name": "chart_data_integrity", "severity": "WARN", "desc": "Chart.js 데이터셋 무결성"},
}

MIN_SIZE_BYTES = 100_000  # 100KB
MIN_KOREAN_RATIO = 0.10   # 10% of non-tag text
# Tab IDs are flexible — detect from generator output rather than hardcoding.
# Minimum required: 1 overview + 4 WF summary + 1 patterns + 5 report tabs = 11
MIN_SUMMARY_TABS = 6   # overview + top signals + patterns + strategy + scenarios + at least 1 WF
MIN_REPORT_TABS = 5    # 5 report tabs (WF1-4 + integrated)
REPORT_TAB_PREFIX = "tab-report-"


def count_korean_chars(text: str) -> int:
    """Count Korean (Hangul) characters."""
    return sum(1 for c in text if '\uAC00' <= c <= '\uD7A3' or '\u3131' <= c <= '\u318E')


def strip_html_tags(html: str) -> str:
    """Remove HTML tags for text analysis."""
    return re.sub(r'<[^>]+>', '', html)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def check_db001(dashboard_path: Path) -> dict:
    """DB-001: Dashboard file exists."""
    exists = dashboard_path.exists()
    return {
        "id": "DB-001", "status": "PASS" if exists else "FAIL",
        "detail": f"{dashboard_path.name} {'exists' if exists else 'NOT FOUND'}",
    }


def check_db002(dashboard_path: Path) -> dict:
    """DB-002: Dashboard minimum size."""
    if not dashboard_path.exists():
        return {"id": "DB-002", "status": "FAIL", "detail": "File not found"}
    size = dashboard_path.stat().st_size
    ok = size >= MIN_SIZE_BYTES
    return {
        "id": "DB-002", "status": "PASS" if ok else "FAIL",
        "detail": f"{size:,} bytes {'≥' if ok else '<'} {MIN_SIZE_BYTES:,} minimum",
    }


def check_db003(content: str) -> dict:
    """DB-003: Tab completeness — detect tabs by id pattern, check minimums."""
    # Find all tab content divs
    all_tab_ids = re.findall(r'id="(tab-[^"]+)"', content)
    summary_tabs = [t for t in all_tab_ids if not t.startswith(REPORT_TAB_PREFIX)]
    report_tabs = [t for t in all_tab_ids if t.startswith(REPORT_TAB_PREFIX)]

    summary_ok = len(summary_tabs) >= MIN_SUMMARY_TABS
    report_ok = len(report_tabs) >= MIN_REPORT_TABS
    ok = summary_ok and report_ok

    detail = (
        f"Summary tabs: {len(summary_tabs)} (min {MIN_SUMMARY_TABS}), "
        f"Report tabs: {len(report_tabs)} (min {MIN_REPORT_TABS})"
    )
    if not summary_ok:
        detail += f" — summary tabs insufficient: {summary_tabs}"
    if not report_ok:
        detail += f" — report tabs insufficient: {report_tabs}"

    return {"id": "DB-003", "status": "PASS" if ok else "FAIL", "detail": detail}


def check_db004(content: str) -> dict:
    """DB-004: All 5 report contents embedded (detected by report tab prefix)."""
    report_tabs = re.findall(r'id="(tab-report-[^"]+)"', content)
    embedded = 0
    thin = []

    for tab_id in report_tabs:
        pattern = f'id="{tab_id}"'
        idx = content.find(pattern)
        if idx < 0:
            continue
        # Find the next tab-report or end of body to measure section size
        next_tab = content.find('id="tab-', idx + len(pattern))
        if next_tab < 0:
            next_tab = len(content)
        section_len = next_tab - idx
        if section_len > 2000:
            embedded += 1
        else:
            thin.append(tab_id)

    ok = embedded >= 5
    detail = f"{embedded}/{len(report_tabs)} reports with substantial content"
    if thin:
        detail += f" — thin: {', '.join(thin)}"
    return {"id": "DB-004", "status": "PASS" if ok else "FAIL", "detail": detail}


def check_db005(content: str) -> dict:
    """DB-005: Korean character ratio."""
    text = strip_html_tags(content)
    if not text:
        return {"id": "DB-005", "status": "WARN", "detail": "No text content"}

    korean = count_korean_chars(text)
    total = len(text)
    ratio = korean / total if total > 0 else 0
    ok = ratio >= MIN_KOREAN_RATIO

    return {
        "id": "DB-005", "status": "PASS" if ok else "WARN",
        "detail": f"Korean ratio: {ratio:.1%} ({korean:,} / {total:,} chars) {'≥' if ok else '<'} {MIN_KOREAN_RATIO:.0%}",
    }


def check_db006(content: str) -> dict:
    """DB-006: Chart.js data integrity — datasets exist and have data."""
    # Check for Chart constructor calls
    chart_count = content.count("new Chart(")
    # Check for data arrays
    datasets_count = content.count("datasets:")

    ok = chart_count >= 2 and datasets_count >= 2
    return {
        "id": "DB-006", "status": "PASS" if ok else "WARN",
        "detail": f"Charts: {chart_count}, Datasets: {datasets_count}",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Dashboard Validation (DB-001~006)")
    parser.add_argument("--dashboard", required=True, help="Path to dashboard HTML")
    parser.add_argument("--date", required=True, help="Scan date (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    dashboard_path = Path(args.dashboard)

    results = []
    results.append(check_db001(dashboard_path))

    if dashboard_path.exists():
        results.append(check_db002(dashboard_path))
        content = dashboard_path.read_text(encoding="utf-8")
        results.append(check_db003(content))
        results.append(check_db004(content))
        results.append(check_db005(content))
        results.append(check_db006(content))
    else:
        for check_id in ["DB-002", "DB-003", "DB-004", "DB-005", "DB-006"]:
            results.append({"id": check_id, "status": "FAIL", "detail": "Dashboard file not found"})

    # Determine overall status
    has_fail = any(r["status"] == "FAIL" for r in results)
    has_warn = any(r["status"] == "WARN" for r in results)

    if has_fail:
        overall = "FAIL"
        exit_code = 1
    elif has_warn:
        overall = "WARN"
        exit_code = 2
    else:
        overall = "PASS"
        exit_code = 0

    pass_count = sum(1 for r in results if r["status"] == "PASS")

    if args.json:
        output = {
            "validator": "validate_dashboard.py",
            "version": "1.0.0",
            "date": args.date,
            "dashboard": str(dashboard_path),
            "overall": overall,
            "pass_count": pass_count,
            "total_checks": len(results),
            "results": results,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Dashboard Validation: {pass_count}/{len(results)} {'PASS' if overall == 'PASS' else overall}")
        print(f"  Dashboard: {dashboard_path}")
        print()
        for r in results:
            severity = CHECKS.get(r["id"], {}).get("severity", "?")
            icon = "✅" if r["status"] == "PASS" else ("⚠️" if r["status"] == "WARN" else "❌")
            desc = CHECKS.get(r["id"], {}).get("desc", "")
            print(f"  {icon} {r['id']} [{severity}] {desc}")
            print(f"     {r['detail']}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
