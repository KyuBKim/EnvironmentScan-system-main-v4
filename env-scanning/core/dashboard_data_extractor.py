#!/usr/bin/env python3
"""
Dashboard Data Extractor — Hallucination Prevention Core Module (v3.5.1)

All quantitative data is computed directly from source JSON files.
LLM-generated numbers in report prose are NEVER used.
Analytical narratives are extracted verbatim from approved reports — never regenerated.

Usage:
    python3 env-scanning/core/dashboard_data_extractor.py \
        --date 2026-03-24 \
        --registry env-scanning/config/workflow-registry.yaml \
        --status-file env-scanning/integrated/logs/master-status-2026-03-24.json \
        --output env-scanning/integrated/analysis/dashboard-data-2026-03-24.json
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STEEPS_MAP = {
    "S_Social": "S", "T_Technological": "T", "E_Economic": "E",
    "E_Environmental": "Env", "P_Political": "P", "s_spiritual": "s",
}
STEEPS_LABELS = {
    "S": "사회 Social (S)", "T": "기술 Technological (T)",
    "E": "경제 Economic (E)", "Env": "환경 Environmental (E)",
    "P": "정치 Political (P)", "s": "정신 Spiritual (s)",
}

# Report section headings (skeleton-guaranteed patterns)
NARRATIVE_SECTIONS = [
    "1. Executive Summary",
    "2. Newly Detected Signals",
    "3. Existing Signal Updates",
    "4. Patterns and Connections",
    "5. Strategic Implications",
    "6. Plausible Scenarios",
    "7. Confidence Analysis",
    "8. Appendix",
]


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Optional[Dict]:
    """Load JSON file or return None on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  WARN: Cannot load {path}: {e}", file=sys.stderr)
        return None


def load_yaml_simple(path: Path) -> Optional[Dict]:
    """Load YAML using PyYAML if available, else minimal parser."""
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except ImportError:
        print("  WARN: PyYAML not available, using minimal parser", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# STEEPs Computation (hallucination-proof)
# ---------------------------------------------------------------------------

def normalize_steeps(raw_category: str) -> str:
    """Normalize any STEEPs category string to short code."""
    if not raw_category:
        return "?"
    # Try direct mapping first
    if raw_category in STEEPS_MAP:
        return STEEPS_MAP[raw_category]
    # Split on underscore: "T_Technological" → "T"
    parts = raw_category.split("_")
    code = parts[0]
    # Handle "E" ambiguity: if second part starts with "E" for Environmental
    if code == "E" and len(parts) > 1 and parts[1].startswith("Env"):
        return "Env"
    if code in ("S", "T", "E", "P", "s"):
        return code
    return "?"


def compute_steeps_from_classified(
    classified: Dict, limit: Optional[int] = None, ranked_ids: Optional[set] = None
) -> Dict[str, int]:
    """
    Count STEEPs distribution directly from classified-signals JSON.

    Args:
        classified: Parsed classified-signals JSON
        limit: If set, only count first N signals (by insertion order)
        ranked_ids: If set, only count signals with these IDs
    """
    counter = Counter()
    for sig in classified.get("signals", []):
        # WF1/WF2/WF4 use "category", WF3 uses "steeps_category"
        cat = sig.get("category") or sig.get("steeps_category", "")
        sid = sig.get("id", "")

        if ranked_ids and sid not in ranked_ids:
            continue

        code = normalize_steeps(cat)
        if code != "?":
            counter[code] += 1

    return dict(counter)


def compute_fssf_from_classified(
    classified: Dict, ranked_ids: Optional[set] = None
) -> Dict[str, int]:
    """Count FSSF distribution directly from classified-signals JSON."""
    counter = Counter()
    for sig in classified.get("signals", []):
        sid = sig.get("id", "")
        if ranked_ids and sid not in ranked_ids:
            continue
        fssf = sig.get("fssf_type", "")
        if fssf:
            counter[fssf] += 1
    return dict(counter)


def compute_three_horizons(
    classified: Dict, ranked_ids: Optional[set] = None
) -> Dict[str, int]:
    """Count Three Horizons distribution."""
    counter = Counter()
    for sig in classified.get("signals", []):
        sid = sig.get("id", "")
        if ranked_ids and sid not in ranked_ids:
            continue
        h = sig.get("three_horizons", "")
        if h:
            counter[h] += 1
    return dict(counter)


# ---------------------------------------------------------------------------
# Top Signals (ranked + classified JOIN)
# ---------------------------------------------------------------------------

def build_top_signals(
    ranked: Dict, classified: Dict, n: int = 20
) -> List[Dict]:
    """
    Join priority-ranked ordering with classified-signals detail.
    All data from source JSON — zero LLM regeneration.
    """
    classified_list = classified.get("signals") or classified.get("items") or []
    classified_by_id = {s["id"]: s for s in classified_list}
    result = []

    for r in ranked.get("ranked_signals", [])[:n]:
        detail = classified_by_id.get(r["id"], {})
        cls = detail.get("classification") or {}  # WF1 nested structure

        # STEEPs: WF3/WF4 → .category, WF2 → .steeps_primary, WF1 → .classification.steeps_category
        cat_raw = (detail.get("category")
                   or detail.get("steeps_category")
                   or detail.get("steeps_primary", "")          # WF2
                   or cls.get("steeps_category", ""))            # WF1 nested

        # Impact: WF3/WF4 → .impact_score, WF2 → .significance, WF1 → .classification.impact_score
        # WF1 uses 0-100 scale; WF2/WF3/WF4 use 0-10. Normalize to 0-10.
        impact = (detail.get("impact_score")
                  or detail.get("significance")                  # WF2
                  or cls.get("impact_score")                     # WF1 nested
                  or 0)
        if isinstance(impact, (int, float)) and impact > 10:
            impact = round(impact / 10.0, 1)                     # 0-100 → 0-10

        # Novelty: WF3/WF4 → .novelty_score, WF2 → .novelty, WF1 → .classification.novelty
        # Same normalization: WF1 uses 0-100 scale
        novelty = (detail.get("novelty_score")
                   or detail.get("novelty")                      # WF2
                   or cls.get("novelty")                         # WF1 nested
                   or 0)
        if isinstance(novelty, (int, float)) and novelty > 10:
            novelty = round(novelty / 10.0, 1)                   # 0-100 → 0-10

        # Urgency: WF1 → .classification.urgency
        # Same normalization: WF1 uses 0-100 scale
        urgency = (detail.get("urgency_score")
                   or cls.get("urgency")                         # WF1 nested
                   or 0)
        if isinstance(urgency, (int, float)) and urgency > 10:
            urgency = round(urgency / 10.0, 1)                   # 0-100 → 0-10

        result.append({
            "rank": r.get("rank", 0),
            "id": r.get("id", ""),
            "title": r.get("title", ""),
            "title_ko": detail.get("title_ko", ""),
            "steeps": normalize_steeps(cat_raw),
            "steeps_raw": cat_raw,
            "fssf_type": detail.get("fssf_type", r.get("fssf_type", "")),
            "three_horizons": detail.get("three_horizons", r.get("three_horizons", "")),
            "impact_score": impact,
            "novelty_score": novelty,
            "urgency_score": urgency,
            "psst_score": r.get("psst_score", 0),
            "psst_grade": r.get("psst_grade", ""),
            "source": detail.get("source", r.get("source", "")),
            "keywords": detail.get("keywords", []),
            "cross_impact": detail.get("cross_impact", []),
        })

    return result


# ---------------------------------------------------------------------------
# Cross-WF Reinforcement Detection
# ---------------------------------------------------------------------------

def _tokenize_signal(sig: Dict) -> set:
    """
    Extract a unified word-level term set from a signal.
    Multi-word keyword phrases are split into individual words.
    Stopwords removed to reduce noise in Jaccard computation.
    Works with both WF1/WF2/WF4 (keywords field) and WF3 (no keywords, title only).

    v1.1.0: Added abstract/content extraction and cross_impact terms
    for richer overlap detection across heterogeneous WF sources.
    """
    STOPWORDS = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "is", "are",
                 "and", "or", "with", "by", "as", "from", "that", "this", "it", "be",
                 "was", "were", "has", "have", "had", "not", "but", "if", "its", "can",
                 "will", "may", "than", "—", "-", "–", ":", "|", "new", "also", "more",
                 "about", "into", "over", "after", "between", "through", "would", "could",
                 "should", "their", "they", "which", "other", "some", "such", "what",
                 "no", "so", "do", "up", "we", "he", "my", "us", "am", "an"}
    # NOTE: min length > 1 (not > 2) — critical 2-char domain terms must be preserved:
    # AI, EU, US, UK, UN, ML, EV, 5G, AR, VR, etc.
    words = set()

    def _add_text(text: str):
        for w in text.lower().split():
            w = w.strip(".,;:!?()[]\"'")
            if w and w not in STOPWORDS and len(w) > 1:
                words.add(w)

    # Keywords: split multi-word phrases into individual words (highest signal)
    for kw in sig.get("keywords", []):
        _add_text(kw)

    # Title words
    _add_text(sig.get("title", ""))

    # Abstract/content (first 200 chars to avoid noise from long text)
    abstract = ""
    content = sig.get("content", {})
    if isinstance(content, dict):
        abstract = content.get("abstract", "")
    elif isinstance(content, str):
        abstract = content
    if abstract:
        _add_text(abstract[:200])

    # Cross-impact terms (signals that reference other STEEPs)
    for ci in sig.get("cross_impact", []):
        if isinstance(ci, dict):
            _add_text(ci.get("description", "")[:100])
        elif isinstance(ci, str):
            _add_text(ci[:100])

    # WF3: also use section name as context
    section = sig.get("section", "")
    if section:
        words.add(section.lower())

    return words


def detect_cross_wf_reinforcements(
    all_wf_signals: Dict[str, List[Dict]],
    threshold: float = 0.10,
    min_shared_terms: int = 3,
) -> List[Dict]:
    """
    Detect signals confirmed across 2+ workflows by word-level overlap.

    v1.2.0: threshold and min_shared_terms are SOT-bound (thresholds.yaml).
    Two-gate filter: Jaccard ≥ threshold AND shared_terms ≥ min_shared_terms.
    The min_shared_terms gate prevents low-information matches (e.g., 2 generic
    terms shared across large token sets producing Jaccard ≈ 0.10).
    Deterministic string matching — no LLM judgment.
    """
    # Build word-level index per WF
    wf_keywords = {}
    for wf_key, signals in all_wf_signals.items():
        for sig in signals:
            terms = _tokenize_signal(sig)
            if terms:
                wf_keywords.setdefault(wf_key, []).append({
                    "id": sig.get("id", ""),
                    "title": sig.get("title", ""),
                    "terms": terms,
                })

    reinforcements = []
    wf_keys = list(wf_keywords.keys())

    for i, wf_a in enumerate(wf_keys):
        for wf_b in wf_keys[i + 1:]:
            for sig_a in wf_keywords[wf_a]:
                for sig_b in wf_keywords[wf_b]:
                    if not sig_a["terms"] or not sig_b["terms"]:
                        continue
                    overlap = sig_a["terms"] & sig_b["terms"]
                    union = sig_a["terms"] | sig_b["terms"]
                    jaccard = len(overlap) / len(union) if union else 0
                    if jaccard >= threshold and len(overlap) >= min_shared_terms:
                        reinforcements.append({
                            "wf_a": wf_a, "signal_a": sig_a["id"],
                            "wf_b": wf_b, "signal_b": sig_b["id"],
                            "overlap_score": round(jaccard, 3),
                            "shared_terms": sorted(overlap)[:10],
                        })

    # Deduplicate by signal pair
    seen = set()
    unique = []
    for r in reinforcements:
        pair = tuple(sorted([r["signal_a"], r["signal_b"]]))
        if pair not in seen:
            seen.add(pair)
            unique.append(r)

    return unique


# ---------------------------------------------------------------------------
# Risk Probability (formula-based, deterministic)
# ---------------------------------------------------------------------------

def compute_risk_probability(
    signals: List[Dict], cross_wf_count: int, max_wfs: int = 4
) -> float:
    """
    Deterministic risk probability computation.
    Formula: (cross_wf_ratio * 0.5 + avg_impact_ratio * 0.5) * 100
    Same input → always same output.
    """
    if not signals:
        return 0.0
    avg_impact = mean(s.get("impact_score", 0) for s in signals)
    cross_ratio = min(cross_wf_count / max_wfs, 1.0)
    impact_ratio = avg_impact / 10.0
    probability = (cross_ratio * 0.5 + impact_ratio * 0.5) * 100
    return round(min(probability, 95.0), 1)


# ---------------------------------------------------------------------------
# Timeline Map Extraction
# ---------------------------------------------------------------------------

def extract_timeline_map(timeline_path: Path) -> Tuple[Optional[str], Optional[Dict]]:
    """
    Read timeline map markdown verbatim.
    Timeline map is a standalone deliverable from Step 5.1.4.

    Returns:
        (content, meta) tuple.
        content: raw markdown or None.
        meta: {"source": "exact"|"fallback", "file": filename, "fallback_date": date_str}
              or None if no timeline map found.

    v1.2.0: Returns metadata tuple for fallback transparency.
    If today's file is missing, falls back to the most recent
    timeline-map-YYYY-MM-DD.md in the same directory.
    """
    if timeline_path.exists():
        content = timeline_path.read_text(encoding="utf-8")
        return content, {"source": "exact", "file": timeline_path.name}

    # Fallback: find most recent timeline map in the same directory
    parent = timeline_path.parent
    if not parent.exists():
        return None, None

    timeline_files = sorted(
        parent.glob("timeline-map-????-??-??.md"),
        reverse=True,
    )
    # Exclude prefilled files
    timeline_files = [f for f in timeline_files if "-prefilled" not in f.name]

    if timeline_files:
        latest = timeline_files[0]
        content = latest.read_text(encoding="utf-8")
        # Extract date from filename: timeline-map-YYYY-MM-DD.md
        import re
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", latest.name)
        fallback_date = date_match.group(1) if date_match else "unknown"
        print(f"  Timeline map: fallback to {latest.name} ({len(content):,} chars)")
        return content, {
            "source": "fallback",
            "file": latest.name,
            "fallback_date": fallback_date,
        }

    return None, None


# ---------------------------------------------------------------------------
# Narrative Extraction (verbatim from approved report)
# ---------------------------------------------------------------------------

def extract_narrative_sections(report_md: str) -> Dict[str, str]:
    """
    Extract narrative sections from integrated report by heading pattern.
    Verbatim extraction — NEVER regenerated. Zero hallucination.

    Uses skeleton-guaranteed heading patterns: "## N. Section Name"
    """
    sections = {}
    current_key = None
    current_lines = []

    for line in report_md.split("\n"):
        # Match "## N. Title" pattern (skeleton headings)
        m = re.match(r"^##\s+(\d+)\.\s+(.+)", line)
        if m:
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            section_num = m.group(1)
            section_name = m.group(2).strip()
            current_key = f"{section_num}. {section_name}"
            current_lines = []
        elif current_key:
            current_lines.append(line)

    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def get_section_by_number(narratives: Dict[str, str], section_num: int) -> str:
    """
    Retrieve a narrative section by its number prefix, regardless of title language.
    Works for both EN ("4. Patterns and Connections") and KO ("4. 패턴 및 연결고리").
    Returns empty string if no matching section found.
    """
    prefix = f"{section_num}."
    for key, value in narratives.items():
        if key.startswith(prefix):
            return value
    return ""


# ---------------------------------------------------------------------------
# Main Extractor
# ---------------------------------------------------------------------------

class DashboardDataExtractor:
    """
    Extracts all dashboard data from source JSON files.
    ALL quantitative data is Python-computed. ZERO LLM dependency.
    """

    def __init__(self, date: str, base_path: Path, master_status: Dict, registry: Optional[Dict] = None):
        self.date = date
        self.base = base_path
        self.status = master_status
        self.registry = registry or {}

        # Workflow configs from master-status
        self.wf_results = master_status.get("workflow_results", {})

        # Data cache
        self._classified = {}
        self._ranked = {}

    def _resolve_wf_paths(self, wf_key: str) -> Tuple[Path, Path]:
        """Resolve classified-signals and priority-ranked paths for a WF."""
        wf_dirs = {
            "wf1-general": "wf1-general",
            "wf2-arxiv": "wf2-arxiv",
            "wf3-naver": "wf3-naver",
            "wf4-multiglobal-news": "wf4-multiglobal-news",
        }
        wf_dir = wf_dirs.get(wf_key, wf_key)
        classified_path = self.base / f"{wf_dir}/structured/classified-signals-{self.date}.json"
        ranked_path = self.base / f"{wf_dir}/analysis/priority-ranked-{self.date}.json"
        return classified_path, ranked_path

    def _load_wf_data(self, wf_key: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Load and cache classified + ranked data for a WF."""
        if wf_key not in self._classified:
            c_path, r_path = self._resolve_wf_paths(wf_key)
            self._classified[wf_key] = load_json(c_path)
            self._ranked[wf_key] = load_json(r_path)
        return self._classified[wf_key], self._ranked[wf_key]

    def _get_selected_ids(self, wf_key: str) -> Optional[set]:
        """
        Get IDs of selected signals (top N from ranking).
        N = signal_count from master-status.
        """
        wf_info = self.wf_results.get(wf_key, {})
        n = wf_info.get("signal_count")
        if not n:
            return None

        _, ranked = self._load_wf_data(wf_key)
        if not ranked:
            return None

        return set(
            s["id"] for s in ranked.get("ranked_signals", [])[:n]
        )

    def extract_kpis(self) -> Dict:
        """Extract KPIs from master-status.json (deterministic)."""
        total = sum(
            wf.get("signal_count", 0) for wf in self.wf_results.values()
        )
        return {
            "total_signals": total,
            "per_workflow": {
                k: {
                    "signal_count": v.get("signal_count", 0),
                    "validation": v.get("validation", "N/A"),
                    "status": v.get("status", "unknown"),
                }
                for k, v in self.wf_results.items()
            },
            "integration": self.status.get("integration_result", {}),
            "master_gates": self.status.get("master_gates", {}),
        }

    def extract_steeps(self) -> Dict:
        """
        Compute STEEPs distribution per WF and total.
        Python-computed from classified-signals — NOT from report text.
        """
        wf_steeps = {}
        total = Counter()

        for wf_key in self.wf_results:
            classified, _ = self._load_wf_data(wf_key)
            if not classified:
                continue

            selected_ids = self._get_selected_ids(wf_key)
            dist = compute_steeps_from_classified(classified, ranked_ids=selected_ids)
            wf_steeps[wf_key] = dist
            total.update(dist)

        return {
            "per_workflow": wf_steeps,
            "total": dict(total),
            "total_count": sum(total.values()),
            "labels": STEEPS_LABELS,
        }

    def extract_fssf(self) -> Dict:
        """Compute FSSF distribution for WF3/WF4 (Python-computed)."""
        fssf_wfs = {}
        for wf_key in ["wf3-naver", "wf4-multiglobal-news"]:
            if wf_key not in self.wf_results:
                continue
            classified, _ = self._load_wf_data(wf_key)
            if not classified:
                continue
            selected_ids = self._get_selected_ids(wf_key)
            fssf_wfs[wf_key] = compute_fssf_from_classified(classified, ranked_ids=selected_ids)

        total = Counter()
        for dist in fssf_wfs.values():
            total.update(dist)

        return {"per_workflow": fssf_wfs, "total": dict(total)}

    def extract_top_signals(self) -> Dict:
        """Build per-WF top signal lists from ranked+classified JOIN."""
        wf_tops = {}
        for wf_key in self.wf_results:
            classified, ranked = self._load_wf_data(wf_key)
            if not classified or not ranked:
                continue
            n = self.wf_results[wf_key].get("signal_count", 10)
            wf_tops[wf_key] = build_top_signals(ranked, classified, n)

        return wf_tops

    def _load_thresholds(self) -> Dict:
        """Load thresholds.yaml for SOT-bound parameters."""
        thresholds_path = self.base / "config" / "thresholds.yaml"
        return load_yaml_simple(thresholds_path) or {}

    def extract_cross_wf(self) -> Dict:
        """Detect cross-WF reinforcements (keyword-based, deterministic).
        Threshold and max_results read from thresholds.yaml (SOT binding)."""
        all_signals = {}
        for wf_key in self.wf_results:
            classified, ranked = self._load_wf_data(wf_key)
            if not classified or not ranked:
                continue
            n = self.wf_results[wf_key].get("signal_count", 10)
            selected_ids = set(s["id"] for s in ranked.get("ranked_signals", [])[:n])
            all_signals[wf_key] = [
                s for s in classified.get("signals", []) if s["id"] in selected_ids
            ]

        # SOT-bound: read parameters from thresholds.yaml
        thresholds = self._load_thresholds()
        db_cfg = thresholds.get("dashboard", {}).get("cross_wf_reinforcement", {})
        threshold = db_cfg.get("threshold", 0.10)
        min_shared_terms = db_cfg.get("min_shared_terms", 3)
        max_results = db_cfg.get("max_results", 20)

        reinforcements = detect_cross_wf_reinforcements(
            all_signals, threshold=threshold, min_shared_terms=min_shared_terms
        )

        return {
            "reinforcement_count": len(reinforcements),
            "reinforcements": reinforcements[:max_results],
        }

    def _load_risk_categories(self) -> Dict:
        """Load risk categories from YAML config (SOT: integration.dashboard.risk_categories).
        Falls back to inline defaults if config unavailable."""
        defaults = {
            "에너지 차단 (Energy Disruption)": {"steeps": ["P", "E"], "keywords": ["hormuz", "energy", "oil"]},
            "AI 거버넌스 갭 (AI Governance Gap)": {"steeps": ["T", "s"], "keywords": ["ai", "autonomous", "safety"]},
            "식량안보 악화 (Food Security)": {"steeps": ["E"], "keywords": ["food", "fertilizer", "agriculture"]},
            "경기 둔화 (Economic Slowdown)": {"steeps": ["E"], "keywords": ["recession", "growth", "gdp"]},
            "클린에너지 가속 (Clean Energy)": {"steeps": ["Env", "T"], "keywords": ["clean", "renewable", "ev"]},
            "생물보안 사고 (Biosecurity)": {"steeps": ["T", "P"], "keywords": ["bio", "pathogen", "biosecurity"]},
        }
        # Try loading from YAML config
        risk_path = self.registry.get("integration", {}).get("dashboard", {}).get("risk_categories", "") if self.registry else ""
        if risk_path:
            full_path = self.base.parent / risk_path if not Path(risk_path).is_absolute() else Path(risk_path)
            data = load_json(full_path) if full_path.suffix == '.json' else None
            if data is None:
                try:
                    import yaml
                    if full_path.exists():
                        data = yaml.safe_load(full_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            if data and "categories" in data:
                result = {}
                for cat_id, cat_def in data["categories"].items():
                    label = f"{cat_def.get('label_ko', cat_id)} ({cat_def.get('label_en', cat_id)})"
                    result[label] = {
                        "steeps": cat_def.get("steeps", []),
                        "keywords": cat_def.get("keywords", []),
                    }
                return result
        return defaults

    def extract_risk_matrix(self) -> List[Dict]:
        """Compute risk matrix with formula-based probabilities."""
        steeps_data = self.extract_steeps()
        cross_wf = self.extract_cross_wf()

        risk_categories = self._load_risk_categories()

        results = []
        for category, config in risk_categories.items():
            # Count matching signals across all WFs
            matching_signals = []
            matching_wfs = set()
            for wf_key in self.wf_results:
                classified, ranked = self._load_wf_data(wf_key)
                if not classified or not ranked:
                    continue
                n = self.wf_results[wf_key].get("signal_count", 10)
                selected_ids = set(s["id"] for s in ranked.get("ranked_signals", [])[:n])
                for sig in classified.get("signals", []):
                    if sig["id"] not in selected_ids:
                        continue
                    cat = normalize_steeps(sig.get("category") or sig.get("steeps_category", ""))
                    kws = set(k.lower() for k in sig.get("keywords", []))
                    title_words = set(sig.get("title", "").lower().split())
                    all_terms = kws | title_words

                    steeps_match = cat in config["steeps"]
                    keyword_match = any(k in " ".join(all_terms) for k in config["keywords"])

                    if steeps_match and keyword_match:
                        matching_signals.append(sig)
                        matching_wfs.add(wf_key)

            prob = compute_risk_probability(matching_signals, len(matching_wfs))
            avg_impact = round(mean(s.get("impact_score", 0) for s in matching_signals), 1) if matching_signals else 0

            results.append({
                "category": category,
                "probability": prob,
                "avg_impact": avg_impact,
                "signal_count": len(matching_signals),
                "cross_wf_count": len(matching_wfs),
                "source_wfs": sorted(matching_wfs),
            })

        # Sort by probability descending
        results.sort(key=lambda x: x["probability"], reverse=True)
        return results

    def extract_narratives(self, integrated_report_path: Path) -> Dict[str, str]:
        """Extract narrative sections verbatim from approved integrated report."""
        if not integrated_report_path.exists():
            return {}
        content = integrated_report_path.read_text(encoding="utf-8")
        return extract_narrative_sections(content)

    def extract_all(self, integrated_report_path: Optional[Path] = None) -> Dict:
        """Run full extraction pipeline. Output = dashboard-data.json."""
        print(f"[DashboardDataExtractor] Extracting data for {self.date}...")

        kpis = self.extract_kpis()
        print(f"  KPIs: {kpis['total_signals']} total signals")

        steeps = self.extract_steeps()
        print(f"  STEEPs: {steeps['total']} (computed from classified-signals)")

        fssf = self.extract_fssf()
        print(f"  FSSF: {fssf['total']}")

        top_signals = self.extract_top_signals()
        total_tops = sum(len(v) for v in top_signals.values())
        print(f"  Top signals: {total_tops} across {len(top_signals)} WFs")

        cross_wf = self.extract_cross_wf()
        print(f"  Cross-WF reinforcements: {cross_wf['reinforcement_count']}")

        risk_matrix = self.extract_risk_matrix()
        print(f"  Risk matrix: {len(risk_matrix)} categories")

        narratives = {}
        narratives_ko = {}
        if integrated_report_path:
            narratives = self.extract_narratives(integrated_report_path)
            print(f"  Narratives (EN): {len(narratives)} sections extracted")

            # Auto-infer KO report path: {name}.md → {name}-ko.md
            # Convention matches SOT deliverables.report_ko pattern
            ko_path = integrated_report_path.with_name(
                integrated_report_path.stem + "-ko" + integrated_report_path.suffix
            )
            if ko_path.exists():
                narratives_ko = self.extract_narratives(ko_path)
                print(f"  Narratives (KO): {len(narratives_ko)} sections extracted")
            else:
                print(f"  Narratives (KO): not found ({ko_path.name})")

        # Timeline map (verbatim, with fallback metadata)
        int_root = self.base / "integrated" / "reports" / "daily"
        timeline_path = int_root / f"timeline-map-{self.date}.md"
        timeline_md, timeline_meta = extract_timeline_map(timeline_path)
        if timeline_md and timeline_meta:
            src = timeline_meta.get("source", "unknown")
            if src == "fallback":
                print(f"  Timeline map: FALLBACK from {timeline_meta['fallback_date']} ({len(timeline_md):,} chars)")
            else:
                print(f"  Timeline map: {len(timeline_md):,} chars")
        else:
            print(f"  Timeline map: not found ({timeline_path.name})")

        result = {
            "metadata": {
                "date": self.date,
                "extractor_version": "1.2.0",
                "source": "dashboard_data_extractor.py",
                "note": "All quantitative data computed by Python. LLM report numbers NOT used.",
            },
            "kpis": kpis,
            "steeps": steeps,
            "fssf": fssf,
            "top_signals": top_signals,
            "cross_wf": cross_wf,
            "risk_matrix": risk_matrix,
            "narratives": narratives,
            "narratives_ko": narratives_ko,
            "timeline_map": timeline_md,
            "timeline_map_meta": timeline_meta,
        }

        print(f"[DashboardDataExtractor] Extraction complete.")
        return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Dashboard Data Extractor")
    parser.add_argument("--date", required=True, help="Scan date (YYYY-MM-DD)")
    parser.add_argument("--registry", required=True, help="Path to workflow-registry.yaml")
    parser.add_argument("--status-file", required=True, help="Path to master-status JSON")
    parser.add_argument("--output", required=True, help="Output path for dashboard-data.json")
    parser.add_argument("--integrated-report", help="Path to integrated report .md (for narrative extraction)")
    args = parser.parse_args()

    base_path = Path(args.registry).parent.parent  # env-scanning/config/ → env-scanning/
    status = load_json(Path(args.status_file))
    if not status:
        print("FATAL: Cannot load master-status file", file=sys.stderr)
        sys.exit(1)

    registry = load_yaml_simple(Path(args.registry))

    extractor = DashboardDataExtractor(
        date=args.date,
        base_path=base_path,
        master_status=status,
        registry=registry,
    )

    int_report = Path(args.integrated_report) if args.integrated_report else None
    data = extractor.extract_all(integrated_report_path=int_report)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DashboardDataExtractor] Written to {output_path} ({output_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
