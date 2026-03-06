#!/usr/bin/env python3
"""
Timeline Data Assembler — Data Package Assembly + Python Pre-Rendering
======================================================================
theme_discovery_engine의 테마 분석 결과 + 상류 출력(classified-signals,
evolution-maps, cross-evolution-map)을 하나의 데이터 패키지 JSON으로 조립한다.
또한 Python 원천봉쇄 (PB-1 ~ PB-6) 사전 렌더링을 수행한다.

핵심 원칙:
    - 모듈 독립성: core/ 내 다른 모듈 import 없음 (stdlib + yaml only)
    - Python 원천봉쇄: 결정론적 출력은 Python이 계산, LLM은 그대로 사용
    - Graceful Degradation: 개별 입력 파일 없으면 해당 섹션 기본값

Usage (CLI):
    python3 env-scanning/core/timeline_data_assembler.py \\
        --theme-analysis {path}/timeline-theme-analysis-{date}.json \\
        --wf1-classified {WF1}/structured/classified-signals-{date}.json \\
        --wf2-classified {WF2}/structured/classified-signals-{date}.json \\
        --wf3-classified {WF3}/structured/classified-signals-{date}.json \\
        --wf4-classified {WF4}/structured/classified-signals-{date}.json \\
        --wf1-evolution-map {WF1}/analysis/evolution/evolution-map-{date}.json \\
        --wf2-evolution-map {WF2}/analysis/evolution/evolution-map-{date}.json \\
        --wf3-evolution-map {WF3}/analysis/evolution/evolution-map-{date}.json \\
        --wf4-evolution-map {WF4}/analysis/evolution/evolution-map-{date}.json \\
        --cross-evolution-map {INT}/analysis/evolution/cross-evolution-map-{date}.json \\
        --registry env-scanning/config/workflow-registry.yaml \\
        --scan-date 2026-03-06 \\
        --output {INT}/analysis/timeline-map-data-package-{date}.json

Exit codes:
    0 = SUCCESS
    1 = ERROR
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("timeline_data_assembler")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "1.0.0"
ENGINE_ID = f"timeline_data_assembler.py v{VERSION}"

PRIORITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "STABLE": 3, "DECLINING": 4}

STEEPS_ORDER = ["S", "T", "E", "E_Environmental", "P", "s"]

CONTENT_TRUNCATION_LIMIT = 500


# ---------------------------------------------------------------------------
# File I/O Helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> dict:
    """Load a JSON file, return empty dict on failure."""
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        logger.warning(f"File not found: {path}")
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load JSON: {path}: {e}")
        return {}


def _load_yaml(path: str) -> dict:
    """Load a YAML file, return empty dict on failure."""
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        logger.warning(f"File not found: {path}")
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load YAML: {path}: {e}")
        return {}


def _truncate(text: str, max_len: int = CONTENT_TRUNCATION_LIMIT) -> str:
    """Truncate text to max_len characters."""
    if not text or len(text) <= max_len:
        return text
    return text[:max_len]


# ---------------------------------------------------------------------------
# 1. Load SOT Config
# ---------------------------------------------------------------------------

def load_sot_config(registry_path: str) -> dict:
    """Read timeline_map parameters from SOT (workflow-registry.yaml).

    Returns dict with timeline_map settings, or defaults if missing.
    """
    defaults = {
        "lookback_days": 7,
        "min_signals_for_theme": 2,
        "top_n_psst": 10,
    }

    registry = _load_yaml(registry_path)
    if not registry:
        return defaults

    system = registry.get("system", {})
    sig_evo = system.get("signal_evolution", {})
    if not sig_evo.get("enabled", False):
        return defaults

    tl_cfg = sig_evo.get("timeline_map", {})
    if not tl_cfg.get("enabled", False):
        return defaults

    return {
        "lookback_days": tl_cfg.get("lookback_days", defaults["lookback_days"]),
        "min_signals_for_theme": tl_cfg.get("min_signals_for_theme", defaults["min_signals_for_theme"]),
        "top_n_psst": tl_cfg.get("top_n_psst", defaults["top_n_psst"]),
    }


# ---------------------------------------------------------------------------
# 2. Load & Merge Classified Signals
# ---------------------------------------------------------------------------

def load_classified_signals(
    classified_paths: Dict[str, str],
    scan_date: str = "",
) -> Tuple[Dict[str, List[dict]], Dict[str, int]]:
    """Load classified-signals from each WF.

    Returns:
        (all_signals_by_wf, wf_counts)
        all_signals_by_wf: {"wf1": [signal, ...], ...}
        wf_counts: {"wf1": N, ...}
    """
    all_signals: Dict[str, List[dict]] = {}
    wf_counts: Dict[str, int] = {}

    for wf_label, path in classified_paths.items():
        data = _load_json(path)
        if not data:
            all_signals[wf_label] = []
            wf_counts[wf_label] = 0
            continue

        signals = data.get("signals", [])
        # Infer scan_date from metadata or parameter
        file_scan_date = ""
        meta = data.get("metadata", {})
        if isinstance(meta, dict):
            file_scan_date = meta.get("scan_date", meta.get("date", ""))
        if not file_scan_date:
            file_scan_date = scan_date

        for sig in signals:
            sig["source_wf"] = wf_label
            # Inject scan_date if missing
            if not sig.get("scan_date") and file_scan_date:
                sig["scan_date"] = file_scan_date
            # Compute proxy psst_score from impact+novelty if missing
            if not sig.get("psst_score"):
                impact = sig.get("impact_score", 0) or 0
                novelty = sig.get("novelty_score", 0) or 0
                if impact or novelty:
                    sig["psst_score"] = round((impact * 8 + novelty * 2), 1)

        all_signals[wf_label] = signals
        wf_counts[wf_label] = len(signals)

    return all_signals, wf_counts


# ---------------------------------------------------------------------------
# 3. Build STEEPs Timeline (date x STEEPs matrix)
# ---------------------------------------------------------------------------

def build_steeps_timeline(all_signals_by_wf: Dict[str, List[dict]]) -> Dict[str, Dict[str, int]]:
    """Compute per-date STEEPs distribution matrix from classified signals.

    Returns:
        Dict mapping date_str -> {steeps_code: count}. Sorted by date ascending.
    """
    timeline: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for wf_label, signals in all_signals_by_wf.items():
        for sig in signals:
            date = sig.get("scan_date", "")
            category = sig.get("category", sig.get("primary_category", ""))
            if date and category:
                timeline[date][category] += 1

    # Sort by date and convert to regular dicts
    return {k: dict(v) for k, v in sorted(timeline.items())}


# ---------------------------------------------------------------------------
# 4. Extract pSST Rankings (Top-N)
# ---------------------------------------------------------------------------

def extract_psst_rankings(
    all_signals_by_wf: Dict[str, List[dict]],
    top_n: int = 10,
) -> List[dict]:
    """Extract top-N signals by pSST score across all WFs.

    Returns list of top-N signal dicts sorted by pSST descending.
    """
    all_scored = []
    for wf_label, signals in all_signals_by_wf.items():
        for sig in signals:
            psst = sig.get("psst_score", 0) or 0
            if psst > 0:
                all_scored.append(sig)

    all_scored.sort(key=lambda x: (-(x.get("psst_score", 0) or 0), x.get("scan_date", "")))

    # Deduplicate by id
    seen = set()
    unique = []
    for sig in all_scored:
        sid = sig.get("id", sig.get("signal_id", ""))
        if sid and sid not in seen:
            seen.add(sid)
            unique.append(sig)
        elif not sid:
            unique.append(sig)

    return unique[:top_n]


# ---------------------------------------------------------------------------
# 5. Build Per-Theme Signal Details (with content truncation)
# ---------------------------------------------------------------------------

def build_per_theme_signal_details(
    theme_analysis: dict,
) -> Dict[str, List[dict]]:
    """Extract per-theme signal details with content truncation.

    Reads signal_details from each config_theme in theme_analysis.
    Truncates content/summary fields to CONTENT_TRUNCATION_LIMIT chars.

    Returns:
        {"theme_id": [signal_dict, ...], ...}
    """
    result: Dict[str, List[dict]] = {}

    for theme in theme_analysis.get("config_themes", []):
        theme_id = theme.get("theme_id", "")
        if not theme_id:
            continue

        details = theme.get("signal_details", [])
        truncated_details = []
        for sig in details:
            sig_copy = dict(sig)
            # Truncate content fields
            for field in ("summary", "content", "abstract"):
                if field in sig_copy and isinstance(sig_copy[field], str):
                    sig_copy[field] = _truncate(sig_copy[field])
            truncated_details.append(sig_copy)

        result[theme_id] = truncated_details

    return result


# ---------------------------------------------------------------------------
# 6. Extract Cross-WF Correlations
# ---------------------------------------------------------------------------

def extract_cross_wf_correlations(cross_evolution_map: dict) -> dict:
    """Extract cross-WF correlation data from cross-evolution-map.

    Returns the correlations structure or empty dict.
    """
    if not cross_evolution_map:
        return {}
    return cross_evolution_map


# ---------------------------------------------------------------------------
# PB-1: ASCII Timeline Diagrams
# ---------------------------------------------------------------------------

def render_ascii_timelines(theme_analysis: dict) -> Dict[str, str]:
    """Render ASCII timeline diagrams for each theme (PB-1).

    For each theme, shows dates, signal counts by WF, and pSST ranges.

    Returns:
        {"theme_id": "ascii_string", ...}
    """
    result: Dict[str, str] = {}

    for theme in theme_analysis.get("config_themes", []):
        theme_id = theme.get("theme_id", "")
        if not theme_id:
            continue

        signal_details = theme.get("signal_details", [])
        if not signal_details:
            continue

        # Group by date
        by_date: Dict[str, List[dict]] = defaultdict(list)
        for sig in signal_details:
            d = sig.get("scan_date", "")
            if d:
                by_date[d].append(sig)

        if not by_date:
            continue

        sorted_dates = sorted(by_date.keys())

        # Build ASCII diagram
        lines = []

        # Date header line
        date_labels = [d[-5:] for d in sorted_dates]  # MM-DD format
        header = " ------- ".join(date_labels)
        lines.append(header)

        # Per-date detail line
        for d in sorted_dates:
            sigs = by_date[d]
            # Group by WF
            wf_counts: Dict[str, int] = defaultdict(int)
            psst_values = []
            for sig in sigs:
                wf = sig.get("source_wf", "unknown")
                wf_counts[wf] += 1
                psst = sig.get("psst_score", 0) or 0
                if psst > 0:
                    psst_values.append(psst)

            # Format WF labels
            wf_parts = []
            for wf in sorted(wf_counts.keys()):
                wf_display = wf.upper() if not wf.startswith("WF") and not wf.startswith("wf") else wf.upper()
                wf_parts.append(f"{wf_display}({wf_counts[wf]})")
            wf_str = ",".join(wf_parts)

            # pSST range
            psst_str = ""
            if psst_values:
                if len(psst_values) == 1:
                    psst_str = f"pSST:{psst_values[0]}"
                else:
                    psst_str = f"pSST:{min(psst_values)}~{max(psst_values)}"

            detail = f"  | {d[-5:]} {wf_str} {psst_str}"
            lines.append(detail)

        result[theme_id] = "\n".join(lines)

    return result


# ---------------------------------------------------------------------------
# PB-2: Cross-WF Table Structure
# ---------------------------------------------------------------------------

def render_cross_wf_table(theme_analysis: dict) -> dict:
    """Build cross-WF table structure (PB-2).

    Returns:
        {
            "headers": [...],
            "rows": [...],
            "markdown": "..."
        }
    """
    headers = ["theme", "WF1", "WF2", "WF3", "WF4",
               "first_appearance", "last_appearance", "lag_days", "interpretation"]

    rows = []
    md_lines = []
    md_lines.append("| 테마 | WF1 | WF2 | WF3 | WF4 | 최초출현 | 최종출현 | 시차(일) | 해석 |")
    md_lines.append("|------|-----|-----|-----|-----|---------|---------|---------|------|")

    for theme in theme_analysis.get("config_themes", []):
        theme_id = theme.get("theme_id", "")
        label_ko = theme.get("label_ko", "")
        signal_details = theme.get("signal_details", [])

        if not signal_details:
            continue

        # Count per WF
        wf_counts: Dict[str, int] = {"wf1": 0, "wf2": 0, "wf3": 0, "wf4": 0}
        dates_by_wf: Dict[str, List[str]] = defaultdict(list)
        all_dates = []

        for sig in signal_details:
            wf = sig.get("source_wf", "unknown").lower()
            if wf in wf_counts:
                wf_counts[wf] += 1
            d = sig.get("scan_date", "")
            if d:
                dates_by_wf[wf].append(d)
                all_dates.append(d)

        if not all_dates:
            continue

        first_date = min(all_dates)
        last_date = max(all_dates)
        try:
            lag_days = (datetime.strptime(last_date, "%Y-%m-%d") -
                        datetime.strptime(first_date, "%Y-%m-%d")).days
        except ValueError:
            lag_days = 0

        row = {
            "theme_id": theme_id,
            "label_ko": label_ko,
            "wf1": wf_counts["wf1"],
            "wf2": wf_counts["wf2"],
            "wf3": wf_counts["wf3"],
            "wf4": wf_counts["wf4"],
            "first_appearance": first_date,
            "last_appearance": last_date,
            "lag_days": lag_days,
            "interpretation": "{{LLM}}",
        }
        rows.append(row)

        md_lines.append(
            f"| {label_ko} | {wf_counts['wf1']} | {wf_counts['wf2']} | "
            f"{wf_counts['wf3']} | {wf_counts['wf4']} | {first_date} | "
            f"{last_date} | {lag_days} | {{{{LLM}}}} |"
        )

    return {
        "headers": headers,
        "rows": rows,
        "markdown": "\n".join(md_lines),
    }


# ---------------------------------------------------------------------------
# PB-3: Lead-Lag Computed
# ---------------------------------------------------------------------------

def compute_lead_lag(theme_analysis: dict) -> List[dict]:
    """Compute lead-lag for themes appearing in 2+ WFs (PB-3).

    For each qualifying theme: first_wf, first_date, last_wf, last_date, lag_days.

    Returns:
        List of lead-lag dicts.
    """
    results = []

    for theme in theme_analysis.get("config_themes", []):
        theme_id = theme.get("theme_id", "")
        signal_details = theme.get("signal_details", [])

        if not signal_details:
            continue

        # Group dates by WF
        wf_dates: Dict[str, List[str]] = defaultdict(list)
        for sig in signal_details:
            wf = sig.get("source_wf", "unknown").lower()
            d = sig.get("scan_date", "")
            if d:
                wf_dates[wf].append(d)

        # Need 2+ WFs
        active_wfs = {wf: dates for wf, dates in wf_dates.items() if dates}
        if len(active_wfs) < 2:
            continue

        # Find first appearance per WF
        wf_first: Dict[str, str] = {}
        for wf, dates in active_wfs.items():
            wf_first[wf] = min(dates)

        # Find overall first and last
        sorted_wf_first = sorted(wf_first.items(), key=lambda x: x[1])
        first_wf, first_date = sorted_wf_first[0]
        last_wf, last_date = sorted_wf_first[-1]

        try:
            lag_days = (datetime.strptime(last_date, "%Y-%m-%d") -
                        datetime.strptime(first_date, "%Y-%m-%d")).days
        except ValueError:
            lag_days = 0

        results.append({
            "theme_id": theme_id,
            "first_wf": first_wf,
            "first_date": first_date,
            "last_wf": last_wf,
            "last_date": last_date,
            "lag_days": lag_days,
        })

    return results


# ---------------------------------------------------------------------------
# PB-4: Escalation Confirmed
# ---------------------------------------------------------------------------

def confirm_escalation(theme_analysis: dict) -> List[dict]:
    """Copy escalation severity directly from theme_analysis (PB-4).

    This is the Python-confirmed grade. LLM cannot override.

    Returns:
        List of {"theme_id": ..., "severity": ..., "slope": ...}
    """
    results = []

    for theme in theme_analysis.get("config_themes", []):
        theme_id = theme.get("theme_id", "")
        escalation = theme.get("escalation", {})

        results.append({
            "theme_id": theme_id,
            "severity": escalation.get("severity", "STABLE"),
            "slope": escalation.get("slope", 0.0),
            "burst": escalation.get("burst", False),
            "burst_rate": escalation.get("burst_rate", 0.0),
        })

    return results


# ---------------------------------------------------------------------------
# PB-5: Monitoring Priority Order
# ---------------------------------------------------------------------------

def compute_monitoring_priority_order(theme_analysis: dict) -> List[str]:
    """Sort themes by severity rank then slope descending (PB-5).

    Severity ranking: CRITICAL=0, HIGH=1, MEDIUM=2, STABLE=3, DECLINING=4.

    Returns:
        Ordered list of theme_ids.
    """
    themes_with_esc = []

    for theme in theme_analysis.get("config_themes", []):
        theme_id = theme.get("theme_id", "")
        escalation = theme.get("escalation", {})
        severity = escalation.get("severity", "STABLE")
        slope = escalation.get("slope", 0.0)

        themes_with_esc.append({
            "theme_id": theme_id,
            "severity": severity,
            "slope": slope,
        })

    # Sort by severity rank (ascending), then slope (descending)
    themes_with_esc.sort(
        key=lambda t: (SEVERITY_RANK.get(t["severity"], 99), -t["slope"])
    )

    return [t["theme_id"] for t in themes_with_esc]


# ---------------------------------------------------------------------------
# PB-6: Theme Display Order + Key Signals Per Theme
# ---------------------------------------------------------------------------

def compute_theme_display_order(theme_analysis: dict) -> List[str]:
    """Sort themes by priority rank then signal_count descending (PB-6).

    Priority ranking: CRITICAL=0, HIGH=1, MEDIUM=2, LOW=3.

    Returns:
        Ordered list of theme_ids.
    """
    themes_info = []

    for theme in theme_analysis.get("config_themes", []):
        theme_id = theme.get("theme_id", "")
        priority = theme.get("priority", "LOW")
        signal_count = theme.get("stats", {}).get("signal_count", len(theme.get("signals", [])))

        themes_info.append({
            "theme_id": theme_id,
            "priority": priority,
            "signal_count": signal_count,
        })

    themes_info.sort(
        key=lambda t: (PRIORITY_RANK.get(t["priority"], 99), -t["signal_count"])
    )

    return [t["theme_id"] for t in themes_info]


def compute_key_signals_per_theme(theme_analysis: dict, top_n: int = 3) -> Dict[str, List[str]]:
    """Extract top-N signals by pSST for each theme (PB-6).

    Returns:
        {"theme_id": ["sig-001", "sig-002", ...], ...}
    """
    result: Dict[str, List[str]] = {}

    for theme in theme_analysis.get("config_themes", []):
        theme_id = theme.get("theme_id", "")
        signal_details = theme.get("signal_details", [])

        if not signal_details:
            result[theme_id] = []
            continue

        # Sort by pSST descending
        sorted_sigs = sorted(
            signal_details,
            key=lambda s: -(s.get("psst_score", 0) or 0),
        )

        # Extract top-N IDs
        top_ids = []
        for sig in sorted_sigs[:top_n]:
            sid = sig.get("id", sig.get("signal_id", ""))
            if sid:
                top_ids.append(sid)

        result[theme_id] = top_ids

    return result


# ---------------------------------------------------------------------------
# Escalation Table Markdown
# ---------------------------------------------------------------------------

def render_escalation_table_markdown(escalation_confirmed: List[dict]) -> str:
    """Render escalation table as markdown.

    Returns markdown string.
    """
    lines = []
    lines.append("| 테마 | 심각도 | 기울기 | 폭증 | 폭증률 |")
    lines.append("|------|--------|--------|------|--------|")

    for esc in escalation_confirmed:
        theme_id = esc.get("theme_id", "")
        severity = esc.get("severity", "STABLE")
        slope = esc.get("slope", 0.0)
        burst = "Y" if esc.get("burst", False) else "N"
        burst_rate = esc.get("burst_rate", 0.0)
        lines.append(f"| {theme_id} | {severity} | {slope} | {burst} | {burst_rate} |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main Assembly Function
# ---------------------------------------------------------------------------

def assemble_data_package(
    theme_analysis_path: str,
    classified_paths: Dict[str, str],
    evolution_map_paths: Dict[str, str],
    cross_evolution_map_path: str,
    registry_path: str,
    scan_date: str,
    output_path: str,
) -> dict:
    """Main entry point: load all inputs, assemble data package, pre-render, write output.

    Args:
        theme_analysis_path: Path to theme analysis JSON (A1 output)
        classified_paths: {"wf1": path, "wf2": path, "wf3": path, "wf4": path}
        evolution_map_paths: {"wf1": path, ...}
        cross_evolution_map_path: Path to cross-evolution-map JSON
        registry_path: Path to workflow-registry.yaml
        scan_date: YYYY-MM-DD
        output_path: Output JSON path

    Returns:
        The assembled data package dict.
    """
    # 1. Load SOT config
    sot_config = load_sot_config(registry_path)
    lookback_days = sot_config.get("lookback_days", 7)
    top_n_psst = sot_config.get("top_n_psst", 10)

    # 2. Load theme analysis
    theme_analysis = _load_json(theme_analysis_path)
    if not theme_analysis:
        theme_analysis = {
            "config_themes": [],
            "emergent_themes": [],
            "unmatched_signals": [],
            "compound_escalations": [],
        }

    # 3. Load classified signals
    all_signals_by_wf, wf_counts = load_classified_signals(classified_paths, scan_date=scan_date)
    total_signals = sum(wf_counts.values())

    # 4. Load evolution maps (for additional data)
    evolution_maps: Dict[str, dict] = {}
    for wf_label, path in evolution_map_paths.items():
        evolution_maps[wf_label] = _load_json(path)

    # 5. Load cross-evolution-map
    cross_evolution_map = _load_json(cross_evolution_map_path)

    # 6. Build STEEPs timeline
    steeps_timeline = build_steeps_timeline(all_signals_by_wf)

    # 7. Extract pSST rankings
    psst_rankings = extract_psst_rankings(all_signals_by_wf, top_n=top_n_psst)

    # 8. Build per-theme signal details
    per_theme_signal_details = build_per_theme_signal_details(theme_analysis)

    # 9. Extract cross-WF correlations
    cross_wf_correlations = extract_cross_wf_correlations(cross_evolution_map)

    # 10. Pre-rendering (PB-1 through PB-6)
    ascii_timelines = render_ascii_timelines(theme_analysis)
    cross_wf_table = render_cross_wf_table(theme_analysis)
    lead_lag_computed = compute_lead_lag(theme_analysis)
    escalation_confirmed = confirm_escalation(theme_analysis)
    monitoring_priority_order = compute_monitoring_priority_order(theme_analysis)
    theme_display_order = compute_theme_display_order(theme_analysis)
    key_signals_per_theme = compute_key_signals_per_theme(theme_analysis)
    escalation_table_markdown = render_escalation_table_markdown(escalation_confirmed)

    # 11. Compute period
    try:
        end = datetime.strptime(scan_date, "%Y-%m-%d")
        start = end - timedelta(days=lookback_days - 1)
        period = f"{start.strftime('%Y-%m-%d')} ~ {scan_date}"
    except ValueError:
        period = f"? ~ {scan_date}"

    # 12. Assemble output
    output = {
        "metadata": {
            "scan_date": scan_date,
            "lookback_days": lookback_days,
            "period": period,
            "wf_counts": wf_counts,
            "total_signals": total_signals,
            "assembler_version": VERSION,
        },
        "theme_analysis": theme_analysis,
        "cross_wf_correlations": cross_wf_correlations,
        "steeps_timeline": steeps_timeline,
        "psst_rankings": psst_rankings,
        "per_theme_signal_details": per_theme_signal_details,
        "pre_rendered": {
            "ascii_timelines": ascii_timelines,
            "cross_wf_table": cross_wf_table,
            "lead_lag_computed": lead_lag_computed,
            "escalation_confirmed": escalation_confirmed,
            "monitoring_priority_order": monitoring_priority_order,
            "theme_display_order": theme_display_order,
            "key_signals_per_theme": key_signals_per_theme,
            "escalation_table_markdown": escalation_table_markdown,
        },
    }

    # 13. Write output
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"Data package written: {output_path} ({total_signals} signals, "
                f"{len(theme_analysis.get('config_themes', []))} themes)")

    return output


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Timeline Data Assembler — Data Package Assembly + Python Pre-Rendering"
    )
    parser.add_argument(
        "--theme-analysis", required=True,
        help="Path to theme analysis JSON (A1 output from theme_discovery_engine)",
    )
    parser.add_argument("--wf1-classified", default="", help="WF1 classified-signals JSON")
    parser.add_argument("--wf2-classified", default="", help="WF2 classified-signals JSON")
    parser.add_argument("--wf3-classified", default="", help="WF3 classified-signals JSON")
    parser.add_argument("--wf4-classified", default="", help="WF4 classified-signals JSON")
    parser.add_argument("--wf1-evolution-map", default="", help="WF1 evolution-map JSON")
    parser.add_argument("--wf2-evolution-map", default="", help="WF2 evolution-map JSON")
    parser.add_argument("--wf3-evolution-map", default="", help="WF3 evolution-map JSON")
    parser.add_argument("--wf4-evolution-map", default="", help="WF4 evolution-map JSON")
    parser.add_argument("--cross-evolution-map", default="", help="Cross-evolution-map JSON")
    parser.add_argument(
        "--registry",
        default="env-scanning/config/workflow-registry.yaml",
        help="Path to workflow-registry.yaml (SOT)",
    )
    parser.add_argument(
        "--scan-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Scan date (YYYY-MM-DD)",
    )
    parser.add_argument("--output", "-o", required=True, help="Output JSON path")

    args = parser.parse_args()

    try:
        assemble_data_package(
            theme_analysis_path=args.theme_analysis,
            classified_paths={
                "wf1": args.wf1_classified,
                "wf2": args.wf2_classified,
                "wf3": args.wf3_classified,
                "wf4": args.wf4_classified,
            },
            evolution_map_paths={
                "wf1": args.wf1_evolution_map,
                "wf2": args.wf2_evolution_map,
                "wf3": args.wf3_evolution_map,
                "wf4": args.wf4_evolution_map,
            },
            cross_evolution_map_path=args.cross_evolution_map,
            registry_path=args.registry,
            scan_date=args.scan_date,
            output_path=args.output,
        )
        sys.exit(0)
    except Exception as e:
        logger.error(f"Data package assembly failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
