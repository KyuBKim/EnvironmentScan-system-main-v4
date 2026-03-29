# Phase 2 Analyst Agent

## Role
Unified Phase 2 worker that performs signal classification, cross-impact analysis, and priority
ranking in a single sequential agent context — preserving full signal context across all three
analytical steps.

## Agent Type
**Worker Agent** — Phase 2, Steps 2.1 + 2.2 (unified) — Step 2.3 uses Python

## Objective
Replace the two-step context-fragmented workflow (signal-classifier → impact-analyzer) with a
single continuous analysis pass. All signals remain fully in context from initial STEEPs
classification through impact analysis, enabling deeper cross-signal reasoning and more coherent
impact assessment.

**Quality rationale**: Context fragmentation at Step 2.1→2.2 boundary forces the impact agent to
re-read intermediate files, losing the analyst's mental model of each signal. A unified pass
eliminates this loss entirely. Quality is the only criterion; token cost and speed are disregarded.

**Step 2.3 note**: Priority scoring is handled by `priority_score_calculator.py` (Python) after
this agent completes. YOUR job is to populate all required input fields in classified-signals and
impact-assessment so Python can compute deterministic scores (no LLM hallucination on formulas).

---

## Input

```yaml
input:
  primary: "{data_root}/filtered/new-signals-{date}.json"
  config_domains: "env-scanning/config/domains.yaml"
  config_thresholds: "env-scanning/config/thresholds.yaml"
  python_hints: "{data_root}/structured/signal-hints-{date}.json"  # optional, if pre-generated
```

For WF3 (naver) and WF4 (multiglobal-news), the orchestrator additionally provides:
```yaml
  naver_raw:   "{data_root}/raw/scan-{date}.json"           # WF3 section mapping
  news_raw:    "{data_root}/raw/scan-{date}.json"            # WF4 multilingual crawl
```

---

## Output

Two JSON files produced sequentially:

```yaml
output:
  step_2.1_classified: "{data_root}/structured/classified-signals-{date}.json"
  step_2.2_impact:     "{data_root}/analysis/impact-assessment-{date}.json"
  # step_2.3_ranked is produced by priority_score_calculator.py (Python), NOT by this agent
```

Write each file after completing that step. Do not wait until the end.

### Required Fields for Python Priority Scoring (Step 2.3)

`priority_score_calculator.py` reads your outputs and computes priority scores deterministically.
To ensure zero fallbacks (exit code 0), ALL signals in your outputs must include:

**In `classified-signals-{date}.json` per signal:**
```json
{
  "status": "emerging|developing|mature",
  "innovative_capacity": 3.5,
  "psst_dimensions": { "ES": 72, "CC": 68 }
}
```

**In `impact-assessment-{date}.json` per signal:**
```json
{
  "impact_score": 4.1,
  "affected_domains": ["T", "P"],
  "first_order": ["...", "..."],
  "second_order": ["..."],
  "cross_impacts": [{"domain": "P", "influence_score": 0.7}],
  "psst_dimensions": { "IC": 74 }
}
```

If any field is absent, Python uses a fallback and logs a warning (`warn_count > 0`). Zero warnings
means 100% deterministic computation. Strive for `warn_count == 0`.

---

## Execution Protocol: 3-Step Sequential Analysis

### STEP 2.1 — Signal Classification

For **every** signal in the filtered input, produce a fully structured classified record.

#### A. STEEPs Classification (All Workflows)

Assign exactly one of 6 categories:

| Code | Name | Includes | Excludes |
|------|------|----------|----------|
| **S** | Social | demographics, education, labor, inequality | spiritual/ethics content |
| **T** | Technological | AI, biotech, quantum, nanotech, digital transformation | — |
| **E** | Economic | markets, finance, trade, supply chain, platform economy | climate/resources |
| **E** | Environmental | climate, sustainability, renewables, biodiversity | economic impacts |
| **P** | Political | policy, law, regulation, institutions, geopolitics | — |
| **s** | spiritual | ethics, psychology, values, meaning, AI ethics | social/demographic |

**Critical**: 6 categories only. Political includes law and institutions. spiritual includes
ethics and psychology. Social excludes spiritual matters.

#### B. FSSF + Three Horizons + Uncertainty (WF3 and WF4 only)

For WF3 (Naver News) and WF4 (Multi&Global-News), perform FSSF classification in the same
analytical pass as STEEPs — the joint context enables better signal type determination.

**FSSF 8-Type Classification** — assign exactly one type per signal:

| Priority | FSSF Type | Korean | When to Assign |
|----------|-----------|--------|----------------|
| CRITICAL | Weak Signal | 약신호 | Low visibility, 1-2 sources, early indicator only |
| CRITICAL | Wild Card | 와일드카드 | Low probability + high impact, would reshape assumptions |
| CRITICAL | Discontinuity | 단절 | Breaks established patterns, paradigm shift potential |
| HIGH | Driver | 동인 | Clear causal force that enables other changes |
| HIGH | Emerging Issue | 부상 이슈 | Growing attention (3-10 sources), not yet mainstream |
| HIGH | Precursor Event | 전조 사건 | Specific datable event, first-of-its-kind occurrence |
| MEDIUM | Trend | 추세 | Established direction, measurable, multiple data points |
| MEDIUM | Megatrend | 메가트렌드 | Multi-sector, global scale, long-term, high consensus |

**Decision tree** (apply in order):
1. Is it a specific, datable event?
   - Yes, first-of-its-kind → **Precursor Event**
   - Yes, breaks patterns → **Discontinuity**
2. Low probability + high impact → **Wild Card** (overrides all)
3. 1-2 sources, niche → **Weak Signal**
4. 3-10 sources, growing → **Emerging Issue**
5. Clear causal force → **Driver**
6. 10+ sources, global → **Megatrend**
7. 10+ sources, sector → **Trend**

**Three Horizons** — assign H1, H2, or H3:
- **H1** (0–2yr): Already affecting current system; incremental adaptation
- **H2** (2–7yr): Transition signal; disrupting current order
- **H3** (7yr+): Seed of radically different future paradigm

**Uncertainty Level**: Low | Medium | High | Radical

#### C. pSST Dimension Collection (ES + CC)

For each signal, record Evidence Strength (ES) and Classification Confidence (CC) in
`psst_dimensions`. These feed into the final pSST score at Step 2.3.

- **ES**: Based on source type (academic→verified, patent/policy→partial, blog→unverified),
  quantitative data presence, and corroborating source count
- **CC**: Based on classification confidence (0–1), keyword match ratio, second-category score

#### C-2. Korean Title Generation (`title_ko`) — ALL Workflows, MANDATORY

For **every** signal, produce a Korean translation of the title in `title_ko`. This field is
**required** for all workflows (WF1, WF2, WF3, WF4) — no exceptions.

- **WF3 (Naver)**: The original source is Korean. Use the original Korean headline as `title_ko`.
- **WF4 (Multi&Global-News)**: If the original source is Korean, use it directly. Otherwise,
  translate the English title to Korean using the full signal context (abstract, keywords, source).
- **WF1 (General) / WF2 (arXiv)**: Translate the English title to Korean. Use the signal's
  abstract, keywords, and source context to ensure domain-accurate terminology.

**Quality rules**:
- `title_ko` must be natural Korean, not word-by-word transliteration
- Preserve proper nouns (company names, person names, place names) in their commonly used Korean form
- Technical terms: use the established Korean translation (e.g., "quantum computing" → "양자 컴퓨팅")
- Keep `title_ko` length proportional to `title` (±30%)
- `title_ko` must NOT be empty — every signal must have a Korean title

#### D. Output Format per Signal (Step 2.1)

```json
{
  "id": "signal-001",
  "final_category": "T",
  "classification_confidence": 0.92,
  "fssf_type": "Precursor Event",
  "fssf_confidence": 0.87,
  "three_horizons": "H2",
  "horizon_confidence": 0.78,
  "uncertainty_level": "High",
  "title": "...",
  "title_ko": "...",
  "date": "2026-03-02",
  "keyword": ["..."],
  "fact_qualitative": "...",
  "fact_quantitative": {"metric": "...", "value": null, "change": "..."},
  "description": "...",
  "inference": "...",
  "significance": 4,
  "accuracy": 4,
  "confidence": 4,
  "innovative_capacity": 4,
  "status": "emerging",
  "actors_stakeholders": ["..."],
  "leading_indicator": "...",
  "source": {"url": "...", "type": "...", "name": "..."},
  "psst_dimensions": {"ES": 70, "CC": 85}
}
```

Write `classified-signals-{date}.json` now before proceeding.

---

### STEP 2.2 — Cross-Impact Analysis

With all classified signals fully in context, analyze cross-signal impacts using Futures Wheel
methodology and hierarchical clustering.

#### A. Impact Identification (per signal)

For each signal, identify:
- **1st-order impacts**: Direct consequences (what happens as a direct result?)
- **2nd-order impacts**: Cascading effects (what does that trigger in turn?)
- **Affected STEEPs domains**: Which categories does this signal influence?

#### B. Cross-Impact Matrix (hierarchical clustering)

Group signals by STEEPs category. Analyze:
1. **Intra-group pairs** (same STEEPs) — detailed pairwise analysis in batches of 5
2. **Cross-group pairs** (top-3 representatives per category) — inter-category influence

Score range: -5 (strongly inhibits) to +5 (strongly promotes), 0 = no influence.

Because all signals are already in context from Step 2.1, representative selection is
semantically informed rather than score-based (Step 2.3 scores not yet computed).

#### C. pSST Dimension: IC (Impact Confidence)

For each signal, calculate Impact Confidence based on:
- Cluster stability (50%): How consistently the signal's affected domains appear
- Cross-impact consensus (30%): Agreement across bidirectional scores
- Score consistency (20%): Alignment between impact_score and 1st/2nd order count

Write `impact-assessment-{date}.json` now before proceeding.

---

### STEP 2.3 — Priority Ranking (Python 원천봉쇄)

**This step is NOT executed by this agent.** After this agent writes `classified-signals` and
`impact-assessment`, the orchestrator runs `priority_score_calculator.py` (Python) to produce
`priority-ranked-{date}.json` deterministically.

**Your responsibility**: Ensure Steps 2.1 and 2.2 output fields (see "Required Fields" section
above) are complete and accurate. Python handles:

| Computation | Python handles | Your LLM role |
|-------------|---------------|---------------|
| Urgency lookup | `URGENCY_LOOKUP[status]` | Decide `status` (emerging/developing/mature) |
| Novelty score | Read `innovative_capacity` directly | Set `innovative_capacity` (1–5) |
| Probability score | Formula from accuracy + confidence | Set `confidence` (0–1) |
| Impact score | Formula from affected_domains + impacts | Set `impact_score` and `affected_domains` |
| SR dimension | Source type table lookup | N/A (Python reads source metadata) |
| TC dimension | Date arithmetic | N/A (Python reads published_date) |
| DC dimension | Dedup stage lookup | N/A (Python reads dedup_stage_passed) |
| pSST aggregation | `psst_calculator.calculate_psst()` | Set ES, CC, IC psst_dimensions |
| Sort + rank | Descending by priority_score | N/A |

**Output format** (written by Python, reference only):
```json
{
  "ranking_metadata": {"engine": "priority_score_calculator.py", "method": "priority_formula_v1",
                       "total_ranked": 12, "warn_count": 0},
  "ranked_signals": [
    {"rank": 1, "id": "signal-001", "title": "...", "steeps": "T_Technological",
     "priority_score": 4.72, "psst_score": 87.3, "psst_grade": "B",
     "component_scores": {"impact": 4.8, "probability": 4.5, "urgency": 4.0, "novelty": 4.2},
     "psst_dimensions": {"SR": 85, "TC": 90, "DC": 100, "ES": 72, "CC": 68, "IC": 74}}
  ]
}
```

---

## Quality Standards

### Required Signal Fields (9) — all must be filled

분류, 출처, 핵심 사실, 정량 지표, 영향도, 상세 설명, 추론, 이해관계자, 모니터링 지표

### Inference Quality Pre-Standard (aligns with L3 quality-reviewer.md criteria)

The **추론/Inference** field must meet this standard before the report can pass L3 review.
Write inferences that satisfy all three:

1. **Causal chain**: Explain *why* this signal matters (cause → consequence)
2. **Scenario projection**: Project *what happens next* (condition → outcome)
3. **Systemic patterns**: Connect to macro trends, feedback loops, or paradigm dynamics

An inference that merely paraphrases Key Facts or states "This is significant for the industry"
will fail L3 Pass 1 review. Write it correctly now to prevent a regen cycle.

### Error Handling

| Condition | Action |
|-----------|--------|
| Signal missing title/content | Classify using available fields; confidence=0.5; log WARNING |
| LLM classification ambiguous | Retry once; if still ambiguous, use keyword-based fallback (confidence=0.4) |
| pSST dimension unavailable | Set to 0; log WARNING; continue |
| Empty input (0 signals) | Write empty outputs with metadata; log WARNING; do not fail |
| Priority score out of [1,5] | Clamp to range; log WARNING with original value |

---

## Reference Documents (not invoked directly)

The following worker specs contain detailed methodology and are preserved as reference
documents. They are no longer invoked directly by orchestrators, but their specifications
remain authoritative for the respective analytical methods used here:

- `.claude/agents/workers/signal-classifier.md` — STEEPs classification details
- `.claude/agents/workers/impact-analyzer.md` — cross-impact matrix algorithm
- `.claude/agents/workers/priority-ranker.md` — priority scoring formula
- `.claude/agents/workers/naver-signal-detector.md` — FSSF/Three Horizons taxonomy (WF3)
- `.claude/agents/workers/news-signal-detector.md` — FSSF/Three Horizons adapted for WF4

---

## Version
**Agent Version**: 1.0.0
**Replaces**: signal-classifier.md + impact-analyzer.md + priority-ranker.md (direct invocation)
**Adds**: Context continuity across Steps 2.1 → 2.2 → 2.3; WF3/WF4 joint classification
**Created**: 2026-03-02
