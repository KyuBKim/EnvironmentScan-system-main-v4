---
name: translator
description: 환경스캐닝 보고서 한국어 번역 전문 스킬. EN 보고서를 KO로 번역하고 품질을 검증한다. 사용 시점 — (1) 워크플로우에서 KO 보고서 누락 시, (2) 사용자가 보고서 번역을 요청할 때, (3) 대시보드 빌드 전 KO 파일 보장이 필요할 때. /translate 커맨드로 호출.
---

# Korean Translation Skill (환경스캐닝 보고서 한국어 번역)

## Purpose

환경스캐닝 시스템의 영어(EN) 보고서를 한국어(KO)로 번역한다.
번역 품질을 `translation_validator.py`로 검증하고, `translation-terms.yaml` 용어집을 준수한다.

---

## When to Use

1. **워크플로우 완료 후 KO 보고서 누락**: Step 5.2(대시보드)에서 KO 파일 부재 감지 시
2. **사용자 수동 요청**: `/translate` 커맨드 실행
3. **M4 Gate 보완**: CG-002/004 실패 시 자동 호출

---

## Architecture

```
┌──────────────────────────────────────────────┐
│  Translator Skill                            │
│                                              │
│  Input: EN 보고서 (.md)                       │
│  Terms: translation-terms.yaml (200+ 용어)    │
│  Agent: @translation-agent (LLM 번역)        │
│  Validate: translation_validator.py (11 checks│
│  Output: KO 보고서 (*-ko.md)                  │
└──────────────────────────────────────────────┘
```

---

## Execution Modes

### Mode 1: Single File Translation

```
/translate --file <path-to-en-report.md>
```

1. Read EN source file
2. Determine output path (`*-ko.md` suffix convention)
3. Read `env-scanning/config/translation-terms.yaml`
4. Invoke `@translation-agent` sub-agent with:
   - Source file path
   - Output file path
   - Terminology map
   - Quality threshold: 0.95
5. Run `translation_validator.py` on output
6. Report result

### Mode 2: All Reports for a Date

```
/translate --date 2026-03-24
```

1. Read SOT (`workflow-registry.yaml`) for enabled workflows
2. For each enabled WF, check if KO report exists
3. Translate ALL missing KO reports (parallel where possible)
4. Validate each KO report
5. Summary report

### Mode 3: Auto (called from Step 5.2)

When invoked programmatically from the dashboard step:

1. Receive list of missing KO file paths
2. Translate each (EN source path → KO output path)
3. Validate
4. Return success/failure list

---

## Translation Protocol

### Step 1: Load Configuration

```python
# SOT 바인딩 — 모든 경로는 SOT에서 읽음
TERMS_FILE = "env-scanning/config/translation-terms.yaml"  # from SOT system.bilingual
VALIDATOR = "env-scanning/core/translation_validator.py"    # from SOT system.bilingual
```

### Step 2: Determine File Pairs (SOT-Driven)

EN/KO 파일명은 **SOT에서 읽음** (하드코딩 금지):

```yaml
# workflow-registry.yaml에서 읽을 필드:
workflows.{wf_key}.deliverables.report_en  # EN 파일명 패턴
workflows.{wf_key}.deliverables.report_ko  # KO 파일명 패턴
workflows.{wf_key}.data_root               # 보고서 디렉토리
integration.deliverables.report_en         # 통합 EN
integration.deliverables.report_ko         # 통합 KO
integration.output_root                    # 통합 디렉토리
```

**현재 SOT 값** (참고용, 반드시 런타임에 SOT에서 읽을 것):

| WF | `report_en` | `report_ko` |
|----|-------------|-------------|
| wf1-general | `environmental-scan-{date}.md` | `environmental-scan-{date}-ko.md` |
| wf2-arxiv | `environmental-scan-{date}.md` | `arxiv-scan-{date}-ko.md` |
| wf3-naver | `naver-scan-{date}.md` | `naver-scan-{date}-ko.md` |
| wf4-multiglobal-news | `environmental-scan-{date}.md` | `environmental-scan-{date}-ko.md` |
| integrated | `integrated-scan-{date}.md` | `integrated-scan-{date}-ko.md` |

### Step 3: Translate via @translation-agent

각 파일에 대해 `@translation-agent` 서브에이전트를 호출:

```
@translation-agent에게 전달할 지시:

1. Read the English source file: {EN_PATH}
2. Read the terminology map: env-scanning/config/translation-terms.yaml
3. Translate the ENTIRE document to Korean following these rules:
   - IMMUTABLE: STEEPs terms (Social, Technological, Economic, Environmental, Political, spiritual), signal IDs, URLs, dates, scores, file paths
   - PRESERVE: arXiv, GPT, AI, EU, WHO, UN 등 고유명사
   - USE MAPPINGS: "weak signal"→"약한 신호", "environmental scanning"→"환경 스캐닝" 등 용어집 매핑 준수
   - REGISTER: 합쇼체 (formal Korean)
   - STRUCTURE: 원문의 마크다운 구조(헤딩, 테이블, 리스트, 볼드 등) 100% 보존
4. Write output to: {KO_PATH}
5. Do NOT add, omit, or reinterpret any content. Translation only.
```

### Step 4: Validate

```bash
python3 env-scanning/core/translation_validator.py \
  --source {EN_PATH} \
  --target {KO_PATH} \
  --terms env-scanning/config/translation-terms.yaml
```

검증 항목:
- STRUCT-001~008: 구조 보존 (헤딩 수, 테이블 수, 리스트 항목 수, 수평선, 링크, 코드블록, 전체 행 수 비율 ±40%, 공행 비율)
- TERM-001: STEEPs 불변 용어 보존
- TERM-002: 고유명사 과번역 방지
- TERM-003: 용어집 매핑 준수율 ≥60%

### Step 5: Retry on Failure

검증 실패 시:
1. 실패 항목 피드백을 @translation-agent에 전달
2. 재번역 (최대 2회)
3. 2회 실패 시 사용자에게 수동 검토 요청

---

## Quality Standards

| 기준 | 값 | 근거 |
|------|-----|------|
| 구조 보존율 | ≥90% | 원문 마크다운 구조 유지 |
| 용어 매핑 준수율 | ≥60% | TERM-003 기준 |
| 한국어 문자 비율 | ≥30% | M4 CG-007 기준 |
| 불변 용어 보존율 | 100% | STEEPs 프레임워크 |
| 번역 문체 | 합쇼체 | 공식 보고서 문체 |

---

## Integration Points

### Dashboard Step 5.2
대시보드 생성 전, KO 파일 존재를 확인하고 없으면 이 스킬을 호출한다.

### M4 Gate Remediation
CG-002 (KO report exists) 실패 시 이 스킬이 보완 경로로 호출된다.

### Manual Invocation
사용자가 `/translate --date YYYY-MM-DD`로 직접 호출하여 누락된 번역을 보충할 수 있다.

---

## Dependencies

- **Worker Agent**: `.claude/agents/workers/translation-agent.md`
- **Validator**: `env-scanning/core/translation_validator.py`
- **Terms Map**: `env-scanning/config/translation-terms.yaml`
- **SOT**: `env-scanning/config/workflow-registry.yaml` (bilingual section)
