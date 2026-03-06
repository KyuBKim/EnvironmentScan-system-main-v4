#!/usr/bin/env python3
"""Tests for timeline_skeleton_filler.py"""

import json
import os
import sys
import tempfile

import pytest
import yaml

# Add core module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "env-scanning", "core"))
from timeline_skeleton_filler import fill_skeleton, VERSION


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SKELETON_EN = """\
# Signal Evolution Timeline Map

**Period**: {{TL_PERIOD}}
**Generated**: {{TL_SCAN_DATE}}
**Engine**: Timeline Map Generator v{{TL_ENGINE_VERSION}}
**Data Sources**: {{TL_WF_COUNTS}} = Total {{TL_TOTAL_SIGNALS}} signals

---

## Timeline Overview

{{TL_OVERVIEW_NARRATIVE}}

---

## 1. Theme-Based Temporal Tracking

> {{TL_THEMES_DETECTED}} themes detected | {{TL_ESCALATIONS_DETECTED}} escalations

{{TL_THEME_SECTIONS}}

---

## 2. STEEPs Domain Temporal Distribution

{{TL_STEEPS_MATRIX}}

---

## 3. pSST Priority Top-{{TL_TOP_N}} Trajectory

{{TL_PSST_TOP_N_TABLE}}

---

## 4. Cross-Workflow Signal Trajectory

> {{TL_CROSS_WF_CORRELATIONS}} cross-WF correlations detected

{{TL_CROSS_WF_NARRATIVE_TABLE}}

---

## 5. Escalation Monitoring

{{TL_ESCALATION_ASSESSMENT_TABLE}}

---

## 6. Strategic Implications

{{TL_STRATEGIC_IMPLICATIONS}}

---

## 7. Metadata

{{TL_METADATA_YAML}}
"""


def _make_data_package(
    total_signals=42,
    period="2026-02-28 ~ 2026-03-06",
    assembler_version="1.0.0",
    top_n_psst=10,
    wf_counts=None,
    theme_count=4,
    escalation_count=2,
    steeps=None,
    psst_rankings=None,
    cross_wf_count=3,
):
    if wf_counts is None:
        wf_counts = {"WF1": 10, "WF2": 12, "WF3": 10, "WF4": 10}
    if steeps is None:
        steeps = {
            "S": {"count": 7, "trend": "up"},
            "T": {"count": 12, "trend": "stable"},
            "E_economic": {"count": 5, "trend": "down"},
            "E_environ": {"count": 6, "trend": "up"},
            "P": {"count": 8, "trend": "stable"},
            "s": {"count": 4, "trend": "up"},
        }
    if psst_rankings is None:
        psst_rankings = [
            {"signal_id": f"wf1-20260306-{i:03d}", "title": f"Signal Title {i}", "psst_score": 90 - i * 5, "trend": "up"}
            for i in range(1, top_n_psst + 1)
        ]

    themes = {f"theme_{i}": {"name": f"Theme {i}", "signals": []} for i in range(1, theme_count + 1)}
    escalations = [{"severity": "CRITICAL", "theme": "t1"}] * escalation_count

    return {
        "metadata": {
            "total_signals": total_signals,
            "period": period,
            "assembler_version": assembler_version,
            "top_n_psst": top_n_psst,
            "wf_signal_counts": wf_counts,
        },
        "theme_trajectories": themes,
        "escalation_alerts": escalations,
        "steeps_timeline": steeps,
        "psst_rankings": psst_rankings,
        "cross_wf_correlations": [{"id": i} for i in range(cross_wf_count)],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_python_placeholders_filled():
    """All TL_ Python-deterministic placeholders are replaced."""
    data = _make_data_package()
    result = fill_skeleton(SKELETON_EN, data, "2026-03-06")

    python_placeholders = [
        "{{TL_SCAN_DATE}}",
        "{{TL_PERIOD}}",
        "{{TL_ENGINE_VERSION}}",
        "{{TL_TOTAL_SIGNALS}}",
        "{{TL_WF_COUNTS}}",
        "{{TL_THEMES_DETECTED}}",
        "{{TL_ESCALATIONS_DETECTED}}",
        "{{TL_CROSS_WF_CORRELATIONS}}",
        "{{TL_STEEPS_MATRIX}}",
        "{{TL_PSST_TOP_N_TABLE}}",
        "{{TL_TOP_N}}",
        "{{TL_METADATA_YAML}}",
    ]
    for ph in python_placeholders:
        assert ph not in result, f"Python placeholder {ph} was not replaced"


def test_llm_placeholders_preserved():
    """LLM placeholders remain untouched after filling."""
    data = _make_data_package()
    result = fill_skeleton(SKELETON_EN, data, "2026-03-06")

    llm_placeholders = [
        "{{TL_OVERVIEW_NARRATIVE}}",
        "{{TL_THEME_SECTIONS}}",
        "{{TL_CROSS_WF_NARRATIVE_TABLE}}",
        "{{TL_ESCALATION_ASSESSMENT_TABLE}}",
        "{{TL_STRATEGIC_IMPLICATIONS}}",
    ]
    for ph in llm_placeholders:
        assert ph in result, f"LLM placeholder {ph} was incorrectly replaced"


def test_steeps_matrix_formatting():
    """ASCII table has proper alignment with pipes and header separator."""
    data = _make_data_package()
    result = fill_skeleton(SKELETON_EN, data, "2026-03-06")

    # Find the STEEPs matrix section
    assert "| Domain | Count | Trend |" in result, "STEEPs table header missing"
    assert "|--------|-------|-------|" in result, "STEEPs table separator missing"
    # Check that domain rows exist
    assert "| S " in result or "|S" in result or "| S" in result, "STEEPs S domain row missing"
    assert "| T " in result or "|T" in result or "| T" in result, "STEEPs T domain row missing"


def test_psst_table_formatting():
    """Markdown table has proper syntax with header, separator, and data rows."""
    data = _make_data_package(top_n_psst=5)
    result = fill_skeleton(SKELETON_EN, data, "2026-03-06")

    # Check table structure
    assert "| Rank | Signal ID | Title | pSST Score | Trend |" in result, "pSST table header missing"
    assert "|------|-----------|-------|------------|-------|" in result, "pSST table separator missing"

    # Count data rows (lines starting with | that contain a rank number)
    lines = result.split("\n")
    psst_data_rows = [
        line for line in lines
        if line.strip().startswith("| ") and
        any(f"| {i} |" in line for i in range(1, 11))
    ]
    assert len(psst_data_rows) >= 5, f"Expected >= 5 pSST data rows, got {len(psst_data_rows)}"


def test_metadata_yaml_valid():
    """YAML block in the filled skeleton can be parsed."""
    data = _make_data_package()
    result = fill_skeleton(SKELETON_EN, data, "2026-03-06")

    # Extract YAML block
    import re
    yaml_match = re.search(r"```yaml\n(.*?)```", result, re.DOTALL)
    assert yaml_match is not None, "No YAML code block found in output"

    parsed = yaml.safe_load(yaml_match.group(1))
    assert parsed is not None, "YAML block parsed to None"
    assert "total_signals" in parsed, "total_signals missing from metadata YAML"
    assert parsed["total_signals"] == 42
