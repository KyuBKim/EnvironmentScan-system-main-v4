#!/usr/bin/env python3
"""Timeline Skeleton Filler — fills Python-deterministic placeholders in timeline map skeletons.

Reads a skeleton template and a data-package JSON from timeline_data_assembler,
fills deterministic placeholders (counts, tables, metadata), and preserves
LLM placeholders for the composer agent.

Usage:
    python3 timeline_skeleton_filler.py \
        --skeleton <path-to-skeleton.md> \
        --data-package <path-to-data-package.json> \
        --scan-date YYYY-MM-DD \
        --output <output-path.md>

Exit codes: 0 = success, 1 = error
"""

VERSION = "1.0.0"

import argparse
import json
import sys
import yaml

# ---------------------------------------------------------------------------
# LLM placeholders — these are NEVER replaced by this module
# ---------------------------------------------------------------------------
LLM_PLACEHOLDERS = frozenset([
    "{{TL_OVERVIEW_NARRATIVE}}",
    "{{TL_THEME_SECTIONS}}",
    "{{TL_CROSS_WF_NARRATIVE_TABLE}}",
    "{{TL_ESCALATION_ASSESSMENT_TABLE}}",
    "{{TL_STRATEGIC_IMPLICATIONS}}",
])


def _format_wf_counts(wf_counts: dict) -> str:
    """Format workflow counts dict into a readable string like 'WF1: 12 + WF2: 8 + ...'."""
    parts = []
    for wf_name in sorted(wf_counts.keys()):
        parts.append(f"{wf_name}: {wf_counts[wf_name]}")
    return " + ".join(parts)


def _count_escalations(escalations: list) -> int:
    """Count escalations with severity CRITICAL or HIGH."""
    count = 0
    for esc in escalations:
        severity = esc.get("severity", "").upper()
        if severity in ("CRITICAL", "HIGH"):
            count += 1
    return count


def _count_themes(data_package: dict) -> int:
    """Count total themes (config + emergent)."""
    theme_analysis = data_package.get("theme_analysis", {})
    config_count = len(theme_analysis.get("config_themes", []))
    emergent_count = len(theme_analysis.get("emergent_themes", []))
    return config_count + emergent_count


def _format_steeps_matrix(steeps_timeline: dict) -> str:
    """Format STEEPs timeline data into an ASCII table.

    Handles two formats:
    - Flat: {domain: {count, trend}} (pre-aggregated)
    - Date-keyed: {date: {category: count}} (from assembler)
    """
    if not steeps_timeline:
        return "| Domain | Count | Trend |\n|--------|-------|-------|\n| (no data) | - | - |"

    # Detect format: if first value is a dict with date-like keys, aggregate
    first_key = next(iter(steeps_timeline))
    first_val = steeps_timeline[first_key]

    if isinstance(first_val, dict) and not first_val.get("count") and not first_val.get("trend"):
        # Date-keyed format: {date: {category: count}} → aggregate to {category: total}
        domain_totals = {}
        dates = sorted(steeps_timeline.keys())
        for date_str in dates:
            for cat, cnt in steeps_timeline[date_str].items():
                domain_totals[cat] = domain_totals.get(cat, 0) + cnt

        lines = []
        lines.append("| Domain | Count | Trend |")
        lines.append("|--------|-------|-------|")
        for domain in sorted(domain_totals.keys()):
            lines.append(f"| {domain:<6} | {str(domain_totals[domain]):>5} | -     |")
        return "\n".join(lines)

    # Flat format
    lines = []
    lines.append("| Domain | Count | Trend |")
    lines.append("|--------|-------|-------|")
    for domain in sorted(steeps_timeline.keys()):
        entry = steeps_timeline[domain]
        if isinstance(entry, dict):
            count = entry.get("count", 0)
            trend = entry.get("trend", "-")
        else:
            count = entry
            trend = "-"
        lines.append(f"| {domain:<6} | {str(count):>5} | {trend:<5} |")
    return "\n".join(lines)


def _format_psst_table(psst_rankings: list, top_n: int) -> str:
    """Format pSST rankings into a markdown table."""
    if not psst_rankings:
        return "| Rank | Signal ID | Title | pSST Score | Trend |\n|------|-----------|-------|------------|-------|\n| (no data) | - | - | - | - |"

    lines = []
    lines.append("| Rank | Signal ID | Title | pSST Score | Trend |")
    lines.append("|------|-----------|-------|------------|-------|")
    for i, entry in enumerate(psst_rankings[:top_n], 1):
        sig_id = entry.get("signal_id", entry.get("id", "-"))
        title = entry.get("title", "-")
        score = entry.get("psst_score", "-")
        trend = entry.get("trend", "-")
        # Truncate title if too long
        if isinstance(title, str) and len(title) > 50:
            title = title[:47] + "..."
        lines.append(f"| {i} | {sig_id} | {title} | {score} | {trend} |")
    return "\n".join(lines)


def _format_metadata_yaml(metadata: dict) -> str:
    """Format metadata dict as a YAML code block."""
    yaml_str = yaml.dump(metadata, default_flow_style=False, allow_unicode=True, sort_keys=True)
    return f"```yaml\n{yaml_str.strip()}\n```"


def fill_skeleton(skeleton_text: str, data_package: dict, scan_date: str) -> str:
    """Fill Python-deterministic placeholders in the skeleton template.

    LLM placeholders are preserved untouched.
    """
    metadata = data_package.get("metadata", {})
    wf_counts = metadata.get("wf_counts", metadata.get("wf_signal_counts", {}))
    pre_rendered = data_package.get("pre_rendered", {})
    escalations = pre_rendered.get("escalation_confirmed", data_package.get("escalation_alerts", []))
    steeps_timeline = data_package.get("steeps_timeline", {})
    psst_rankings = data_package.get("psst_rankings", [])
    top_n = metadata.get("top_n_psst", 10)
    cross_wf = data_package.get("cross_wf_correlations", [])

    # Build replacement map for Python-deterministic placeholders
    replacements = {
        "{{TL_SCAN_DATE}}": scan_date,
        "{{TL_PERIOD}}": metadata.get("period", f"{scan_date}"),
        "{{TL_ENGINE_VERSION}}": metadata.get("assembler_version", VERSION),
        "{{TL_TOTAL_SIGNALS}}": str(metadata.get("total_signals", 0)),
        "{{TL_WF_COUNTS}}": _format_wf_counts(wf_counts),
        "{{TL_THEMES_DETECTED}}": str(_count_themes(data_package)),
        "{{TL_ESCALATIONS_DETECTED}}": str(_count_escalations(escalations)),
        "{{TL_CROSS_WF_CORRELATIONS}}": str(len(cross_wf)),
        "{{TL_STEEPS_MATRIX}}": _format_steeps_matrix(steeps_timeline),
        "{{TL_PSST_TOP_N_TABLE}}": _format_psst_table(psst_rankings, top_n),
        "{{TL_TOP_N}}": str(top_n),
        "{{TL_METADATA_YAML}}": _format_metadata_yaml(metadata),
    }

    result = skeleton_text
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    return result


def main():
    parser = argparse.ArgumentParser(description="Timeline Skeleton Filler")
    parser.add_argument("--skeleton", required=True, help="Path to skeleton template (EN or KO)")
    parser.add_argument("--data-package", required=True, help="Path to data-package JSON")
    parser.add_argument("--scan-date", required=True, help="Scan date (YYYY-MM-DD)")
    parser.add_argument("--output", required=True, help="Output path for pre-filled skeleton")
    args = parser.parse_args()

    try:
        with open(args.skeleton, "r", encoding="utf-8") as f:
            skeleton_text = f.read()
    except FileNotFoundError:
        print(f"ERROR: Skeleton file not found: {args.skeleton}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.data_package, "r", encoding="utf-8") as f:
            data_package = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Data-package file not found: {args.data_package}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in data-package: {e}", file=sys.stderr)
        sys.exit(1)

    filled = fill_skeleton(skeleton_text, data_package, args.scan_date)

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(filled)
    except OSError as e:
        print(f"ERROR: Cannot write output: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: Pre-filled skeleton written to {args.output}")
    sys.exit(0)


if __name__ == "__main__":
    main()
