"""
Tests for theme_discovery_engine.py

Validates config-driven theme matching, exclusion keywords, emergent clustering,
multi-theme assignment, pSST statistics, escalation detection, compound escalation,
cross-WF enrichment, and graceful empty-input handling.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

# Add core module path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "env-scanning" / "core"))
import theme_discovery_engine as tde


# ---------------------------------------------------------------------------
# Test Fixtures / Helpers
# ---------------------------------------------------------------------------

def _make_theme_config_yaml(tmp_path):
    """Create a minimal timeline-themes.yaml for testing."""
    config = {
        "version": "1.0.0",
        "themes": {
            "trade_tariff": {
                "label_ko": "무역·관세 전쟁",
                "label_en": "Trade & Tariffs",
                "priority": "CRITICAL",
                "keywords_en": ["tariff", "trade war", "customs duty"],
                "keywords_ko": ["관세", "무역전쟁"],
                "exclusion_keywords": ["fair trade coffee", "trade-off"],
                "steeps_affinity": ["E", "P"],
            },
            "energy_climate": {
                "label_ko": "에너지·기후 전환",
                "label_en": "Energy & Climate",
                "priority": "HIGH",
                "keywords_en": ["climate change", "renewable energy", "carbon emission"],
                "keywords_ko": ["기후변화", "재생에너지", "탄소"],
                "exclusion_keywords": ["diffusion model", "latent diffusion", "solar system"],
                "steeps_affinity": ["E_Environmental", "T"],
            },
            "semiconductor": {
                "label_ko": "반도체 전쟁",
                "label_en": "Semiconductor",
                "priority": "MEDIUM",
                "keywords_en": ["semiconductor", "chip", "foundry"],
                "keywords_ko": ["반도체", "파운드리"],
                "exclusion_keywords": [],
                "steeps_affinity": ["T", "E"],
            },
            "ai_technology": {
                "label_ko": "AI·기술 진화",
                "label_en": "AI & Technology",
                "priority": "HIGH",
                "keywords_en": ["artificial intelligence", "machine learning", "quantum computing"],
                "keywords_ko": ["인공지능", "머신러닝"],
                "exclusion_keywords": [],
                "steeps_affinity": ["T"],
            },
        },
    }
    theme_path = tmp_path / "timeline-themes.yaml"
    with open(theme_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    return str(theme_path)


def _make_registry_yaml(tmp_path, overrides=None):
    """Create a minimal workflow-registry.yaml for testing."""
    tl_cfg = {
        "enabled": True,
        "lookback_days": 7,
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
    if overrides:
        tl_cfg.update(overrides)
    config = {
        "system": {
            "signal_evolution": {
                "enabled": True,
                "timeline_map": tl_cfg,
            },
        },
    }
    registry_path = tmp_path / "workflow-registry.yaml"
    with open(registry_path, "w") as f:
        yaml.dump(config, f)
    return str(registry_path)


def _make_signal(signal_id, title, keywords=None, psst_score=80,
                 scan_date="2026-03-06", primary_category="T", wf="wf1"):
    """Create a signal dict for testing."""
    return {
        "signal_id": signal_id,
        "title": title,
        "canonical_title": title,
        "keywords": keywords or [],
        "psst_score": psst_score,
        "scan_date": scan_date,
        "primary_category": primary_category,
        "source_wf": wf,
    }


def _make_evolution_map(scan_date="2026-03-06", entries=None):
    return {
        "scan_date": scan_date,
        "evolution_entries": entries or [],
    }


def _make_evolution_index(threads=None):
    return {
        "threads": threads or {},
    }


# ---------------------------------------------------------------------------
# Test 1: test_whole_word_matching
# ---------------------------------------------------------------------------

class TestWholeWordMatching:
    def test_whole_word_matching(self, tmp_path):
        """'diffusion model' should NOT match energy_climate theme.

        The energy_climate theme has 'diffusion model' in exclusion_keywords.
        Even though 'diffusion' is a substring, the matching uses whole-word
        boundary matching, and 'diffusion model' is excluded explicitly.
        """
        theme_path = _make_theme_config_yaml(tmp_path)
        themes = tde.load_theme_config(theme_path)

        signal = _make_signal(
            "sig-001", "Diffusion Model for Image Generation",
            keywords=["diffusion model", "generative AI"],
        )

        matches = tde.match_signal_to_themes(signal, themes)
        matched_ids = [m["theme_id"] for m in matches]
        assert "energy_climate" not in matched_ids


# ---------------------------------------------------------------------------
# Test 2: test_exclusion_keywords
# ---------------------------------------------------------------------------

class TestExclusionKeywords:
    def test_exclusion_keywords(self, tmp_path):
        """Signals matching exclusion keywords are filtered out."""
        theme_path = _make_theme_config_yaml(tmp_path)
        themes = tde.load_theme_config(theme_path)

        # "fair trade coffee" is excluded from trade_tariff
        signal = _make_signal(
            "sig-002", "Fair Trade Coffee Initiative Grows",
            keywords=["fair trade coffee", "sustainability"],
        )

        matches = tde.match_signal_to_themes(signal, themes)
        matched_ids = [m["theme_id"] for m in matches]
        assert "trade_tariff" not in matched_ids

        # But a real tariff signal should match
        signal2 = _make_signal(
            "sig-003", "New tariff on steel imports announced",
            keywords=["tariff", "steel", "imports"],
        )
        matches2 = tde.match_signal_to_themes(signal2, themes)
        matched_ids2 = [m["theme_id"] for m in matches2]
        assert "trade_tariff" in matched_ids2


# ---------------------------------------------------------------------------
# Test 3: test_config_loading_from_yaml
# ---------------------------------------------------------------------------

class TestConfigLoadingFromYaml:
    def test_config_loading_from_yaml(self, tmp_path):
        """Themes load correctly from timeline-themes.yaml fixture."""
        theme_path = _make_theme_config_yaml(tmp_path)
        themes = tde.load_theme_config(theme_path)

        assert len(themes) == 4
        assert "trade_tariff" in themes
        assert "energy_climate" in themes
        assert themes["trade_tariff"]["label_ko"] == "무역·관세 전쟁"
        assert themes["trade_tariff"]["priority"] == "CRITICAL"
        assert "tariff" in themes["trade_tariff"]["keywords_en"]
        assert "fair trade coffee" in themes["trade_tariff"]["exclusion_keywords"]


# ---------------------------------------------------------------------------
# Test 4: test_emergent_cluster_minimum
# ---------------------------------------------------------------------------

class TestEmergentClusterMinimum:
    def test_emergent_cluster_minimum(self):
        """Clusters below min_cluster_size are excluded."""
        # 2 signals with shared keywords — below min_size=3
        unmatched = [
            _make_signal("s1", "BlockchainX supply chain", keywords=["blockchainx", "supply chain"]),
            _make_signal("s2", "BlockchainX logistics", keywords=["blockchainx", "logistics"]),
        ]
        params = {
            "emergent_cluster_min_size": 3,
            "emergent_max_themes": 5,
            "emergent_cooccurrence_threshold": 2,
            "emergent_title_similarity_threshold": 0.55,
        }
        emergent = tde.discover_emergent_themes(unmatched, params)
        # Should find 0 themes because cluster size < 3
        assert len(emergent) == 0

        # Now 3 signals — meets min_size=3
        unmatched_3 = unmatched + [
            _make_signal("s3", "BlockchainX integration", keywords=["blockchainx", "integration"]),
        ]
        emergent_3 = tde.discover_emergent_themes(unmatched_3, params)
        # Should find at least 1 theme via title similarity clustering
        assert len(emergent_3) >= 1


# ---------------------------------------------------------------------------
# Test 5: test_multi_theme_assignment
# ---------------------------------------------------------------------------

class TestMultiThemeAssignment:
    def test_multi_theme_assignment(self, tmp_path):
        """A signal with 'tariff semiconductor' matches both themes."""
        theme_path = _make_theme_config_yaml(tmp_path)
        themes = tde.load_theme_config(theme_path)

        signal = _make_signal(
            "sig-005", "Tariff on semiconductor imports rises",
            keywords=["tariff", "semiconductor", "imports"],
        )

        matches = tde.match_signal_to_themes(signal, themes)
        matched_ids = [m["theme_id"] for m in matches]
        assert "trade_tariff" in matched_ids
        assert "semiconductor" in matched_ids


# ---------------------------------------------------------------------------
# Test 6: test_empty_input_graceful
# ---------------------------------------------------------------------------

class TestEmptyInputGraceful:
    def test_empty_input_graceful(self, tmp_path):
        """Empty evolution maps produce valid empty result."""
        theme_path = _make_theme_config_yaml(tmp_path)
        registry_path = _make_registry_yaml(tmp_path)

        result = tde.run_theme_discovery(
            registry_path=registry_path,
            theme_config_path=theme_path,
            evolution_maps={},
            evolution_indices={},
            cross_evolution_map={},
            scan_date="2026-03-06",
        )

        assert result["scan_date"] == "2026-03-06"
        assert result["config_themes"] == []
        assert result["emergent_themes"] == []
        assert result["unmatched_signals"] == []
        assert result["compound_escalations"] == []
        assert "engine" in result


# ---------------------------------------------------------------------------
# Test 7: test_psst_statistics_accuracy
# ---------------------------------------------------------------------------

class TestPsstStatisticsAccuracy:
    def test_psst_statistics_accuracy(self):
        """min/max/avg/median calculations are exact."""
        signals = [
            _make_signal("s1", "A", psst_score=70),
            _make_signal("s2", "B", psst_score=80),
            _make_signal("s3", "C", psst_score=90),
            _make_signal("s4", "D", psst_score=100),
        ]

        stats = tde.compute_theme_stats(signals)

        assert stats["psst"]["min"] == 70
        assert stats["psst"]["max"] == 100
        assert stats["psst"]["avg"] == 85.0  # (70+80+90+100)/4
        assert stats["psst"]["median"] == 85.0  # median of [70,80,90,100]


# ---------------------------------------------------------------------------
# Test 8: test_escalation_slope_calculation
# ---------------------------------------------------------------------------

class TestEscalationSlopeCalculation:
    def test_escalation_slope_calculation(self):
        """pSST slope calculation matches expected value."""
        # Day 0: psst=80, Day 1: psst=85, Day 2: psst=90
        # Slope should be 5.0 per day
        signal_details = [
            {"signal_id": "s1", "psst_score": 80, "scan_date": "2026-03-04"},
            {"signal_id": "s2", "psst_score": 85, "scan_date": "2026-03-05"},
            {"signal_id": "s3", "psst_score": 90, "scan_date": "2026-03-06"},
        ]

        escalation = tde.detect_escalation(signal_details, {
            "critical_slope": 5.0,
            "high_slope": 2.0,
            "burst_factor": 2.0,
        })

        assert abs(escalation["slope"] - 5.0) < 0.01
        assert escalation["severity"] == "CRITICAL"


# ---------------------------------------------------------------------------
# Test 9: test_compound_escalation_detection
# ---------------------------------------------------------------------------

class TestCompoundEscalationDetection:
    def test_compound_escalation_detection(self):
        """2 themes with CRITICAL severity detected as compound escalation."""
        theme_escalations = [
            {
                "theme_id": "trade_tariff",
                "severity": "CRITICAL",
                "slope": 6.0,
            },
            {
                "theme_id": "geopolitics",
                "severity": "CRITICAL",
                "slope": 5.5,
            },
            {
                "theme_id": "ai_technology",
                "severity": "MEDIUM",
                "slope": 1.0,
            },
        ]

        compounds = tde.detect_compound_escalations(theme_escalations)

        assert len(compounds) >= 1
        compound = compounds[0]
        assert "trade_tariff" in compound["theme_ids"]
        assert "geopolitics" in compound["theme_ids"]
        # ai_technology is MEDIUM, not part of compound escalation
        assert "ai_technology" not in compound["theme_ids"]


# ---------------------------------------------------------------------------
# Test 10: test_cross_wf_enrichment
# ---------------------------------------------------------------------------

class TestCrossWfEnrichment:
    def test_cross_wf_enrichment(self, tmp_path):
        """Cross-evolution-map correlations tagged to correct themes."""
        theme_path = _make_theme_config_yaml(tmp_path)
        themes = tde.load_theme_config(theme_path)

        cross_map = {
            "correlations": [
                {
                    "source_wf": "wf1",
                    "source_title": "New tariff on semiconductor",
                    "source_keywords": ["tariff", "semiconductor"],
                    "target_wf": "wf3",
                    "target_title": "반도체 관세 강화",
                    "target_keywords": ["반도체", "관세"],
                    "combined_score": 0.85,
                },
                {
                    "source_wf": "wf2",
                    "source_title": "Quantum computing advances",
                    "source_keywords": ["quantum computing"],
                    "target_wf": "wf1",
                    "target_title": "Quantum AI convergence",
                    "target_keywords": ["quantum computing", "AI"],
                    "combined_score": 0.72,
                },
            ],
        }

        enriched = tde.enrich_with_cross_wf(cross_map, themes)

        # First correlation should tag trade_tariff and semiconductor
        corr0_themes = enriched[0]["matched_themes"]
        assert "trade_tariff" in corr0_themes
        assert "semiconductor" in corr0_themes

        # Second should tag ai_technology (quantum computing keyword)
        corr1_themes = enriched[1]["matched_themes"]
        assert "ai_technology" in corr1_themes


# ---------------------------------------------------------------------------
# Test 11: test_stable_no_false_alarm
# ---------------------------------------------------------------------------

class TestStableNoFalseAlarm:
    def test_stable_no_false_alarm(self):
        """Flat pSST pattern results in STABLE, not escalation."""
        # All same score — slope should be ~0
        signal_details = [
            {"signal_id": "s1", "psst_score": 80, "scan_date": "2026-03-04"},
            {"signal_id": "s2", "psst_score": 80, "scan_date": "2026-03-05"},
            {"signal_id": "s3", "psst_score": 80, "scan_date": "2026-03-06"},
        ]

        escalation = tde.detect_escalation(signal_details, {
            "critical_slope": 5.0,
            "high_slope": 2.0,
            "burst_factor": 2.0,
        })

        assert escalation["severity"] == "STABLE"
        assert abs(escalation["slope"]) < 0.01
