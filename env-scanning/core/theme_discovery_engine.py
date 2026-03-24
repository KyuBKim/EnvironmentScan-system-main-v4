#!/usr/bin/env python3
"""
Theme Discovery Engine — Config-Driven + Emergent Theme Discovery
=================================================================
evolution-map과 evolution-index에서 시그널을 수집하고,
timeline-themes.yaml의 키워드 정의 기반으로 테마 매칭 + 미매칭 시그널에서
emergent 테마를 클러스터링 + 에스컬레이션 탐지를 수행한다.

핵심 원칙:
    - 모듈 독립성: core/ 내 다른 모듈 import 없음 (stdlib + yaml only)
    - SOT Direct Reading: --registry에서 설정 직접 읽기
    - Config-Driven: 테마 정의는 timeline-themes.yaml에서 로드
    - Whole-word matching with exclusion keywords

Usage (CLI):
    python3 env-scanning/core/theme_discovery_engine.py \\
        --registry env-scanning/config/workflow-registry.yaml \\
        --theme-config env-scanning/config/timeline-themes.yaml \\
        --wf1-evolution-map {path} --wf2-evolution-map {path} \\
        --wf3-evolution-map {path} --wf4-evolution-map {path} \\
        --wf1-index {path} --wf2-index {path} \\
        --wf3-index {path} --wf4-index {path} \\
        --cross-evolution-map {path} \\
        --scan-date 2026-03-06 \\
        --output {path}/timeline-theme-analysis-2026-03-06.json

Exit codes:
    0 = SUCCESS
    1 = ERROR
"""

import argparse
import difflib
import json
import logging
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("theme_discovery_engine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "1.0.0"
ENGINE_ID = f"theme_discovery_engine.py v{VERSION}"


# ---------------------------------------------------------------------------
# 1. Configuration Loading
# ---------------------------------------------------------------------------

def load_sot_config(registry_path: str) -> dict:
    """Read timeline_map parameters from SOT (workflow-registry.yaml).

    Returns dict with all timeline_map settings, or defaults if missing.
    """
    defaults = {
        "lookback_days": 0,
        "include_faded_threads": True,
        "trend_analysis_min_appearances": 3,
        "min_signals_for_theme": 2,
        "top_n_psst": 10,
        "emergent_cluster_min_size": 3,
        "emergent_max_themes": 5,
        "emergent_cooccurrence_threshold": 3,
        "emergent_title_similarity_threshold": 0.55,
        "escalation_thresholds": {
            "critical_slope": 5.0,
            "high_slope": 2.0,
            "burst_factor": 2.0,
        },
    }

    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to read registry: {e} — using defaults")
        return defaults

    system = registry.get("system", {})
    sig_evo = system.get("signal_evolution", {})
    if not sig_evo.get("enabled", False):
        return defaults

    tl_cfg = sig_evo.get("timeline_map", {})
    if not tl_cfg.get("enabled", False):
        return defaults

    result = dict(defaults)
    for key in defaults:
        if key in tl_cfg:
            result[key] = tl_cfg[key]
    return result


def load_theme_config(theme_config_path: str) -> Dict[str, dict]:
    """Load theme definitions from timeline-themes.yaml.

    Returns dict mapping theme_id to theme definition.
    """
    try:
        with open(theme_config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load theme config: {e}")
        return {}

    return data.get("themes", {})


# ---------------------------------------------------------------------------
# 2. Signal Collection from Evolution Maps + Indices
# ---------------------------------------------------------------------------

def collect_signals(
    evolution_maps: Dict[str, dict],
    evolution_indices: Dict[str, dict],
    lookback_days: int,
    scan_date: str,
    include_faded_threads: bool = True,
) -> List[dict]:
    """Collect all signals from evolution maps and indices.

    Args:
        lookback_days: 0 = unlimited (use ALL accumulated history).
                       >0 = filter to [scan_date - lookback_days, scan_date].
        include_faded_threads: If True, include FADED threads (for full timeline analysis).

    Returns flat list of signal dicts with source_wf tag.
    """
    all_signals: List[dict] = []
    seen_ids: set = set()

    # From evolution maps (current day signals)
    for wf_label, evo_map in evolution_maps.items():
        if not evo_map:
            continue
        entries = evo_map.get("evolution_entries", [])
        map_date = evo_map.get("scan_date", scan_date)
        for entry in entries:
            sid = entry.get("signal_id", "")
            if sid and sid in seen_ids:
                continue
            entry_copy = dict(entry)
            entry_copy["source_wf"] = wf_label
            if not entry_copy.get("scan_date"):
                entry_copy["scan_date"] = map_date
            all_signals.append(entry_copy)
            if sid:
                seen_ids.add(sid)

    # From evolution indices (historical data)
    # lookback_days == 0 → unlimited (全期間), >0 → windowed
    try:
        end_date = datetime.strptime(scan_date, "%Y-%m-%d")
        if lookback_days > 0:
            start_date = end_date - timedelta(days=lookback_days)
        else:
            start_date = None  # unlimited — include ALL accumulated history
    except ValueError:
        return all_signals

    for wf_label, index_data in evolution_indices.items():
        if not index_data:
            continue
        threads_raw = index_data.get("threads", {})
        # Normalize: some WFs use dict {thread_id: {...}}, others use list [{thread_id: ..., ...}]
        if isinstance(threads_raw, list):
            threads_iter = [(t.get("thread_id", f"anon-{i}"), t) for i, t in enumerate(threads_raw)]
        else:
            threads_iter = threads_raw.items()
        for thread_id, thread in threads_iter:
            # Skip FADED threads if not requested (v3.4.0)
            if not include_faded_threads and thread.get("state") == "FADED":
                continue

            canonical_title = thread.get("canonical_title", "")
            primary_category = thread.get("primary_category", "")
            keywords = thread.get("keywords", [])

            appearances_raw = thread.get("appearances", [])
            # Normalize: some WFs store appearances as int (count), others as list of dicts
            if isinstance(appearances_raw, int) or not isinstance(appearances_raw, list):
                # Flat thread format (WF3/WF4): synthesize single appearance from thread fields
                sid = thread.get("signal_id", "")
                if sid and sid in seen_ids:
                    continue
                app_date_str = thread.get("last_seen", thread.get("last_seen_date", ""))
                try:
                    app_date = datetime.strptime(app_date_str, "%Y-%m-%d")
                except ValueError:
                    continue
                if start_date and not (start_date <= app_date <= end_date):
                    continue
                psst_history = thread.get("psst_history", [])
                psst_score = psst_history[-1].get("score", 0) if psst_history else 0
                entry = {
                    "signal_id": sid,
                    "thread_id": thread_id,
                    "title": thread.get("title", canonical_title),
                    "canonical_title": canonical_title or thread.get("title", ""),
                    "keywords": keywords,
                    "psst_score": psst_score,
                    "scan_date": app_date_str,
                    "primary_category": primary_category or thread.get("primary_category", ""),
                    "source_wf": wf_label,
                }
                all_signals.append(entry)
                if sid:
                    seen_ids.add(sid)
            else:
                for appearance in appearances_raw:
                    sid = appearance.get("signal_id", "")
                    if sid and sid in seen_ids:
                        continue
                    app_date_str = appearance.get("scan_date", "")
                    try:
                        app_date = datetime.strptime(app_date_str, "%Y-%m-%d")
                    except ValueError:
                        continue
                    if start_date and not (start_date <= app_date <= end_date):
                        continue
                    entry = {
                        "signal_id": sid,
                        "thread_id": thread_id,
                        "title": appearance.get("title", canonical_title),
                        "canonical_title": canonical_title,
                        "keywords": keywords,
                        "psst_score": appearance.get("psst_score", 0) or 0,
                        "scan_date": app_date_str,
                        "primary_category": primary_category,
                        "source_wf": wf_label,
                    }
                    all_signals.append(entry)
                    if sid:
                        seen_ids.add(sid)

    return all_signals


# ---------------------------------------------------------------------------
# 2b. Thread Trend Computation (v3.4.0 — Python 원천봉쇄)
# ---------------------------------------------------------------------------

def _least_squares_slope(xs: List[float], ys: List[float]) -> float:
    """Simple least-squares slope. No external dependencies."""
    n = len(xs)
    if n < 2:
        return 0.0
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs)
    return num / den if den != 0 else 0.0


def compute_thread_trend(
    thread: dict,
    min_appearances: int = 3,
    slope_thresholds: Optional[dict] = None,
) -> dict:
    """
    Compute trend direction, velocity, and strength from full accumulated data.
    Python 원천봉쇄 — deterministic, no LLM judgment.

    Args:
        thread: A thread dict from evolution-index.json
        min_appearances: Minimum appearances for trend computation (SOT: trend_analysis_min_appearances)
        slope_thresholds: {"critical_slope": 5.0, "high_slope": 2.0} from SOT escalation_thresholds

    Returns:
        dict with direction, velocity, strength, slope, span_days, first/last_seen, total_appearances
    """
    appearances_raw = thread.get("appearances", [])

    # Handle non-list appearances (WF3/WF4 may store as int count)
    if not isinstance(appearances_raw, list) or len(appearances_raw) < min_appearances:
        return {
            "direction": "INSUFFICIENT_DATA",
            "velocity": 0.0,
            "strength": 0.0,
            "slope": 0.0,
            "total_appearances": len(appearances_raw) if isinstance(appearances_raw, list) else 0,
            "span_days": 0,
            "first_seen": thread.get("created_date", ""),
            "last_seen": thread.get("last_seen_date", ""),
        }

    # Sort by date
    sorted_apps = sorted(appearances_raw, key=lambda a: a.get("scan_date", ""))

    # Date span
    try:
        first_dt = datetime.strptime(sorted_apps[0].get("scan_date", ""), "%Y-%m-%d")
        last_dt = datetime.strptime(sorted_apps[-1].get("scan_date", ""), "%Y-%m-%d")
        span_days = max((last_dt - first_dt).days, 1)
    except (ValueError, TypeError):
        span_days = 1
        first_dt = None
        last_dt = None

    # Direction: slope of pSST scores over time (days from first appearance)
    dates_numeric = []
    scores = []
    for app in sorted_apps:
        try:
            app_dt = datetime.strptime(app.get("scan_date", ""), "%Y-%m-%d")
            day_offset = (app_dt - first_dt).days if first_dt else 0
            dates_numeric.append(float(day_offset))
            scores.append(float(app.get("psst_score", 0) or 0))
        except (ValueError, TypeError):
            continue

    slope = _least_squares_slope(dates_numeric, scores) if len(dates_numeric) >= 2 else 0.0

    # Velocity: appearance frequency (appearances / span_days)
    velocity = len(sorted_apps) / span_days

    # Strength: average of last 3 pSST scores
    recent_scores = scores[-3:] if scores else [0]
    strength = sum(recent_scores) / len(recent_scores)

    # Direction classification (thresholds from SOT escalation_thresholds)
    t = slope_thresholds or {}
    high_slope = t.get("high_slope", 2.0)
    low_slope = high_slope * 0.25  # gradual threshold = 25% of high
    if slope > high_slope:
        direction = "ACCELERATING"
    elif slope < -high_slope:
        direction = "DECELERATING"
    elif slope > low_slope:
        direction = "GRADUAL_RISE"
    elif slope < -low_slope:
        direction = "GRADUAL_DECLINE"
    else:
        direction = "STABLE"

    return {
        "direction": direction,
        "velocity": round(velocity, 4),
        "strength": round(strength, 2),
        "slope": round(slope, 4),
        "total_appearances": len(sorted_apps),
        "span_days": span_days,
        "first_seen": sorted_apps[0].get("scan_date", ""),
        "last_seen": sorted_apps[-1].get("scan_date", ""),
    }


def compute_all_thread_trends(
    evolution_indices: Dict[str, dict],
    min_appearances: int = 3,
    slope_thresholds: Optional[dict] = None,
) -> Dict[str, dict]:
    """Compute trends for ALL threads across all WFs. Returns {thread_id: trend_dict}."""
    all_trends = {}
    for wf_label, index_data in evolution_indices.items():
        if not index_data:
            continue
        threads = index_data.get("threads", {})
        if isinstance(threads, list):
            threads = {t.get("thread_id", f"anon-{i}"): t for i, t in enumerate(threads)}
        for thread_id, thread in threads.items():
            trend = compute_thread_trend(thread, min_appearances, slope_thresholds)
            trend["source_wf"] = wf_label
            trend["state"] = thread.get("state", "UNKNOWN")
            trend["canonical_title"] = thread.get("canonical_title", "")
            all_trends[thread_id] = trend
    return all_trends


# ---------------------------------------------------------------------------
# 3. Config-Driven Theme Matching
# ---------------------------------------------------------------------------

def _build_keyword_patterns(themes: Dict[str, dict]) -> Dict[str, Tuple[List, List]]:
    """Build compiled regex patterns for each theme.

    Returns dict: theme_id -> (include_patterns, exclusion_patterns)
    where each pattern is (compiled_regex, original_keyword).
    """
    result = {}
    for theme_id, theme_def in themes.items():
        include_patterns = []
        for kw in theme_def.get("keywords_en", []) + theme_def.get("keywords_ko", []):
            try:
                pattern = re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
                include_patterns.append((pattern, kw))
            except re.error:
                continue

        exclusion_patterns = []
        for kw in theme_def.get("exclusion_keywords", []):
            if not kw:
                continue
            try:
                pattern = re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
                exclusion_patterns.append((pattern, kw))
            except re.error:
                continue

        result[theme_id] = (include_patterns, exclusion_patterns)
    return result


def match_signal_to_themes(
    signal: dict,
    themes: Dict[str, dict],
    _pattern_cache: Optional[Dict[str, Tuple]] = None,
) -> List[dict]:
    """Match a single signal against all themes using whole-word matching.

    Returns list of match dicts: [{"theme_id": ..., "matched_keyword": ...}, ...]
    A signal can match multiple themes.
    """
    if _pattern_cache is None:
        _pattern_cache = _build_keyword_patterns(themes)

    # Build searchable text
    title = signal.get("title", "") or ""
    canonical = signal.get("canonical_title", "") or ""
    keywords_list = signal.get("keywords", [])
    keywords_text = " ".join(kw if isinstance(kw, str) else "" for kw in keywords_list)
    search_text = f"{title} {canonical} {keywords_text}"

    matches = []
    for theme_id, (include_patterns, exclusion_patterns) in _pattern_cache.items():
        # Check exclusions first
        excluded = False
        for pattern, kw in exclusion_patterns:
            if pattern.search(search_text):
                excluded = True
                break
        if excluded:
            continue

        # Check inclusion keywords
        for pattern, kw in include_patterns:
            if pattern.search(search_text):
                matches.append({"theme_id": theme_id, "matched_keyword": kw})
                break  # One match per theme is enough

    return matches


def match_all_signals(
    signals: List[dict],
    themes: Dict[str, dict],
) -> Tuple[Dict[str, List[dict]], List[dict]]:
    """Match all signals to themes.

    Returns:
        (theme_signals, unmatched_signals)
        theme_signals: dict theme_id -> list of signal dicts
        unmatched_signals: list of signals that matched no theme
    """
    pattern_cache = _build_keyword_patterns(themes)
    theme_signals: Dict[str, List[dict]] = defaultdict(list)
    unmatched: List[dict] = []

    for signal in signals:
        matches = match_signal_to_themes(signal, themes, _pattern_cache=pattern_cache)
        if matches:
            for m in matches:
                theme_signals[m["theme_id"]].append(signal)
        else:
            unmatched.append(signal)

    return dict(theme_signals), unmatched


# ---------------------------------------------------------------------------
# 4. Emergent Theme Discovery
# ---------------------------------------------------------------------------

def discover_emergent_themes(
    unmatched_signals: List[dict],
    params: dict,
) -> List[dict]:
    """Discover emergent themes from unmatched signals.

    Uses keyword co-occurrence + title similarity clustering.

    Returns list of emergent theme dicts.
    """
    min_size = params.get("emergent_cluster_min_size", 3)
    max_themes = params.get("emergent_max_themes", 5)
    similarity_threshold = params.get("emergent_title_similarity_threshold", 0.55)

    if len(unmatched_signals) < min_size:
        return []

    # Strategy 1: Title similarity clustering
    clusters: List[List[int]] = []
    assigned: set = set()

    for i in range(len(unmatched_signals)):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        title_i = (unmatched_signals[i].get("title", "") or "").lower()

        for j in range(i + 1, len(unmatched_signals)):
            if j in assigned:
                continue
            title_j = (unmatched_signals[j].get("title", "") or "").lower()
            ratio = difflib.SequenceMatcher(None, title_i, title_j).ratio()
            if ratio >= similarity_threshold:
                cluster.append(j)
                assigned.add(j)

        if len(cluster) >= min_size:
            clusters.append(cluster)

    # Strategy 2: Keyword co-occurrence clustering for remaining
    remaining_indices = [i for i in range(len(unmatched_signals)) if i not in assigned]
    if len(remaining_indices) >= min_size:
        kw_to_signals: Dict[str, List[int]] = defaultdict(list)
        for idx in remaining_indices:
            kws = unmatched_signals[idx].get("keywords", [])
            for kw in kws:
                if isinstance(kw, str) and len(kw) > 2:
                    kw_to_signals[kw.lower()].append(idx)

        # Find keywords that appear in >= min_size signals
        cooccurrence_threshold = params.get("emergent_cooccurrence_threshold", 3)
        for kw, indices in kw_to_signals.items():
            if len(indices) >= cooccurrence_threshold:
                new_cluster = [i for i in indices if i not in assigned]
                if len(new_cluster) >= min_size:
                    clusters.append(new_cluster)
                    assigned.update(new_cluster)

    # Build emergent themes from clusters
    emergent_themes: List[dict] = []
    for cluster_idx, cluster in enumerate(clusters[:max_themes]):
        cluster_signals = [unmatched_signals[i] for i in cluster]

        # Extract common keywords
        all_kws = Counter()
        for sig in cluster_signals:
            for kw in sig.get("keywords", []):
                if isinstance(kw, str):
                    all_kws[kw.lower()] += 1
        top_keywords = [kw for kw, cnt in all_kws.most_common(5)]

        # Generate label from most common keyword or first title
        label = top_keywords[0].title() if top_keywords else f"Emergent-{cluster_idx + 1}"

        emergent_themes.append({
            "theme_id": f"emergent_{cluster_idx + 1}",
            "label_en": f"Emergent: {label}",
            "label_ko": f"신흥테마: {label}",
            "priority": "LOW",
            "match_type": "emergent",
            "signal_count": len(cluster_signals),
            "signals": [s.get("signal_id", "") for s in cluster_signals],
            "signal_details": cluster_signals,
            "top_keywords": top_keywords,
        })

    return emergent_themes


# ---------------------------------------------------------------------------
# 5. Per-Theme Statistics
# ---------------------------------------------------------------------------

def compute_theme_stats(signals: List[dict]) -> dict:
    """Compute statistics for a set of signals belonging to a theme.

    Returns dict with psst stats, date distribution, steeps/wf distribution,
    temporal density.
    """
    if not signals:
        return {
            "signal_count": 0,
            "psst": {"min": 0, "max": 0, "avg": 0, "median": 0},
            "date_distribution": {},
            "steeps_distribution": {},
            "wf_distribution": {},
            "temporal_density": 0.0,
        }

    psst_scores = [s.get("psst_score", 0) or 0 for s in signals]

    # pSST stats
    psst_min = min(psst_scores)
    psst_max = max(psst_scores)
    psst_avg = statistics.mean(psst_scores)
    psst_median = statistics.median(psst_scores)

    # Date distribution
    date_dist: Dict[str, int] = Counter()
    for s in signals:
        d = s.get("scan_date", "")
        if d:
            date_dist[d] += 1

    # STEEPs distribution
    steeps_dist: Dict[str, int] = Counter()
    for s in signals:
        cat = s.get("primary_category", "")
        if cat:
            steeps_dist[cat] += 1

    # WF distribution
    wf_dist: Dict[str, int] = Counter()
    for s in signals:
        wf = s.get("source_wf", "")
        if wf:
            wf_dist[wf] += 1

    # Temporal density (signals per day)
    dates = sorted(date_dist.keys())
    if len(dates) >= 2:
        try:
            first = datetime.strptime(dates[0], "%Y-%m-%d")
            last = datetime.strptime(dates[-1], "%Y-%m-%d")
            span = (last - first).days or 1
            temporal_density = round(len(signals) / span, 2)
        except ValueError:
            temporal_density = float(len(signals))
    else:
        temporal_density = float(len(signals))

    return {
        "signal_count": len(signals),
        "psst": {
            "min": psst_min,
            "max": psst_max,
            "avg": round(psst_avg, 2),
            "median": round(psst_median, 2),
        },
        "date_distribution": dict(sorted(date_dist.items())),
        "steeps_distribution": dict(steeps_dist),
        "wf_distribution": dict(wf_dist),
        "temporal_density": temporal_density,
    }


# ---------------------------------------------------------------------------
# 6. Escalation Detection
# ---------------------------------------------------------------------------

def detect_escalation(signal_details: List[dict], thresholds: dict) -> dict:
    """Detect escalation for a single theme based on pSST over time.

    Uses linear regression on (day_offset, psst_score).

    Returns dict with slope, severity, burst info.
    """
    critical_slope = thresholds.get("critical_slope", 5.0)
    high_slope = thresholds.get("high_slope", 2.0)
    burst_factor = thresholds.get("burst_factor", 2.0)

    if len(signal_details) < 2:
        return {"slope": 0.0, "severity": "STABLE", "burst": False, "burst_rate": 0.0}

    # Sort by date
    dated = []
    for s in signal_details:
        d = s.get("scan_date", "")
        psst = s.get("psst_score", 0) or 0
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            dated.append((dt, psst))
        except ValueError:
            continue

    if len(dated) < 2:
        return {"slope": 0.0, "severity": "STABLE", "burst": False, "burst_rate": 0.0}

    dated.sort(key=lambda x: x[0])
    base_date = dated[0][0]

    # Convert to day offsets for regression
    x_vals = [(dt - base_date).days for dt, _ in dated]
    y_vals = [psst for _, psst in dated]

    # If all x_vals are the same day, group by date and average
    if x_vals[0] == x_vals[-1]:
        return {"slope": 0.0, "severity": "STABLE", "burst": False, "burst_rate": 0.0}

    # Linear regression
    try:
        slope, _intercept = statistics.linear_regression(x_vals, y_vals)
    except (statistics.StatisticsError, ValueError):
        # Manual fallback
        n = len(x_vals)
        mean_x = sum(x_vals) / n
        mean_y = sum(y_vals) / n
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
        denominator = sum((x - mean_x) ** 2 for x in x_vals)
        slope = numerator / denominator if denominator != 0 else 0.0

    slope = round(slope, 4)

    # Burst detection: signal count density change
    date_counts: Dict[str, int] = Counter()
    for s in signal_details:
        d = s.get("scan_date", "")
        if d:
            date_counts[d] += 1
    sorted_dates = sorted(date_counts.keys())
    burst = False
    burst_rate = 0.0
    if len(sorted_dates) >= 2:
        first_count = date_counts[sorted_dates[0]]
        last_count = date_counts[sorted_dates[-1]]
        if first_count > 0:
            burst_rate = round(last_count / first_count, 2)
            burst = burst_rate >= burst_factor

    # Severity classification
    if slope >= critical_slope:
        severity = "CRITICAL"
    elif slope >= high_slope:
        severity = "HIGH"
    elif slope > 0.1:  # Small positive
        severity = "MEDIUM"
    elif slope < -0.1:
        severity = "DECLINING"
    else:
        severity = "STABLE"

    return {
        "slope": slope,
        "severity": severity,
        "burst": burst,
        "burst_rate": burst_rate,
    }


def detect_compound_escalations(theme_escalations: List[dict]) -> List[dict]:
    """Detect compound escalation: 2+ themes escalating at CRITICAL or HIGH simultaneously.

    Args:
        theme_escalations: List of dicts with theme_id, severity, slope.

    Returns:
        List of compound escalation dicts.
    """
    # Filter to CRITICAL or HIGH
    escalating = [t for t in theme_escalations if t.get("severity") in ("CRITICAL", "HIGH")]

    if len(escalating) < 2:
        return []

    # Group: any 2+ CRITICAL/HIGH themes form a compound
    compound_ids = [t["theme_id"] for t in escalating]
    compound_severities = [t["severity"] for t in escalating]
    max_slope = max(t.get("slope", 0) for t in escalating)

    return [{
        "theme_ids": compound_ids,
        "severities": compound_severities,
        "theme_count": len(compound_ids),
        "max_slope": max_slope,
        "alert": "COMPOUND_ESCALATION",
    }]


# ---------------------------------------------------------------------------
# 7. Cross-WF Enrichment
# ---------------------------------------------------------------------------

def enrich_with_cross_wf(
    cross_map: dict,
    themes: Dict[str, dict],
) -> List[dict]:
    """Tag cross-evolution-map correlations to matching themes.

    Returns enriched correlation list with 'matched_themes' field.
    """
    correlations = cross_map.get("correlations", [])
    if not correlations:
        return []

    pattern_cache = _build_keyword_patterns(themes)
    enriched = []

    for corr in correlations:
        # Build searchable text from both source and target
        source_title = corr.get("source_title", "") or ""
        target_title = corr.get("target_title", "") or ""
        source_kws = corr.get("source_keywords", [])
        target_kws = corr.get("target_keywords", [])
        all_kws = " ".join(
            kw if isinstance(kw, str) else "" for kw in source_kws + target_kws
        )
        search_text = f"{source_title} {target_title} {all_kws}"

        matched_themes = set()
        for theme_id, (include_patterns, exclusion_patterns) in pattern_cache.items():
            # Check exclusions
            excluded = False
            for pattern, kw in exclusion_patterns:
                if pattern.search(search_text):
                    excluded = True
                    break
            if excluded:
                continue
            # Check inclusions
            for pattern, kw in include_patterns:
                if pattern.search(search_text):
                    matched_themes.add(theme_id)
                    break

        enriched_corr = dict(corr)
        enriched_corr["matched_themes"] = sorted(matched_themes)
        enriched.append(enriched_corr)

    return enriched


# ---------------------------------------------------------------------------
# 8. Main Orchestration
# ---------------------------------------------------------------------------

def run_theme_discovery(
    registry_path: str,
    theme_config_path: str,
    evolution_maps: Dict[str, dict],
    evolution_indices: Dict[str, dict],
    cross_evolution_map: dict,
    scan_date: str,
) -> dict:
    """Main entry point: collect signals, match themes, discover emergent,
    compute stats, detect escalations, enrich cross-WF.

    Returns the complete output JSON structure.
    """
    # Load config
    sot_config = load_sot_config(registry_path)
    themes = load_theme_config(theme_config_path)

    lookback_days = sot_config.get("lookback_days", 7)
    min_signals = sot_config.get("min_signals_for_theme", 2)
    esc_thresholds = sot_config.get("escalation_thresholds", {
        "critical_slope": 5.0, "high_slope": 2.0, "burst_factor": 2.0,
    })

    # Collect all signals (v3.4.0: include_faded_threads from SOT)
    include_faded = sot_config.get("include_faded_threads", True)
    all_signals = collect_signals(
        evolution_maps, evolution_indices, lookback_days, scan_date,
        include_faded_threads=include_faded,
    )
    logger.info(f"Collected {len(all_signals)} total signals (lookback={lookback_days}, include_faded={include_faded})")

    # Compute full-history thread trends (v3.4.0)
    min_app = sot_config.get("trend_analysis_min_appearances", 3)
    thread_trends = compute_all_thread_trends(evolution_indices, min_appearances=min_app, slope_thresholds=esc_thresholds)
    logger.info(f"Computed trends for {len(thread_trends)} threads")

    # Match to config themes
    theme_signals, unmatched = match_all_signals(all_signals, themes)

    # Build config_themes output
    config_themes: List[dict] = []
    all_escalation_results: List[dict] = []

    for theme_id, theme_def in themes.items():
        sigs = theme_signals.get(theme_id, [])
        if len(sigs) < min_signals:
            continue

        stats = compute_theme_stats(sigs)
        escalation = detect_escalation(sigs, esc_thresholds)

        esc_result = {
            "theme_id": theme_id,
            "severity": escalation["severity"],
            "slope": escalation["slope"],
        }
        all_escalation_results.append(esc_result)

        # Cross-WF correlation count for this theme
        cross_wf_count = 0
        if cross_evolution_map:
            enriched = enrich_with_cross_wf(cross_evolution_map, {theme_id: theme_def})
            cross_wf_count = sum(1 for c in enriched if theme_id in c.get("matched_themes", []))

        config_themes.append({
            "theme_id": theme_id,
            "label_ko": theme_def.get("label_ko", ""),
            "label_en": theme_def.get("label_en", ""),
            "priority": theme_def.get("priority", "MEDIUM"),
            "match_type": "config",
            "signals": [s.get("signal_id", "") for s in sigs],
            "signal_details": sigs,
            "stats": stats,
            "escalation": escalation,
            "cross_wf_correlations": cross_wf_count,
        })

    # Sort config_themes by priority then signal count
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    config_themes.sort(
        key=lambda t: (priority_order.get(t["priority"], 99), -t["stats"]["signal_count"])
    )

    # Discover emergent themes
    emergent_params = {
        "emergent_cluster_min_size": sot_config.get("emergent_cluster_min_size", 3),
        "emergent_max_themes": sot_config.get("emergent_max_themes", 5),
        "emergent_cooccurrence_threshold": sot_config.get("emergent_cooccurrence_threshold", 3),
        "emergent_title_similarity_threshold": sot_config.get("emergent_title_similarity_threshold", 0.55),
    }
    emergent_themes = discover_emergent_themes(unmatched, emergent_params)

    # Detect compound escalations
    compound_escalations = detect_compound_escalations(all_escalation_results)

    # Build output
    output = {
        "engine": ENGINE_ID,
        "scan_date": scan_date,
        "lookback_days": lookback_days,
        "lookback_mode": "unlimited" if lookback_days == 0 else f"{lookback_days}_days",
        "include_faded_threads": include_faded,
        "total_signals_collected": len(all_signals),
        "config_themes": config_themes,
        "emergent_themes": emergent_themes,
        "unmatched_signals": [
            {"signal_id": s.get("signal_id", ""), "title": s.get("title", "")}
            for s in unmatched
            if not any(s in et.get("signal_details", []) for et in emergent_themes)
        ],
        "compound_escalations": compound_escalations,
        "thread_trends": thread_trends,
    }

    return output


# ---------------------------------------------------------------------------
# 9. File I/O Helpers
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


# ---------------------------------------------------------------------------
# 10. CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Theme Discovery Engine — Config-Driven + Emergent Theme Discovery"
    )
    parser.add_argument(
        "--registry",
        default="env-scanning/config/workflow-registry.yaml",
        help="Path to workflow-registry.yaml (SOT)",
    )
    parser.add_argument(
        "--theme-config",
        default="env-scanning/config/timeline-themes.yaml",
        help="Path to timeline-themes.yaml",
    )
    parser.add_argument("--wf1-evolution-map", default="", help="WF1 evolution-map JSON")
    parser.add_argument("--wf2-evolution-map", default="", help="WF2 evolution-map JSON")
    parser.add_argument("--wf3-evolution-map", default="", help="WF3 evolution-map JSON")
    parser.add_argument("--wf4-evolution-map", default="", help="WF4 evolution-map JSON")
    parser.add_argument("--wf1-index", default="", help="WF1 evolution-index JSON")
    parser.add_argument("--wf2-index", default="", help="WF2 evolution-index JSON")
    parser.add_argument("--wf3-index", default="", help="WF3 evolution-index JSON")
    parser.add_argument("--wf4-index", default="", help="WF4 evolution-index JSON")
    parser.add_argument("--cross-evolution-map", default="", help="Cross-evolution-map JSON")
    parser.add_argument(
        "--scan-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Scan date (YYYY-MM-DD)",
    )
    parser.add_argument("--output", "-o", required=True, help="Output JSON path")

    args = parser.parse_args()

    try:
        # Load input files
        evo_maps = {}
        for wf, attr in [("wf1", "wf1_evolution_map"), ("wf2", "wf2_evolution_map"),
                         ("wf3", "wf3_evolution_map"), ("wf4", "wf4_evolution_map")]:
            path = getattr(args, attr)
            evo_maps[wf] = _load_json(path)

        evo_indices = {}
        for wf, attr in [("wf1", "wf1_index"), ("wf2", "wf2_index"),
                         ("wf3", "wf3_index"), ("wf4", "wf4_index")]:
            path = getattr(args, attr)
            evo_indices[wf] = _load_json(path)

        cross_map = _load_json(args.cross_evolution_map)

        # Run discovery
        result = run_theme_discovery(
            registry_path=args.registry,
            theme_config_path=args.theme_config,
            evolution_maps=evo_maps,
            evolution_indices=evo_indices,
            cross_evolution_map=cross_map,
            scan_date=args.scan_date,
        )

        # Write output
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"Theme analysis written: {args.output}")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Theme discovery failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
