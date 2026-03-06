#!/usr/bin/env python3
"""Validate generated Timeline Map reports.

Usage:
    python3 validate_timeline_map.py --input <file.md> --profile timeline

Exit codes:
    0 = PASS
    1 = CRITICAL (must fix before proceeding)
    2 = WARN (advisory, non-blocking)
"""

VERSION = "1.1.0"

import argparse
import re
import sys
import yaml


# ---------------------------------------------------------------------------
# Required sections — TL-001
# ---------------------------------------------------------------------------
REQUIRED_SECTIONS_EN = [
    "Timeline Overview",
    "Theme-Based Temporal Tracking",
    "STEEPs Domain Temporal Distribution",
    "pSST Priority Top-",
    "Cross-Workflow Signal Trajectory",
    "Escalation Monitoring",
    "Metadata",
]

REQUIRED_SECTIONS_KO = [
    "타임라인 개관",
    "핵심 테마별 시간축 추적",
    "STEEPs 영역별 시간축 분포",
    "pSST 우선순위 Top-",
    "교차 워크플로우 시그널 궤적",
    "에스컬레이션 모니터링",
    "메타데이터",
]

MIN_WORD_COUNT = 3000
MIN_THEME_SECTIONS = 3
MIN_PSST_ROWS = 5
MIN_STRATEGIC_ITEMS = 3


class ValidationResult:
    def __init__(self):
        self.results = []  # list of (rule_id, severity, message, passed)

    def add(self, rule_id: str, severity: str, message: str, passed: bool):
        self.results.append((rule_id, severity, message, passed))

    @property
    def has_critical(self) -> bool:
        return any(not passed and sev == "CRITICAL" for _, sev, _, passed in self.results)

    @property
    def has_warn(self) -> bool:
        return any(not passed and sev == "WARN" for _, sev, _, passed in self.results)

    def summary(self) -> str:
        lines = []
        for rule_id, severity, message, passed in self.results:
            status = "PASS" if passed else severity
            lines.append(f"  [{status}] {rule_id}: {message}")
        return "\n".join(lines)


def _detect_language(content: str) -> str:
    """Detect if content is Korean or English based on section headers."""
    if "타임라인 개관" in content or "핵심 테마별" in content:
        return "ko"
    return "en"


def _get_required_sections(lang: str) -> list:
    return REQUIRED_SECTIONS_KO if lang == "ko" else REQUIRED_SECTIONS_EN


def validate_timeline_map(content: str, profile: str = "timeline") -> ValidationResult:
    """Run all validation rules on the timeline map content.

    profile='prefilled': LLM-dependent checks (TL-003,004,005,007,010,013)
    are downgraded to INFO (always pass) since LLM hasn't filled them yet.
    """
    result = ValidationResult()
    lang = _detect_language(content)
    # In prefilled mode, LLM-dependent checks are skipped (always pass)
    is_prefilled = (profile == "prefilled")
    required_sections = _get_required_sections(lang)

    # TL-001: 7 required sections exist
    missing_sections = []
    for section in required_sections:
        if section not in content:
            missing_sections.append(section)
    result.add(
        "TL-001", "CRITICAL",
        f"Required sections: {7 - len(missing_sections)}/7 present"
        + (f" (missing: {', '.join(missing_sections)})" if missing_sections else ""),
        len(missing_sections) == 0
    )

    # TL-002: Metadata YAML block is parseable
    yaml_match = re.search(r"```yaml\n(.*?)```", content, re.DOTALL)
    yaml_ok = False
    if yaml_match:
        try:
            yaml.safe_load(yaml_match.group(1))
            yaml_ok = True
        except yaml.YAMLError:
            pass
    result.add(
        "TL-002", "CRITICAL",
        "Metadata YAML block" + (" parseable" if yaml_ok else " missing or invalid"),
        yaml_ok
    )

    # TL-003: No {{PLACEHOLDER}} tokens remain (skip in prefilled — LLM hasn't filled yet)
    placeholders = re.findall(r"\{\{[A-Z_]+\}\}", content)
    result.add(
        "TL-003", "CRITICAL",
        f"Unfilled placeholders: {len(placeholders)} found"
        + (f" ({', '.join(placeholders[:5])})" if placeholders else "")
        + (" [SKIPPED: prefilled]" if is_prefilled else ""),
        len(placeholders) == 0 or is_prefilled
    )

    # TL-004: Minimum word count >= 3000 (skip in prefilled)
    word_count = len(content.split())
    result.add(
        "TL-004", "CRITICAL",
        f"Word count: {word_count} (min {MIN_WORD_COUNT})"
        + (" [SKIPPED: prefilled]" if is_prefilled else ""),
        word_count >= MIN_WORD_COUNT or is_prefilled
    )

    # TL-005: At least 3 theme sections
    # Theme sections are typically ### level headers within section 1
    theme_pattern = r"###\s+(?:Theme|테마)\s*(?:\d+|:)"
    theme_matches = re.findall(theme_pattern, content, re.IGNORECASE)
    # Also count ### headers that look like theme names (between section 1 and section 2)
    if len(theme_matches) < MIN_THEME_SECTIONS:
        # Alternative: count ### headers in the theme tracking section
        section1_pattern_en = r"Theme-Based Temporal Tracking(.*?)(?=\n## \d+\.|\n---|\Z)"
        section1_pattern_ko = r"핵심 테마별 시간축 추적(.*?)(?=\n## \d+\.|\n---|\Z)"
        section1_match = re.search(section1_pattern_en, content, re.DOTALL) or \
                         re.search(section1_pattern_ko, content, re.DOTALL)
        if section1_match:
            subsection_headers = re.findall(r"###\s+", section1_match.group(1))
            theme_matches = subsection_headers if len(subsection_headers) > len(theme_matches) else theme_matches
    result.add(
        "TL-005", "CRITICAL",
        f"Theme sections: {len(theme_matches)} (min {MIN_THEME_SECTIONS})"
        + (" [SKIPPED: prefilled]" if is_prefilled else ""),
        len(theme_matches) >= MIN_THEME_SECTIONS or is_prefilled
    )

    # TL-006: Each theme has trajectory/궤적 (count both languages)
    trajectory_count = content.lower().count("trajectory") + content.count("궤적")
    result.add(
        "TL-006", "WARN",
        f"Trajectory mentions: {trajectory_count}",
        trajectory_count >= max(1, len(theme_matches))
    )

    # TL-007: Each theme has judgment/판단 (count both languages)
    judgment_count = content.lower().count("judgment") + content.count("판단")
    result.add(
        "TL-007", "WARN",
        f"Judgment mentions: {judgment_count}",
        judgment_count >= max(1, len(theme_matches))
    )

    # TL-008: Each theme has ASCII code block (``` delimited)
    code_blocks = re.findall(r"```", content)
    # Pairs of ``` make code blocks; the YAML metadata is at least 1
    code_block_count = len(code_blocks) // 2
    result.add(
        "TL-008", "WARN",
        f"Code blocks: {code_block_count}",
        code_block_count >= max(1, len(theme_matches))
    )

    # TL-009: pSST Top-N table has >= 5 rows
    # Find the pSST table section and count data rows
    psst_section_en = re.search(r"pSST Priority Top-.*?(?=\n## \d+\.|\n---|\Z)", content, re.DOTALL)
    psst_section_ko = re.search(r"pSST 우선순위 Top-.*?(?=\n## \d+\.|\n---|\Z)", content, re.DOTALL)
    psst_section = psst_section_en or psst_section_ko
    psst_rows = 0
    if psst_section:
        table_rows = re.findall(r"^\|[^|]+\|", psst_section.group(0), re.MULTILINE)
        # Subtract header and separator rows
        psst_rows = max(0, len(table_rows) - 2)
    result.add(
        "TL-009", "WARN",
        f"pSST table data rows: {psst_rows} (min {MIN_PSST_ROWS})",
        psst_rows >= MIN_PSST_ROWS
    )

    # TL-010: Escalation table has "다음 예상" or "Next Expected" column
    has_next_expected = ("다음 예상" in content) or ("Next Expected" in content)
    result.add(
        "TL-010", "WARN",
        "Escalation table 'Next Expected' column" + (" present" if has_next_expected else " missing"),
        has_next_expected
    )

    # TL-011: Metadata total_signals matches signal count in body
    total_signals_match = True  # default pass if no metadata
    if yaml_match:
        try:
            meta = yaml.safe_load(yaml_match.group(1))
            if meta and "total_signals" in meta:
                declared_total = meta["total_signals"]
                # Count signal IDs in body (patterns like WF1-xxx, naver-xxx, news-xxx, etc.)
                signal_ids = re.findall(
                    r"\b(?:wf[1-4]-|naver-|news-|arxiv-|explore-)\d{8}-\w+-\d+",
                    content, re.IGNORECASE
                )
                # This is advisory — exact match is hard to guarantee
                if len(signal_ids) > 0 and abs(len(set(signal_ids)) - declared_total) > declared_total * 0.5:
                    total_signals_match = False
        except (yaml.YAMLError, TypeError):
            pass
    result.add(
        "TL-011", "WARN",
        "Metadata total_signals consistency",
        total_signals_match
    )

    # TL-012: Date range consistency
    dates_found = re.findall(r"\d{4}-\d{2}-\d{2}", content)
    date_consistent = len(dates_found) >= 1  # At least one date present
    result.add(
        "TL-012", "WARN",
        f"Date references: {len(dates_found)} found",
        date_consistent
    )

    # TL-013: Strategic implications has >= 3 items
    # Look in section 6
    strat_section_en = re.search(r"Strategic Implications(.*?)(?=\n## \d+\.|\n---|\Z)", content, re.DOTALL)
    strat_section_ko = re.search(r"전략적 시사점(.*?)(?=\n## \d+\.|\n---|\Z)", content, re.DOTALL)
    strat_section = strat_section_en or strat_section_ko
    strat_items = 0
    if strat_section:
        # Count list items (- or numbered)
        items = re.findall(r"^\s*(?:[-*]|\d+\.)\s+", strat_section.group(1), re.MULTILINE)
        strat_items = len(items)
    result.add(
        "TL-013", "WARN",
        f"Strategic implication items: {strat_items} (min {MIN_STRATEGIC_ITEMS})",
        strat_items >= MIN_STRATEGIC_ITEMS
    )

    # =========================================================================
    # v1.1.0: Enhanced quality defense rules (TL-014 ~ TL-018)
    # =========================================================================

    # TL-014: Each theme section must have ≥2 temporal transition points with dates
    # A temporal transition point is a date (YYYY-MM-DD) within a theme section.
    theme_section_en = re.search(r"Theme-Based Temporal Tracking(.*?)(?=\n## \d+\.|\n---|\Z)", content, re.DOTALL)
    theme_section_ko = re.search(r"핵심 테마별 시간축 추적(.*?)(?=\n## \d+\.|\n---|\Z)", content, re.DOTALL)
    theme_body = theme_section_en or theme_section_ko
    theme_temporal_ok = True
    theme_temporal_detail = ""
    if theme_body and not is_prefilled:
        # Split into individual theme subsections by ### headers
        # First element is intro text (before first ###), skip it
        subsections = re.split(r"\n###\s+", theme_body.group(1))
        themes_with_few_dates = []
        for i, sub in enumerate(subsections):
            if i == 0 or not sub.strip():
                continue  # Skip intro text before first ### header
            sub_dates = re.findall(r"\d{2}-\d{2}", sub)  # MM-DD or full dates
            sub_full_dates = re.findall(r"\d{4}-\d{2}-\d{2}", sub)
            total_date_refs = len(sub_dates)
            if total_date_refs < 2:
                # Extract theme name (first line of subsection)
                first_line = sub.strip().split("\n")[0][:50]
                themes_with_few_dates.append(first_line)
        if themes_with_few_dates:
            theme_temporal_ok = False
            theme_temporal_detail = f" (insufficient dates in: {', '.join(themes_with_few_dates[:3])})"
    result.add(
        "TL-014", "CRITICAL",
        f"Theme sections have ≥2 temporal transition points{theme_temporal_detail}"
        + (" [SKIPPED: prefilled]" if is_prefilled else ""),
        theme_temporal_ok or is_prefilled
    )

    # TL-015: Cross-WF table has data for ≥2 workflows
    cross_wf_section_en = re.search(r"Cross-Workflow Signal Trajectory(.*?)(?=\n## \d+\.|\n---|\Z)", content, re.DOTALL)
    cross_wf_section_ko = re.search(r"교차 워크플로우 시그널 궤적(.*?)(?=\n## \d+\.|\n---|\Z)", content, re.DOTALL)
    cross_wf_body = cross_wf_section_en or cross_wf_section_ko
    wf_refs_in_cross = set()
    if cross_wf_body:
        for wf_tag in ["WF1", "WF2", "WF3", "WF4"]:
            if wf_tag in cross_wf_body.group(1):
                wf_refs_in_cross.add(wf_tag)
    result.add(
        "TL-015", "CRITICAL",
        f"Cross-WF table references {len(wf_refs_in_cross)} workflows (min 2)"
        + (" [SKIPPED: prefilled]" if is_prefilled else ""),
        len(wf_refs_in_cross) >= 2 or is_prefilled
    )

    # TL-016: Strategic implications reference specific theme interactions
    strat_refs_themes = False
    if strat_section:
        strat_text = strat_section.group(1).lower()
        # Check for theme interaction markers
        interaction_markers = ["theme", "테마", "interaction", "상호작용",
                               "compound", "복합", "feedback", "피드백", "loop", "루프"]
        strat_refs_themes = any(m in strat_text for m in interaction_markers)
    result.add(
        "TL-016", "WARN",
        "Strategic implications reference theme interactions"
        + (" present" if strat_refs_themes else " missing"),
        strat_refs_themes
    )

    # TL-017: Each theme judgment cites ≥1 quantitative metric
    theme_judgment_ok = True
    if theme_body and not is_prefilled:
        subsections = re.split(r"\n###\s+", theme_body.group(1))
        themes_no_metrics = []
        for sub in subsections:
            if not sub.strip():
                continue
            # Look for judgment section within the subsection
            judgment_match = re.search(r"(?:판단|Judgment|judgment)[:\s]*(.*?)(?=\n(?:###|\*\*)|$)",
                                       sub, re.DOTALL | re.IGNORECASE)
            if judgment_match:
                jtext = judgment_match.group(1)
                # Check for numeric values (at least 1 number)
                has_number = bool(re.search(r"\d+", jtext))
                if not has_number:
                    first_line = sub.strip().split("\n")[0][:50]
                    themes_no_metrics.append(first_line)
        if themes_no_metrics:
            theme_judgment_ok = False
    result.add(
        "TL-017", "WARN",
        "Theme judgments cite quantitative metrics"
        + (" [SKIPPED: prefilled]" if is_prefilled else ""),
        theme_judgment_ok or is_prefilled
    )

    # TL-018: ASCII timelines present in code blocks (Python 원천봉쇄 enforcement)
    # Verifies that each theme section contains a code block (``` delimited)
    # representing the PB-1 ASCII timeline.
    theme_ascii_ok = True
    if theme_body and not is_prefilled:
        subsections = re.split(r"\n###\s+", theme_body.group(1))
        # Skip first element (intro text before first ### header)
        non_empty_themes = [s for i, s in enumerate(subsections) if i > 0 and s.strip()]
        themes_without_ascii = 0
        for sub in non_empty_themes:
            if "```" not in sub:
                themes_without_ascii += 1
        if non_empty_themes and themes_without_ascii > 0:
            theme_ascii_ok = False
    result.add(
        "TL-018", "CRITICAL",
        f"ASCII timelines (PB-1) present in all theme sections"
        + (" [SKIPPED: prefilled]" if is_prefilled else ""),
        theme_ascii_ok or is_prefilled
    )

    return result


def main():
    parser = argparse.ArgumentParser(description="Validate Timeline Map reports")
    parser.add_argument("--input", required=True, help="Path to timeline map markdown file")
    parser.add_argument("--profile", default="timeline", help="Validation profile (default: timeline)")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    result = validate_timeline_map(content, profile=args.profile)

    print(f"Timeline Map Validation (profile={args.profile})")
    print(f"{'=' * 60}")
    print(result.summary())
    print(f"{'=' * 60}")

    if result.has_critical:
        print("RESULT: CRITICAL — must fix before proceeding")
        sys.exit(1)
    elif result.has_warn:
        print("RESULT: WARN — advisory issues found")
        sys.exit(2)
    else:
        print("RESULT: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
