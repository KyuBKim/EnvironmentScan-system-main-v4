---
name: translate
description: 환경스캐닝 보고서 한국어 번역. 누락된 KO 보고서를 자동 감지하여 번역하거나, 특정 파일을 번역한다.
context: fork
---

# Translate Environmental Scanning Reports to Korean

환경스캐닝 보고서를 한국어로 번역합니다.

## Usage

```bash
# 특정 날짜의 누락된 KO 보고서 전체 번역
/translate 2026-03-24

# 특정 파일 번역
/translate --file env-scanning/wf1-general/reports/daily/environmental-scan-2026-03-24.md
```

## Execution

Use the `translator` skill to perform translation.

### Step 1: Determine Scope

If a date is provided (e.g., `$ARGUMENTS` contains `2026-`):
1. Read SOT: `env-scanning/config/workflow-registry.yaml`
2. For each enabled workflow, check if KO report exists
3. Collect all missing KO file paths

If `--file` is provided:
1. Translate that single file

### Step 2: Read Translation Configuration

```
Terms file: env-scanning/config/translation-terms.yaml
Validator: env-scanning/core/translation_validator.py
```

### Step 3: For Each Missing KO Report

Invoke `@translation-agent` as a sub-agent with these instructions:

```
You are translating an environmental scanning report from English to Korean.

INSTRUCTIONS:
1. Read the English source file: {EN_PATH}
2. Read the terminology map: env-scanning/config/translation-terms.yaml
3. Translate the ENTIRE document to Korean.

RULES:
- IMMUTABLE (never translate): STEEPs terms (Social, Technological, Economic, Environmental, Political, spiritual), S/T/E/P/s codes, signal IDs, URLs, dates, numerical scores, file paths
- PRESERVE as-is: arXiv, GPT, AI, EU, WHO, UN, IEEE, CNBC, NPR, Reuters, Bloomberg, and all proper nouns
- USE TERM MAPPINGS from translation-terms.yaml consistently
- REGISTER: 합쇼체 (formal Korean) throughout
- STRUCTURE: Preserve ALL markdown structure exactly — headings (##), tables (|), lists (-), bold (**), blockquotes (>), horizontal rules (---)
- DO NOT add, omit, summarize, or reinterpret any content
- DO NOT translate content inside code blocks

4. Write the complete Korean translation to: {KO_PATH}
```

Launch translations in parallel using multiple Agent calls when translating multiple files.

### Step 4: Validate Each Translation

Run for each translated file:
```bash
python3 env-scanning/core/translation_validator.py \
  --source {EN_PATH} --target {KO_PATH} \
  --terms env-scanning/config/translation-terms.yaml
```

### Step 5: Report Results

Display summary table:
```
| 보고서 | EN 원본 | KO 번역 | 검증 |
|--------|---------|---------|------|
| WF1    | ✅ exists | ✅ translated | PASS |
| WF2    | ✅ exists | ✅ translated | PASS |
...
```

### File Naming Convention (SOT-Driven)

EN/KO 파일명은 SOT(`workflow-registry.yaml`)에서 읽음:
- `workflows.{wf_key}.deliverables.report_en` / `report_ko`
- `workflows.{wf_key}.data_root` + `/reports/daily/`
- `integration.deliverables.report_en` / `report_ko`

**하드코딩 금지** — SOT가 변경되면 자동 반영.
