#!/usr/bin/env python3
"""Tests for validate_timeline_map.py"""

import os
import re
import sys

import pytest
import yaml

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "env-scanning", "scripts"))
from validate_timeline_map import validate_timeline_map, ValidationResult


# ---------------------------------------------------------------------------
# Helper: build a valid timeline map report
# ---------------------------------------------------------------------------

def _make_valid_report(lang="en") -> str:
    """Generate a complete valid timeline map report for testing."""
    if lang == "en":
        sections = _make_valid_en()
    else:
        sections = _make_valid_ko()
    return sections


def _make_valid_en() -> str:
    # Generate enough words to pass the 3000 minimum
    filler = " ".join(["analysis"] * 600)

    themes = ""
    for i in range(1, 5):
        themes += f"""
### Theme {i}: Sample Theme {i}

**Trajectory**: This theme shows a clear upward trajectory in signal frequency.

**Judgment**: Based on cross-referencing multiple sources, this theme is accelerating.

```
Signal evolution timeline:
2026-02-28  ●  First detection (WF1)
2026-03-01  ●● Confirmation (WF2)
2026-03-06  ●●● Escalation (WF3)
```

{filler}
"""

    psst_rows = ""
    for i in range(1, 8):
        psst_rows += f"| {i} | wf1-20260306-{i:03d} | Signal Title {i} | {90 - i * 5} | up |\n"

    metadata = yaml.dump({
        "total_signals": 42,
        "period": "2026-02-28 ~ 2026-03-06",
        "assembler_version": "1.0.0",
        "scan_date": "2026-03-06",
    }, default_flow_style=False)

    return f"""# Signal Evolution Timeline Map

**Period**: 2026-02-28 ~ 2026-03-06
**Generated**: 2026-03-06
**Engine**: Timeline Map Generator v1.0.0
**Data Sources**: WF1: 10 + WF2: 12 + WF3: 10 + WF4: 10 = Total 42 signals

---

## Timeline Overview

This timeline map tracks the evolution of 42 signals across 4 workflows over a 7-day period.
The analysis reveals several accelerating themes and cross-workflow convergences.
{filler}

---

## 1. Theme-Based Temporal Tracking

> 4 themes detected | 2 escalations

{themes}

---

## 2. STEEPs Domain Temporal Distribution

| Domain | Count | Trend |
|--------|-------|-------|
| S      |     7 | up    |
| T      |    12 | stable|
| E_eco  |     5 | down  |
| E_env  |     6 | up    |
| P      |     8 | stable|
| s      |     4 | up    |

---

## 3. pSST Priority Top-10 Trajectory

| Rank | Signal ID | Title | pSST Score | Trend |
|------|-----------|-------|------------|-------|
{psst_rows}

---

## 4. Cross-Workflow Signal Trajectory

> 3 cross-WF correlations detected

| Correlation | WF Source | WF Target | Strength | Next Expected |
|-------------|-----------|-----------|----------|---------------|
| AI Regulation | WF1 | WF3 | 0.85 | Policy announcement |
| Climate Risk | WF2 | WF4 | 0.78 | Next Expected Q2 report |
| Tech Disruption | WF1 | WF2 | 0.72 | Next Expected patent filing |

---

## 5. Escalation Monitoring

| Theme | Severity | Current | Previous | Next Expected |
|-------|----------|---------|----------|---------------|
| AI Regulation | CRITICAL | 0.92 | 0.75 | Next Expected congressional hearing |
| Quantum Compute | HIGH | 0.85 | 0.60 | Next Expected demonstration |

---

## 6. Strategic Implications

- Implication 1: AI regulation is accelerating across multiple jurisdictions
- Implication 2: Climate-related signals show increasing cross-domain impact
- Implication 3: Technology disruption signals are converging with political responses
- Implication 4: Emerging market dynamics require revised monitoring parameters

---

## 7. Metadata

```yaml
{metadata.strip()}
```
"""


def _make_valid_ko() -> str:
    filler = " ".join(["분석"] * 300)

    themes = ""
    for i in range(1, 5):
        themes += f"""
### 테마 {i}: 샘플 테마 {i}

**궤적**: 이 테마는 시그널 빈도가 상승 궤적을 보인다.

**판단**: 교차 검증 결과, 이 테마는 가속화되고 있다.

```
시그널 진화 타임라인:
2026-02-28  ●  최초 탐지 (WF1)
2026-03-01  ●● 확인 (WF2)
2026-03-06  ●●● 에스컬레이션 (WF3)
```

{filler}
"""

    psst_rows = ""
    for i in range(1, 8):
        psst_rows += f"| {i} | wf1-20260306-{i:03d} | 시그널 제목 {i} | {90 - i * 5} | 상승 |\n"

    metadata = yaml.dump({
        "total_signals": 42,
        "period": "2026-02-28 ~ 2026-03-06",
        "assembler_version": "1.0.0",
        "scan_date": "2026-03-06",
    }, default_flow_style=False)

    return f"""# 시그널 진화 타임라인 맵

**기간**: 2026-02-28 ~ 2026-03-06
**생성일**: 2026-03-06
**엔진**: Timeline Map Generator v1.0.0
**데이터 소스**: WF1: 10 + WF2: 12 + WF3: 10 + WF4: 10 = 총 42 시그널

---

## 타임라인 개관

이 타임라인 맵은 4개 워크플로우에서 42개 시그널의 진화를 7일간 추적한다.
{filler}

---

## 1. 핵심 테마별 시간축 추적

> 4개 테마 탐지 | 2건 에스컬레이션

{themes}

---

## 2. STEEPs 영역별 시간축 분포

| Domain | Count | Trend |
|--------|-------|-------|
| S      |     7 | up    |
| T      |    12 | stable|

---

## 3. pSST 우선순위 Top-10 궤적

| Rank | Signal ID | Title | pSST Score | Trend |
|------|-----------|-------|------------|-------|
{psst_rows}

---

## 4. 교차 워크플로우 시그널 궤적

> 3건 교차 WF 상관관계

| 상관관계 | WF 소스 | WF 대상 | 강도 | 다음 예상 |
|----------|---------|---------|------|-----------|
| AI 규제 | WF1 | WF3 | 0.85 | 정책 발표 |

---

## 5. 에스컬레이션 모니터링

| 테마 | 심각도 | 현재 | 이전 | 다음 예상 |
|------|--------|------|------|-----------|
| AI 규제 | CRITICAL | 0.92 | 0.75 | 의회 청문회 |

---

## 6. 전략적 시사점

- 시사점 1: AI 규제가 여러 관할권에서 가속화되고 있다
- 시사점 2: 기후 관련 시그널이 교차 영역 영향을 증가시킨다
- 시사점 3: 기술 파괴 시그널이 정치적 대응과 수렴하고 있다

---

## 7. 메타데이터

```yaml
{metadata.strip()}
```
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidateTimelineMap:

    def test_all_sections_present(self):
        """Valid report with all 7 sections -> all TL-001 passes."""
        report = _make_valid_report("en")
        result = validate_timeline_map(report)
        tl001 = [r for r in result.results if r[0] == "TL-001"]
        assert len(tl001) == 1
        assert tl001[0][3] is True, f"TL-001 failed: {tl001[0][2]}"

    def test_missing_section_critical(self):
        """Report with a missing required section -> CRITICAL."""
        report = _make_valid_report("en")
        # Remove the Escalation Monitoring section entirely
        report = report.replace("## 5. Escalation Monitoring", "## 5. Something Else")
        result = validate_timeline_map(report)
        tl001 = [r for r in result.results if r[0] == "TL-001"]
        assert len(tl001) == 1
        assert tl001[0][3] is False, "TL-001 should fail with missing section"
        assert result.has_critical

    def test_placeholder_detection(self):
        """Report with remaining {{...}} placeholders -> CRITICAL."""
        report = _make_valid_report("en")
        report = report.replace("This timeline map tracks", "{{TL_OVERVIEW_NARRATIVE}} This timeline map tracks")
        result = validate_timeline_map(report)
        tl003 = [r for r in result.results if r[0] == "TL-003"]
        assert len(tl003) == 1
        assert tl003[0][3] is False, "TL-003 should fail with unfilled placeholders"
        assert result.has_critical

    def test_min_word_count(self):
        """Report below 3000 words -> CRITICAL."""
        # Create a minimal report with all sections but very few words
        report = """# Signal Evolution Timeline Map

## Timeline Overview
Short.

## 1. Theme-Based Temporal Tracking
### Theme 1: A
trajectory judgment
```
code
```
### Theme 2: B
trajectory judgment
```
code
```
### Theme 3: C
trajectory judgment
```
code
```

## 2. STEEPs Domain Temporal Distribution
| Domain | Count | Trend |
|--------|-------|-------|
| S | 1 | up |

## 3. pSST Priority Top-10 Trajectory
| Rank | Signal ID | Title | pSST Score | Trend |
|------|-----------|-------|------------|-------|
| 1 | a | b | 1 | up |
| 2 | a | b | 1 | up |
| 3 | a | b | 1 | up |
| 4 | a | b | 1 | up |
| 5 | a | b | 1 | up |

## 4. Cross-Workflow Signal Trajectory
Short.

## 5. Escalation Monitoring
| Theme | Next Expected |
|-------|---------------|
| A | B |

## 6. Strategic Implications
- a
- b
- c

## 7. Metadata

```yaml
total_signals: 1
```
"""
        result = validate_timeline_map(report)
        tl004 = [r for r in result.results if r[0] == "TL-004"]
        assert len(tl004) == 1
        assert tl004[0][3] is False, f"TL-004 should fail: word count too low. {tl004[0][2]}"

    def test_trajectory_presence(self):
        """Each theme has trajectory mentions -> PASS."""
        report = _make_valid_report("en")
        result = validate_timeline_map(report)
        tl006 = [r for r in result.results if r[0] == "TL-006"]
        assert len(tl006) == 1
        assert tl006[0][3] is True, f"TL-006 failed: {tl006[0][2]}"

    def test_judgment_presence(self):
        """Each theme has judgment mentions -> PASS."""
        report = _make_valid_report("en")
        result = validate_timeline_map(report)
        tl007 = [r for r in result.results if r[0] == "TL-007"]
        assert len(tl007) == 1
        assert tl007[0][3] is True, f"TL-007 failed: {tl007[0][2]}"

    def test_psst_table_row_count(self):
        """pSST table with >= 5 rows -> PASS."""
        report = _make_valid_report("en")
        result = validate_timeline_map(report)
        tl009 = [r for r in result.results if r[0] == "TL-009"]
        assert len(tl009) == 1
        assert tl009[0][3] is True, f"TL-009 failed: {tl009[0][2]}"

    def test_metadata_total_consistency(self):
        """Metadata total_signals matches -> PASS (advisory)."""
        report = _make_valid_report("en")
        result = validate_timeline_map(report)
        tl011 = [r for r in result.results if r[0] == "TL-011"]
        assert len(tl011) == 1
        assert tl011[0][3] is True, f"TL-011 failed: {tl011[0][2]}"

    def test_pass_on_valid_report(self):
        """Full valid report -> no CRITICAL failures (exit code 0)."""
        report = _make_valid_report("en")
        result = validate_timeline_map(report)
        assert not result.has_critical, (
            f"Valid report has CRITICAL failures:\n{result.summary()}"
        )
