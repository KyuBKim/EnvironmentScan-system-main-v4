# Timeline Map Enhancement — 설계안 v2.2

> **절대 기준**: 최종 결과물의 '품질'과 '최고 수준의 질적 결과물'이 유일한 기준이다.
> 속도와 토큰 비용은 완전히 무시한다.

> **v2.0 변경**: v1.0 설계안에 대한 Critical Reflection을 수행하여
> 의존성/결합도/변경 파급 효과 분석 결과 **심각한 결함 5건**을 발견하고 수정함.
> 기존 워크플로우의 철학, 목적, 핵심은 완벽하게 보존한다.

> **v2.1 변경**: v2.0 설계안에 대한 2차 Critical Reflection을 수행하여
> **품질 기반 기술 선택 근거 미명시(CR-1)**, **SOT 검증 규칙 5개 누락 + 파라미터 이중화(CR-2)**,
> **fallback 기본값/타임아웃 미설계(CR-3)**, **TDD 총괄표 불일치(CR-6)**,
> **변경 범위 과소 기술(CR-7)** 등 7건을 분석하고 수정함.
> RLM 패턴 유지(CR-4), 기능 개선 성격(CR-5) 확인 완료.

> **v2.2 변경**: Python 원천봉쇄 전수조사(Critical Reflection v4)를 수행하여
> LLM에게 맡긴 작업 중 **결정론적이어야 하는 6건(PB-1~PB-6)**을 발견하고
> 전부 Python 사전 렌더링(pre-rendering)으로 이전함.
> "계산은 Python이, 판단은 LLM이" 원칙의 완전한 적용.
> 기존 워크플로우의 철학·목적·핵심 보존, RLM 패턴 유지, 기능 개선 범위 준수.

---

## 0. Critical Reflection — v1.0 설계안의 결함 분석

### 성찰 기준

> "기존 코드와 연관된 의존성/결합도/변경 파급 효과까지 고려하여 일관된 구현을 하였는가?"

### 결함 CF-1: 기존 모듈과의 기능 중복 (CRITICAL — 아키텍처 위반)

**발견**: v1.0에서 제안한 `cross_wf_correlator.py`(신규)는 이미 존재하는
`signal_evolution_tracker.py`의 `cross_correlate_threads()` 함수(L1031~L1157)와
**완전히 동일한 역할**을 수행한다.

```
기존 파이프라인 (master-orchestrator Step 5.1.2.4):
  python3 {EVOLUTION_TRACKER} cross-correlate \
    --wf1-index ... --wf2-index ... --wf3-index ... --wf4-index ... \
    --output {INT_OUTPUT_ROOT}/analysis/evolution/cross-evolution-map-{date}.json

v1.0 제안 (A2):
  python3 cross_wf_correlator.py \     ← 동일 기능을 재구현
    --wf1-evo-map ... --wf2-evo-map ...
```

**파급 효과**:
- `cross-evolution-map-{date}.json`을 2번 생성 → 데이터 불일치 가능
- `signal_evolution_tracker.py`의 SOT 설정(`cross_workflow_correlation.matching`)과
  `cross_wf_correlator.py`의 설정이 이중화 → SOT 단일 원칙 위반
- master-orchestrator의 Step 5.1.2.4와 timeline-map-orchestrator의 A2가 충돌

**수정**: `cross_wf_correlator.py` 신규 생성을 **삭제**한다.
기존 Step 5.1.2.4의 출력(`cross-evolution-map-{date}.json`)을 **그대로 소비**한다.
Timeline Map은 상류 파이프라인의 **소비자(consumer)**이지 **생산자(producer)**가 아니다.

---

### 결함 CF-2: report_statistics_engine.py와의 기능 중복 (HIGH)

**발견**: v1.0의 A4(`timeline_data_assembler.py`)가 수행하려는 작업 중 상당 부분이
이미 `report_statistics_engine.py`에 구현되어 있다:

| 기능 | report_statistics_engine.py | v1.0 A4 (중복) |
|------|---------------------------|----------------|
| evolution 통계 추출 | `_extract_evolution_distribution()` | 동일 로직 재구현 |
| cross-evolution 테이블 | `compute_cross_evolution_table()` | 동일 로직 재구현 |
| evolution-map 병합 | `merge_evolution_maps()` | 동일 로직 재구현 |
| weekly evolution 집계 | `compute_weekly_evolution_stats()` | 유사 로직 |

**파급 효과**:
- STEEPs 라벨 정의가 `report_statistics_engine.py`, `timeline_map_generator.py`,
  그리고 새 모듈에까지 3중 하드코딩 → 하나 변경 시 나머지 누락 위험
- evolution-map 파싱 로직이 분산 → 포맷 변경 시 shotgun surgery

**수정**: 기존 `report_statistics_engine.py`의 출력을 **소비**하되,
타임라인 맵 고유의 신규 계산(테마 클러스터링, 에스컬레이션 궤적)만 새 모듈에서 수행한다.

---

### 결함 CF-3: 외부 의존성 도입 (HIGH — 프로젝트 정책 위반)

**발견**: v1.0의 A1(`theme_discovery_engine.py`)에서 제안한 "TF-IDF 기반 키워드 추출 →
코사인 유사도 클러스터링"은 **scikit-learn** 의존성을 필요로 한다.

기존 코드베이스의 의존성 프로파일:
```
core/ 모듈 전체의 import: 표준 라이브러리 + yaml (PyYAML) 만 사용
scikit-learn, numpy, scipy 등 과학 계산 라이브러리: 사용 없음
```

또한 `timeline_map_generator.py`는 명시적으로 "모듈 독립성: core/ 내 다른 모듈 import 없음"
을 선언하고 있다. 이 원칙은 모든 신규 모듈에도 적용되어야 한다.

**수정**: scikit-learn 의존 TF-IDF를 **제거**한다.
대신 표준 라이브러리만으로 구현 가능한 키워드 동시출현(co-occurrence) 기반 클러스터링을 사용한다.
`collections.Counter` + `difflib.SequenceMatcher`로 충분하다.

---

### 결함 CF-4: 에이전트 과잉 (MEDIUM — 복잡도 증가)

**발견**: v1.0은 5개 신규 에이전트(1 오케스트레이터 + 4 워커)를 추가한다.
기존 시스템은 34개 워커로 **전체 4중 워크플로우 + 통합 + 주간 분석**을 처리한다.
타임라인 맵은 통합 보고서의 **보강 요소**(supplementary output)인데,
전체 시스템 워커의 15%에 해당하는 에이전트를 추가하는 것은 비례성이 맞지 않는다.

더 중요한 문제: B1(theme-narrator), B2(cross-wf-analyst), B3(escalation-assessor)를
별도 에이전트로 분리하면 **테마 간 상호작용 분석이 불가능**해진다.
수동 생성 버전(02-06-to-02-11)의 핵심 가치는 "관세 전쟁 + 반도체 규제 → compound effect"처럼
**테마를 관통하는 통합 분석**이었다. 이것은 3개 에이전트가 각자 자기 영역만 보면 나올 수 없다.

**수정**: 4개 LLM 워커 → **2개**로 축소:
- `timeline-narrative-analyst`: B1+B2+B3 통합 (모든 테마를 한 컨텍스트에서 분석)
- `timeline-map-composer`: C2 유지 (조립 + 최종 품질)

이렇게 하면 전체 컨텍스트를 유지한 채 cross-theme insight가 자연스럽게 생성된다.

---

### 결함 CF-5: 파이프라인 위치의 오해 (MEDIUM — 설계 결함)

**발견**: v1.0은 Timeline Map을 "Step 5.1.4에서 서브 오케스트레이터를 호출"하는 것으로 설계했다.
하지만 master-orchestrator의 실제 파이프라인 순서를 보면:

```
Step 5.1.2.4: cross-correlate                    ← cross-evolution-map 생성
Step 5.1.3:   compute integrated evolution stats ← 통합 evolution 통계 생성
Step 5.1.4:   generate timeline map              ← 여기
Step 5.1.5:   pre-fill integrated skeleton       ← 통합 스켈레톤 메타데이터 주입
Step 5.2:     integration method selection        ← 통합 보고서 생성
```

Timeline Map은 Step 5.1.2.4와 5.1.3의 출력을 **소비**해야 한다.
v1.0은 이 의존관계를 무시하고 같은 데이터를 독자적으로 재생산하려 했다.

또한, v1.0의 타임라인 맵 요약을 통합 보고서에 인라인하려면 Step 5.1.4가
Step 5.1.5 **이전에** 완료되어야 하는데, 이 시간 의존성은 이미 올바르다.
단, `report_metadata_injector.py`에 새 플레이스홀더(`INT_TIMELINE_SUMMARY`)를 추가하면
Step 5.1.3의 `report_statistics_engine.py`와의 **이중 주입 경로**가 생긴다.

**수정**: `INT_TIMELINE_SUMMARY`는 `report_statistics_engine.py`의
`build_placeholder_map()`에서 **통합적으로** 주입한다.
`report_metadata_injector.py`에 별도 경로를 만들지 않는다.
이것이 기존 "temporal_anchor → report_statistics → report_metadata_injector" 파이프라인의
일관성을 유지하는 방법이다.

---

### 결함 요약표

| ID | 심각도 | 결함 | 원인 | v2.0 수정 |
|----|--------|------|------|----------|
| CF-1 | CRITICAL | cross_wf_correlator.py가 기존 cross_correlate_threads()와 중복 | 기존 코드 미조사 | 신규 모듈 삭제, 기존 출력 소비 |
| CF-2 | HIGH | report_statistics_engine.py 기능 중복 | 기존 코드 미조사 | 기존 출력 소비, 신규 계산만 분리 |
| CF-3 | HIGH | scikit-learn 의존성 도입 | 프로젝트 의존성 정책 미확인 | 표준 라이브러리만 사용 |
| CF-4 | MEDIUM | 에이전트 4개 과잉, cross-theme 분석 불가 | 분리가 품질 저하 유발 | 2개로 축소, 통합 분석 |
| CF-5 | MEDIUM | 파이프라인 순서/의존관계 오해 | 상류 출력 소비 vs 재생산 혼동 | 소비자 역할 명확화 |

---

## 0.2 Critical Reflection v3 — v2.0 설계안의 추가 결함 분석 (v2.1)

### 성찰 기준

> 1. "sub-agent와 agent-teams 중 어느 기술을 사용할지는 '속도'가 아니라 '결과의 품질'이 기준이다."
> 2. "일일 실행 워크플로우의 철학, 목적, 핵심 기능과 단계를 붕괴시켜서는 안 된다. RLM 패턴 절대 유지."

### CR-1: Task Subagent 선택에 품질 근거 미명시 (CRITICAL)

v2.0은 Phase B/C에서 Task subagent를 사용하지만 왜 Agent Teams가 아닌지 품질 근거를 명시하지 않았다.
선택 자체는 올바르다(Cross-theme synthesis는 단일 컨텍스트 필수, 통합 보고서와 달리 분업 축 부재).
**시정**: §5.0에 품질 기반 기술 선택 근거 테이블 추가.

### CR-2: SOT 검증 규칙 5개 누락 + 파라미터 이중화 (HIGH)

`theme_discovery_engine`, `data_assembler`, `skeleton_filler`, `emergent_cluster_min_size`, `fallback_script`의 검증 규칙이 누락("검증 없는 SOT는 SOT가 아니다" 위반).
또한 `emergent_discovery` 파라미터가 `timeline-themes.yaml`과 `workflow-registry.yaml`에 이중 존재(SOT 단일 원칙 위반).
**시정**: 검증 규칙 5개 보완 + `timeline-themes.yaml`에서 파라미터 섹션 제거 → `workflow-registry.yaml`로 단일화.

### CR-3: Fallback 시 INT_TIMELINE_SUMMARY 기본값 + 타임아웃 미설계 (HIGH)

Enhanced pipeline 실패 → fallback(기존 generator) 시 `timeline-summary-{date}.txt`가 생성되지 않는 경로 미설계.
서브 오케스트레이터 무한 루프 방지를 위한 타임아웃 미설계.
**시정**: 기본값 메시지 명시 + max_execution_minutes SOT 키 추가.

### CR-4: RLM 패턴 유지 확인 (OK)

timeline-map-orchestrator의 구조가 기존 exploration-orchestrator와 동일한 패턴(Sub-Orch → Worker 단방향, Python은 도구 사용). 문제 없음.

### CR-5: "기능 개선" 성격 확인 (OK)

새 3-Phase Pipeline 없음, 독립 데이터 디렉토리 없음, 새 Human Checkpoint 없음, 기존 Step 5.1.4 내부 확장. 기능 개선이 맞음.

### CR-6: TDD 총괄표 불일치 (MEDIUM)

§12.1/§12.3에 CF-1/CF-4로 삭제된 모듈의 테스트가 잔존. 합계 44 → 실제 31.
`test_timeline_skeleton_filler.py`를 validator에 통합한다고 했으나, 대상이 다르므로 독립 유지 필요.
**시정**: §12 전체 수정.

### CR-7: report_statistics_engine 변경 범위 과소 기술 (MEDIUM)

"15줄 추가"가 아니라, 외부 파일 읽기 로직 + graceful fallback + 매핑 추가(약 20줄).
**시정**: §13.2 변경 내용 정확화.

### CR 결과 요약표

| ID | 심각도 | 발견 | v2.1 시정 |
|----|--------|------|----------|
| CR-1 | CRITICAL | 기술 선택 품질 근거 미명시 | §5.0 품질 기반 선택 근거 추가 |
| CR-2 | HIGH | SOT 검증 5개 누락 + 이중화 | §8.3 검증 규칙 보완 + themes.yaml 파라미터 제거 |
| CR-3 | HIGH | fallback 기본값 + 타임아웃 미설계 | §9.1 fallback/timeout 경로 명시 |
| CR-4 | — | RLM 패턴 유지 | 확인 완료 |
| CR-5 | — | 기능 개선 성격 | 확인 완료 |
| CR-6 | MEDIUM | TDD 총괄표 불일치 | §12 수정 |
| CR-7 | MEDIUM | 변경 범위 과소 기술 | §13.2 정확화 |

---

## 0.3 Critical Reflection v4 — Python 원천봉쇄 전수조사 (v2.2)

### 성찰 기준

> "엄밀하고, 100% 정확한 결과를 **반복적으로** 내야 하는 task는 Python으로 원천봉쇄"
> "계산은 Python이, 판단은 LLM이" — 이 프로젝트의 핵심 원칙

### 분석: v2.1의 모든 LLM task를 "계산 vs 판단"으로 재분류

v2.1에서 LLM(`timeline-narrative-analyst`)에게 할당된 작업을 전수조사한 결과,
**결정론적이어야 하는 6건의 task**가 LLM에게 잘못 할당되어 있었다.

| ID | Task | 왜 Python이어야 하는가 | 시정 |
|----|------|----------------------|------|
| PB-1 | ASCII 타임라인 다이어그램 | 날짜/pSST/WF 배치는 100% 정확해야 함. LLM은 ASCII 정렬 붕괴, 날짜 오기 빈발. 기존 `timeline_map_generator.py`도 Python으로 생성. | `timeline_data_assembler.py`에서 사전 렌더링 |
| PB-2 | Cross-WF 테이블 구조 (수치 셀) | 테마×WF 카운트는 결정론적 집계. LLM이 표를 만들면 셀 값 오류 가능. | Python이 구조 생성, LLM은 해석 셀만 |
| PB-3 | Lead-Lag 시간차 | "3일 선행"의 "3"은 날짜 차이 계산. LLM 산술 오류 위험. | Python이 `lag_days` 계산 |
| PB-4 | Escalation severity 등급 | `assessed_severity`가 `python_severity`와 다를 수 있는 구조는 반복 실행 시 불일치 유발. | Python 등급을 확정. LLM override 금지. |
| PB-5 | monitoring_priority 순번 | severity + slope 기반 정렬은 결정론적. | Python이 순번 할당 |
| PB-6 | key_signals + 테마 순서 | pSST 상위 N개 선택과 priority 기반 정렬은 결정론적. | Python이 선택/정렬 |

### 시정 원칙

`timeline_data_assembler.py`의 출력 JSON에 `pre_rendered` 섹션을 추가한다.
이 섹션은 LLM이 **그대로 복사/인용**해야 하는 결정론적 산출물을 포함한다.
LLM의 역할은 순수하게 "판단/서사/해석/예측"만 남는다:

```
Python 원천봉쇄 영역 (pre_rendered):        LLM 판단 영역:
  - ASCII 다이어그램                          - 궤적 서사 ("배경→위협→확산")
  - Cross-WF 테이블 수치                      - 판단/평가 ("정책 대응 긴급")
  - Lead-Lag 시간차 (일수)                    - 다음 예상 (미래 예측)
  - Escalation 확정 등급                      - Cross-Theme 종합 분석
  - 모니터링 순위                             - 전략적 시사점
  - 하이라이트 시그널 선택                     - Emergent Theme 명명
  - 테마 표시 순서                            - Cross-WF 해석 문장
  - 에스컬레이션 테이블 수치 열               - 에스컬레이션 "다음 예상" 열
```

이것은 기존 시스템의 `report_metadata_injector.py` 패턴과 동일하다:
Python이 정량 데이터를 사전 생성 → LLM이 정성 분석만 수행.

### TDD 영향

`timeline_data_assembler.py` 테스트: 6개 → 14개 (PB-1~PB-6 정확성 테스트 8개 추가)
전체 TDD 합계: 31개 → 39개

---

## 0.1 의존성 지도 — 변경 파급 효과 분석

타임라인 맵 강화가 영향을 미치는 기존 모듈의 **실제 결합 관계**를 명시한다.
이 지도에 없는 모듈은 변경하지 않는다.

```
┌─────────────────────────────────────────────────────────────────┐
│                    master-orchestrator.md                        │
│  Step 5.1.2.4: cross-correlate (기존 유지, 출력 소비)            │
│  Step 5.1.3:   report_statistics_engine (기존 유지, 출력 소비)   │
│  Step 5.1.4:   timeline map (★ 이 단계만 변경)                   │
│  Step 5.1.5:   report_metadata_injector (최소 변경)              │
└──────────────┬──────────────────────────────────────────────────┘
               │ Step 5.1.4 호출
               ▼
┌──────────────────────────────────────────┐
│  timeline-map-orchestrator.md  (신규)     │
│                                          │
│  입력 (모두 상류 파이프라인의 기존 출력물):  │
│  ├── WF1~4 evolution-map-{date}.json     │ ← signal_evolution_tracker.py가 생성
│  ├── WF1~4 evolution-index.json          │ ← signal_evolution_tracker.py가 관리
│  ├── cross-evolution-map-{date}.json     │ ← signal_evolution_tracker.py cross-correlate
│  ├── integrated-report-statistics.json   │ ← report_statistics_engine.py가 생성
│  └── WF1~4 classified-signals-{date}.json│ ← phase2-analyst가 생성
│                                          │
│  Phase A: Python (신규 모듈 2개)          │
│  ├── theme_discovery_engine.py           │ ← timeline-themes.yaml (신규 SOT)
│  └── timeline_data_assembler.py          │ ← 상류 출력 수집 + 테마 데이터 통합
│                                          │
│  Phase B: LLM (워커 1개)                  │
│  └── @timeline-narrative-analyst         │ ← 전체 테마 서사 통합 분석
│                                          │
│  Phase C: Assembly                       │
│  ├── timeline_skeleton_filler.py         │ ← 정량 데이터 주입
│  └── @timeline-map-composer              │ ← 서사 + 데이터 최종 조합
│                                          │
│  Phase D: Quality Defense                │
│  ├── validate_timeline_map.py            │ ← L2a+L2b 검증
│  └── @quality-reviewer (기존 재사용)      │ ← L3 의미 리뷰
└──────────────────────────────────────────┘

영향받는 기존 파일 (최소 변경):
  ├── master-orchestrator.md           → Step 5.1.4 호출 방식만 변경
  ├── workflow-registry.yaml           → timeline_map 섹션 확장
  ├── validate_registry.py             → SOT-036 확장
  ├── report_statistics_engine.py      → INT_TIMELINE_SUMMARY 플레이스홀더 추가
  ├── integrated-report-skeleton-en.md → §7 타임라인 요약 섹션 추가
  └── integrated-report-skeleton.md    → §7 타임라인 요약 섹션 추가 (KO)

영향받지 않는 기존 파일 (변경 금지):
  ├── signal_evolution_tracker.py      → 변경 없음 (상류 생산자)
  ├── report_metadata_injector.py      → 변경 없음 (기존 주입 경로 유지)
  ├── 각 WF orchestrator (4개)          → 변경 없음
  ├── report-merger.md                 → 변경 없음
  ├── quality-reviewer.md              → 변경 없음 (재사용만)
  └── 기존 timeline_map_generator.py   → 변경 없음 (fallback 유지)
```

### 결합도 분석

| 변경 대상 | 결합 유형 | 결합 강도 | 파급 범위 |
|-----------|----------|----------|----------|
| workflow-registry.yaml (SOT 확장) | 데이터 결합 | 약 | validate_registry.py만 |
| master-orchestrator.md (Step 5.1.4) | 제어 결합 | 중 | timeline-map-orchestrator만 |
| report_statistics_engine.py | 데이터 결합 | 약 | 새 플레이스홀더 1개 추가 |
| integrated-report-skeleton | 스탬프 결합 | 약 | report_metadata_injector 경유 |

모든 변경이 **약~중 결합**이며, **강결합(tight coupling)**은 없다.
Shotgun surgery 위험: **없음** (변경이 한 방향으로만 흐름).

---

## 1. 현재 상태 진단

### 1.1 핵심 문제: "자동 생성물 ≠ 수동 생성물"

두 개의 실제 출력물을 비교하면 문제가 명확하다.

| 항목 | 수동 생성 (02-06-to-02-11) | 자동 생성 (02-16) |
|------|--------------------------|------------------|
| 테마별 서사 | "배경 리스크 → 위협 구체화 → 확정·확산" | 없음 (시그널 나열만) |
| 판단/전망 | "6일간 가장 빠르게 에스컬레이션된 테마. 정책적 대응 긴급." | 없음 |
| ASCII 타임라인 | 의미 있는 흐름 다이어그램 | 기계적 날짜-개수 표 |
| 교차 WF 분석 | 5개 실제 교차 사례 매핑 | "데이터 없음" |
| pSST 데이터 | 모든 시그널에 pSST 존재 | "pSST 데이터 없음" |
| false positive | 거의 없음 | "diffusion" 논문이 에너지·기후로 분류 |

**근본 원인**: 현재 `timeline_map_generator.py`는 **계산만** 하고 **판단을 전혀 하지 않는다**.
수동 버전의 핵심 가치는 LLM의 **서사적 분석 능력**에서 나왔다.
"계산은 Python이, 판단은 LLM이" 원칙이 타임라인 맵에서는 **절반만 구현**된 상태이다.

### 1.2 구조적 결함

| # | 결함 | 영향 |
|---|------|------|
| 1 | 테마 8개가 Python 코드에 하드코딩 | SOT 원칙 위반, 유연성 없음 |
| 2 | 단순 substring 키워드 매칭 | false positive 다수 (정밀도 ↓) |
| 3 | LLM 서사 분석 레이어 없음 | 품질 최대 손실 원인 |
| 4 | cross-evolution-map 생성 파이프라인 단절 | 교차 WF 분석 항상 비어있음 |
| 5 | 통합 보고서 스켈레톤과 비연결 | 타임라인 맵이 고립된 부속물 |
| 6 | 전용 오케스트레이터/워커 없음 | master-orchestrator에서 1줄 Python 호출로 끝남 |
| 7 | Quality Defense 없음 | L2a/L2b/L3 검증 체계 미적용 |

---

## 2. 설계 원칙

### 2.1 기존 시스템 원칙 준수 (비협상)

| 원칙 | 적용 방식 |
|------|----------|
| Python 원천봉쇄 | 테마 클러스터링, pSST 계산, 에스컬레이션 수치, STEEPs 분포 → Python |
| 판단은 LLM이 | 서사 분석, 궤적 해석, 판단/전망, 교차 WF 패턴 해석 → LLM Agent |
| SOT Direct Reading | 모든 설정은 `workflow-registry.yaml`에서 읽기 |
| Skeleton-Fill | 자유 생성 금지, 스켈레톤 템플릿 채우기 |
| Quality Defense 4-Layer | L1(스켈레톤) → L2a(구조 검증) → L2b(QC) → L3(의미 리뷰) |
| VEV Protocol | Pre-Verify → Execute → Post-Verify → Retry → Record |
| Modification Cascade | SOT 변경 → Agent Spec + Skeleton + Validation 동시 업데이트 |

### 2.2 이 설계 고유의 원칙

| 원칙 | 의미 |
|------|------|
| **Compute-then-Narrate** | Python이 먼저 모든 정량 데이터를 생성 → LLM이 그 데이터를 기반으로 서사 분석 |
| **No Hallucinated Numbers** | LLM은 Python이 제공한 수치만 인용. 자체적으로 수치를 생성하지 않음 |
| **Theme Emergence** | 하드코딩 테마 제거. Python이 데이터 기반으로 테마를 발견하고, LLM이 명명/해석 |
| **Progressive Depth** | 얕은 분석 → 깊은 분석 → 교차 분석 순서로 점진적 심화 |

---

## 3. 아키텍처 (v2.0 — Critical Reflection 반영)

### 3.1 핵심 설계 결정: "소비자, 생산자 아님"

v2.0의 가장 중요한 설계 결정:

> **Timeline Map 파이프라인은 기존 상류 모듈의 출력을 소비(consume)한다.**
> **상류 모듈이 이미 생성하는 데이터를 재생산(reproduce)하지 않는다.**

| 데이터 | 생산자 (기존, 변경 없음) | 소비자 (Timeline Map) |
|--------|------------------------|---------------------|
| evolution-map-{date}.json | `signal_evolution_tracker.py track` | `timeline_data_assembler.py` |
| evolution-index.json | `signal_evolution_tracker.py track` | `timeline_data_assembler.py` |
| cross-evolution-map-{date}.json | `signal_evolution_tracker.py cross-correlate` | `timeline_data_assembler.py` |
| report-statistics-{date}.json | `report_statistics_engine.py` | `timeline_skeleton_filler.py` |
| classified-signals-{date}.json | `phase2-analyst.md` | `theme_discovery_engine.py` |

이 원칙으로 v1.0의 CF-1(cross_wf 중복), CF-2(statistics 중복)를 제거한다.

### 3.2 전체 흐름도

```
master-orchestrator.md (Step 5.1.4)
│
└── timeline-map-orchestrator.md  ← 신규 전용 서브 오케스트레이터
    │
    ├── Phase A: Data Foundation (Python 결정론적, 모듈 2개)
    │   ├── A1: theme_discovery_engine.py     ← 테마 발견 + 클러스터링 + 에스컬레이션
    │   └── A2: timeline_data_assembler.py    ← 상류 출력 수집 + A1 결과 통합
    │
    ├── Phase B: Narrative Analysis (LLM 판단, 워커 1개)
    │   └── B1: @timeline-narrative-analyst   ← 전체 테마 통합 서사 분석
    │       (테마 서사 + 교차 WF 해석 + 에스컬레이션 평가를 한 컨텍스트에서)
    │
    ├── Phase C: Assembly (Python 1개 + LLM 워커 1개)
    │   ├── C1: timeline_skeleton_filler.py   ← 스켈레톤에 정량 데이터 주입
    │   └── C2: @timeline-map-composer        ← 서사 + 데이터 → 최종 마크다운
    │
    └── Phase D: Quality Defense
        ├── D1: validate_timeline_map.py      ← L2a+L2b 구조/QC 검증
        └── D2: @quality-reviewer (기존 재사용) ← L3 의미 리뷰
```

**v1.0 대비 변경**:
- ~~`cross_wf_correlator.py`~~ 삭제 (CF-1: 기존 모듈 중복)
- ~~`escalation_detector.py`~~ 삭제 → `theme_discovery_engine.py`에 통합 (응집도 증가)
- ~~3개 LLM 워커~~ → **1개** 통합 (CF-4: cross-theme insight 품질 확보)
- 신규 Python 모듈: 4개 → **3개** (theme_discovery + data_assembler + skeleton_filler)
- 신규 LLM 에이전트: 4개 → **2개** (narrative-analyst + composer)
- 오케스트레이터: 1개 유지

### 3.3 호출 위치 (기존 파이프라인 내 정확한 위치)

```
master-orchestrator Step 5.1 (Integration Preparation):
  5.1.1:   Load WF1~4 final reports            (기존 유지)
  5.1.2.4: cross-correlate                     (기존 유지 — 출력을 Timeline Map이 소비)
  5.1.3:   compute integrated report statistics (기존 유지 — 출력을 Timeline Map이 소비)
  ──────────────────────────────────────────
  5.1.4:   Generate Timeline Map               (★ 변경: Python 호출 → 서브 오케스트레이터)
  ──────────────────────────────────────────
  5.1.5:   Pre-fill integrated skeleton        (기존 유지 + INT_TIMELINE_SUMMARY 추가 주입)
```

**Step 5.1.4 변경 내용**:
```yaml
# 변경 전 (v1.0 기존):
python3 {TIMELINE_SCRIPT} generate --registry ... --output ...

# 변경 후 (v2.0):
IF EVOLUTION_ENABLED == true AND TIMELINE_MAP_ENABLED == true:
  → Invoke @timeline-map-orchestrator as Task subagent
  → Inputs: 상류 Step 5.1.2.4 + 5.1.3 출력 경로 전달
  → Output: timeline-map-{date}.md + timeline-summary-{date}.txt
ELSE:
  → Skip (no timeline map for this run)

On failure (max 2 retries exhausted):
  → Fallback: python3 {TIMELINE_SCRIPT} generate ...  (기존 generator.py)
  → Log: "Enhanced timeline map failed, falling back to basic generator"
  → Fallback 시 timeline-summary-{date}.txt는 생성되지 않음
    → report_statistics_engine.py의 INT_TIMELINE_SUMMARY는 기본값 반환:
      "> 타임라인 맵 심화 분석이 이번 스캔에서는 생성되지 않았습니다.
      > 기본 타임라인은 별도 파일을 참조하세요."  (CR-3 추가)

Timeout (CR-3 추가):
  → Phase A~D 전체 실행에 SOT에서 정의된 max_execution_minutes 적용
  → 초과 시 즉시 fallback으로 전환
  → 구체적 시간은 구현 후 실측하여 SOT에 기록
```

**지위 변경 없음**: Timeline Map은 여전히 **supplementary output**이다.
실패해도 master-orchestrator의 전체 파이프라인을 블로킹하지 않는다.
단, 성공 시 통합 보고서에 요약이 인라인된다.

---

## 4. Phase A: Data Foundation (Python 결정론적)

> "계산은 Python이" — 표준 라이브러리 + PyYAML만 사용 (CF-3 수정)

### 4.1 A1 — `theme_discovery_engine.py` (신규)

**역할**: 하드코딩 테마를 제거하고, 설정 기반 + 데이터 기반으로 테마를 발견한다.
에스컬레이션 분석도 이 모듈에 포함 (응집도 최적화: 테마와 에스컬레이션은 같은 데이터를 공유).

**모듈 독립성**: core/ 내 다른 모듈 import 없음 (기존 관례 준수).

**입력**:
```yaml
inputs:
  evolution_maps: WF1~WF4 evolution-map-{date}.json       # 상류 출력 소비
  evolution_indices: WF1~WF4 evolution-index.json          # 상류 출력 소비
  cross_evolution_map: cross-evolution-map-{date}.json     # 상류 출력 소비 (CF-1)
  theme_config: env-scanning/config/timeline-themes.yaml   # 신규 SOT 파일
  registry: env-scanning/config/workflow-registry.yaml
  scan_date: "{date}"
```

**처리 로직**:

```
1. Config-Driven Theme Matching (1차: 설정 기반)
   - timeline-themes.yaml에서 테마 정의 로딩
   - 각 테마: id, label_ko, label_en, priority, keywords_en[], keywords_ko[],
              steeps_affinity[], exclusion_keywords[]
   - Whole-word matching (re.compile + word boundary) + exclusion keyword 적용
   - 결과: config_themes[] (설정에 정의된 테마에 매칭된 시그널)

2. Emergent Theme Discovery (2차: 데이터 기반 발견)
   - config_themes에 매칭되지 않은 시그널 풀에서
   - 키워드 동시출현(co-occurrence) 기반 클러스터링 (표준 라이브러리만 사용):
     a) collections.Counter로 키워드 빈도 집계
     b) 빈도 상위 키워드 간 동시출현 매트릭스 구성
     c) difflib.SequenceMatcher로 시그널 제목 간 유사도 → 그룹핑
   - min_cluster_size (SOT에서 읽기) 이상인 클러스터 → emergent_themes[]
   - 각 emergent_theme: auto_id, representative_keywords[], signal_ids[], steeps_codes[]
   - LLM이 Phase B에서 이름을 부여

3. Per-Theme Statistics 계산
   - signal_count, date_distribution, psst_distribution (min/max/avg/median)
   - steeps_distribution, wf_distribution
   - temporal_density (signals/day)

4. Escalation Detection (v1.0의 A3를 여기에 통합)
   - 테마별 pSST 궤적 분석:
     a) 선형 회귀 기울기 (slope) — statistics.linear_regression() (Python 3.10+)
     b) 시그널 밀도 변화율 (burst detection)
     c) 다중 테마 동시 에스컬레이션 (compound escalation)
   - Severity: CRITICAL / HIGH / MEDIUM / STABLE / DECLINING

5. Cross-WF Enrichment
   - 기존 cross-evolution-map-{date}.json을 로딩 (생성하지 않음 — CF-1)
   - 각 correlation을 해당 테마에 태깅
   - 테마별 cross-WF 상관관계 수 집계
```

**출력**: `timeline-theme-analysis-{date}.json`

```json
{
  "engine": "theme_discovery_engine.py v1.0.0",
  "scan_date": "2026-03-06",
  "lookback_days": 7,
  "config_themes": [
    {
      "theme_id": "trade_tariff",
      "label_ko": "무역·관세 전쟁",
      "label_en": "Trade & Tariffs",
      "priority": "CRITICAL",
      "match_type": "config",
      "signals": ["sig-001", "sig-005", ...],
      "signal_details": [
        {
          "signal_id": "sig-001",
          "title": "US-China Trade Tensions Escalate",
          "scan_date": "2026-03-01",
          "source_wf": "WF1",
          "psst_score": 88,
          "primary_category": "E",
          "keywords": ["trade", "tariff", "us-china"]
        }
      ],
      "stats": {
        "count": 11,
        "date_distribution": {"2026-03-01": 3, "2026-03-02": 4, "2026-03-06": 4},
        "psst": {"min": 82, "max": 93, "avg": 88.5, "median": 89},
        "wf_distribution": {"WF1": 4, "WF3": 5, "WF4": 2},
        "steeps_distribution": {"E": 6, "P": 5}
      },
      "escalation": {
        "severity": "CRITICAL",
        "slope": 3.2,
        "direction": "RISING",
        "trajectory": [
          {"date": "2026-03-01", "avg_psst": 85.0, "count": 3},
          {"date": "2026-03-06", "avg_psst": 91.5, "count": 4}
        ]
      },
      "cross_wf_correlations": 2
    }
  ],
  "emergent_themes": [...],
  "unmatched_signals": [...],
  "compound_escalations": [
    {
      "themes": ["trade_tariff", "semiconductor"],
      "description": "2 themes escalating simultaneously",
      "combined_severity": "CRITICAL"
    }
  ]
}
```

**TDD 검증 항목** (11개):
```
test_whole_word_matching           — "diffusion" ≠ "energy" 테마 매칭 방지
test_exclusion_keywords            — 제외 키워드로 false positive 차단
test_config_loading_from_yaml      — SOT 파일에서 테마 정의 정상 로딩
test_emergent_cluster_minimum      — min_cluster_size 미만은 테마 제외
test_multi_theme_assignment        — 하나의 시그널이 2개 테마에 소속 가능
test_empty_input_graceful          — 입력 없으면 빈 결과 정상 반환
test_psst_statistics_accuracy      — min/max/avg/median 정확성
test_escalation_slope_calculation  — pSST 기울기 계산 정확성
test_compound_escalation_detection — 다중 테마 동시 에스컬레이션 탐지
test_cross_wf_enrichment           — 기존 cross-evolution-map 소비 정상
test_stable_no_false_alarm         — 안정 패턴 오탐 방지
```

### 4.2 A2 — `timeline_data_assembler.py` (신규)

**역할**: A1의 테마 분석 + 기존 상류 출력들을 하나의 통합 데이터 패키지로 조합한다.
LLM 에이전트에게 전달할 **단일 입력 파일**을 생성.

**핵심 원칙** (v2.2 — CR-v4/PB-1~PB-6 반영):
이 모듈은 **데이터 수집 + 포맷팅 + 결정론적 사전 렌더링(pre-rendering)**을 수행한다.
"엄밀하고, 100% 정확한 결과를 반복적으로 내야 하는" 산출물은
**모두 이 모듈에서 Python으로 사전 생성**하여 LLM 할루시네이션을 원천봉쇄한다.
LLM은 이 사전 생성물을 **그대로 사용**하고, 순수한 "판단/서사/해석/예측"만 수행한다.

**입력**:
```yaml
inputs:
  theme_analysis: timeline-theme-analysis-{date}.json           # A1 출력
  evolution_maps: WF1~WF4 evolution-map-{date}.json             # 상류 출력
  evolution_indices: WF1~WF4 evolution-index.json               # 상류 출력
  cross_evolution_map: cross-evolution-map-{date}.json          # 상류 출력
  classified_signals: WF1~WF4 classified-signals-{date}.json   # 상류 출력 (시그널 원문)
  registry: env-scanning/config/workflow-registry.yaml
```

**출력**: `timeline-map-data-package-{date}.json`

```json
{
  "metadata": {
    "scan_date": "2026-03-06",
    "lookback_days": 7,
    "period": "2026-02-28 ~ 2026-03-06",
    "wf_counts": {"wf1": 47, "wf2": 30, "wf3": 45, "wf4": 38},
    "total_signals": 160,
    "assembler_version": "1.0.0"
  },
  "theme_analysis": { ... },            // A1 출력 전체
  "cross_wf_correlations": { ... },     // 상류 cross-evolution-map 그대로
  "steeps_timeline": { ... },           // evolution-map에서 날짜×STEEPs 집계
  "psst_rankings": [ ... ],            // evolution-map에서 Top-N pSST 추출
  "per_theme_signal_details": {         // classified-signals에서 시그널 원문 추출
    "trade_tariff": [
      {
        "signal_id": "sig-001",
        "title": "...",
        "content_summary": "...",       // abstract 또는 content의 처음 500자
        "psst_score": 88,
        "source_wf": "WF1",
        "scan_date": "2026-03-01",
        "source_name": "Reuters",
        "primary_category": "E"
      }
    ]
  },

  // ── Python 원천봉쇄 사전 렌더링 (PB-1~PB-6) ──
  // LLM은 이 섹션의 값을 그대로 사용한다. 수치를 자체 생성하지 않는다.
  "pre_rendered": {
    // PB-1: ASCII 타임라인 다이어그램 (테마별, Python이 날짜/pSST/WF 정확히 배치)
    "ascii_timelines": {
      "trade_tariff": "02-28 ─────── 03-02 ─────── 03-06\n  │ WF1(3) pSST:85   │ WF3(4) pSST:89   │ WF1,WF3(4) pSST:91\n",
      "geopolitics": "..."
    },
    // PB-2: Cross-WF 매트릭스 구조 (수치 셀은 Python이 채움, LLM은 해석 열만 추가)
    "cross_wf_table": {
      "headers": ["테마", "WF1", "WF2", "WF3", "WF4", "최초출현", "최종출현", "시차(일)"],
      "rows": [
        {"theme": "trade_tariff", "wf1": 4, "wf2": 0, "wf3": 5, "wf4": 2, "first_date": "2026-03-01", "last_date": "2026-03-06", "lag_days": 5},
        "..."
      ],
      "markdown": "| 테마 | WF1 | WF2 | WF3 | WF4 | 최초 | 최종 | 시차 | 해석 |\n|------|-----|-----|-----|-----|------|------|------|------|\n| 무역·관세 | 4 | 0 | 5 | 2 | 03-01 | 03-06 | 5일 | {{LLM}} |\n"
    },
    // PB-3: Lead-Lag 시간차 계산 (Python이 정확한 일수 산출)
    "lead_lag_computed": [
      {"theme": "trade_tariff", "first_wf": "WF2", "first_date": "2026-03-01", "last_wf": "WF3", "last_date": "2026-03-04", "lag_days": 3}
    ],
    // PB-4: Escalation 확정 등급 (Python이 결정, LLM override 불가)
    "escalation_confirmed": [
      {"theme_id": "trade_tariff", "severity": "CRITICAL", "slope": 3.2, "direction": "RISING", "signal_count": 11}
    ],
    // PB-5: 모니터링 우선순위 순번 (severity + slope 기반 결정론적 정렬)
    "monitoring_priority_order": ["trade_tariff", "semiconductor", "geopolitics"],
    // PB-6: 테마 표시 순서 + 테마별 하이라이트 시그널 (pSST Top-3)
    "theme_display_order": ["trade_tariff", "geopolitics", "semiconductor", "ai_technology"],
    "key_signals_per_theme": {
      "trade_tariff": ["sig-001", "sig-005", "sig-011"],
      "geopolitics": ["sig-003", "sig-007", "sig-012"]
    },
    // 에스컬레이션 모니터링 테이블 (수치 열은 Python, "다음 예상" 열만 LLM)
    "escalation_table_markdown": "| 순위 | 테마 | 심각도 | 기울기 | 방향 | 시그널 수 | 다음 예상 |\n|------|------|--------|--------|------|----------|----------|\n| 1 | 무역·관세 | CRITICAL | 3.2 | RISING | 11 | {{LLM}} |\n"
  }
}
```

**핵심 설계 결정**: `per_theme_signal_details`에는 각 테마의 시그널 원문이 포함된다.
LLM이 서사 분석을 할 때 **원문을 직접 읽고 판단**할 수 있도록 하기 위함이다.
content는 500자로 truncate하여 JSON 크기를 제어한다.

**TDD 검증 항목** (14개 — PB-1~PB-6 원천봉쇄 테스트 포함):
```
# 기존 조립 테스트
test_assembly_completeness          — 모든 필수 섹션 존재 (pre_rendered 포함)
test_wf_counts_accuracy             — WF별 카운트 정합성
test_signal_detail_inclusion        — 시그널 원문 포함 확인
test_content_truncation             — 500자 초과 시 truncate 확인
test_missing_component_graceful     — 상류 출력 누락 시 해당 섹션 빈 값으로 진행
test_steeps_timeline_computation    — 날짜×STEEPs 매트릭스 정확성

# PB-1: ASCII 다이어그램 사전 렌더링
test_ascii_timeline_dates_correct   — 다이어그램 내 날짜가 실제 시그널 날짜와 일치
test_ascii_timeline_psst_correct    — 다이어그램 내 pSST 값이 실제 값과 일치
test_ascii_timeline_wf_labels       — WF 레이블이 정확

# PB-2~PB-3: Cross-WF 테이블 + Lead-Lag
test_cross_wf_table_cell_accuracy   — 테마×WF 셀 카운트가 실제 데이터와 일치
test_lead_lag_days_calculation      — lag_days = last_date - first_date 정확

# PB-4~PB-5: 에스컬레이션 + 모니터링 순위
test_escalation_confirmed_matches   — Python severity가 theme_analysis와 일치
test_monitoring_order_deterministic — 동일 입력에 대해 순서가 항상 동일

# PB-6: 테마 순서 + 하이라이트
test_theme_order_by_priority_slope  — CRITICAL>HIGH>MEDIUM 순, 동일 priority 내 slope 역순
test_key_signals_top3_psst          — 각 테마 내 pSST 상위 3개가 선택됨
```

---

## 5. Phase B: Narrative Analysis (LLM 판단)

> "판단은 LLM이" — 1개 통합 에이전트가 전체 테마를 한 컨텍스트에서 분석 (CF-4 수정)

### 5.0 기술 선택 근거: Task Subagent vs Agent Teams (CR-1 추가)

> **품질이 유일한 기준이다.** 속도가 아니라 결과의 품질로 판단한다.

**Phase B (`timeline-narrative-analyst`) → Task Subagent 선택**

| 대안 | 품질 영향 | 판정 |
|------|----------|------|
| Task Subagent (단일 에이전트) | 모든 테마가 한 컨텍스트에 있으므로 cross-theme strategic synthesis가 자연스럽게 발생. CF-4의 핵심 원칙("모든 테마를 한 컨텍스트에서 볼 때만 cross-theme insight 가능") 유지. | **채택** |
| Agent Teams (테마별 전문가 + synthesizer) | 분업 축이 "테마별"이 되면 CF-4에서 제거한 "각자 자기 영역만 보는" 문제가 재현. 통합 보고서의 Agent Teams는 WF1/WF2/WF3/WF4라는 자연스러운 분업 축이 있었으나, Timeline Map에는 이에 상응하는 분업 축이 부재. | 기각 |

**Phase C (`timeline-map-composer`) → Task Subagent 선택**

| 대안 | 품질 영향 | 판정 |
|------|----------|------|
| Task Subagent (단일 에이전트) | 최종 문서의 문체·흐름·톤 일관성은 단일 저자가 보장. 조립(assembly) 작업에 다중 에이전트 토론은 품질 향상에 기여하지 않음. | **채택** |
| Agent Teams | 조립 작업은 분석이 아님. 토론에서 추가 insight 발생 가능성 극히 낮음. 오히려 문체 불일치 위험. | 기각 |

### 5.1 B1 — `timeline-narrative-analyst.md` (신규 워커 에이전트, 통합)

**역할**: v1.0의 B1(theme-narrator) + B2(cross-wf-analyst) + B3(escalation-assessor)를
**단일 에이전트**로 통합한다.

**통합 근거 (CF-4)**:
수동 생성 버전(02-06-to-02-11)의 핵심 품질은 **테마 간 상호작용 분석**이었다:
- "관세 전쟁 + 반도체 규제 → compound effect" (cross-theme)
- "기술 가속과 정책 역행이 동시 진행 → 역설적 충돌" (cross-theme)
- "원자력이 에너지와 안보 양쪽에서 동시에 부상" (cross-theme)

이러한 cross-theme insight는 **모든 테마를 하나의 컨텍스트에서 볼 때만** 가능하다.
3개 에이전트로 분리하면 각자 자기 테마만 보게 되어 이 핵심 가치가 소멸한다.

**입력**: `timeline-map-data-package-{date}.json` (전체)

**수행 작업** (전체 데이터를 한 번에 분석):

```
STEP 1: 테마별 서사 분석 (Per-Theme Narrative)
  각 테마(config + emergent)에 대해:

  1a. 궤적 분석 (Trajectory)
      - 시그널들의 시간순 배열을 읽고, 전개 과정을 서사로 요약
      - 형식: "배경 리스크 → 위협 구체화 → 확정·확산"
      - 근거: Python이 제공한 date_distribution + 시그널 원문(content_summary)

  1b. 판단 (Judgment)
      - 이 테마가 왜 중요한지, 현재 어떤 단계인지 판단
      - 형식: "7일간 가장 빠르게 에스컬레이션된 테마. 정책적 대응 긴급."
      - 근거: Python이 제공한 escalation severity + pSST trajectory

  1c. 다음 예상 (Next Expected)
      - 향후 전개 방향 예측
      - 구체적 사건 유형 명시 (추상적 "변화 예상" 금지)

  1d. ASCII 타임라인 다이어그램 (PB-1 원천봉쇄)
      - Python이 사전 렌더링한 ascii_timelines를 **그대로 복사**
      - LLM은 다이어그램을 수정하거나 재생성하지 않음
      - 필요시 다이어그램 앞뒤에 해석 문장만 추가

  1e. Emergent Theme 명명 (해당 시)
      - 대표 키워드와 시그널 원문 기반으로 한국어/영어 명칭 생성

STEP 2: 교차 워크플로우 해석 (Cross-WF Narrative)
  - Python이 제공한 cross_wf_correlations + pre_rendered.cross_wf_table을 기반으로 해석
  - cross_wf_table.markdown의 {{LLM}} 셀에 해석 문장을 채움 (PB-2 원천봉쇄: 수치 셀 변경 금지)
  - lead_lag_computed의 lag_days를 **인용**하여 해석 (PB-3 원천봉쇄: 시간차 재계산 금지)
    예: "WF2(학계)가 3일 선행 → WF1(산업) 확산" (3일은 Python이 계산한 값)
  - Convergence: 같은 사건의 WF별 관점 차이 해석
  - Divergence: WF 간 관점 양극화 식별

STEP 3: 에스컬레이션 평가 (Escalation Assessment)
  - Python이 확정한 severity 등급을 **그대로 사용** (PB-4 원천봉쇄: LLM override 불가)
  - escalation_table_markdown의 {{LLM}} 셀("다음 예상")만 채움
  - monitoring_priority_order를 **그대로 사용** (PB-5 원천봉쇄: 순번 재계산 금지)
  - 정성적 맥락 추가: 왜 이 심각도인지, 어떤 정책적 의미가 있는지
  - False positive 필터링: Python 등급이 과대인 경우 근거와 함께 플래그 (등급 변경 아님, 주석만)
  - Compound escalation 해석

STEP 4: Cross-Theme Strategic Synthesis (★ 통합 에이전트만 가능)
  - 테마 간 상호작용/인과관계/모순 식별
  - "관세 전쟁(테마A) + 반도체(테마B) → 공급망 위기(compound)"
  - "에너지 기술 가속(테마C) ↔ 정책 역행(테마D) → 역설적 충돌"
  - 전략적 시사점 3~5개 도출 (의사결정자용)
```

**출력**: `timeline-narratives-{date}.json`

```json
{
  "analyst_version": "1.0.0",
  "scan_date": "2026-03-06",
  "theme_narratives": [
    {
      "theme_id": "trade_tariff",
      "trajectory": "배경 리스크 → 위협 구체화 → 확정·확산",
      "judgment": "7일간 가장 빠르게 에스컬레이션된 테마. 정책적 대응 긴급.",
      "next_expected": "보복 관세 및 2라운드 확대 가능성. 공급망 재편 가속."
      // NOTE: ascii_timeline은 Python pre_rendered를 그대로 사용 (PB-1)
      // NOTE: key_signals_highlighted는 Python pre_rendered를 그대로 사용 (PB-6)
    }
  ],
  "emergent_theme_names": [
    {
      "auto_id": "emergent_001",
      "label_ko": "공급망 리쇼어링",
      "label_en": "Supply Chain Reshoring",
      "rationale": "..."
    }
  ],
  "cross_wf_narrative": {
    "convergence_patterns": [...],
    "lead_lag_interpretations": [...],
    "narrative_table": "| 테마 | WF1 | WF3 | WF4 | 날짜 |\n|...|"
  },
  "escalation_assessments": [
    {
      "theme_id": "trade_tariff",
      "severity": "CRITICAL",              // Python 확정 등급 그대로 (PB-4: LLM override 불가)
      "assessment": "정책 확정 단계 진입. 보복 사이클 개시 가능성.",
      "next_expected": "보복 관세, 2라운드 확대",
      "false_positive_flag": null           // Python 등급이 과대라고 판단 시에만 근거 문자열
      // NOTE: monitoring_priority는 Python pre_rendered를 그대로 사용 (PB-5)
    }
  ],
  "cross_theme_synthesis": {
    "interactions": [
      {
        "themes": ["trade_tariff", "semiconductor"],
        "pattern": "compound_escalation",
        "narrative": "관세 전쟁과 반도체 규제가 결합하여 공급망 위기를 가속"
      }
    ],
    "strategic_implications": [
      "1. 관세·반도체 compound effect에 대한 공급망 재편 전략 필요",
      "2. 에너지 기술 가속 vs 정책 역행 역설의 투자 기회/리스크 평가",
      "3. ..."
    ]
  }
}
```

**품질 제어 규칙** (에이전트 spec에 명시):

**Python 원천봉쇄 규칙 (PB — 위반 시 REJECT)**:
- PB-1: ASCII 다이어그램은 `pre_rendered.ascii_timelines`를 **그대로 복사**. 수정/재생성 금지.
- PB-2: Cross-WF 테이블의 수치 셀은 `pre_rendered.cross_wf_table`에서 **그대로 사용**. {{LLM}} 셀만 채움.
- PB-3: Lead-Lag 시간차는 `pre_rendered.lead_lag_computed`의 lag_days를 **인용**. 재계산 금지.
- PB-4: Escalation severity는 `pre_rendered.escalation_confirmed`의 등급을 **그대로 사용**. Override 불가. 과대 판단 시 `false_positive_flag`로 주석만 가능.
- PB-5: 모니터링 순위는 `pre_rendered.monitoring_priority_order`를 **그대로 사용**. 순번 재배정 금지.
- PB-6: 하이라이트 시그널은 `pre_rendered.key_signals_per_theme`를 **그대로 사용**. 테마 표시 순서는 `pre_rendered.theme_display_order`를 따름.
- **수치를 만들지 않음**: `pre_rendered`와 `theme_analysis`에 없는 숫자를 사용하면 **REJECT**.

**서사 품질 규칙 (LLM 고유 판단 영역)**:
- 궤적에는 반드시 **시간 순서 전환점** 2개 이상 포함 (lookback 내 출현 날짜 기반)
- 판단에는 반드시 **정량 근거** 1개 이상 인용 (Python이 제공한 수치)
- 다음 예상에는 반드시 **구체적 사건 유형** 명시 (추상적 "변화 예상" 금지)
- cross_theme_synthesis에 최소 **2개** 테마 상호작용 + **3개** 전략적 시사점

---

## 6. Phase C: Assembly (스켈레톤 조립)

### 6.1 C1 — `timeline_skeleton_filler.py` (신규)

**역할**: 타임라인 맵 전용 스켈레톤에 Python 정량 데이터를 주입한다.

기존 시스템의 `report_metadata_injector.py`와 동일한 패턴: 플레이스홀더 토큰을 정량 데이터로 교체.

**주입할 플레이스홀더**:

```
{{TL_SCAN_DATE}}                   — 스캔 날짜
{{TL_PERIOD}}                      — 분석 기간
{{TL_ENGINE_VERSION}}              — 엔진 버전
{{TL_TOTAL_SIGNALS}}               — 총 시그널 수
{{TL_WF_COUNTS}}                   — WF별 시그널 수
{{TL_THEMES_DETECTED}}             — 탐지된 테마 수
{{TL_ESCALATIONS_DETECTED}}        — 에스컬레이션 수
{{TL_CROSS_WF_CORRELATIONS}}       — 교차 WF 상관관계 수
{{TL_STEEPS_MATRIX}}               — STEEPs × 날짜 매트릭스 (ASCII 테이블)
{{TL_PSST_TOP_N_TABLE}}            — pSST Top-N 테이블
{{TL_METADATA_YAML}}               — 메타데이터 YAML 블록
```

LLM이 채울 플레이스홀더 (Phase B 출력으로):

```
{{TL_OVERVIEW_NARRATIVE}}          — 타임라인 개관 서사
{{TL_THEME_SECTIONS}}              — 테마별 서사 분석 블록 (반복)
{{TL_CROSS_WF_NARRATIVE_TABLE}}    — 교차 WF 서사 테이블
{{TL_ESCALATION_ASSESSMENT_TABLE}} — 에스컬레이션 평가 테이블
{{TL_STRATEGIC_IMPLICATIONS}}      — 전략적 시사점
```

**TDD 검증 항목**:
```
test_all_python_placeholders_filled — 모든 Python 플레이스홀더 교체 완료
test_llm_placeholders_preserved     — LLM용 플레이스홀더는 보존
test_steeps_matrix_formatting       — ASCII 테이블 정렬 정확성
test_psst_table_formatting          — pSST 테이블 마크다운 문법
test_metadata_yaml_valid            — YAML 블록 파싱 가능
```

### 6.2 C2 — `timeline-map-composer.md` (신규 워커 에이전트)

**역할**: C1이 반쯤 채운 스켈레톤에 Phase B의 서사 분석을 주입하여 최종 마크다운을 완성한다.

**입력**:
- C1 출력: 정량 데이터가 주입된 반완성 스켈레톤
- B1 출력: 테마별 서사 분석
- B2 출력: 교차 WF 서사 분석
- B3 출력: 에스컬레이션 평가

**수행 작업**:
```
1. LLM 플레이스홀더에 서사 분석 주입
2. 전체 문서 흐름 조정 (섹션 간 연결성)
3. 타임라인 개관 서사 작성 (전체를 총괄하는 1단락)
4. 전략적 시사점 작성 (의사결정자를 위한 종합 판단)
5. 최종 마크다운 품질 확인
```

**품질 규칙**:
- `{{...}}` 토큰이 하나라도 남으면 REJECT
- 각 테마 섹션에 궤적 + 판단 + ASCII 타임라인이 모두 있어야 PASS
- 전략적 시사점에 최소 3개 actionable recommendation 포함

---

## 7. Phase D: Quality Defense

### 7.1 D1 — `validate_timeline_map.py` (신규)

**역할**: 타임라인 맵 전용 구조/QC 검증 스크립트.

**검증 규칙**:

```
# L2a — 구조 검증 (Structural)
TL-001: 필수 섹션 7개 존재 확인
        (개관, 테마별 추적, STEEPs 분포, pSST Top-N,
         교차 WF 궤적, 에스컬레이션 모니터링, 메타데이터)
TL-002: 메타데이터 YAML 블록 파싱 가능
TL-003: {{PLACEHOLDER}} 잔존 확인 → 있으면 CRITICAL
TL-004: 최소 단어수 ≥ 3000 (한국어+영어 합산)
TL-005: 테마 섹션 수 ≥ 3 (최소 3개 테마)

# L2b — 품질 검증 (Cross-Reference Quality)
TL-006: 각 테마에 "궤적" 문자열 존재
TL-007: 각 테마에 "판단" 문자열 존재
TL-008: 각 테마에 ASCII 코드블록 존재 (``` 기준)
TL-009: pSST Top-N 테이블에 최소 5개 행
TL-010: 에스컬레이션 테이블에 "다음 예상" 컬럼 존재
TL-011: 메타데이터의 total_signals와 본문 시그널 수 정합성
TL-012: 날짜 범위 일관성 (메타데이터 period와 본문 날짜)
TL-013: 전략적 시사점 섹션에 최소 3개 항목
```

**Exit codes**: 0=PASS, 1=CRITICAL, 2=WARN

**TDD 검증 항목**:
```
test_all_sections_present          — 7개 섹션 모두 존재 시 PASS
test_missing_section_critical      — 필수 섹션 누락 시 CRITICAL
test_placeholder_detection         — {{...}} 잔존 탐지
test_min_word_count                — 최소 단어수 체크
test_trajectory_presence           — 궤적 문자열 존재 확인
test_judgment_presence             — 판단 문자열 존재 확인
test_psst_table_row_count          — pSST 테이블 행 수 확인
test_metadata_total_consistency    — 메타데이터 정합성
test_pass_on_valid_report          — 유효한 보고서에서 PASS 확인
```

### 7.2 D2 — Quality Reviewer (기존 `quality-reviewer.md` 재사용)

기존 L3 Semantic Depth Reviewer를 타임라인 맵에도 적용한다.
타임라인 맵 전용 검토 항목을 추가:

```
기존 L3 체크 (재사용):
- Inference quality: 추론이 사실 재서술을 넘어서는가?
- Narrative flow: 문서가 일관된 이야기를 전달하는가?
- Internal consistency: 섹션 간 교차 참조가 정확한가?

타임라인 맵 전용 체크 (추가):
- Temporal coherence: 시간순 전개가 논리적인가?
- Cross-theme insight: 테마 간 상호작용이 분석되었는가?
- Actionability: 전략적 시사점이 실행 가능한 수준인가?
- Escalation realism: 에스컬레이션 전망이 현실적인가?
```

---

## 8. SOT 확장

### 8.1 `workflow-registry.yaml` 변경 (v2.0 — CF-1/CF-2 반영)

```yaml
system:
  signal_evolution:
    # ... 기존 설정 전부 유지 (cross_workflow_correlation 포함) ...

    # ── Timeline Map Generation (v3.0.0 Enhanced) ──
    # v2.0: cross_wf 설정은 기존 cross_workflow_correlation 섹션을 그대로 사용 (CF-1)
    timeline_map:
      enabled: true

      # Phase A: Data Foundation (2개 모듈만)
      theme_config: "env-scanning/config/timeline-themes.yaml"
      theme_discovery_engine: "env-scanning/core/theme_discovery_engine.py"
      data_assembler: "env-scanning/core/timeline_data_assembler.py"
      # ❌ cross_wf_correlator 삭제 (CF-1: 기존 cross_correlate_threads() 소비)
      # ❌ escalation_detector 삭제 (theme_discovery_engine에 통합)

      # Phase C: Assembly
      skeleton_filler: "env-scanning/core/timeline_skeleton_filler.py"
      skeleton_template_en: ".claude/skills/env-scanner/references/timeline-map-skeleton-en.md"
      skeleton_template_ko: ".claude/skills/env-scanner/references/timeline-map-skeleton.md"

      # Phase D: Quality Defense
      validator: "env-scanning/scripts/validate_timeline_map.py"

      # Parameters
      output_filename_pattern: "timeline-map-{date}.md"
      lookback_days: 7
      min_signals_for_theme: 2
      top_n_psst: 10
      # Emergent theme discovery (CR-2: 모든 파라미터를 여기에 단일화)
      emergent_cluster_min_size: 3
      emergent_max_themes: 5
      emergent_cooccurrence_threshold: 3
      emergent_title_similarity_threshold: 0.55
      escalation_thresholds:
        critical_slope: 5.0
        high_slope: 2.0
        burst_factor: 2.0

      # Orchestrator
      orchestrator: ".claude/agents/timeline-map-orchestrator.md"
      max_execution_minutes: 15    # CR-3: 타임아웃 (초과 시 fallback 전환)

      # Fallback (기존 generator 유지)
      fallback_script: "env-scanning/core/timeline_map_generator.py"
```

**변경 최소화 원칙**: 기존 `timeline_map` 섹션의 `enabled`, `generator_script`,
`output_filename_pattern`, `lookback_days`, `min_signals_for_theme`, `top_n_psst`는
**기존 키를 그대로 유지**한다. 기존 키를 삭제하거나 이름을 변경하면
`validate_registry.py` SOT-036과 기존 `timeline_map_generator.py`의
`load_timeline_config()`가 깨진다.

새 키(`theme_config`, `theme_discovery_engine`, `data_assembler`, `skeleton_filler`,
`skeleton_template_en`, `skeleton_template_ko`, `validator`, `orchestrator`,
`escalation_thresholds`, `emergent_cluster_min_size`, `fallback_script`)만 **추가**한다.

### 8.2 `timeline-themes.yaml` (신규 SOT 파일)

```yaml
# Timeline Map Theme Definitions
# Referenced by: theme_discovery_engine.py
# Path declared in: workflow-registry.yaml → system.signal_evolution.timeline_map.theme_config
#
# 각 테마에 이중언어 키워드, STEEPs 친화도, 우선순위, 제외 키워드를 정의.
# whole_word 매칭으로 false positive 차단 (CF-3 대응).
#
# 변경 시: validate_registry.py SOT-036 체크 자동 검증.
# SIE가 키워드를 제안할 수 있으나 변경은 사용자 승인 필요.

version: "1.0.0"

themes:
  trade_tariff:
    label_ko: "무역·관세 전쟁"
    label_en: "Trade & Tariffs"
    priority: "CRITICAL"
    keywords_en:
      - "tariff"
      - "trade war"
      - "customs duty"
      - "import duty"
      - "export control"
      - "trade policy"
      - "trade tension"
    keywords_ko:
      - "관세"
      - "무역전쟁"
      - "수출규제"
      - "수입규제"
      - "통상"
    exclusion_keywords:
      - "fair trade coffee"
      - "trade-off"
      - "tradeoff"
    steeps_affinity: ["E", "P"]

  geopolitics:
    label_ko: "지정학적 긴장"
    label_en: "Geopolitics"
    priority: "CRITICAL"
    keywords_en:
      - "geopolitics"
      - "geopolitical"
      - "us-china"
      - "nato"
      - "alliance"
      - "sanctions"
      - "diplomacy"
      - "arms race"
    keywords_ko:
      - "지정학"
      - "미중"
      - "안보"
      - "동맹"
      - "군사"
      - "제재"
      - "외교"
    exclusion_keywords:
      - "cybersecurity"
      - "network security"
      - "information security"
    steeps_affinity: ["P"]

  energy_climate:
    label_ko: "에너지·기후 전환"
    label_en: "Energy & Climate"
    priority: "HIGH"
    keywords_en:
      - "climate change"
      - "renewable energy"
      - "solar power"
      - "wind power"
      - "nuclear fusion"
      - "carbon emission"
      - "energy transition"
      - "greenhouse gas"
    keywords_ko:
      - "기후변화"
      - "재생에너지"
      - "태양광"
      - "풍력"
      - "핵융합"
      - "탄소"
      - "에너지전환"
      - "온실가스"
    exclusion_keywords:
      - "diffusion model"
      - "latent diffusion"
      - "solar system"
    steeps_affinity: ["E_Environmental", "T"]

  ai_technology:
    label_ko: "AI·기술 진화"
    label_en: "AI & Technology"
    priority: "HIGH"
    keywords_en:
      - "artificial intelligence"
      - "machine learning"
      - "deep learning"
      - "large language model"
      - "agentic ai"
      - "autonomous"
      - "robotics"
      - "quantum computing"
    keywords_ko:
      - "인공지능"
      - "머신러닝"
      - "딥러닝"
      - "에이전트"
      - "로봇"
      - "양자컴퓨팅"
      - "생성형"
    exclusion_keywords: []
    steeps_affinity: ["T"]

  semiconductor:
    label_ko: "반도체 전쟁"
    label_en: "Semiconductor"
    priority: "MEDIUM"
    keywords_en:
      - "semiconductor"
      - "chip"
      - "hbm"
      - "dram"
      - "foundry"
      - "lithography"
      - "wafer"
    keywords_ko:
      - "반도체"
      - "파운드리"
      - "웨이퍼"
      - "삼성전자"
      - "하이닉스"
    exclusion_keywords: []
    steeps_affinity: ["T", "E"]

  demographics:
    label_ko: "인구·사회 위기"
    label_en: "Demographics"
    priority: "MEDIUM"
    keywords_en:
      - "demographics"
      - "population decline"
      - "birth rate"
      - "fertility rate"
      - "aging society"
      - "labor shortage"
    keywords_ko:
      - "인구"
      - "출산율"
      - "고령화"
      - "저출생"
      - "인구절벽"
      - "노동력"
    exclusion_keywords:
      - "population synthesis"
      - "population dynamics"
    steeps_affinity: ["S"]

  biotech_health:
    label_ko: "바이오·의료"
    label_en: "Biotech & Health"
    priority: "MEDIUM"
    keywords_en:
      - "biotech"
      - "crispr"
      - "gene editing"
      - "genomics"
      - "pharmaceutical"
      - "drug discovery"
      - "pandemic"
    keywords_ko:
      - "바이오"
      - "유전자"
      - "의료"
      - "제약"
      - "의대"
      - "크리스퍼"
    exclusion_keywords: []
    steeps_affinity: ["T", "S"]

  nuclear_security:
    label_ko: "핵무기·전략 균형"
    label_en: "Nuclear Security"
    priority: "MEDIUM"
    keywords_en:
      - "nuclear weapon"
      - "nuclear arms"
      - "nuclear proliferation"
      - "arms control"
      - "nuclear treaty"
      - "deterrence"
    keywords_ko:
      - "핵무기"
      - "핵군비"
      - "핵확산"
      - "군축"
      - "핵전략"
    exclusion_keywords:
      - "nuclear fusion"
      - "nuclear energy"
      - "nuclear power plant"
    steeps_affinity: ["P"]

# NOTE (CR-2): Emergent theme discovery 파라미터는 이 파일에 두지 않는다.
# workflow-registry.yaml → timeline_map 섹션이 모든 파라미터의 단일 SOT.
# 이 파일은 "테마 정의"만 담당한다. 파라미터 이중화 금지.
```

### 8.3 검증 규칙 변경 (`validate_registry.py`)

**기존 SOT-036 확장** (WARN 레벨 유지 — 기존과 동일):

```
기존 체크 (유지):
  - timeline_map.enabled: boolean
  - timeline_map.generator_script: 파일 존재
  - timeline_map.lookback_days: int [1, 90]
  - timeline_map.min_signals_for_theme: int >= 1
  - timeline_map.top_n_psst: int >= 1

추가 체크 (v2.1 — CR-2 반영, 누락 5개 보완):
  - timeline_map.theme_config: 파일 존재 확인
  - theme_config 내용: 각 theme에 label_ko, label_en, priority, keywords_en, keywords_ko 필수
  - priority ∈ {CRITICAL, HIGH, MEDIUM, LOW}
  - timeline_map.theme_discovery_engine: 파일 존재 확인           # CR-2 추가
  - timeline_map.data_assembler: 파일 존재 확인                   # CR-2 추가
  - timeline_map.skeleton_filler: 파일 존재 확인                  # CR-2 추가
  - timeline_map.emergent_cluster_min_size: int >= 1              # CR-2 추가
  - timeline_map.fallback_script: 파일 존재 확인                  # CR-2 추가
  - timeline_map.orchestrator: 파일 존재 확인 (있을 때만)
  - timeline_map.skeleton_template_en/ko: 파일 존재 확인 (있을 때만)
  - timeline_map.validator: 파일 존재 확인 (있을 때만)
  - escalation_thresholds: 각 값 > 0 (있을 때만)
  - emergent_max_themes: int >= 1 (있을 때만)                     # CR-2 추가
  - emergent_cooccurrence_threshold: int >= 1 (있을 때만)         # CR-2 추가
  - emergent_title_similarity_threshold: float (0, 1] (있을 때만) # CR-2 추가
```

**새 SOT-042 추가하지 않음**: 모든 타임라인 맵 설정은 기존 SOT-036 내에서 처리한다.
별도 SOT-042를 추가하면 검증 규칙이 분산되어 관리 복잡도가 증가한다.

---

## 9. 에이전트 정의 (v2.0 — CF-4 반영)

### 9.1 `timeline-map-orchestrator.md` (신규)

```
위치: .claude/agents/timeline-map-orchestrator.md
유형: Sub-Orchestrator (master-orchestrator Step 5.1.4에서 호출)
역할: Timeline Map 생성 전체 파이프라인 조율
```

**실행 흐름**:

```
Step 0: SOT 읽기 + 변수 추출
  → workflow-registry.yaml에서 timeline_map 설정 로딩
  → 상류 출력 파일 경로 확인 (evolution-map, cross-evolution-map 등)

Step A: Data Foundation (Python, 순차 실행 — 모듈 2개)
  A1: python3 {THEME_DISCOVERY_ENGINE} \
        --registry ... \
        --theme-config {THEME_CONFIG} \
        --wf1-evolution-map ... --wf2-evolution-map ... --wf3-evolution-map ... --wf4-evolution-map ... \
        --wf1-index ... --wf2-index ... --wf3-index ... --wf4-index ... \
        --cross-evolution-map {cross-evolution-map path from Step 5.1.2.4} \
        --scan-date {date} \
        --output {INT_OUTPUT_ROOT}/analysis/timeline-theme-analysis-{date}.json
      → exit code 확인, CRITICAL 시 재시도 (max 2)

  A2: python3 {DATA_ASSEMBLER} \
        --theme-analysis {A1 출력} \
        --wf1-classified ... --wf2-classified ... --wf3-classified ... --wf4-classified ... \
        --wf1-evolution-map ... --wf2-evolution-map ... --wf3-evolution-map ... --wf4-evolution-map ... \
        --cross-evolution-map ... \
        --registry ... \
        --scan-date {date} \
        --output {INT_OUTPUT_ROOT}/analysis/timeline-map-data-package-{date}.json
      → exit code 확인

Step B: Narrative Analysis (LLM 워커 1개 — CF-4 수정)
  B1: Invoke @timeline-narrative-analyst (Task subagent)
      Input: timeline-map-data-package-{date}.json
      Output: timeline-narratives-{date}.json
      → 테마 서사 + 교차 WF 해석 + 에스컬레이션 평가 + cross-theme 종합을 한 컨텍스트에서

Step C: Assembly
  C1: python3 {SKELETON_FILLER} \
        --skeleton {SKELETON_TEMPLATE_EN} \
        --data-package {A2 출력} \
        --scan-date {date} \
        --output {INT_OUTPUT_ROOT}/reports/daily/_timeline-skeleton-prefilled-{date}.md
      → 정량 데이터 주입된 반완성 스켈레톤

  C2: Invoke @timeline-map-composer (Task subagent)
      Input:
        - C1 출력 (반완성 스켈레톤)
        - B1 출력 (서사 분석 JSON)
      Output: timeline-map-{date}.md + timeline-summary-{date}.txt
      → 서사 분석 주입 → 최종 마크다운 완성
      → 별도로 3~5 단락 요약문(timeline-summary) 생성 (통합 보고서 인라인용)

Step D: Quality Defense
  D1: python3 {VALIDATOR} --input {C2 출력 md} --profile timeline
      → exit code 0 확인
  D2: Invoke @quality-reviewer (기존 에이전트 재사용, 추가 변경 없음)
      → review_type: "timeline_map"

  IF D1 CRITICAL or D2 REJECT:
    → Progressive Retry (max 2):
      1st retry: C2에게 D1/D2 피드백 전달 → 재생성
      2nd retry: B1 재실행 → C1+C2 재실행 → D1+D2 재검증
    → 2회 실패 시:
      python3 {FALLBACK_SCRIPT} generate ... (기존 timeline_map_generator.py)
      Log: "Enhanced pipeline failed, using basic generator as fallback"

Step E: Output
  → timeline-map-{date}.md 최종 저장
  → timeline-summary-{date}.txt 저장 (report_statistics_engine이 읽을 수 있는 위치)
  → 실행 증명 로깅
```

### 9.2 워커 에이전트 목록 (v2.0 — 4개 → 2개)

| 에이전트 | 파일 위치 | 유형 | v1.0 대비 |
|---------|----------|------|----------|
| `timeline-narrative-analyst` | `.claude/agents/workers/timeline-narrative-analyst.md` | LLM Worker | B1+B2+B3 통합 |
| `timeline-map-composer` | `.claude/agents/workers/timeline-map-composer.md` | LLM Worker | 유지 |
| ~~timeline-theme-narrator~~ | — | — | 삭제 (CF-4) |
| ~~timeline-cross-wf-analyst~~ | — | — | 삭제 (CF-4) |
| ~~timeline-escalation-assessor~~ | — | — | 삭제 (CF-4) |

---

## 10. 스켈레톤 템플릿

### 10.1 `timeline-map-skeleton-en.md` (신규)

```markdown
# Signal Evolution Timeline Map
## 시그널 진화 타임라인 맵

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
```

---

## 11. 통합 보고서 연결

### 11.1 `integrated-report-skeleton-en.md` 변경

기존 통합 보고서 스켈레톤에 타임라인 맵 요약 섹션을 추가한다.

```markdown
## 7. Signal Evolution Timeline Summary

> Full timeline map: see `timeline-map-{date}.md`

{{INT_TIMELINE_SUMMARY}}
```

`{{INT_TIMELINE_SUMMARY}}`는 `timeline-map-composer`가 타임라인 맵의 핵심 내용을
3~5 단락으로 축약한 요약을 별도로 생성하여 `report_metadata_injector.py`가 주입한다.

### 11.2 Weekly Report 연결

`weekly-report-skeleton.md`의 `## 4. 신호 진화 타임라인` 섹션은
지난 7일간의 daily timeline-map들을 종합하는 주간 타임라인이다.
이 섹션의 데이터는 `timeline_data_assembler.py`의 lookback_days=7 출력을 재사용한다.

---

## 12. TDD 전략

### 12.1 테스트 파일 구조 (v2.1 — CR-6 수정)

```
tests/unit/
├── test_theme_discovery_engine.py       # A1 (escalation 포함)
├── test_timeline_data_assembler.py      # A2
├── test_timeline_skeleton_filler.py     # C1 (독립 유지 — validator와 대상이 다름)
├── test_validate_timeline_map.py        # D1
└── test_timeline_map_generator.py       # 기존 (유지, regression guard)
```

### 12.2 TDD 실행 원칙

```
1. Red: 테스트 먼저 작성 → 실패 확인
2. Green: 최소 구현으로 테스트 통과
3. Refactor: 코드 정리 (테스트 통과 유지)
4. 모든 Python 모듈은 pytest로 자동 실행
5. 각 모듈 구현 완료 시 전체 테스트 스위트 실행
6. 기존 test_timeline_map_generator.py는 regression guard로 유지
```

### 12.3 TDD 검증 총괄표 (v2.2 — CR-v4 Python 원천봉쇄 테스트 추가)

| 모듈 | 테스트 수 | 핵심 검증 |
|------|----------|----------|
| theme_discovery_engine.py | 11 | whole-word 매칭, exclusion, 클러스터 발견, escalation 기울기, compound |
| timeline_data_assembler.py | 14 | 조립 완전성, 시그널 원문, **PB-1~PB-6 사전 렌더링 정확성** |
| timeline_skeleton_filler.py | 5 | 플레이스홀더 교체, LLM용 보존, ASCII 테이블 정렬 |
| validate_timeline_map.py | 9 | 13개 검증 규칙 |
| **합계** | **39** | (기존 regression guard 12개 별도) |

---

## 13. 파일 생성/변경 총괄 (v2.0 — 최소 변경 원칙)

### 13.1 신규 생성 파일 (13개, v1.0 대비 -5)

| # | 파일 | 유형 | v1.0 대비 |
|---|------|------|----------|
| 1 | `env-scanning/core/theme_discovery_engine.py` | Python 모듈 | 유지 (에스컬레이션 통합) |
| 2 | `env-scanning/core/timeline_data_assembler.py` | Python 모듈 | 유지 (소비자 역할 명확화) |
| 3 | `env-scanning/core/timeline_skeleton_filler.py` | Python 모듈 | 유지 |
| 4 | `env-scanning/scripts/validate_timeline_map.py` | 검증 스크립트 | 유지 |
| 5 | `env-scanning/config/timeline-themes.yaml` | SOT 설정 | 유지 |
| 6 | `.claude/agents/timeline-map-orchestrator.md` | 오케스트레이터 | 유지 |
| 7 | `.claude/agents/workers/timeline-narrative-analyst.md` | LLM 워커 | B1+B2+B3 통합 |
| 8 | `.claude/agents/workers/timeline-map-composer.md` | LLM 워커 | 유지 |
| 9 | `.claude/skills/env-scanner/references/timeline-map-skeleton-en.md` | 스켈레톤 | 유지 |
| 10 | `.claude/skills/env-scanner/references/timeline-map-skeleton.md` | 스켈레톤 (KO) | 유지 |
| 11 | `tests/unit/test_theme_discovery_engine.py` | 테스트 | 유지 |
| 12 | `tests/unit/test_timeline_data_assembler.py` | 테스트 | 유지 |
| 13 | `tests/unit/test_validate_timeline_map.py` | 테스트 | 신규 추가 |

**삭제된 파일 (v1.0에서 제거)**:
- ~~`cross_wf_correlator.py`~~ (CF-1: 기존 모듈 중복)
- ~~`escalation_detector.py`~~ (theme_discovery_engine에 통합)
- ~~`timeline-theme-narrator.md`~~ (CF-4: 통합 에이전트)
- ~~`timeline-cross-wf-analyst.md`~~ (CF-4: 통합 에이전트)
- ~~`timeline-escalation-assessor.md`~~ (CF-4: 통합 에이전트)
- ~~`test_cross_wf_correlator.py`~~ (대상 모듈 삭제)
- ~~`test_escalation_detector.py`~~ (theme_discovery 테스트에 통합)

**주의 (CR-6)**: `test_timeline_skeleton_filler.py`는 삭제하지 않는다.
skeleton_filler(플레이스홀더 교체)와 validator(섹션 존재 검증)는 완전히 다른 대상이므로
독립 테스트 파일이 필요하다.

### 13.2 변경 파일 (7개, v1.0 대비 -1)

| # | 파일 | 변경 내용 | 변경 규모 |
|---|------|----------|----------|
| 1 | `workflow-registry.yaml` | timeline_map 섹션에 키 추가 (기존 키 유지) | 약 15줄 추가 |
| 2 | `validate_registry.py` | SOT-036 내부에 theme_config 검증 추가 | 약 30줄 추가 |
| 3 | `master-orchestrator.md` | Step 5.1.4 호출 방식만 변경 | 약 20줄 변경 |
| 4 | `integrated-report-skeleton-en.md` | §7 타임라인 요약 섹션 추가 | 약 5줄 추가 |
| 5 | `integrated-report-skeleton.md` | §7 타임라인 요약 섹션 추가 (KO) | 약 5줄 추가 |
| 6 | `report_statistics_engine.py` | `build_placeholder_map()`에 timeline-summary 파일 읽기 로직 + graceful fallback(파일 없으면 기본값) + INT_TIMELINE_SUMMARY 플레이스홀더 매핑 추가 (CR-7 정확화) | 약 20줄 추가 |
| 7 | `CHANGELOG.md` | 변경 이력 기록 | 약 10줄 추가 |

**변경하지 않는 파일** (v1.0에서 제거):
- ~~`report_metadata_injector.py`~~ (CF-5: 기존 주입 경로 유지, 변경 불필요)
- ~~`AGENTS.md`~~ (타임라인 맵은 기존 아키텍처에 추가되는 보강 요소 — AGENTS.md의 §2 Immutable Rules를 변경할 필요 없음)

### 13.3 유지 파일 (변경 없음, 2개)

| # | 파일 | 상태 | 이유 |
|---|------|------|------|
| 1 | `timeline_map_generator.py` | **유지** | Phase D fallback + 기존 SOT 호환 |
| 2 | `test_timeline_map_generator.py` | **유지** | regression guard |

### 13.4 변경하지 않는 기존 모듈 (변경 금지, 명시)

| 파일 | 이유 |
|------|------|
| `signal_evolution_tracker.py` | 상류 생산자 — 소비만 함 (CF-1) |
| `report_metadata_injector.py` | 기존 주입 경로 유지 (CF-5) |
| 각 WF orchestrator (4개) | WF 독립성 원칙 |
| `report-merger.md` | 통합 보고서 생성과 무관 |
| `quality-reviewer.md` | 재사용만 (추가 변경 불필요) |

---

## 14. 구현 순서 (v2.0 — 의존성 순서 + TDD-first)

> TDD-first: 매 단계에서 테스트 먼저, 구현 후 검증.
> 의존성 방향: SOT → Python 모듈 → 스켈레톤 → 에이전트 → 통합 연결 → E2E

```
Phase 0: SOT 기반 준비 (의존성 최하류 — 모든 것의 기반)
  0.1 timeline-themes.yaml 생성
  0.2 workflow-registry.yaml에 timeline_map 키 추가 (기존 키 보존)
  0.3 validate_registry.py SOT-036 내 theme_config 검증 추가
  0.4 validate_registry.py 실행 → 전체 PASS 확인
      → 기존 SOT-001 ~ SOT-041 전부 PASS 유지 확인 (regression)

Phase 1: Python 모듈 (TDD, 의존성 순서)
  1.1 test_theme_discovery_engine.py 작성 (Red)
      → theme_discovery_engine.py 구현 (Green)
      → 11개 테스트 ALL PASS 확인
  1.2 test_timeline_data_assembler.py 작성 (Red)
      → timeline_data_assembler.py 구현 (Green)
      → 6개 테스트 ALL PASS 확인
  1.3 전체 기존 테스트 실행 → 기존 테스트 regression 없음 확인
      (특히 test_timeline_map_generator.py, test_signal_evolution_tracker.py)

Phase 2: 스켈레톤 + 검증 스크립트
  2.1 timeline-map-skeleton-en.md 생성
  2.2 timeline-map-skeleton.md 생성 (KO)
  2.3 timeline_skeleton_filler.py 구현
  2.4 test_validate_timeline_map.py 작성 (Red)
      → validate_timeline_map.py 구현 (Green)
      → 9개 테스트 ALL PASS 확인
  2.5 전체 테스트 스위트 실행 → ALL PASS

Phase 3: 에이전트 정의 (코드 의존성 없음 — 병렬 가능)
  3.1 timeline-map-orchestrator.md
  3.2 timeline-narrative-analyst.md
  3.3 timeline-map-composer.md

Phase 4: 통합 연결 (기존 파일 최소 변경)
  4.1 master-orchestrator.md Step 5.1.4 변경
      → 기존 Python 호출 블록을 IF/ELSE로 감싸서 서브에이전트 호출 추가
      → ELSE 경로에 기존 호출 보존 (fallback)
  4.2 integrated-report-skeleton-en.md에 §7 추가
  4.3 integrated-report-skeleton.md에 §7 추가 (KO)
  4.4 report_statistics_engine.py에 INT_TIMELINE_SUMMARY 플레이스홀더 추가
      → 기존 build_placeholder_map() 함수 내 integrated 분기에 추가
      → timeline-summary-{date}.txt 파일이 없으면 기본값 반환 (graceful)
  4.5 CHANGELOG.md 업데이트

Phase 5: End-to-End 검증
  5.1 실제 데이터(2026-03-06)로 Phase A 실행 → JSON 출력 구조 검증
  5.2 Phase B 에이전트 단독 테스트 (data-package 수동 투입)
  5.3 Phase C 조립 + Phase D 품질 검증
  5.4 master-orchestrator를 통한 전체 파이프라인 E2E 테스트

Phase 6: Pre-Completion Checklist (Modification Cascade Rule)
  □ 새 SOT 필드(timeline_map.*) → validate_registry.py 대응 체크 존재?
  □ 새 필수 보고서 섹션(§7) → integrated 스켈레톤에 서브섹션 + 플레이스홀더?
  □ SOT 값 기반 IF 분기(TIMELINE_MAP_ENABLED) → ELSE/default 절?
  □ validate_registry.py 실행 → 전체 PASS? (SOT-001 ~ SOT-041 + SOT-036 확장)
  □ 유닛 테스트 실행 → 전체 PASS? (기존 + 신규 모두)
  □ 기존 timeline_map_generator.py 테스트 → regression 없음?
  □ 기존 test_signal_evolution_tracker.py → regression 없음?
  □ report_statistics_engine.py 기존 테스트 → regression 없음?
```

---

## 15. Side Effect 분석 (v2.0 — 결합도/파급 효과 정밀 분석)

### 15.1 기존 시스템 영향 — 변경 파급 경로

```
변경 1: workflow-registry.yaml (SOT 확장)
  │
  ├── 직접 영향: validate_registry.py SOT-036 (동시 업데이트)
  ├── 간접 영향: timeline_map_generator.py load_timeline_config()
  │     → 기존 키를 유지하므로 깨지지 않음 (새 키는 무시됨)
  └── 파급 없음: 다른 모든 모듈 (timeline_map 섹션을 읽지 않음)

변경 2: master-orchestrator.md Step 5.1.4
  │
  ├── 직접 영향: 없음 (신규 서브 오케스트레이터만 호출)
  ├── ELSE 경로: 기존 Python 호출 보존 → fallback 안전망
  └── 파급 없음: Step 5.1.5 이후는 변경 없음 (Step 5.1.4 출력물 경로 동일)

변경 3: report_statistics_engine.py
  │
  ├── 직접 영향: build_placeholder_map() 함수의 integrated 분기
  │     → INT_TIMELINE_SUMMARY 플레이스홀더 1개 추가
  │     → timeline-summary 파일 없으면 기본값 반환 (빈 문자열)
  ├── 기존 테스트: test_report_statistics_engine.py에 1개 테스트 추가
  └── 파급 없음: 기존 플레이스홀더(EVOLUTION_*, INT_EVOLUTION_CROSS_TABLE 등) 변경 없음

변경 4: integrated-report-skeleton-en.md / .md
  │
  ├── 직접 영향: report_metadata_injector.py가 {{INT_TIMELINE_SUMMARY}} 주입
  │     → report_metadata_injector.py는 변경 불필요!
  │     → 이유: report_statistics_engine.py의 출력에 INT_TIMELINE_SUMMARY가 포함되면
  │       report_metadata_injector.py는 자동으로 해당 플레이스홀더를 교체함
  │       (기존 패턴: statistics → injector → skeleton, 이미 구현됨)
  └── 파급 없음: 기존 섹션(§1~§6) 변경 없음
```

### 15.2 "변경하지 않아도 되는" 이유 (CF-5 수정의 핵심)

**report_metadata_injector.py를 변경하지 않는 이유**:

기존 코드 흐름:
```
report_statistics_engine.py
  → compute_statistics() → build_placeholder_map()
  → {"INT_TIMELINE_SUMMARY": "..."} 포함된 stats JSON 출력

report_metadata_injector.py
  → inject_temporal_metadata()
  → statistics JSON에서 모든 placeholder key를 읽어서 스켈레톤에 주입
  → INT_TIMELINE_SUMMARY도 자동으로 처리됨 (범용 로직)
```

`report_metadata_injector.py`의 `_inject_statistics()` 함수는
statistics JSON의 `placeholders` dict를 **범용적으로** 순회하며 스켈레톤의
`{{KEY}}`를 교체한다. 새 키를 추가해도 injector 코드 변경이 불필요하다.
이것이 기존 설계의 우수한 점이며, 우리는 이 패턴을 **그대로 활용**한다.

### 15.3 실패 시나리오 및 복원

| 실패 지점 | 복원 방안 | master-orchestrator 영향 |
|-----------|----------|------------------------|
| Phase A Python 모듈 실패 | 재시도 (max 2) → 실패 시 기존 generator.py fallback | 없음 |
| Phase B LLM 에이전트 실패 | 재시도 (max 2) → 실패 시 기존 generator.py fallback | 없음 |
| Phase C 조립 실패 | C2 재시도 → 실패 시 기존 generator.py fallback | 없음 |
| Phase D 검증 실패 | Progressive Retry → 2회 실패 시 기존 generator.py fallback | 없음 |
| 전체 파이프라인 실패 | 기존 timeline_map_generator.py 실행 | 없음 |
| timeline-summary.txt 미생성 | report_statistics_engine이 빈 값 반환 | 통합 보고서에 §7 비어있음 (정상) |

**핵심 보장**: 어떤 상황에서도 master-orchestrator의 전체 워크플로우를 블로킹하지 않는다.
타임라인 맵은 통합 보고서의 **보강 요소**(supplementary output)이지, 필수 게이트가 아니다.

### 15.4 v1.0 대비 v2.0 변경 요약

| 항목 | v1.0 | v2.0 | 감소율 |
|------|------|------|--------|
| 신규 Python 모듈 | 5개 | 3개 | -40% |
| 신규 LLM 워커 | 4개 | 2개 | -50% |
| 신규 파일 총계 | 18개 | 13개 | -28% |
| 변경 기존 파일 | 8개 | 7개 | -13% |
| TDD 테스트 | 44개 | 28개 | -36% |
| 기능 중복 모듈 | 2개 (CF-1, CF-2) | 0개 | -100% |
| 외부 의존성 | scikit-learn | 없음 | -100% |
| 기존 모듈 변경 금지 위반 | 1개 (CF-5) | 0개 | -100% |

---

## 16. TDD 검증 총괄표 (v2.0)

| 모듈 | 테스트 수 | 핵심 검증 |
|------|----------|----------|
| theme_discovery_engine.py | 11 | whole-word 매칭, exclusion, 에스컬레이션, 클러스터 발견, cross-WF 소비 |
| timeline_data_assembler.py | 6 | 조립 완전성, 시그널 원문 포함, 상류 출력 누락 graceful |
| validate_timeline_map.py | 9 | 13개 검증 규칙 |
| report_statistics_engine.py 추가분 | 2 | INT_TIMELINE_SUMMARY 플레이스홀더, 파일 없을 때 기본값 |
| **합계** | **28** | |

모든 기존 테스트도 regression guard로 실행:
- test_timeline_map_generator.py (기존)
- test_signal_evolution_tracker.py (기존)
- test_report_statistics_engine.py (기존)
