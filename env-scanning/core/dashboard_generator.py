#!/usr/bin/env python3
"""
Dashboard Generator — SOT-Driven Interactive HTML Dashboard (v1.0.0)

Reads dashboard-data.json (from dashboard_data_extractor.py) and EN/KO report files,
then assembles an interactive HTML dashboard. ALL quantitative data comes from the
dashboard-data.json — NEVER from report text parsing.

Usage:
    python3 env-scanning/core/dashboard_generator.py \
        --date 2026-03-24 \
        --data-file env-scanning/integrated/analysis/dashboard-data-2026-03-24.json \
        --registry env-scanning/config/workflow-registry.yaml \
        --output dashboard-2026-03-24.html
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "1.0.0"

WF_KEYS = ["wf1-general", "wf2-arxiv", "wf3-naver", "wf4-multiglobal-news"]

WF_LABELS = {
    "wf1-general": "WF1 일반",
    "wf2-arxiv": "WF2 arXiv",
    "wf3-naver": "WF3 네이버",
    "wf4-multiglobal-news": "WF4 글로벌뉴스",
}

WF_LABELS_SHORT = {
    "wf1-general": "WF1",
    "wf2-arxiv": "WF2",
    "wf3-naver": "WF3",
    "wf4-multiglobal-news": "WF4",
}

WF_CSS_VARS = {
    "wf1-general": "var(--wf1)",
    "wf2-arxiv": "var(--wf2)",
    "wf3-naver": "var(--wf3)",
    "wf4-multiglobal-news": "var(--wf4)",
}

WF_CSS_HEX = {
    "wf1-general": "#2d5be3",
    "wf2-arxiv": "#7c3aed",
    "wf3-naver": "#059669",
    "wf4-multiglobal-news": "#ea580c",
}

STEEPS_COLORS = {
    "S": "#2d5be3",
    "T": "#7c3aed",
    "E": "#ea580c",
    "Env": "#059669",
    "P": "#dc2626",
    "s": "#ca8a04",
}

STEEPS_ORDER = ["S", "T", "E", "Env", "P", "s"]

FSSF_ORDER = [
    "Weak Signal", "Wild Card", "Discontinuity",
    "Driver", "Emerging Issue", "Precursor Event",
    "Trend", "Megatrend",
]

FSSF_COLORS = {
    "Weak Signal": "#dc2626",
    "Wild Card": "#ea580c",
    "Discontinuity": "#ca8a04",
    "Driver": "#059669",
    "Emerging Issue": "#0891b2",
    "Precursor Event": "#2d5be3",
    "Trend": "#7c3aed",
    "Megatrend": "#5f6577",
}

# Report file naming patterns per WF
# (base_dir, en_pattern, ko_pattern)
# Default report patterns — used when SOT is unavailable.
# When SOT (workflow-registry.yaml) is loaded, paths are resolved from
# wf.data_root and integration.output_root instead.
_DEFAULT_REPORT_PATTERNS = {
    "wf1-general": {
        "base_dir": "env-scanning/wf1-general/reports/daily",
        "en": "environmental-scan-{date}.md",
        "ko": "environmental-scan-{date}-ko.md",
    },
    "wf2-arxiv": {
        "base_dir": "env-scanning/wf2-arxiv/reports/daily",
        "en": "environmental-scan-{date}.md",
        "ko": "arxiv-scan-{date}-ko.md",
    },
    "wf3-naver": {
        "base_dir": "env-scanning/wf3-naver/reports/daily",
        "en": "naver-scan-{date}.md",
        "ko": "naver-scan-{date}-ko.md",
    },
    "wf4-multiglobal-news": {
        "base_dir": "env-scanning/wf4-multiglobal-news/reports/daily",
        "en": "environmental-scan-{date}.md",
        "ko": "environmental-scan-{date}-ko.md",
    },
    "integrated": {
        "base_dir": "env-scanning/integrated/reports/daily",
        "en": "integrated-scan-{date}.md",
        "ko": "integrated-scan-{date}-ko.md",
    },
}


def resolve_report_patterns_from_sot(registry: Dict) -> Dict:
    """
    Build report patterns from SOT rather than hardcoded defaults.
    Falls back to defaults if SOT is unavailable or incomplete.
    """
    if not registry:
        return _DEFAULT_REPORT_PATTERNS

    patterns = {}
    workflows = registry.get("workflows", {})
    integration = registry.get("integration", {})

    # WF report patterns from SOT data_root
    wf_report_names = {
        "wf1-general": {"en": "environmental-scan-{date}.md", "ko": "environmental-scan-{date}-ko.md"},
        "wf2-arxiv": {"en": "environmental-scan-{date}.md", "ko": "arxiv-scan-{date}-ko.md"},
        "wf3-naver": {"en": "naver-scan-{date}.md", "ko": "naver-scan-{date}-ko.md"},
        "wf4-multiglobal-news": {"en": "environmental-scan-{date}.md", "ko": "environmental-scan-{date}-ko.md"},
    }
    for wf_key, names in wf_report_names.items():
        wf_cfg = workflows.get(wf_key, {})
        data_root = wf_cfg.get("data_root", _DEFAULT_REPORT_PATTERNS.get(wf_key, {}).get("base_dir", "").rsplit("/reports", 1)[0])
        patterns[wf_key] = {
            "base_dir": f"{data_root}/reports/daily",
            "en": names["en"],
            "ko": names["ko"],
        }

    # Integrated report from SOT output_root
    int_root = integration.get("output_root", "env-scanning/integrated")
    patterns["integrated"] = {
        "base_dir": f"{int_root}/reports/daily",
        "en": "integrated-scan-{date}.md",
        "ko": "integrated-scan-{date}-ko.md",
    }

    return patterns

REPORT_TAB_LABELS = {
    "wf1-general": "WF1 보고서",
    "wf2-arxiv": "WF2 보고서",
    "wf3-naver": "WF3 보고서",
    "wf4-multiglobal-news": "WF4 보고서",
    "integrated": "통합 보고서",
}


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
    """Load YAML using PyYAML if available."""
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except ImportError:
        print("  WARN: PyYAML not available", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  WARN: Cannot load YAML {path}: {e}", file=sys.stderr)
        return None


def load_report_file(path: Path) -> str:
    """Load a report markdown file, returning empty string on failure."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"  WARN: Report not found: {path}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"  WARN: Cannot read report {path}: {e}", file=sys.stderr)
        return ""


# ---------------------------------------------------------------------------
# Markdown-to-HTML Converter
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """HTML-escape text."""
    return html.escape(text, quote=True)


def md_to_html(md_text: str) -> str:
    """
    Convert Markdown text to HTML.

    Handles: headings (#-######), horizontal rules (---), tables (| col | col |),
    unordered lists (- item), ordered lists (1. item), blockquotes (> text),
    bold (**text**), links ([text](url)), and paragraph wrapping.
    """
    if not md_text:
        return "<p><em>(보고서 내용 없음)</em></p>"

    lines = md_text.split("\n")
    result = []
    in_table = False
    in_list = False
    list_type = None  # "ul" or "ol"
    in_blockquote = False
    in_paragraph = False
    table_header_done = False

    def close_open():
        nonlocal in_table, in_list, list_type, in_blockquote, in_paragraph, table_header_done
        if in_table:
            result.append("</tbody></table></div>")
            in_table = False
            table_header_done = False
        if in_list:
            result.append(f"</{list_type}>")
            in_list = False
            list_type = None
        if in_blockquote:
            result.append("</blockquote>")
            in_blockquote = False
        if in_paragraph:
            result.append("</p>")
            in_paragraph = False

    def inline_format(text: str) -> str:
        """Apply inline formatting: bold, links."""
        # Bold: **text**
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Links: [text](url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
        return text

    for raw_line in lines:
        line = raw_line.rstrip()

        # --- Heading ---
        m_heading = re.match(r'^(#{1,6})\s+(.+)$', line)
        if m_heading:
            close_open()
            level = len(m_heading.group(1))
            content = inline_format(_esc(m_heading.group(2)))
            result.append(f'<h{level} class="md-h{level}">{content}</h{level}>')
            continue

        # --- Horizontal Rule ---
        if re.match(r'^---+\s*$', line):
            close_open()
            result.append("<hr>")
            continue

        # --- Table ---
        if line.strip().startswith("|") and line.strip().endswith("|"):
            # Check if this is a separator line (|---|---|)
            stripped = line.strip()
            is_separator = bool(re.match(r'^\|[\s\-:|]+\|$', stripped))

            if is_separator:
                # Skip separator, mark header as done
                table_header_done = True
                continue

            cells = [c.strip() for c in stripped.split("|")[1:-1]]

            if not in_table:
                # Close other blocks
                if in_list:
                    result.append(f"</{list_type}>")
                    in_list = False
                    list_type = None
                if in_blockquote:
                    result.append("</blockquote>")
                    in_blockquote = False
                if in_paragraph:
                    result.append("</p>")
                    in_paragraph = False

                result.append('<div class="table-wrap"><table class="md-table">')
                result.append("<thead><tr>")
                for cell in cells:
                    result.append(f"<th>{inline_format(_esc(cell))}</th>")
                result.append("</tr></thead><tbody>")
                in_table = True
                table_header_done = False
                continue

            # Body row
            result.append("<tr>")
            for cell in cells:
                result.append(f"<td>{inline_format(_esc(cell))}</td>")
            result.append("</tr>")
            continue

        # If we were in a table but this line isn't a table row, close table
        if in_table and not (line.strip().startswith("|") and line.strip().endswith("|")):
            result.append("</tbody></table></div>")
            in_table = False
            table_header_done = False

        # --- Unordered List ---
        m_ul = re.match(r'^(\s*)[-*]\s+(.+)$', line)
        if m_ul:
            if in_paragraph:
                result.append("</p>")
                in_paragraph = False
            if in_blockquote:
                result.append("</blockquote>")
                in_blockquote = False
            if in_list and list_type != "ul":
                result.append(f"</{list_type}>")
                in_list = False
            if not in_list:
                result.append("<ul>")
                in_list = True
                list_type = "ul"
            result.append(f"<li>{inline_format(_esc(m_ul.group(2)))}</li>")
            continue

        # --- Ordered List ---
        m_ol = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
        if m_ol:
            if in_paragraph:
                result.append("</p>")
                in_paragraph = False
            if in_blockquote:
                result.append("</blockquote>")
                in_blockquote = False
            if in_list and list_type != "ol":
                result.append(f"</{list_type}>")
                in_list = False
            if not in_list:
                result.append("<ol>")
                in_list = True
                list_type = "ol"
            result.append(f"<li>{inline_format(_esc(m_ol.group(2)))}</li>")
            continue

        # Close list if we're no longer in list items
        if in_list:
            result.append(f"</{list_type}>")
            in_list = False
            list_type = None

        # --- Blockquote ---
        m_bq = re.match(r'^>\s*(.*)$', line)
        if m_bq:
            if in_paragraph:
                result.append("</p>")
                in_paragraph = False
            if not in_blockquote:
                result.append("<blockquote>")
                in_blockquote = True
            content = m_bq.group(1).strip()
            if content:
                result.append(f"<p>{inline_format(_esc(content))}</p>")
            continue

        if in_blockquote:
            result.append("</blockquote>")
            in_blockquote = False

        # --- Empty line ---
        if not line.strip():
            if in_paragraph:
                result.append("</p>")
                in_paragraph = False
            continue

        # --- Paragraph text ---
        escaped = inline_format(_esc(line))
        if in_paragraph:
            result.append(f"<br>{escaped}")
        else:
            result.append(f"<p>{escaped}")
            in_paragraph = True

    close_open()
    return "\n".join(result)


# ---------------------------------------------------------------------------
# HTML Template Components
# ---------------------------------------------------------------------------

def _build_css() -> str:
    """Return the complete CSS stylesheet."""
    return """
:root {
  --bg: #f5f6f8; --card: #fff; --border: #e2e4ea; --text: #1a1d27; --muted: #5f6577;
  --accent: #2d5be3; --red: #dc2626; --orange: #ea580c; --yellow: #ca8a04;
  --green: #059669; --cyan: #0891b2; --purple: #7c3aed;
  --wf1: #2d5be3; --wf2: #7c3aed; --wf3: #059669; --wf4: #ea580c;
  --radius: 10px; --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans KR', sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.6;
}

.dashboard-header {
  background: linear-gradient(135deg, #1a1d27, #2d3748);
  color: #fff; padding: 24px 32px; display: flex; align-items: center; justify-content: space-between;
}
.dashboard-header h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }
.dashboard-header .meta { font-size: 13px; opacity: 0.7; }

/* Tabs */
.tab-bar {
  display: flex; gap: 0; background: var(--card); border-bottom: 2px solid var(--border);
  padding: 0 16px; overflow-x: auto; position: sticky; top: 0; z-index: 100;
}
.tab-btn {
  padding: 12px 18px; font-size: 13px; font-weight: 600; cursor: pointer;
  border: none; background: none; color: var(--muted); white-space: nowrap;
  border-bottom: 3px solid transparent; transition: all 0.15s;
}
.tab-btn:hover { color: var(--text); background: rgba(0,0,0,0.02); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-content { display: none; padding: 24px 32px; max-width: 1400px; margin: 0 auto; }
.tab-content.active { display: block; }

/* Sub-tabs (EN/KO toggle) */
.subtab-bar {
  display: flex; gap: 4px; margin-bottom: 16px; padding: 4px; background: var(--bg);
  border-radius: 8px; width: fit-content;
}
.subtab-btn {
  padding: 6px 16px; font-size: 12px; font-weight: 600; cursor: pointer;
  border: none; background: none; color: var(--muted); border-radius: 6px;
  transition: all 0.15s;
}
.subtab-btn.active { background: var(--card); color: var(--accent); box-shadow: var(--shadow); }
.subtab-content { display: none; }
.subtab-content.active { display: block; }

/* Cards */
.card {
  background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 20px; box-shadow: var(--shadow); margin-bottom: 20px;
}
.card-title { font-size: 15px; font-weight: 700; margin-bottom: 14px; color: var(--text); }

/* KPI Grid */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.kpi-card {
  background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 18px; text-align: center; box-shadow: var(--shadow);
}
.kpi-value { font-size: 32px; font-weight: 800; color: var(--accent); }
.kpi-label { font-size: 12px; color: var(--muted); margin-top: 4px; }
.kpi-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }

/* Chart containers */
.chart-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 20px; margin-bottom: 24px; }
.chart-box {
  background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 20px; box-shadow: var(--shadow);
}
.chart-box canvas { max-height: 320px; }

/* Mega themes */
.mega-theme {
  padding: 16px; border-left: 4px solid var(--accent); margin-bottom: 12px;
  background: rgba(45, 91, 227, 0.03); border-radius: 0 var(--radius) var(--radius) 0;
}
.mega-theme h4 { font-size: 14px; font-weight: 700; margin-bottom: 6px; }
.mega-theme p { font-size: 13px; color: var(--muted); }

/* Signal table */
.signal-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; }
.signal-table thead { position: sticky; top: 50px; z-index: 10; }
.signal-table th {
  background: #f0f1f5; padding: 10px 12px; text-align: left; font-weight: 700;
  border-bottom: 2px solid var(--border); font-size: 12px; color: var(--muted);
}
.signal-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
.signal-table tr:hover td { background: rgba(45, 91, 227, 0.02); }

/* Rank badge */
.rank-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 50%; color: #fff;
  font-size: 12px; font-weight: 800;
}
.rank-tier-1 { background: var(--red); }
.rank-tier-2 { background: var(--orange); }
.rank-tier-3 { background: var(--accent); }

/* WF badge */
.wf-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px;
  font-weight: 700; color: #fff;
}

/* STEEPs tag */
.steeps-tag {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px;
  font-weight: 700; color: #fff;
}

/* FSSF tag */
.fssf-tag {
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px;
  font-weight: 600; color: #fff; background: var(--muted);
}

/* Gate status */
.gate-pass { color: var(--green); font-weight: 700; }
.gate-fail { color: var(--red); font-weight: 700; }
.gate-warn { color: var(--yellow); font-weight: 700; }

/* Risk matrix table */
.risk-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.risk-table th { background: #f0f1f5; padding: 10px 12px; text-align: left; font-weight: 700; font-size: 12px; }
.risk-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
.risk-bar {
  height: 8px; border-radius: 4px; background: var(--border);
}
.risk-bar-fill { height: 100%; border-radius: 4px; }

/* Report content */
.report-content {
  max-height: 80vh; overflow-y: auto; padding: 20px; background: var(--card);
  border: 1px solid var(--border); border-radius: var(--radius);
}
.report-content h1, .report-content h2, .report-content h3,
.report-content h4, .report-content h5, .report-content h6 {
  margin-top: 20px; margin-bottom: 10px; line-height: 1.3;
}
.report-content h1 { font-size: 22px; border-bottom: 2px solid var(--border); padding-bottom: 8px; }
.report-content h2 { font-size: 19px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
.report-content h3 { font-size: 16px; }
.report-content h4 { font-size: 14px; }
.report-content p { margin-bottom: 10px; }
.report-content ul, .report-content ol { margin: 8px 0 8px 24px; }
.report-content li { margin-bottom: 4px; }
.report-content blockquote {
  border-left: 3px solid var(--accent); padding: 8px 16px; margin: 12px 0;
  background: rgba(45, 91, 227, 0.03); color: var(--muted);
}
.report-content hr { border: none; border-top: 1px solid var(--border); margin: 16px 0; }
.report-content .md-table {
  width: 100%; border-collapse: collapse; font-size: 13px; margin: 12px 0;
}
.report-content .md-table th {
  background: #f0f1f5; padding: 8px 10px; text-align: left; font-weight: 600;
  border-bottom: 2px solid var(--border);
}
.report-content .md-table td { padding: 8px 10px; border-bottom: 1px solid var(--border); }
.report-content .table-wrap { overflow-x: auto; }
.report-content a { color: var(--accent); text-decoration: none; }
.report-content a:hover { text-decoration: underline; }
.notice { padding: 12px 16px; border-radius: 8px; border-left: 4px solid var(--accent); background: rgba(45,91,227,.04); font-size: 12px; color: var(--muted); margin-bottom: 16px; line-height: 1.6; }
.notice strong { color: var(--text); }
.notice code { background: var(--border); padding: 1px 4px; border-radius: 3px; font-size: 11px; }

/* Narrative section */
.narrative-section { margin-bottom: 24px; }
.narrative-section .report-content { max-height: none; }

/* Responsive */
@media (max-width: 768px) {
  .tab-bar { padding: 0 8px; }
  .tab-btn { padding: 10px 12px; font-size: 12px; }
  .tab-content { padding: 16px; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .chart-grid { grid-template-columns: 1fr; }
}
"""


def _build_js() -> str:
    """Return the complete JavaScript code."""
    return """
function showTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  const target = document.getElementById(tabId);
  if (target) target.classList.add('active');
  const btn = document.querySelector('[data-tab="' + tabId + '"]');
  if (btn) btn.classList.add('active');
}

function showSubTab(parentId, subTabId) {
  const parent = document.getElementById(parentId);
  if (!parent) return;
  parent.querySelectorAll('.subtab-content').forEach(el => el.classList.remove('active'));
  parent.querySelectorAll('.subtab-btn').forEach(el => el.classList.remove('active'));
  const target = parent.querySelector('#' + subTabId);
  if (target) target.classList.add('active');
  const btn = parent.querySelector('[data-subtab="' + subTabId + '"]');
  if (btn) btn.classList.add('active');
}

document.addEventListener('DOMContentLoaded', function() {
  showTab('tab-overview');
});
"""


# ---------------------------------------------------------------------------
# Component Renderers
# ---------------------------------------------------------------------------

def _rank_tier_class(rank: int) -> str:
    """Return CSS class for rank badge tier."""
    if rank <= 3:
        return "rank-tier-1"
    elif rank <= 10:
        return "rank-tier-2"
    else:
        return "rank-tier-3"


def _steeps_tag_html(code: str) -> str:
    """Render a STEEPs category tag."""
    labels = {
        "S": "S 사회", "T": "T 기술", "E": "E 경제",
        "Env": "E 환경", "P": "P 정치", "s": "s 정신",
    }
    label = labels.get(code, code)
    color = STEEPS_COLORS.get(code, "#5f6577")
    return f'<span class="steeps-tag" style="background:{color}">{_esc(label)}</span>'


def _wf_badge_html(wf_key: str) -> str:
    """Render a WF badge."""
    label = WF_LABELS_SHORT.get(wf_key, wf_key)
    color = WF_CSS_HEX.get(wf_key, "#5f6577")
    return f'<span class="wf-badge" style="background:{color}">{_esc(label)}</span>'


def _fssf_tag_html(fssf_type: str) -> str:
    """Render an FSSF type tag."""
    if not fssf_type:
        return ""
    color = FSSF_COLORS.get(fssf_type, "#5f6577")
    return f'<span class="fssf-tag" style="background:{color}">{_esc(fssf_type)}</span>'


def _gate_status_html(status: str) -> str:
    """Render a gate status badge."""
    s = status.upper() if status else "N/A"
    if s == "PASS":
        return '<span class="gate-pass">PASS</span>'
    elif s == "FAIL":
        return '<span class="gate-fail">FAIL</span>'
    elif s == "WARN":
        return '<span class="gate-warn">WARN</span>'
    return f'<span>{_esc(s)}</span>'


def _source_display(source: Any) -> str:
    """Extract display name from source field (may be string or dict)."""
    if isinstance(source, dict):
        parts = []
        if source.get("press"):
            parts.append(source["press"])
        elif source.get("name"):
            parts.append(source["name"])
        return " / ".join(parts) if parts else "N/A"
    elif isinstance(source, str):
        return source
    return "N/A"


# ---------------------------------------------------------------------------
# Tab Builders
# ---------------------------------------------------------------------------

_DATA_SOURCE_NOTICE = '''<div class="notice">
<strong>데이터 출처 안내</strong>: 이 탭의 모든 정량 데이터(시그널 수, STEEPs 분포, 리스크 확률 등)는 <code>dashboard_data_extractor.py</code>가 원본 JSON에서 직접 계산한 값입니다. 보고서 원문 탭의 수치는 LLM이 분석 과정에서 기술한 값으로, Python 계산 값과 다를 수 있습니다. <strong>정량 데이터는 이 요약 탭의 Python 계산 값이 정확합니다.</strong>
</div>'''


def build_overview_tab(data: Dict) -> str:
    """Build the '종합 개요' tab content."""
    kpis = data.get("kpis", {})
    steeps = data.get("steeps", {})
    fssf = data.get("fssf", {})
    narratives = data.get("narratives", {})

    total_signals = kpis.get("total_signals", 0)
    per_wf = kpis.get("per_workflow", {})
    gates = kpis.get("master_gates", {})
    integration = kpis.get("integration", {})

    # --- Data Source Notice ---
    kpi_html = _DATA_SOURCE_NOTICE

    # --- KPI Cards ---
    kpi_html += '<div class="kpi-grid">'
    kpi_html += f'''
    <div class="kpi-card">
      <div class="kpi-value">{total_signals}</div>
      <div class="kpi-label">총 시그널 수</div>
      <div class="kpi-sub">Total Signals</div>
    </div>'''

    for wf_key in WF_KEYS:
        wf_info = per_wf.get(wf_key, {})
        count = wf_info.get("signal_count", 0)
        status = wf_info.get("status", "unknown")
        validation = wf_info.get("validation", "N/A")
        color = WF_CSS_HEX.get(wf_key, "#5f6577")
        label = WF_LABELS.get(wf_key, wf_key)
        kpi_html += f'''
    <div class="kpi-card" style="border-top: 3px solid {color}">
      <div class="kpi-value" style="color:{color}">{count}</div>
      <div class="kpi-label">{_esc(label)}</div>
      <div class="kpi-sub">{_esc(validation)}</div>
    </div>'''

    kpi_html += '</div>'

    # --- Gate Status ---
    gate_html = '<div class="card"><div class="card-title">마스터 게이트 상태</div><div style="display:flex;gap:16px;flex-wrap:wrap">'
    for gate_id in ["M1", "M2", "M2a", "M2b", "M3"]:
        gate_info = gates.get(gate_id, {})
        status = gate_info.get("status", "N/A")
        gate_html += f'<div style="text-align:center"><div style="font-size:12px;color:var(--muted)">{gate_id}</div><div>{_gate_status_html(status)}</div></div>'
    # Integration status
    int_status = integration.get("status", "N/A")
    int_validation = integration.get("validation", "N/A")
    gate_html += f'<div style="text-align:center"><div style="font-size:12px;color:var(--muted)">통합</div><div>{_gate_status_html(int_status)}</div><div style="font-size:10px;color:var(--muted)">{_esc(str(int_validation))}</div></div>'
    gate_html += '</div></div>'

    # --- Chart data (inline JSON for Chart.js) ---
    steeps_total = steeps.get("total", {})
    steeps_labels_map = steeps.get("labels", {})
    steeps_chart_labels = []
    steeps_chart_values = []
    steeps_chart_colors = []
    for code in STEEPS_ORDER:
        steeps_chart_labels.append(steeps_labels_map.get(code, code))
        steeps_chart_values.append(steeps_total.get(code, 0))
        steeps_chart_colors.append(STEEPS_COLORS.get(code, "#5f6577"))

    fssf_total = fssf.get("total", {})
    fssf_chart_labels = []
    fssf_chart_values = []
    fssf_chart_colors = []
    for ftype in FSSF_ORDER:
        if ftype in fssf_total:
            fssf_chart_labels.append(ftype)
            fssf_chart_values.append(fssf_total[ftype])
            fssf_chart_colors.append(FSSF_COLORS.get(ftype, "#5f6577"))

    # WF pie chart data
    wf_pie_labels = []
    wf_pie_values = []
    wf_pie_colors = []
    for wf_key in WF_KEYS:
        wf_info = per_wf.get(wf_key, {})
        count = wf_info.get("signal_count", 0)
        if count > 0:
            wf_pie_labels.append(WF_LABELS.get(wf_key, wf_key))
            wf_pie_values.append(count)
            wf_pie_colors.append(WF_CSS_HEX.get(wf_key, "#5f6577"))

    charts_html = '<div class="chart-grid">'

    # STEEPs Radar
    charts_html += f'''
    <div class="chart-box">
      <div class="card-title">STEEPs 분포 (레이더)</div>
      <canvas id="steepsRadar"></canvas>
    </div>'''

    # FSSF Bar
    if fssf_chart_labels:
        charts_html += f'''
    <div class="chart-box">
      <div class="card-title">FSSF 유형 분포</div>
      <canvas id="fssfBar"></canvas>
    </div>'''

    # WF Pie
    charts_html += f'''
    <div class="chart-box">
      <div class="card-title">워크플로우별 시그널 비율</div>
      <canvas id="wfPie"></canvas>
    </div>'''

    charts_html += '</div>'

    # Chart.js initialization script
    chart_script = f'''
<script>
document.addEventListener('DOMContentLoaded', function() {{
  // Guard: skip all chart init if Chart.js unavailable (CDN offline)
  if (typeof Chart === 'undefined') return;

  // STEEPs Radar Chart
  const steepsCtx = document.getElementById('steepsRadar');
  if (steepsCtx) {{
    new Chart(steepsCtx, {{
      type: 'radar',
      data: {{
        labels: {json.dumps(steeps_chart_labels, ensure_ascii=False)},
        datasets: [{{
          label: '시그널 수',
          data: {json.dumps(steeps_chart_values)},
          backgroundColor: 'rgba(45, 91, 227, 0.15)',
          borderColor: 'rgba(45, 91, 227, 0.8)',
          borderWidth: 2,
          pointBackgroundColor: {json.dumps(steeps_chart_colors)},
          pointRadius: 5,
        }}]
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ display: false }},
          datalabels: {{
            color: '#1a1d27',
            font: {{ size: 11, weight: 'bold' }},
            anchor: 'end',
            align: 'end',
            offset: 4,
          }}
        }},
        scales: {{
          r: {{
            beginAtZero: true,
            ticks: {{ stepSize: 5, font: {{ size: 10 }} }},
            pointLabels: {{ font: {{ size: 11 }} }}
          }}
        }}
      }},
      plugins: [ChartDataLabels]
    }});
  }}

  // FSSF Bar Chart
  const fssfCtx = document.getElementById('fssfBar');
  if (fssfCtx) {{
    new Chart(fssfCtx, {{
      type: 'bar',
      data: {{
        labels: {json.dumps(fssf_chart_labels, ensure_ascii=False)},
        datasets: [{{
          data: {json.dumps(fssf_chart_values)},
          backgroundColor: {json.dumps(fssf_chart_colors)},
          borderRadius: 6,
          barThickness: 32,
        }}]
      }},
      options: {{
        responsive: true,
        indexAxis: 'y',
        plugins: {{
          legend: {{ display: false }},
          datalabels: {{
            color: '#fff',
            font: {{ size: 11, weight: 'bold' }},
            anchor: 'center',
            align: 'center',
          }}
        }},
        scales: {{
          x: {{ beginAtZero: true, ticks: {{ stepSize: 5 }} }},
          y: {{ ticks: {{ font: {{ size: 11 }} }} }}
        }}
      }},
      plugins: [ChartDataLabels]
    }});
  }}

  // WF Pie Chart
  const wfCtx = document.getElementById('wfPie');
  if (wfCtx) {{
    new Chart(wfCtx, {{
      type: 'doughnut',
      data: {{
        labels: {json.dumps(wf_pie_labels, ensure_ascii=False)},
        datasets: [{{
          data: {json.dumps(wf_pie_values)},
          backgroundColor: {json.dumps(wf_pie_colors)},
          borderWidth: 2,
          borderColor: '#fff',
        }}]
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ position: 'bottom', labels: {{ font: {{ size: 12 }}, padding: 16 }} }},
          datalabels: {{
            color: '#fff',
            font: {{ size: 13, weight: 'bold' }},
            formatter: function(value, ctx) {{
              var total = ctx.chart.data.datasets[0].data.reduce(function(a,b){{ return a+b; }}, 0);
              return Math.round(value/total*100) + '%';
            }}
          }}
        }}
      }},
      plugins: [ChartDataLabels]
    }});
  }}
}});
</script>'''

    # --- Mega Themes (from narratives section 1) ---
    mega_html = ""
    exec_summary = narratives.get("1. Executive Summary", "")
    if exec_summary:
        mega_themes = _extract_mega_themes(exec_summary)
        if mega_themes:
            mega_html = '<div class="card"><div class="card-title">3대 메가 테마</div>'
            theme_colors = [WF_CSS_HEX["wf1-general"], WF_CSS_HEX["wf2-arxiv"], WF_CSS_HEX["wf3-naver"]]
            for i, theme in enumerate(mega_themes[:3]):
                color = theme_colors[i % len(theme_colors)]
                mega_html += f'''
      <div class="mega-theme" style="border-left-color:{color}">
        <h4>{_esc(theme["title"])}</h4>
        <p>{_esc(theme["description"])}</p>
      </div>'''
            mega_html += '</div>'

    return f'''
    {kpi_html}
    {gate_html}
    {charts_html}
    {chart_script}
    {mega_html}
    '''


def _extract_mega_themes(exec_summary: str) -> List[Dict]:
    """Extract top 3 themes from Executive Summary narrative text."""
    themes = []
    # Pattern: numbered items with bold titles
    # e.g. "1. **Title** [WF1] [WF4]\n   - Description"
    pattern = re.compile(
        r'^\d+\.\s+\*\*(.+?)\*\*\s*((?:\[WF\d+\]\s*)*)\s*\n\s*[-–]\s*(.+?)(?=\n\d+\.|\n###|\Z)',
        re.MULTILINE | re.DOTALL
    )
    for m in pattern.finditer(exec_summary):
        title = m.group(1).strip()
        wf_tags = m.group(2).strip()
        desc_block = m.group(3).strip()
        # Take first line of description
        desc_lines = desc_block.split("\n")
        desc = desc_lines[0].strip().lstrip("- ")
        if wf_tags:
            title = f"{title} {wf_tags}"
        themes.append({"title": title, "description": desc})

    # Fallback: try simpler pattern
    if not themes:
        for line in exec_summary.split("\n"):
            m2 = re.match(r'^\d+\.\s+\*\*(.+?)\*\*(.*)$', line.strip())
            if m2:
                title = m2.group(1).strip()
                rest = m2.group(2).strip()
                themes.append({"title": title, "description": rest})

    return themes[:3]


def build_top20_tab(data: Dict) -> str:
    """Build the 'Top 20 통합' tab — all WFs merged, sorted by psst_score."""
    top_signals = data.get("top_signals", {})

    # Merge all WFs, annotate with WF key
    all_signals = []
    for wf_key in WF_KEYS:
        for sig in top_signals.get(wf_key, []):
            sig_copy = dict(sig)
            sig_copy["_wf"] = wf_key
            all_signals.append(sig_copy)

    # Sort by psst_score descending, then impact_score descending
    all_signals.sort(key=lambda s: (-s.get("psst_score", 0), -s.get("impact_score", 0)))
    top20 = all_signals[:20]

    if not top20:
        return '<div class="card"><p>통합 Top 20 시그널 데이터 없음</p></div>'

    rows = ""
    for i, sig in enumerate(top20, 1):
        tier = _rank_tier_class(i)
        title = sig.get("title", "N/A")
        steeps = sig.get("steeps", "?")
        fssf = sig.get("fssf_type", "")
        impact = sig.get("impact_score", 0)
        psst = sig.get("psst_score", 0)
        source = _source_display(sig.get("source", ""))
        wf_key = sig.get("_wf", "")

        # Determine if title is English (simple heuristic: mostly ASCII)
        is_english = sum(1 for c in title if ord(c) < 128) / max(len(title), 1) > 0.7
        ko_annotation = ""
        if is_english:
            # For English titles, we show a small Korean annotation hint
            ko_annotation = '<div style="font-size:11px;color:var(--muted);margin-top:2px">[EN]</div>'
        else:
            ko_annotation = '<div style="font-size:11px;color:var(--muted);margin-top:2px">[KO]</div>'

        rows += f'''<tr>
  <td><span class="rank-badge {tier}">{i}</span></td>
  <td>
    <div style="font-weight:600">{_esc(title)}</div>
    {ko_annotation}
  </td>
  <td>{_steeps_tag_html(steeps)}</td>
  <td>{_fssf_tag_html(fssf)}</td>
  <td>{_esc(source)}</td>
  <td style="text-align:right">{impact}</td>
  <td style="text-align:right;font-weight:700">{psst}</td>
  <td>{_wf_badge_html(wf_key)}</td>
</tr>'''

    return f'''
    <div class="card">
      <div class="card-title">Top 20 통합 시그널 (pSST 기준 정렬)</div>
      <div style="overflow-x:auto">
        <table class="signal-table">
          <thead><tr>
            <th style="width:44px">#</th>
            <th>시그널 제목</th>
            <th>STEEPs</th>
            <th>FSSF</th>
            <th>출처</th>
            <th style="text-align:right">영향도</th>
            <th style="text-align:right">pSST</th>
            <th>WF</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>'''


def build_wf_summary_tab(data: Dict, wf_key: str) -> str:
    """Build a per-WF summary tab with signal table."""
    top_signals = data.get("top_signals", {}).get(wf_key, [])
    label = WF_LABELS.get(wf_key, wf_key)
    color = WF_CSS_HEX.get(wf_key, "#5f6577")

    kpis = data.get("kpis", {}).get("per_workflow", {}).get(wf_key, {})
    count = kpis.get("signal_count", 0)
    validation = kpis.get("validation", "N/A")

    steeps_wf = data.get("steeps", {}).get("per_workflow", {}).get(wf_key, {})

    # STEEPs mini distribution
    steeps_mini = ""
    for code in STEEPS_ORDER:
        val = steeps_wf.get(code, 0)
        if val > 0:
            steeps_mini += f'{_steeps_tag_html(code)} <span style="font-size:12px;margin-right:8px">{val}</span>'

    if not top_signals:
        return f'''
    <div class="card" style="border-top:3px solid {color}">
      <div class="card-title">{_esc(label)} — 시그널 요약</div>
      <p>시그널 데이터 없음</p>
    </div>'''

    rows = ""
    for sig in top_signals:
        rank = sig.get("rank", "-")
        title = sig.get("title", "N/A")
        steeps = sig.get("steeps", "?")
        fssf = sig.get("fssf_type", "")
        impact = sig.get("impact_score", 0)
        psst = sig.get("psst_score", 0)
        source = _source_display(sig.get("source", ""))

        rows += f'''<tr>
  <td style="text-align:center;font-weight:700">{rank}</td>
  <td style="font-weight:600">{_esc(title)}</td>
  <td>{_steeps_tag_html(steeps)}</td>
  <td>{_fssf_tag_html(fssf)}</td>
  <td>{_esc(source)}</td>
  <td style="text-align:right">{impact}</td>
  <td style="text-align:right;font-weight:700">{psst}</td>
</tr>'''

    return f'''
    <div class="card" style="border-top:3px solid {color}">
      <div class="card-title">{_esc(label)} — 시그널 요약</div>
      <div style="display:flex;gap:16px;align-items:center;margin-bottom:12px">
        <span style="font-size:24px;font-weight:800;color:{color}">{count}</span>
        <span style="font-size:12px;color:var(--muted)">시그널</span>
        <span style="font-size:12px;color:var(--muted)">검증: {_esc(validation)}</span>
      </div>
      <div style="margin-bottom:12px">{steeps_mini}</div>
      <div style="overflow-x:auto">
        <table class="signal-table">
          <thead><tr>
            <th style="width:44px;text-align:center">순위</th>
            <th>시그널 제목</th>
            <th>STEEPs</th>
            <th>FSSF</th>
            <th>출처</th>
            <th style="text-align:right">영향도</th>
            <th style="text-align:right">pSST</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>'''


def build_patterns_tab(data: Dict) -> str:
    """Build the '패턴·클러스터' tab from narratives section 4."""
    narratives = data.get("narratives", {})
    section4 = narratives.get("4. Patterns and Connections", "")
    cross_wf = data.get("cross_wf", {})
    reinforcement_count = cross_wf.get("reinforcement_count", 0)
    reinforcements = cross_wf.get("reinforcements", [])

    content_html = md_to_html(section4) if section4 else "<p><em>패턴 및 연결 데이터 없음</em></p>"

    # Cross-WF reinforcement table
    reinf_html = ""
    if reinforcements:
        reinf_rows = ""
        for r in reinforcements:
            reinf_rows += f'''<tr>
  <td>{_wf_badge_html(r.get("wf_a", ""))}</td>
  <td>{_esc(r.get("signal_a", ""))}</td>
  <td>{_wf_badge_html(r.get("wf_b", ""))}</td>
  <td>{_esc(r.get("signal_b", ""))}</td>
  <td style="text-align:right">{r.get("overlap_score", 0)}</td>
  <td>{_esc(", ".join(r.get("shared_terms", [])[:5]))}</td>
</tr>'''
        reinf_html = f'''
    <div class="card">
      <div class="card-title">교차 워크플로우 강화 ({reinforcement_count}건)</div>
      <div style="overflow-x:auto">
        <table class="signal-table">
          <thead><tr><th>WF A</th><th>시그널 A</th><th>WF B</th><th>시그널 B</th><th style="text-align:right">유사도</th><th>공유 키워드</th></tr></thead>
          <tbody>{reinf_rows}</tbody>
        </table>
      </div>
    </div>'''
    else:
        reinf_html = f'''
    <div class="card">
      <div class="card-title">교차 워크플로우 강화</div>
      <p style="color:var(--muted)">교차 워크플로우 강화 감지: {reinforcement_count}건</p>
    </div>'''

    return f'''
    <div class="card">
      <div class="card-title">패턴 및 연결</div>
      <div class="report-content narrative-section">{content_html}</div>
    </div>
    {reinf_html}
    '''


def build_strategic_tab(data: Dict) -> str:
    """Build the '전략적 함의' tab from narratives section 5 + risk matrix."""
    narratives = data.get("narratives", {})
    section5 = narratives.get("5. Strategic Implications", "")
    risk_matrix = data.get("risk_matrix", [])

    content_html = md_to_html(section5) if section5 else "<p><em>전략적 함의 데이터 없음</em></p>"

    # Risk matrix table
    risk_html = ""
    if risk_matrix:
        risk_rows = ""
        for rm in risk_matrix:
            prob = rm.get("probability", 0)
            impact = rm.get("avg_impact", 0)
            sig_count = rm.get("signal_count", 0)
            cross_count = rm.get("cross_wf_count", 0)
            category = rm.get("category", "")
            source_wfs = rm.get("source_wfs", [])

            # Color based on probability
            if prob >= 60:
                bar_color = "var(--red)"
            elif prob >= 40:
                bar_color = "var(--orange)"
            else:
                bar_color = "var(--green)"

            wf_badges = " ".join(_wf_badge_html(wf) for wf in source_wfs)

            risk_rows += f'''<tr>
  <td style="font-weight:600">{_esc(category)}</td>
  <td style="width:140px">
    <div style="display:flex;align-items:center;gap:8px">
      <div class="risk-bar" style="flex:1"><div class="risk-bar-fill" style="width:{prob}%;background:{bar_color}"></div></div>
      <span style="font-weight:700;font-size:12px">{prob}%</span>
    </div>
  </td>
  <td style="text-align:right">{impact}</td>
  <td style="text-align:right">{sig_count}</td>
  <td style="text-align:right">{cross_count}</td>
  <td>{wf_badges}</td>
</tr>'''

        risk_html = f'''
    <div class="card">
      <div class="card-title">리스크 매트릭스</div>
      <div style="overflow-x:auto">
        <table class="risk-table">
          <thead><tr>
            <th>리스크 카테고리</th>
            <th>확률</th>
            <th style="text-align:right">평균 영향도</th>
            <th style="text-align:right">시그널 수</th>
            <th style="text-align:right">교차 WF</th>
            <th>출처 WF</th>
          </tr></thead>
          <tbody>{risk_rows}</tbody>
        </table>
      </div>
    </div>'''

    return f'''
    <div class="card">
      <div class="card-title">전략적 함의</div>
      <div class="report-content narrative-section">{content_html}</div>
    </div>
    {risk_html}
    '''


def build_scenario_tab(data: Dict) -> str:
    """Build the '시나리오·리스크' tab from narratives section 6 + risk matrix."""
    narratives = data.get("narratives", {})
    section6 = narratives.get("6. Plausible Scenarios", "")
    risk_matrix = data.get("risk_matrix", [])

    content_html = md_to_html(section6) if section6 else "<p><em>시나리오 데이터 없음</em></p>"

    # Risk matrix summary (compact visual)
    risk_summary = ""
    if risk_matrix:
        cards = ""
        for rm in risk_matrix:
            prob = rm.get("probability", 0)
            category = rm.get("category", "")
            impact = rm.get("avg_impact", 0)
            sig_count = rm.get("signal_count", 0)

            if prob >= 60:
                border_color = "var(--red)"
                bg = "rgba(220, 38, 38, 0.04)"
            elif prob >= 40:
                border_color = "var(--orange)"
                bg = "rgba(234, 88, 12, 0.04)"
            else:
                border_color = "var(--green)"
                bg = "rgba(5, 150, 105, 0.04)"

            cards += f'''
      <div style="border:1px solid var(--border);border-left:4px solid {border_color};border-radius:var(--radius);padding:14px;background:{bg}">
        <div style="font-weight:700;font-size:13px;margin-bottom:6px">{_esc(category)}</div>
        <div style="display:flex;gap:16px;font-size:12px;color:var(--muted)">
          <span>확률: <strong style="color:var(--text)">{prob}%</strong></span>
          <span>영향도: <strong style="color:var(--text)">{impact}</strong></span>
          <span>시그널: <strong style="color:var(--text)">{sig_count}</strong></span>
        </div>
      </div>'''

        risk_summary = f'''
    <div class="card">
      <div class="card-title">리스크 카테고리 요약</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px">
        {cards}
      </div>
    </div>'''

    return f'''
    <div class="card">
      <div class="card-title">시나리오 및 리스크</div>
      <div class="report-content narrative-section">{content_html}</div>
    </div>
    {risk_summary}
    '''


def build_report_tab(
    report_key: str,
    en_content: str,
    ko_content: str,
) -> str:
    """Build a report tab with EN/KO sub-tabs."""
    tab_id = f"report-{report_key}"
    en_sub_id = f"{tab_id}-en"
    ko_sub_id = f"{tab_id}-ko"

    en_html = md_to_html(en_content) if en_content else "<p><em>EN 보고서 없음</em></p>"
    ko_html = md_to_html(ko_content) if ko_content else "<p><em>KO 보고서 없음</em></p>"

    # KO is default active; EN is secondary toggle
    return f'''
    <div class="subtab-bar">
      <button class="subtab-btn active" data-subtab="{ko_sub_id}" onclick="showSubTab('{tab_id}', '{ko_sub_id}')">한국어</button>
      <button class="subtab-btn" data-subtab="{en_sub_id}" onclick="showSubTab('{tab_id}', '{en_sub_id}')">English</button>
    </div>
    <div id="{ko_sub_id}" class="subtab-content active">
      <div class="report-content">{ko_html}</div>
    </div>
    <div id="{en_sub_id}" class="subtab-content">
      <div class="report-content">{en_html}</div>
    </div>
    '''


# ---------------------------------------------------------------------------
# Main Assembly
# ---------------------------------------------------------------------------

class DashboardGenerator:
    """
    Assembles an interactive HTML dashboard from dashboard-data.json and report files.
    ALL quantitative data comes from dashboard-data.json. NEVER from report text parsing.
    """

    def __init__(
        self,
        date: str,
        data: Dict,
        registry: Optional[Dict] = None,
        project_root: Optional[Path] = None,
    ):
        self.date = date
        self.data = data
        self.registry = registry or {}
        self.project_root = project_root or Path.cwd()

    def _resolve_report_paths(self) -> Dict[str, Dict[str, Path]]:
        """
        Resolve EN/KO report file paths from SOT (registry).
        Falls back to default patterns if SOT unavailable.
        """
        report_patterns = resolve_report_patterns_from_sot(self.registry)
        paths = {}
        for key, patterns in report_patterns.items():
            base_dir = self.project_root / patterns["base_dir"]
            en_file = base_dir / patterns["en"].format(date=self.date)
            ko_file = base_dir / patterns["ko"].format(date=self.date)
            paths[key] = {"en": en_file, "ko": ko_file}
        return paths

    def _load_reports(self) -> Dict[str, Dict[str, str]]:
        """Load all EN/KO report files."""
        report_paths = self._resolve_report_paths()
        reports = {}
        for key, paths in report_paths.items():
            en_content = load_report_file(paths["en"])
            ko_content = load_report_file(paths["ko"])
            reports[key] = {"en": en_content, "ko": ko_content}
            en_size = len(en_content)
            ko_size = len(ko_content)
            print(f"  Report [{key}]: EN={en_size:,} chars, KO={ko_size:,} chars")
        return reports

    def generate(self) -> str:
        """Generate the complete HTML dashboard."""
        print(f"[DashboardGenerator] Generating dashboard for {self.date}...")

        reports = self._load_reports()
        data = self.data
        date = self.date

        # --- Build tabs ---
        overview_content = build_overview_tab(data)
        top20_content = build_top20_tab(data)

        wf_tabs = {}
        for wf_key in WF_KEYS:
            wf_tabs[wf_key] = build_wf_summary_tab(data, wf_key)

        patterns_content = build_patterns_tab(data)
        strategic_content = build_strategic_tab(data)
        scenario_content = build_scenario_tab(data)

        # Timeline map tab (with fallback transparency)
        timeline_md = data.get("timeline_map")
        timeline_meta = data.get("timeline_map_meta") or {}
        timeline_content = ""
        if timeline_md:
            timeline_html = md_to_html(timeline_md)
            # Show fallback warning if timeline is not from today
            timeline_banner = ""
            if timeline_meta.get("source") == "fallback":
                fb_date = _esc(timeline_meta.get("fallback_date", "?"))
                fb_file = _esc(timeline_meta.get("file", "?"))
                timeline_banner = f'''<div class="notice" style="border-left-color:var(--orange);background:rgba(234,88,12,0.04);margin-bottom:16px">
<strong>Fallback 데이터</strong>: 금일({_esc(date)}) 타임라인 맵이 생성되지 않아 가장 최근 파일(<code>{fb_file}</code>, {fb_date})을 표시합니다. 최신 시그널이 반영되지 않았을 수 있습니다.
</div>'''
                timeline_label = f"timeline-map-{fb_date}.md (fallback)"
            else:
                timeline_label = f"timeline-map-{_esc(date)}.md"
            timeline_content = f'''
{timeline_banner}
<div class="card report-card">
<div class="card-hdr"><span class="card-title">타임라인 맵 (Timeline Map)</span><span class="muted-sm">{timeline_label}</span></div>
<div class="report-body">{timeline_html}</div>
</div>'''
        else:
            timeline_content = '<div class="card"><p class="muted-sm">이번 스캔 주기에 타임라인 맵이 생성되지 않았습니다.</p></div>'

        report_tabs = {}
        report_order = ["wf1-general", "wf2-arxiv", "wf3-naver", "wf4-multiglobal-news", "integrated"]
        for rkey in report_order:
            rdata = reports.get(rkey, {"en": "", "ko": ""})
            report_tabs[rkey] = build_report_tab(rkey, rdata["en"], rdata["ko"])

        # --- Assemble tab bar ---
        tab_buttons = []
        tab_sections = []

        # Tab definitions: (tab_id, label)
        all_tabs = [
            ("tab-overview", "종합 개요"),
            ("tab-top20", "Top 20 통합"),
        ]
        for wf_key in WF_KEYS:
            all_tabs.append((f"tab-{wf_key}", WF_LABELS.get(wf_key, wf_key)))
        all_tabs.extend([
            ("tab-patterns", "패턴·클러스터"),
            ("tab-strategic", "전략적 함의"),
            ("tab-scenario", "시나리오·리스크"),
            ("tab-timeline", "타임라인 맵"),
        ])
        for rkey in report_order:
            all_tabs.append((f"tab-report-{rkey}", REPORT_TAB_LABELS.get(rkey, rkey)))

        for tab_id, label in all_tabs:
            active = " active" if tab_id == "tab-overview" else ""
            tab_buttons.append(f'<button class="tab-btn{active}" data-tab="{tab_id}" onclick="showTab(\'{tab_id}\')">{_esc(label)}</button>')

        # Build tab content sections
        def _tab_section(tab_id: str, content: str, active: bool = False) -> str:
            cls = " active" if active else ""
            # For report tabs, add the report-key id wrapper
            extra_id = ""
            for rkey in report_order:
                if tab_id == f"tab-report-{rkey}":
                    extra_id = f' id="report-{rkey}"'
                    # Wrap content in a div with the report-key id for sub-tab targeting
                    return f'<div id="{tab_id}" class="tab-content{cls}"><div{extra_id}>{content}</div></div>'
            return f'<div id="{tab_id}" class="tab-content{cls}">{content}</div>'

        tab_sections.append(_tab_section("tab-overview", overview_content, active=True))
        tab_sections.append(_tab_section("tab-top20", top20_content))
        for wf_key in WF_KEYS:
            tab_sections.append(_tab_section(f"tab-{wf_key}", wf_tabs[wf_key]))
        tab_sections.append(_tab_section("tab-patterns", patterns_content))
        tab_sections.append(_tab_section("tab-strategic", strategic_content))
        tab_sections.append(_tab_section("tab-scenario", scenario_content))
        tab_sections.append(_tab_section("tab-timeline", timeline_content))
        for rkey in report_order:
            tab_sections.append(_tab_section(f"tab-report-{rkey}", report_tabs[rkey]))

        metadata = data.get("metadata", {})
        extractor_version = metadata.get("extractor_version", "?")

        html_output = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>환경스캐닝 대시보드 — {_esc(date)}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4" onerror="window.__chartjsFailed=true"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2" onerror="window.__chartjsFailed=true"></script>
<script>
// CDN fallback: if Chart.js failed to load (offline), remove canvas elements
// and show fallback messages. canvas.remove() ensures getElementById returns null
// in chart init code, preventing uncaught ReferenceError on new Chart().
window.addEventListener('DOMContentLoaded', function() {{
  if (window.__chartjsFailed || typeof Chart === 'undefined') {{
    document.querySelectorAll('.chart-box canvas').forEach(function(c) {{
      var p = c.parentElement;
      c.remove();
      var msg = document.createElement('div');
      msg.style.cssText = 'padding:32px;text-align:center;color:#5f6577;font-size:13px;border:1px dashed #e2e4ea;border-radius:8px;background:#f9fafb';
      msg.innerHTML = '<strong>차트 로딩 실패</strong><br>오프라인 환경에서는 Chart.js CDN에 접근할 수 없습니다.<br>정량 데이터는 각 탭의 테이블에서 확인하세요.';
      p.appendChild(msg);
    }});
    window.__chartjsOffline = true;
  }}
}});
</script>
<style>
{_build_css()}
</style>
</head>
<body>

<div class="dashboard-header">
  <div>
    <h1>Quadruple Environmental Scanning Dashboard</h1>
    <div class="meta">환경스캐닝 통합 대시보드 &mdash; {_esc(date)}</div>
  </div>
  <div style="text-align:right">
    <div class="meta">Generator v{VERSION} / Extractor v{_esc(extractor_version)}</div>
    <div class="meta">{_esc(metadata.get("note", ""))}</div>
  </div>
</div>

<nav class="tab-bar">
  {"".join(tab_buttons)}
</nav>

{"".join(tab_sections)}

<script>
{_build_js()}
</script>

</body>
</html>'''

        print(f"[DashboardGenerator] HTML generated: {len(html_output):,} chars")
        return html_output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Dashboard Generator — SOT-Driven Interactive HTML Dashboard"
    )
    parser.add_argument("--date", required=True, help="Scan date (YYYY-MM-DD)")
    parser.add_argument(
        "--data-file", required=True,
        help="Path to dashboard-data-{date}.json (from dashboard_data_extractor.py)"
    )
    parser.add_argument(
        "--registry", required=True,
        help="Path to workflow-registry.yaml"
    )
    parser.add_argument(
        "--output", required=True,
        help="Output path for dashboard-{date}.html"
    )
    parser.add_argument(
        "--project-root",
        help="Project root directory (default: auto-detect from registry path)"
    )
    args = parser.parse_args()

    # Load dashboard data
    data_path = Path(args.data_file)
    data = load_json(data_path)
    if not data:
        print(f"FATAL: Cannot load dashboard data from {data_path}", file=sys.stderr)
        sys.exit(1)

    # Load registry (for reference, paths are resolved via standard patterns)
    registry = load_yaml_simple(Path(args.registry))

    # Determine project root
    if args.project_root:
        project_root = Path(args.project_root)
    else:
        # registry path: env-scanning/config/workflow-registry.yaml
        # project_root: ../../ from registry
        project_root = Path(args.registry).resolve().parent.parent.parent
    print(f"[DashboardGenerator] Project root: {project_root}")

    # Validate date format
    date = args.date
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        print(f"FATAL: Invalid date format: {date} (expected YYYY-MM-DD)", file=sys.stderr)
        sys.exit(1)

    # Validate data date matches
    data_date = data.get("metadata", {}).get("date", "")
    if data_date and data_date != date:
        print(
            f"WARN: Data file date ({data_date}) does not match --date ({date})",
            file=sys.stderr
        )

    # Generate dashboard
    generator = DashboardGenerator(
        date=date,
        data=data,
        registry=registry,
        project_root=project_root,
    )
    html_output = generator.generate()

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_output, encoding="utf-8")

    file_size = output_path.stat().st_size
    print(f"[DashboardGenerator] Written to {output_path} ({file_size:,} bytes)")

    # Exit code: 0 = success
    sys.exit(0)


if __name__ == "__main__":
    main()
