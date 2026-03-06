"""
Tests for timeline_data_assembler.py

Validates assembly completeness, WF counts, signal detail inclusion,
content truncation, graceful degradation, STEEPs timeline computation,
and all pre-rendered outputs (PB-1 through PB-6).
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add core module path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "env-scanning" / "core"))
import timeline_data_assembler as tda


# ---------------------------------------------------------------------------
# Test Fixtures — helpers to build realistic input data
# ---------------------------------------------------------------------------

def _make_signal(signal_id, title, category="T", psst_score=80,
                 scan_date="2026-03-06", source_wf="wf1", content="Short content"):
    """Helper to create a classified signal entry."""
    return {
        "id": signal_id,
        "title": title,
        "category": category,
        "sub_theme": "Test Sub",
        "impact_score": 7,
        "novelty_score": 6,
        "confidence": 0.85,
        "cross_impact": [],
        "summary": content,
        "psst_score": psst_score,
        "scan_date": scan_date,
        "source_wf": source_wf,
    }


def _make_classified_signals(signals, workflow="wf1-general", scan_date="2026-03-06"):
    """Build a classified-signals JSON structure."""
    return {
        "metadata": {
            "workflow": workflow,
            "scan_date": scan_date,
            "total_classified": len(signals),
        },
        "signals": signals,
    }


def _make_evolution_map(entries, workflow="wf1-general", scan_date="2026-03-06"):
    """Build an evolution-map JSON structure."""
    return {
        "tracker_version": "1.3.0",
        "workflow": workflow,
        "scan_date": scan_date,
        "evolution_entries": entries,
    }


def _make_theme_analysis(config_themes=None, scan_date="2026-03-06"):
    """Build a theme_analysis JSON (output from theme_discovery_engine)."""
    if config_themes is None:
        config_themes = []
    return {
        "engine": "theme_discovery_engine.py v1.0.0",
        "scan_date": scan_date,
        "lookback_days": 7,
        "total_signals_collected": sum(len(t.get("signals", [])) for t in config_themes),
        "config_themes": config_themes,
        "emergent_themes": [],
        "unmatched_signals": [],
        "compound_escalations": [],
    }


def _make_theme(theme_id, label_ko, label_en, priority, signals,
                signal_details, escalation=None):
    """Build a single config_theme entry for theme_analysis."""
    if escalation is None:
        escalation = {"slope": 0.0, "severity": "STABLE", "burst": False, "burst_rate": 0.0}
    stats = {
        "signal_count": len(signals),
        "wf_distribution": {},
        "date_range": [],
        "avg_psst": 0,
    }
    # Compute wf_distribution and date_range from signal_details
    wf_dist = {}
    dates = set()
    psst_vals = []
    for sd in signal_details:
        wf = sd.get("source_wf", "unknown")
        wf_dist[wf] = wf_dist.get(wf, 0) + 1
        d = sd.get("scan_date", "")
        if d:
            dates.add(d)
        p = sd.get("psst_score", 0) or 0
        psst_vals.append(p)
    stats["wf_distribution"] = wf_dist
    stats["date_range"] = sorted(dates)
    stats["avg_psst"] = round(sum(psst_vals) / len(psst_vals), 1) if psst_vals else 0

    return {
        "theme_id": theme_id,
        "label_ko": label_ko,
        "label_en": label_en,
        "priority": priority,
        "match_type": "config",
        "signals": signals,
        "signal_details": signal_details,
        "stats": stats,
        "escalation": escalation,
        "cross_wf_correlations": 0,
    }


def _build_full_test_data():
    """Build a complete set of test inputs for the assembler."""
    # WF1 classified signals
    wf1_sigs = [
        _make_signal("wf1-001", "AI agent platform launch", "T", 85, "2026-03-04", "wf1"),
        _make_signal("wf1-002", "Trade tariff escalation US-China", "P", 90, "2026-03-05", "wf1"),
        _make_signal("wf1-003", "Solar panel cost reduction", "E_Environmental", 70, "2026-03-06", "wf1"),
    ]
    wf1_classified = _make_classified_signals(wf1_sigs, "wf1-general")

    # WF2 classified signals
    wf2_sigs = [
        _make_signal("wf2-001", "Quantum error correction breakthrough", "T", 88, "2026-03-05", "wf2"),
        _make_signal("wf2-002", "LLM reasoning paper", "T", 75, "2026-03-06", "wf2"),
    ]
    wf2_classified = _make_classified_signals(wf2_sigs, "wf2-arxiv")

    # WF3 classified signals
    wf3_sigs = [
        _make_signal("wf3-001", "Trade tariff Korea impact", "E", 89, "2026-03-05", "wf3"),
        _make_signal("wf3-002", "Birth rate record low", "S", 82, "2026-03-06", "wf3"),
        _make_signal("wf3-003", "AI regulation bill", "P", 78, "2026-03-06", "wf3"),
        _make_signal("wf3-004", "Trade tariff extension", "P", 91, "2026-03-06", "wf3"),
    ]
    wf3_classified = _make_classified_signals(wf3_sigs, "wf3-naver")

    # WF4 — empty (missing)
    wf4_classified = None

    # Theme analysis
    trade_details = [
        _make_signal("wf1-002", "Trade tariff escalation US-China", "P", 90, "2026-03-05", "wf1"),
        _make_signal("wf3-001", "Trade tariff Korea impact", "E", 89, "2026-03-05", "wf3"),
        _make_signal("wf3-004", "Trade tariff extension", "P", 91, "2026-03-06", "wf3"),
    ]
    ai_details = [
        _make_signal("wf1-001", "AI agent platform launch", "T", 85, "2026-03-04", "wf1"),
        _make_signal("wf2-001", "Quantum error correction breakthrough", "T", 88, "2026-03-05", "wf2"),
        _make_signal("wf2-002", "LLM reasoning paper", "T", 75, "2026-03-06", "wf2"),
    ]

    trade_theme = _make_theme(
        "trade_tariff", "Trade/Tariff", "Trade & Tariffs", "CRITICAL",
        ["wf1-002", "wf3-001", "wf3-004"],
        trade_details,
        escalation={"slope": 3.5, "severity": "HIGH", "burst": False, "burst_rate": 1.0},
    )
    ai_theme = _make_theme(
        "ai_technology", "AI/Tech", "AI & Technology", "HIGH",
        ["wf1-001", "wf2-001", "wf2-002"],
        ai_details,
        escalation={"slope": 1.0, "severity": "MEDIUM", "burst": False, "burst_rate": 0.0},
    )

    theme_analysis = _make_theme_analysis([trade_theme, ai_theme])

    # Evolution maps (minimal)
    wf1_evo = _make_evolution_map([
        {"signal_id": "wf1-001", "scan_date": "2026-03-04", "psst_score": 85,
         "primary_category": "T", "title": "AI agent platform launch"},
        {"signal_id": "wf1-002", "scan_date": "2026-03-05", "psst_score": 90,
         "primary_category": "P", "title": "Trade tariff escalation US-China"},
    ], "wf1-general")

    wf2_evo = _make_evolution_map([
        {"signal_id": "wf2-001", "scan_date": "2026-03-05", "psst_score": 88,
         "primary_category": "T", "title": "Quantum error correction breakthrough"},
    ], "wf2-arxiv")

    wf3_evo = _make_evolution_map([
        {"signal_id": "wf3-001", "scan_date": "2026-03-05", "psst_score": 89,
         "primary_category": "E", "title": "Trade tariff Korea impact"},
        {"signal_id": "wf3-004", "scan_date": "2026-03-06", "psst_score": 91,
         "primary_category": "P", "title": "Trade tariff extension"},
    ], "wf3-naver")

    cross_evo = {
        "correlations": [
            {
                "source_wf": "wf1", "target_wf": "wf3",
                "source_signal": "wf1-002", "target_signal": "wf3-001",
                "combined_score": 0.92,
            }
        ]
    }

    return {
        "theme_analysis": theme_analysis,
        "wf1_classified": wf1_classified,
        "wf2_classified": wf2_classified,
        "wf3_classified": wf3_classified,
        "wf4_classified": wf4_classified,
        "wf1_evo": wf1_evo,
        "wf2_evo": wf2_evo,
        "wf3_evo": wf3_evo,
        "wf4_evo": None,
        "cross_evo": cross_evo,
    }


def _write_json(tmp_dir, filename, data):
    """Write JSON data to a temp file and return the path."""
    path = Path(tmp_dir) / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return str(path)


def _write_registry(tmp_dir):
    """Write a minimal workflow-registry.yaml."""
    import yaml
    registry = {
        "system": {
            "signal_evolution": {
                "enabled": True,
                "timeline_map": {
                    "enabled": True,
                    "lookback_days": 7,
                    "min_signals_for_theme": 2,
                    "top_n_psst": 10,
                },
            },
        },
    }
    path = Path(tmp_dir) / "workflow-registry.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(registry, f)
    return str(path)


@pytest.fixture
def full_test_env(tmp_path):
    """Create a complete test environment with all input files."""
    data = _build_full_test_data()
    paths = {}

    paths["registry"] = _write_registry(str(tmp_path))
    paths["theme_analysis"] = _write_json(tmp_path, "theme-analysis.json", data["theme_analysis"])
    paths["wf1_classified"] = _write_json(tmp_path, "wf1-classified.json", data["wf1_classified"])
    paths["wf2_classified"] = _write_json(tmp_path, "wf2-classified.json", data["wf2_classified"])
    paths["wf3_classified"] = _write_json(tmp_path, "wf3-classified.json", data["wf3_classified"])
    paths["wf4_classified"] = ""  # missing
    paths["wf1_evo"] = _write_json(tmp_path, "wf1-evo.json", data["wf1_evo"])
    paths["wf2_evo"] = _write_json(tmp_path, "wf2-evo.json", data["wf2_evo"])
    paths["wf3_evo"] = _write_json(tmp_path, "wf3-evo.json", data["wf3_evo"])
    paths["wf4_evo"] = ""  # missing
    paths["cross_evo"] = _write_json(tmp_path, "cross-evo.json", data["cross_evo"])
    paths["output"] = str(tmp_path / "output.json")
    paths["scan_date"] = "2026-03-06"
    paths["data"] = data

    return paths


def _run_assembler(paths):
    """Run the assembler and return the output dict."""
    return tda.assemble_data_package(
        theme_analysis_path=paths["theme_analysis"],
        classified_paths={
            "wf1": paths["wf1_classified"],
            "wf2": paths["wf2_classified"],
            "wf3": paths["wf3_classified"],
            "wf4": paths["wf4_classified"],
        },
        evolution_map_paths={
            "wf1": paths["wf1_evo"],
            "wf2": paths["wf2_evo"],
            "wf3": paths["wf3_evo"],
            "wf4": paths["wf4_evo"],
        },
        cross_evolution_map_path=paths["cross_evo"],
        registry_path=paths["registry"],
        scan_date=paths["scan_date"],
        output_path=paths["output"],
    )


# ---------------------------------------------------------------------------
# Basic Assembly Tests
# ---------------------------------------------------------------------------

class TestAssemblyCompleteness:
    """test_assembly_completeness — output has all required keys including pre_rendered."""

    def test_assembly_completeness(self, full_test_env):
        result = _run_assembler(full_test_env)

        # Top-level keys
        assert "metadata" in result
        assert "theme_analysis" in result
        assert "cross_wf_correlations" in result
        assert "steeps_timeline" in result
        assert "psst_rankings" in result
        assert "per_theme_signal_details" in result
        assert "pre_rendered" in result

        # pre_rendered sub-keys
        pr = result["pre_rendered"]
        assert "ascii_timelines" in pr
        assert "cross_wf_table" in pr
        assert "lead_lag_computed" in pr
        assert "escalation_confirmed" in pr
        assert "monitoring_priority_order" in pr
        assert "theme_display_order" in pr
        assert "key_signals_per_theme" in pr
        assert "escalation_table_markdown" in pr

        # metadata fields
        meta = result["metadata"]
        assert meta["scan_date"] == "2026-03-06"
        assert meta["assembler_version"] == "1.0.0"
        assert "wf_counts" in meta
        assert "total_signals" in meta
        assert "lookback_days" in meta
        assert "period" in meta


class TestWfCountsAccuracy:
    """test_wf_counts_accuracy — WF counts match actual signal counts."""

    def test_wf_counts_accuracy(self, full_test_env):
        result = _run_assembler(full_test_env)
        wf_counts = result["metadata"]["wf_counts"]

        # WF1 has 3 classified signals
        assert wf_counts["wf1"] == 3
        # WF2 has 2
        assert wf_counts["wf2"] == 2
        # WF3 has 4
        assert wf_counts["wf3"] == 4
        # WF4 is missing → 0
        assert wf_counts.get("wf4", 0) == 0
        # Total
        assert result["metadata"]["total_signals"] == 9


class TestSignalDetailInclusion:
    """test_signal_detail_inclusion — per_theme_signal_details contains signal content."""

    def test_signal_detail_inclusion(self, full_test_env):
        result = _run_assembler(full_test_env)
        details = result["per_theme_signal_details"]

        # trade_tariff theme should have details
        assert "trade_tariff" in details
        trade_sigs = details["trade_tariff"]
        assert len(trade_sigs) >= 2

        # Each signal should have title, id, psst_score
        for sig in trade_sigs:
            assert "id" in sig or "signal_id" in sig
            assert "title" in sig
            assert "psst_score" in sig


class TestContentTruncation:
    """test_content_truncation — content over 500 chars is truncated to 500."""

    def test_content_truncation(self, full_test_env):
        # Create a signal with very long content
        long_content = "A" * 800
        data = full_test_env["data"]

        # Modify a signal in the theme analysis to have long content
        theme = data["theme_analysis"]["config_themes"][0]
        theme["signal_details"][0]["summary"] = long_content

        # Re-write the theme analysis file
        _write_json(
            str(Path(full_test_env["theme_analysis"]).parent),
            "theme-analysis.json",
            data["theme_analysis"],
        )

        result = _run_assembler(full_test_env)
        details = result["per_theme_signal_details"]

        # Find the truncated signal
        for theme_id, sigs in details.items():
            for sig in sigs:
                if "summary" in sig or "content" in sig:
                    content_val = sig.get("summary", sig.get("content", ""))
                    assert len(content_val) <= 500


class TestMissingComponentGraceful:
    """test_missing_component_graceful — missing upstream file gives empty/default value."""

    def test_missing_component_graceful(self, tmp_path):
        """When an input file doesn't exist, that section should degrade gracefully."""
        import yaml
        registry_path = _write_registry(str(tmp_path))

        # Create minimal theme analysis
        theme_analysis = _make_theme_analysis([])
        ta_path = _write_json(tmp_path, "theme-analysis.json", theme_analysis)
        output_path = str(tmp_path / "output.json")

        result = tda.assemble_data_package(
            theme_analysis_path=ta_path,
            classified_paths={
                "wf1": "/nonexistent/wf1.json",
                "wf2": "",
                "wf3": "",
                "wf4": "",
            },
            evolution_map_paths={
                "wf1": "/nonexistent/evo.json",
                "wf2": "",
                "wf3": "",
                "wf4": "",
            },
            cross_evolution_map_path="/nonexistent/cross.json",
            registry_path=registry_path,
            scan_date="2026-03-06",
            output_path=output_path,
        )

        # Should still produce valid output with empty sections
        assert result["metadata"]["total_signals"] == 0
        assert result["steeps_timeline"] == {}
        assert result["psst_rankings"] == []
        assert result["cross_wf_correlations"] == {}


class TestSteepsTimelineComputation:
    """test_steeps_timeline_computation — date x STEEPs matrix is correct."""

    def test_steeps_timeline_computation(self, full_test_env):
        result = _run_assembler(full_test_env)
        steeps = result["steeps_timeline"]

        # Should have dates from classified signals
        assert len(steeps) > 0

        # Each date entry should map STEEPs categories to counts
        for date_str, cat_counts in steeps.items():
            assert isinstance(cat_counts, dict)
            for cat, count in cat_counts.items():
                assert isinstance(count, int)
                assert count > 0


# ---------------------------------------------------------------------------
# PB-1: ASCII Timeline Tests
# ---------------------------------------------------------------------------

class TestAsciiTimelineDatesCorrect:
    """test_ascii_timeline_dates_correct — dates in ASCII diagram match actual signal dates."""

    def test_ascii_timeline_dates_correct(self, full_test_env):
        result = _run_assembler(full_test_env)
        ascii_tl = result["pre_rendered"]["ascii_timelines"]

        # trade_tariff theme has signals on 2026-03-05 and 2026-03-06
        if "trade_tariff" in ascii_tl:
            diagram = ascii_tl["trade_tariff"]
            assert "03-05" in diagram
            assert "03-06" in diagram


class TestAsciiTimelinePsstCorrect:
    """test_ascii_timeline_psst_correct — pSST values in diagram match actual values."""

    def test_ascii_timeline_psst_correct(self, full_test_env):
        result = _run_assembler(full_test_env)
        ascii_tl = result["pre_rendered"]["ascii_timelines"]

        if "trade_tariff" in ascii_tl:
            diagram = ascii_tl["trade_tariff"]
            # Trade theme has pSST values 89, 90, 91
            # The diagram should contain at least one of these
            assert any(str(v) in diagram for v in [89, 90, 91])


class TestAsciiTimelineWfLabels:
    """test_ascii_timeline_wf_labels — WF labels are correct in diagram."""

    def test_ascii_timeline_wf_labels(self, full_test_env):
        result = _run_assembler(full_test_env)
        ascii_tl = result["pre_rendered"]["ascii_timelines"]

        if "trade_tariff" in ascii_tl:
            diagram = ascii_tl["trade_tariff"]
            # Trade theme has signals from wf1 and wf3
            assert "WF1" in diagram or "wf1" in diagram.lower()
            assert "WF3" in diagram or "wf3" in diagram.lower()


# ---------------------------------------------------------------------------
# PB-2: Cross-WF Table Tests
# ---------------------------------------------------------------------------

class TestCrossWfTableCellAccuracy:
    """test_cross_wf_table_cell_accuracy — theme x WF cell counts match data."""

    def test_cross_wf_table_cell_accuracy(self, full_test_env):
        result = _run_assembler(full_test_env)
        table = result["pre_rendered"]["cross_wf_table"]

        assert "headers" in table
        assert "rows" in table

        # Find trade_tariff row
        trade_row = None
        for row in table["rows"]:
            if row.get("theme_id") == "trade_tariff":
                trade_row = row
                break

        assert trade_row is not None
        # trade_tariff: WF1 has 1 signal, WF3 has 2 signals
        assert trade_row["wf1"] == 1
        assert trade_row["wf3"] == 2
        assert trade_row.get("wf2", 0) == 0


# ---------------------------------------------------------------------------
# PB-3: Lead-Lag Tests
# ---------------------------------------------------------------------------

class TestLeadLagDaysCalculation:
    """test_lead_lag_days_calculation — lag_days = (last_date - first_date).days."""

    def test_lead_lag_days_calculation(self, full_test_env):
        result = _run_assembler(full_test_env)
        lead_lag = result["pre_rendered"]["lead_lag_computed"]

        # trade_tariff appears in wf1 (2026-03-05) and wf3 (2026-03-05, 2026-03-06)
        trade_ll = None
        for entry in lead_lag:
            if entry.get("theme_id") == "trade_tariff":
                trade_ll = entry
                break

        assert trade_ll is not None
        # first and last date
        from datetime import datetime
        first = datetime.strptime(trade_ll["first_date"], "%Y-%m-%d")
        last = datetime.strptime(trade_ll["last_date"], "%Y-%m-%d")
        expected_lag = (last - first).days
        assert trade_ll["lag_days"] == expected_lag


# ---------------------------------------------------------------------------
# PB-4: Escalation Confirmed Tests
# ---------------------------------------------------------------------------

class TestEscalationConfirmedMatches:
    """test_escalation_confirmed_matches — severity matches theme_analysis input."""

    def test_escalation_confirmed_matches(self, full_test_env):
        result = _run_assembler(full_test_env)
        esc = result["pre_rendered"]["escalation_confirmed"]

        # Build lookup
        esc_map = {e["theme_id"]: e for e in esc}

        # trade_tariff should be HIGH (from fixture)
        assert esc_map["trade_tariff"]["severity"] == "HIGH"
        # ai_technology should be MEDIUM (from fixture)
        assert esc_map["ai_technology"]["severity"] == "MEDIUM"


# ---------------------------------------------------------------------------
# PB-5: Monitoring Priority Order Tests
# ---------------------------------------------------------------------------

class TestMonitoringOrderDeterministic:
    """test_monitoring_order_deterministic — same input always produces same order."""

    def test_monitoring_order_deterministic(self, full_test_env):
        result1 = _run_assembler(full_test_env)
        result2 = _run_assembler(full_test_env)

        order1 = result1["pre_rendered"]["monitoring_priority_order"]
        order2 = result2["pre_rendered"]["monitoring_priority_order"]

        assert order1 == order2
        assert len(order1) > 0


# ---------------------------------------------------------------------------
# PB-6: Theme Display Order + Key Signals Tests
# ---------------------------------------------------------------------------

class TestThemeOrderByPrioritySlope:
    """test_theme_order_by_priority_slope — CRITICAL>HIGH>MEDIUM, within same priority sort by count desc."""

    def test_theme_order_by_priority_slope(self, full_test_env):
        result = _run_assembler(full_test_env)
        order = result["pre_rendered"]["theme_display_order"]

        assert len(order) >= 2

        # Get theme details to verify ordering
        themes = {t["theme_id"]: t for t in result["theme_analysis"]["config_themes"]}
        priority_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

        # Verify order is correct: each theme's priority rank should be <= the next
        for i in range(len(order) - 1):
            t1 = themes.get(order[i], {})
            t2 = themes.get(order[i + 1], {})
            p1 = priority_rank.get(t1.get("priority", "LOW"), 99)
            p2 = priority_rank.get(t2.get("priority", "LOW"), 99)
            if p1 == p2:
                # Same priority: higher signal count first
                c1 = t1.get("stats", {}).get("signal_count", 0)
                c2 = t2.get("stats", {}).get("signal_count", 0)
                assert c1 >= c2
            else:
                assert p1 < p2


class TestKeySignalsTop3Psst:
    """test_key_signals_top3_psst — each theme's key signals are the top 3 by pSST."""

    def test_key_signals_top3_psst(self, full_test_env):
        result = _run_assembler(full_test_env)
        key_sigs = result["pre_rendered"]["key_signals_per_theme"]

        # trade_tariff has 3 signals with pSST 90, 89, 91
        trade_keys = key_sigs.get("trade_tariff", [])
        assert len(trade_keys) <= 3

        # Verify they are the top by pSST
        theme_details = result["per_theme_signal_details"].get("trade_tariff", [])
        all_psst = sorted(
            [(s.get("psst_score", 0), s.get("id", s.get("signal_id", ""))) for s in theme_details],
            key=lambda x: -x[0],
        )
        top3_ids = [sid for _, sid in all_psst[:3]]

        for kid in trade_keys:
            assert kid in top3_ids
