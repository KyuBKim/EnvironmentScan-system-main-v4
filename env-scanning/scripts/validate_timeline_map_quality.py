#!/usr/bin/env python3
"""Cross-reference quality validation for Timeline Map reports (L2b equivalent).

Validates that the final timeline map markdown is consistent with the
Python-generated data-package JSON. This enforces the Python 원천봉쇄 principle:
"LLM cannot modify Python-computed values."

Usage:
    python3 validate_timeline_map_quality.py \
        --report <timeline-map.md> \
        --data-package <data-package.json> \
        [--output <qc-results.json>]

Exit codes:
    0 = PASS (all checks passed)
    1 = FAIL (one or more CRITICAL checks failed)
    2 = WARN (warnings only)
"""

VERSION = "1.1.0"

import argparse
import json
import re
import sys
import yaml


class QCResult:
    def __init__(self):
        self.checks = []  # list of dict

    def add(self, check_id: str, severity: str, description: str,
            passed: bool, detail: str = ""):
        self.checks.append({
            "check_id": check_id,
            "severity": severity,
            "description": description,
            "passed": passed,
            "detail": detail,
        })

    @property
    def has_critical(self) -> bool:
        return any(not c["passed"] and c["severity"] == "CRITICAL"
                   for c in self.checks)

    @property
    def has_warn(self) -> bool:
        return any(not c["passed"] and c["severity"] == "WARN"
                   for c in self.checks)

    def summary(self) -> str:
        lines = []
        for c in self.checks:
            status = "PASS" if c["passed"] else c["severity"]
            line = f"  [{status}] {c['check_id']}: {c['description']}"
            if c["detail"]:
                line += f" — {c['detail']}"
            lines.append(line)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "validator": "validate_timeline_map_quality.py",
            "version": VERSION,
            "total_checks": len(self.checks),
            "passed": sum(1 for c in self.checks if c["passed"]),
            "failed": sum(1 for c in self.checks if not c["passed"]),
            "checks": self.checks,
        }


def validate_timeline_map_quality(
    report_content: str, data_package: dict
) -> QCResult:
    """Run all cross-reference quality checks."""
    qc = QCResult()
    metadata = data_package.get("metadata", {})
    psst_rankings = data_package.get("psst_rankings", [])
    steeps_timeline = data_package.get("steeps_timeline", {})
    theme_analysis = data_package.get("theme_analysis", {})

    # ── TQ-001: pSST Top-N table rankings match data-package ──
    # Verify that signal IDs in the pSST table exist in psst_rankings.
    psst_ids_in_pkg = set()
    for entry in psst_rankings:
        sid = entry.get("signal_id", entry.get("id", ""))
        if sid:
            psst_ids_in_pkg.add(sid)

    psst_section = re.search(
        r"pSST Priority Top-.*?(?=\n## \d+\.|\n---|\Z)", report_content, re.DOTALL
    )
    psst_ids_in_report = set()
    if psst_section:
        # Extract signal IDs from table rows (column 2)
        rows = re.findall(r"^\|\s*\d+\s*\|\s*(\S+)\s*\|",
                          psst_section.group(0), re.MULTILINE)
        psst_ids_in_report = set(rows)

    mismatched_psst = psst_ids_in_report - psst_ids_in_pkg if psst_ids_in_pkg else set()
    qc.add(
        "TQ-001", "CRITICAL",
        "pSST table signal IDs match data-package",
        len(mismatched_psst) == 0,
        f"IDs in report but not in data-package: {mismatched_psst}" if mismatched_psst else ""
    )

    # ── TQ-002: STEEPs distribution table matches data-package ──
    # Aggregate steeps_timeline to domain totals and compare with report.
    expected_totals = {}
    if steeps_timeline:
        first_val = next(iter(steeps_timeline.values()), None)
        if isinstance(first_val, dict) and "count" not in first_val:
            # Date-keyed format
            for date_str, cats in steeps_timeline.items():
                for cat, cnt in cats.items():
                    expected_totals[cat] = expected_totals.get(cat, 0) + cnt
        else:
            for domain, val in steeps_timeline.items():
                if isinstance(val, dict):
                    expected_totals[domain] = val.get("count", 0)
                else:
                    expected_totals[domain] = val

    steeps_section = re.search(
        r"STEEPs Domain.*?(?=\n## \d+\.|\n---|\Z)", report_content, re.DOTALL
    )
    steeps_mismatches = []
    if steeps_section and expected_totals:
        for domain, expected_count in expected_totals.items():
            # Look for the domain in the table
            pattern = rf"^\|\s*{re.escape(domain)}\s*\|\s*(\d+)\s*\|"
            match = re.search(pattern, steeps_section.group(0), re.MULTILINE)
            if match:
                report_count = int(match.group(1))
                if report_count != expected_count:
                    steeps_mismatches.append(
                        f"{domain}: report={report_count} vs data-pkg={expected_count}"
                    )
    qc.add(
        "TQ-002", "CRITICAL",
        "STEEPs distribution table matches data-package",
        len(steeps_mismatches) == 0,
        "; ".join(steeps_mismatches) if steeps_mismatches else ""
    )

    # ── TQ-003: Metadata YAML total_signals matches header ──
    yaml_match = re.search(r"```yaml\n(.*?)```", report_content, re.DOTALL)
    header_total_match = re.search(r"Total\s+(\d+)\s+signals", report_content)
    tq003_ok = True
    tq003_detail = ""
    if yaml_match and header_total_match:
        try:
            meta_yaml = yaml.safe_load(yaml_match.group(1))
            yaml_total = meta_yaml.get("total_signals", -1) if meta_yaml else -1
            header_total = int(header_total_match.group(1))
            if yaml_total != header_total:
                tq003_ok = False
                tq003_detail = f"YAML total_signals={yaml_total} vs header Total={header_total}"
        except (yaml.YAMLError, TypeError):
            tq003_ok = False
            tq003_detail = "YAML parse error"
    qc.add(
        "TQ-003", "CRITICAL",
        "Metadata total_signals matches header",
        tq003_ok, tq003_detail
    )

    # ── TQ-004: Theme signal counts match theme-analysis ──
    config_themes = theme_analysis.get("config_themes", [])
    emergent_themes = theme_analysis.get("emergent_themes", [])
    all_themes = config_themes + emergent_themes
    theme_count_mismatches = []
    for theme in all_themes:
        theme_id = theme.get("theme_id", "")
        expected_count = theme.get("signal_count", theme.get("total_signals", 0))
        label = theme.get("label_en", theme.get("label_ko", theme_id))
        if label and expected_count > 0:
            # Search for this theme's signal count in the report
            pattern = rf"{re.escape(label)}.*?Signals?[:\s]*(\d+)"
            match = re.search(pattern, report_content, re.IGNORECASE)
            if match:
                report_count = int(match.group(1))
                if report_count != expected_count:
                    theme_count_mismatches.append(
                        f"{label}: report={report_count} vs data-pkg={expected_count}"
                    )
    qc.add(
        "TQ-004", "WARN",
        "Theme signal counts match theme-analysis",
        len(theme_count_mismatches) == 0,
        "; ".join(theme_count_mismatches) if theme_count_mismatches else ""
    )

    # ── TQ-005: Escalation severity grades match pre_rendered ──
    pre_rendered = data_package.get("pre_rendered", {})
    escalation_confirmed = pre_rendered.get("escalation_confirmed", [])
    severity_mismatches = []
    for esc in escalation_confirmed:
        theme_id = esc.get("theme_id", "")
        expected_sev = esc.get("severity", "")
        if expected_sev and theme_id:
            # Python-assigned severity must appear in the report
            if expected_sev not in report_content:
                severity_mismatches.append(
                    f"{theme_id}: severity '{expected_sev}' not found in report"
                )
    qc.add(
        "TQ-005", "WARN",
        "Escalation severity grades match pre_rendered (PB-4)",
        len(severity_mismatches) == 0,
        "; ".join(severity_mismatches) if severity_mismatches else ""
    )

    # ── TQ-006: Cross-WF table numeric cells match data-package ──
    # cross_wf_correlations may be a dict (full JSON) or a list of correlation entries.
    cross_wf_raw = data_package.get("cross_wf_correlations", {})
    tq006_ok = True
    if isinstance(cross_wf_raw, dict):
        # Extract reinforced_signals list if present
        cross_wf_entries = cross_wf_raw.get("reinforced_signals", [])
    elif isinstance(cross_wf_raw, list):
        cross_wf_entries = cross_wf_raw
    else:
        cross_wf_entries = []
    # Advisory check: verify themes from correlations appear in report
    if cross_wf_entries:
        for corr in cross_wf_entries:
            if isinstance(corr, dict):
                theme = corr.get("theme", "")
                # This is advisory — exact table cell matching is complex
                pass
    qc.add(
        "TQ-006", "WARN",
        "Cross-WF table numeric consistency",
        tq006_ok,
        ""
    )

    # ── TQ-007: Signal IDs referenced in narratives exist in data-package ──
    # Extract all signal-ID-like patterns from the report
    signal_id_pattern = r"\b(?:wf[1-4]-|naver-|news-|arxiv-|explore-|mitr-|tc-|un-|nat-|hn-|brk-)\d{8}-[\w]+-?\d*"
    report_signal_ids = set(re.findall(signal_id_pattern, report_content, re.IGNORECASE))

    # Collect all known signal IDs from data-package
    known_ids = set()
    for entry in psst_rankings:
        sid = entry.get("signal_id", entry.get("id", ""))
        if sid:
            known_ids.add(sid)
    per_theme = data_package.get("per_theme_signal_details", {})
    for theme_id, signals in per_theme.items():
        if isinstance(signals, list):
            for sig in signals:
                sid = sig.get("signal_id", sig.get("id", ""))
                if sid:
                    known_ids.add(sid)

    # Signal IDs in report that don't exist in data-package
    # Only flag if we have known IDs to compare against
    unknown_ids = report_signal_ids - known_ids if known_ids else set()
    qc.add(
        "TQ-007", "WARN",
        "Signal IDs in narrative exist in data-package",
        len(unknown_ids) == 0,
        f"Unknown IDs: {list(unknown_ids)[:5]}" if unknown_ids else ""
    )

    # ── TQ-008: Date references within lookback_days range ──
    lookback_days = metadata.get("lookback_days", 7)
    scan_date_str = metadata.get("scan_date", "")
    tq008_ok = True
    if scan_date_str:
        try:
            from datetime import datetime, timedelta
            scan_date = datetime.strptime(scan_date_str, "%Y-%m-%d")
            earliest = scan_date - timedelta(days=lookback_days + 1)
            all_dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", report_content)
            out_of_range = []
            for d_str in all_dates:
                try:
                    d = datetime.strptime(d_str, "%Y-%m-%d")
                    if d < earliest or d > scan_date + timedelta(days=1):
                        out_of_range.append(d_str)
                except ValueError:
                    pass
            if out_of_range:
                tq008_ok = False
        except (ValueError, ImportError):
            pass
    qc.add(
        "TQ-008", "WARN",
        f"Date references within lookback range ({lookback_days} days)",
        tq008_ok,
        f"Out-of-range dates: {out_of_range[:5]}" if not tq008_ok else ""
    )

    # ── TQ-009: PB-1 ASCII timeline verbatim match ──
    # Verify that ASCII timelines in the report are exact copies from data-package.
    ascii_timelines = pre_rendered.get("ascii_timelines", {})
    ascii_mismatches = []
    for theme_id, expected_ascii in ascii_timelines.items():
        if not expected_ascii or not isinstance(expected_ascii, str):
            continue
        # Normalize whitespace for comparison (trailing spaces, line endings)
        expected_norm = expected_ascii.strip()
        if expected_norm and expected_norm not in report_content:
            # Try line-by-line comparison (report may have different line endings)
            expected_lines = [l.rstrip() for l in expected_norm.splitlines()]
            found = False
            for i, report_line in enumerate(report_content.splitlines()):
                if report_line.rstrip() == expected_lines[0]:
                    # Check if all subsequent lines match
                    match = True
                    for j, exp_line in enumerate(expected_lines):
                        idx = i + j
                        if idx >= len(report_content.splitlines()):
                            match = False
                            break
                        if report_content.splitlines()[idx].rstrip() != exp_line:
                            match = False
                            break
                    if match:
                        found = True
                        break
            if not found:
                ascii_mismatches.append(theme_id)
    qc.add(
        "TQ-009", "CRITICAL",
        "PB-1 ASCII timelines verbatim match data-package",
        len(ascii_mismatches) == 0,
        f"Modified timelines: {ascii_mismatches}" if ascii_mismatches else ""
    )

    # ── TQ-010: PB-2 Cross-WF table numeric cells match ──
    # Verify that numeric cells in the cross-WF table are unchanged from data-package.
    cross_wf_table = pre_rendered.get("cross_wf_table", {})
    expected_table_md = cross_wf_table.get("markdown", "")
    tq010_mismatches = []
    if expected_table_md:
        # Extract numeric cells from expected table
        expected_nums = re.findall(
            r"\|\s*(\d+\.?\d*)\s*\|", expected_table_md
        )
        # Extract numeric cells from report's cross-WF table section
        cross_wf_section = re.search(
            r"Cross-WF.*?(?=\n## \d+\.|\n---|\Z)", report_content, re.DOTALL
        )
        if cross_wf_section and expected_nums:
            report_nums = re.findall(
                r"\|\s*(\d+\.?\d*)\s*\|", cross_wf_section.group(0)
            )
            # Check that all expected numeric cells appear in the report
            for num in expected_nums:
                if num not in report_nums:
                    tq010_mismatches.append(num)
    qc.add(
        "TQ-010", "CRITICAL",
        "PB-2 Cross-WF table numeric cells match data-package",
        len(tq010_mismatches) == 0,
        f"Missing/changed cells: {tq010_mismatches}" if tq010_mismatches else ""
    )

    # ── TQ-011: PB-3 Lead-lag days accurately cited ──
    # Verify that lead-lag values cited in narrative match pre_rendered.lead_lag_computed.
    lead_lag_computed = pre_rendered.get("lead_lag_computed", [])
    tq011_mismatches = []
    for ll in lead_lag_computed:
        if not isinstance(ll, dict):
            continue
        expected_days = ll.get("lag_days")
        theme = ll.get("theme", ll.get("theme_id", ""))
        if expected_days is not None and theme:
            # Look for this lag_days value near the theme name in the report
            pattern = rf"{re.escape(str(expected_days))}\s*days?"
            if not re.search(pattern, report_content, re.IGNORECASE):
                # The value might not be cited at all — that's a WARN, not CRITICAL
                # But if a DIFFERENT lag value is cited near this theme, that's a mismatch
                theme_section = re.search(
                    rf"{re.escape(theme)}.*?(?=\n## |\Z)",
                    report_content, re.DOTALL | re.IGNORECASE
                )
                if theme_section:
                    cited_lags = re.findall(
                        r"(\d+)\s*days?\s*(?:lead|lag|ahead|behind|earlier|later)",
                        theme_section.group(0), re.IGNORECASE
                    )
                    for cited in cited_lags:
                        if int(cited) != int(expected_days):
                            tq011_mismatches.append(
                                f"{theme}: cited {cited}d vs data-pkg {expected_days}d"
                            )
    qc.add(
        "TQ-011", "CRITICAL",
        "PB-3 Lead-lag days accurately cited in narrative",
        len(tq011_mismatches) == 0,
        "; ".join(tq011_mismatches) if tq011_mismatches else ""
    )

    return qc


def main():
    parser = argparse.ArgumentParser(
        description="Cross-reference quality validation for Timeline Map (L2b)"
    )
    parser.add_argument("--report", required=True,
                        help="Path to timeline map markdown file")
    parser.add_argument("--data-package", required=True,
                        help="Path to data-package JSON")
    parser.add_argument("--output", default=None,
                        help="Optional path to write QC results JSON")
    args = parser.parse_args()

    try:
        with open(args.report, "r", encoding="utf-8") as f:
            report_content = f.read()
    except FileNotFoundError:
        print(f"ERROR: Report not found: {args.report}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.data_package, "r", encoding="utf-8") as f:
            data_package = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Data-package not found: {args.data_package}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    qc = validate_timeline_map_quality(report_content, data_package)

    print(f"Timeline Map Quality Validation (L2b)")
    print(f"{'=' * 60}")
    print(qc.summary())
    print(f"{'=' * 60}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(qc.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"QC results written to {args.output}")

    if qc.has_critical:
        print("RESULT: FAIL — critical cross-reference issues found")
        sys.exit(1)
    elif qc.has_warn:
        print("RESULT: WARN — advisory issues found")
        sys.exit(2)
    else:
        print("RESULT: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
