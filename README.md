# 4중 환경스캐닝 시스템 (Quadruple Environmental Scanning System)

AI 기반 자동화 환경스캐닝 시스템. STEEPs 전 영역에서 미래 변화의 약신호를 탐지합니다. **4개 독립 워크플로우**(일반, arXiv, 네이버 뉴스, 글로벌 뉴스)가 통합 전략 보고서로 합쳐집니다.

## 절대 목표

> **전 세계(한국, 아시아, 유럽, 아프리카, 아메리카)에서 미래 트렌드, 중기 변화, 거시 전환, 패러다임 변혁, 임계적 전환, 싱귤래리티, 돌발 사건, 예상치 못한 미래의 조기 신호를 "가능한 한 빨리" 포착한다.**

**운영 가이드**: 일일 운영 절차, 커맨드 사용법, 설정 변경법은 [USER-MANUAL.md](USER-MANUAL.md)를 참조하세요.

## 가장 쉬운 사용법

```bash
# Claude Code CLI에서 한 줄이면 됩니다
/env-scan:run
```

이 한 줄로 전체 스캔(WF1 + WF2 + WF3 + WF4 + 통합)이 시작됩니다. 9개 체크포인트에서 사용자 승인을 요청하며, 완료 시 4개 워크플로우 보고서(EN/KO) + 통합보고서(EN/KO) + 인터랙티브 대시보드(HTML)가 생성됩니다.

## 개요

이 시스템은 전 세계 정보 소스를 4개 독립 워크플로우로 매일 자동 스캔하고, 중복을 필터링하고, 시그널을 분류·분석하여, 의사결정자를 위한 전략 보고서를 생성합니다.

### 4개 독립 워크플로우

| 워크플로우 | 범위 | 소스 |
|-----------|------|------|
| **WF1** 일반 | 특허, 정책, 기술 블로그 | 다중 소스 (arXiv 제외) |
| **WF2** arXiv | 학술 논문 | arXiv 전용 |
| **WF3** 네이버 뉴스 | 한국 뉴스 | 네이버 뉴스 전용 |
| **WF4** 글로벌 뉴스 | 전 세계 다국어 뉴스 | 43개 뉴스 사이트, 11개 언어 |

각 워크플로우는 완전히 독립적입니다 — 다른 워크플로우의 데이터를 볼 수도, 접근할 수도 없습니다. 통합은 최종 보고서 단계에서만 이루어집니다.

### 주요 기능

- **4중 워크플로우 아키텍처**: 4개 독립 스캐닝 파이프라인 + 통합
- **다중 소스 스캐닝**: 학술 논문, 특허, 정책 문서, 기술 블로그, 한국 뉴스, 글로벌 다국어 뉴스
- **4단계 중복 제거**: URL → 문자열 → 시맨틱 → 엔티티 매칭 (정확도 >95%)
- **STEEPs 분류**: 6개 카테고리 (사회, 기술, 경제, 환경, 정치, 정신)
- **FSSF 8유형 분류** (WF3/WF4): 약신호, 와일드카드, 단절, 동인, 부상 이슈, 전조 사건, 추세, 메가트렌드
- **Three Horizons** (WF3/WF4): H1 (0-2년), H2 (2-7년), H3 (7년+)
- **티핑 포인트 탐지** (WF3/WF4): 임계 감속(Critical Slowing Down) 및 깜빡임(Flickering) 패턴 분석
- **Python 원천봉쇄**: "계산은 Python이, 판단은 LLM이" — 점수 계산, 중복 제거, 시간 필터링, 파이프라인 게이트 모두 Python 강제
- **할루시네이션 방지**: Pipeline Gate 2 (`validate_phase2_output.py`, PG2-001~009), 번역 용어 충실도 (TERM-001~003), 핵심 요약 교차 검증 (QC-014)
- **통합 Phase 2 에이전트**: `phase2-analyst.md`가 Step 2.1+2.2 처리 (LLM); Step 2.3은 `priority_score_calculator.py` (Python)
- **타임라인 맵 + 챌린지-리스폰스**: 적대적 피어 리뷰(challenger → 서사 개선), Python 서사 게이트 (NG-001~005), L2a+L2b+L3 품질 동등성
- **4계층 품질 방어**: L1 (스켈레톤-필) → L2a (구조 검증 15-20개) → L2b (품질 검증 14개) → L3 (LLM 시맨틱 리뷰) → L4 (골든 레퍼런스)
- **인터랙티브 대시보드**: Python 원천봉쇄 데이터 파이프라인 (LLM 의존 없음) → Chart.js 시각화 → CDN 오프라인 폴백 → 브라우저 자동 열기
- **이중언어 대시보드 (EN/KO)**: 모든 시그널 제목이 영어+한국어 병기. 내러티브 섹션에 EN/KO 토글 탭. D3.js 인터랙티브 시그널 맵 시각화
- **교차 WF 강화 탐지**: SOT 바인딩 자카드 유사도 (thresholds.yaml), 2글자 도메인 용어 보존 (AI, EU, EV)
- **품질 최우선 컨텍스트 메모리**: Phase 2에서 abstract 포함으로 더 깊은 분류, Phase 3에서 풍부한 보고서를 위한 강화된 컨텍스트, 14일 아카이브 윈도우 (SOT 바인딩)
- **영향 분석**: 확률적 교차 영향 매트릭스 + 베이지안 네트워크
- **전문가 검증**: 대량 시그널용 실시간 AI 델파이 (선택)
- **시나리오 생성**: QUEST 기반 가능한 미래 시나리오 (선택)
- **이중언어 출력**: 영문 우선 워크플로우 + 자동 한국어 번역
  - 모든 산출물이 EN/KO 양쪽으로 생성
  - 한국어 우선 사용자 인터페이스
  - STEEPs 용어 100% 보존
  - 고품질 역번역 검증
- **WF4 다국어 파이프라인**: 11개 언어 소스 스캐닝 + 영문 우선 번역 파이프라인

## 아키텍처

### 4중 오케스트레이터-에이전트 패턴

```
마스터 오케스트레이터
├── WF1: env-scan-orchestrator (일반)
│   ├── Phase 1: Research (워커 4개)
│   ├── Phase 2: Planning (워커 4개)
│   └── Phase 3: Implementation (워커 3개)
│
├── WF2: arxiv-scan-orchestrator (arXiv)
│   ├── Phase 1: Research (워커 4개)
│   ├── Phase 2: Planning (워커 4개)
│   └── Phase 3: Implementation (워커 3개)
│
├── WF3: naver-scan-orchestrator (네이버 뉴스)
│   ├── Phase 1: Research (워커 4개)
│   ├── Phase 2: Planning (워커 4개 + FSSF)
│   └── Phase 3: Implementation (워커 3개)
│
├── WF4: multiglobal-news-scan-orchestrator (글로벌 뉴스)
│   ├── Phase 1: Research (워커 4개 + 다국어 번역)
│   ├── Phase 2: Planning (워커 4개 + FSSF)
│   └── Phase 3: Implementation (워커 3개)
│
├── 타임라인 맵: timeline-map-orchestrator
│   ├── Phase A: 데이터 기반 (Python: 테마 발견 + 데이터 조립)
│   ├── Phase B: 서사 분석 + 챌린지-리스폰스
│   │   ├── B1: @timeline-narrative-analyst (초안)
│   │   ├── B2: @timeline-quality-challenger (적대적 리뷰)
│   │   ├── B3: @timeline-narrative-analyst (개선)
│   │   └── B4: narrative_gate.py (Python 검증)
│   ├── Phase C: 조립 (스켈레톤 채움 + 컴포저)
│   └── Phase D: 품질 방어 (L2a + L2b + L3)
│
└── 통합: report-merger
    └── 에이전트 팀 (5명: wf1-analyst, wf2-analyst, wf3-analyst, wf4-analyst, synthesizer)
```

전체 워크플로우 공유 워커: archive-loader, multi-source-scanner, deduplication-filter, **phase2-analyst** (통합 Step 2.1+2.2), report-generator, database-updater, archive-notifier, quality-reviewer, self-improvement-analyzer 등 (총 42개 에이전트 스펙). Step 2.3 우선순위 랭킹은 `priority_score_calculator.py` (Python 원천봉쇄). 타임라인 맵은 챌린지-리스폰스 패턴: `timeline-narrative-analyst` + `timeline-quality-challenger` + `timeline-map-composer`.

### 휴먼-인-더-루프 체크포인트 (총 9개)

워크플로우별 (x4):
1. **Phase 2.5** (필수): 분석 결과 검토 및 우선순위 조정
2. **Phase 3.4** (필수): 최종 보고서 승인

통합 후 (x1):
3. **통합 보고서 승인** (필수): 합쳐진 4중 보고서 승인

## 빠른 시작

### 1. 설치

```bash
# 저장소 클론
cd /path/to/EnvironmentScan-system-main

# 의존성 설치
pip install -r requirements.txt

# API 키 설정
export SERPAPI_KEY="your_key_here"
```

### 2. 설정

`env-scanning/config/`의 설정 파일 편집:

- `domains.yaml` - STEEPs 키워드 조정
- `sources.yaml` - 소스 활성화/비활성화, API 키 추가
- `thresholds.yaml` - 필터링 임계값 조정
- `ml-models.yaml` - AI 모델 설정

### 3. 첫 스캔 실행

```bash
# Claude Code CLI에서 — 전체 4중 스캔 (WF1 + WF2 + WF3 + WF4 + 통합)
/env-scan:run
```

워크플로우가 자동으로:
1. WF1 (일반), WF2 (arXiv), WF3 (네이버), WF4 (글로벌 뉴스)를 순차 실행
2. 각 워크플로우: 소스 스캔 → 중복 필터링 → 분류 → 분석 → 검토 일시정지 → 보고서 생성 → 승인 대기
3. 승인된 4개 보고서를 통합 보고서로 병합
4. 최종 통합 보고서 승인 대기

### 4. 검토 및 승인

```bash
# 진행 상황 확인
/env-scan:status

# Phase 2.5 - 분석 검토
/env-scan:review-analysis

# Phase 3.4 - 보고서 승인
/env-scan:approve
```

## 디렉토리 구조

```
EnvironmentScan-system-main/
├── .claude/
│   ├── agents/
│   │   ├── master-orchestrator.md
│   │   ├── env-scan-orchestrator.md              (WF1)
│   │   ├── arxiv-scan-orchestrator.md             (WF2)
│   │   ├── naver-scan-orchestrator.md             (WF3)
│   │   ├── multiglobal-news-scan-orchestrator.md  (WF4)
│   │   └── workers/                               (25+ 공유 워커)
│   ├── skills/
│   │   └── env-scanner/
│   │       ├── SKILL.md
│   │       └── references/                        (스켈레톤 10개)
│   └── commands/
│       └── env-scan/
│           ├── run.md
│           ├── status.md
│           └── ... (커맨드 7개 추가)
│
├── env-scanning/
│   ├── config/
│   │   ├── workflow-registry.yaml   ← SOT (단일 진실 소스)
│   │   ├── core-invariants.yaml
│   │   ├── domains.yaml
│   │   ├── sources.yaml             (WF1)
│   │   ├── sources-arxiv.yaml       (WF2)
│   │   ├── sources-naver.yaml       (WF3)
│   │   ├── sources-multiglobal-news.yaml  (WF4)
│   │   ├── thresholds.yaml
│   │   ├── translation-terms.yaml
│   │   └── ... (설정 파일 총 12개)
│   ├── core/                        (Python 모듈 36개, priority_score_calculator.py 포함)
│   ├── scripts/                     (검증 스크립트: validate_registry, validate_report, validate_report_quality, validate_phase2_output, validate_timeline_map, validate_timeline_map_quality, narrative_gate, validate_completion, validate_state_consistency)
│   ├── wf1-general/                 ← WF1 데이터 디렉토리
│   │   ├── raw/ structured/ filtered/ analysis/ signals/ reports/
│   │   └── exploration/             (v2.5.0 소스 탐색)
│   ├── wf2-arxiv/                   ← WF2 데이터 디렉토리
│   │   └── raw/ structured/ filtered/ analysis/ signals/ reports/
│   ├── wf3-naver/                   ← WF3 데이터 디렉토리
│   │   └── raw/ structured/ filtered/ analysis/ signals/ reports/
│   ├── wf4-multiglobal-news/        ← WF4 데이터 디렉토리
│   │   └── raw/ structured/ filtered/ analysis/ signals/ reports/
│   └── integrated/                  ← 통합 산출물
│       ├── reports/daily/
│       ├── reports/archive/{year}/{month}/
│       └── weekly/
│
├── tests/                           (테스트 파일 28개, ~995개 테스트)
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── AGENTS.md                        ← 크로스플랫폼 방법론
├── CLAUDE.md                        ← Claude Code 지시문
├── GEMINI.md                        ← Gemini CLI 지시문
└── README.md
```

## 사용 가능한 커맨드

| 커맨드 | 설명 |
|--------|------|
| `/env-scan:run` | 전체 4중 스캔 실행 (WF1 + WF2 + WF3 + WF4 + 통합) |
| `/env-scan:run-arxiv` | WF2 단독 실행 (arXiv만) |
| `/env-scan:run-naver` | WF3 단독 실행 (네이버 뉴스만) |
| `/env-scan:run-multiglobal-news` | WF4 단독 실행 (글로벌 뉴스만) |
| `/env-scan:run-weekly` | 주간 메타 분석 (신규 스캔 없음) |
| `/env-scan:status` | 현재 워크플로우 진행 상황 확인 |
| `/env-scan:review-filter` | 중복 필터링 결과 검토 |
| `/env-scan:review-analysis` | 분석 결과 검토 및 우선순위 조정 |
| `/env-scan:approve` | 최종 보고서 승인 |
| `/env-scan:revision` | 피드백과 함께 보고서 수정 요청 |

## STEEPs 프레임워크

6개 카테고리 분류 체계 (불변):

- **S** - 사회 (인구, 교육, 노동)
- **T** - 기술 (혁신, 디지털 전환)
- **E** - 경제 (시장, 금융, 무역)
- **E** - 환경 (기후, 지속가능성)
- **P** - 정치 (정책, 법률, 규제, 제도)
- **s** - 정신 (윤리, 심리, 가치, 의미)

상세 정의: `.claude/skills/env-scanner/references/steep-framework.md` 참조.

## 성능 목표

- **중복 탐지 정확도**: > 95%
- **처리 시간 단축**: 기준 대비 30%
- **시그널 탐지 속도**: 수동 대비 2배
- **전문가 피드백 소요**: < 3일 (델파이 활성화 시)

## 테스트

```bash
# 단위 테스트
pytest tests/unit/

# 통합 테스트
pytest tests/integration/

# 엔드투엔드 테스트
pytest tests/e2e/
```

## 문제 해결

### 문제: 필터율 낮음 (< 30%)

소스가 오래된 콘텐츠를 반환하는지 확인. `config/sources.yaml`의 날짜 필터 검증.

### 문제: 데이터베이스 손상

스냅샷에서 복원 (각 워크플로우에 자체 데이터베이스 존재):

```bash
# WF1 예시:
cp env-scanning/wf1-general/signals/snapshots/database-{최근날짜}.json \
   env-scanning/wf1-general/signals/database.json
```

### 문제: 분류 오류

`config/domains.yaml`의 STEEPs 정의 검토. `config/ml-models.yaml`의 AI 모델 설정 확인.

## 기여

이 시스템은 Claude Code의 에이전트 아키텍처를 사용합니다. 수정 시:

1. **에이전트**: `.claude/agents/` 파일 편집
2. **커맨드**: `.claude/commands/env-scan/` 파일 편집
3. **설정**: `env-scanning/config/` YAML 파일 편집

모든 에이전트 지시문은 최적의 AI 성능을 위해 **영문**으로 작성됩니다. 이중언어 워크플로우가 자동으로 산출물을 한국어로 번역하며 기술 용어를 보존합니다.

## 이중언어 워크플로우

### 영문 우선, 한국어 항상

시스템은 최적의 AI 성능을 위해 **영문**으로 동작하고, 모든 산출물을 자동으로 **한국어**로 번역합니다:

```
에이전트 (EN) → 산출물 (EN) → 번역 에이전트 → 산출물 (KO)
```

**파일 명명 규칙**:
- 영문: `environmental-scan-2026-01-30.md`
- 한국어: `environmental-scan-2026-01-30-ko.md`

**번역 대상**:
- 보고서 (Markdown)
- 시그널 분류 (JSON)
- 분석 결과 (JSON)
- 로그 요약 (로그 파일)
- 품질 지표 (JSON)

**영문 유지 대상**:
- `database.json` (데이터 무결성)
- 설정 파일
- 에이전트 지시문
- 기술 필드명

**번역 품질**:
- 평균 신뢰도: >0.90
- STEEPs 용어 보존: 100%
- 역번역 검증: 활성화
- 처리 오버헤드: ~22% (워크플로우당 +40초)

## 버전

- **시스템 버전**: 3.6.0 (4중 워크플로우, 이중언어 EN-KR, Python 원천봉쇄, 할루시네이션 방지, 타임라인 맵 챌린지-리스폰스, 이중언어 대시보드 + 시그널 맵, 마스터 게이트 M4, 품질 최우선 컨텍스트 최적화)
- **워크플로우 버전**: 4중 환경스캐닝 v3.6.0
- **아키텍처**: 에이전트 스펙 43개, Python 모듈 42개 + 검증 스크립트 11개, 설정 파일 12개, 스켈레톤 14개, 테스트 파일 28개 (~1069개 테스트)
- **검증**: SOT 체크 68개 (SOT-001~065), 4계층 품질 방어 (L1→L4), QC 체크 14개 (L2b), PG2 체크 9개 (PG2-001~009, title_ko 포함), 타임라인 QC 체크 11개 (TQ-001~011), 서사 게이트 체크 5개 (NG-001~005), TERM 충실도 체크 3개, CG 완결성 체크 10개 (M4, CG-010 대시보드), 대시보드 체크 6개 (DB-001~006) — 총 145+
- **최종 업데이트**: 2026-03-29
- **v3.6.0 변경사항**: 대시보드 이중언어 표시 (EN/KO 시그널 제목, 내러티브 서브탭), D3.js 인터랙티브 시그널 맵 (STEEPs x Impact), PG2-009 title_ko 한국어 존재 검증 (전체 4개 WF, Python 강제), WF1 영향도 점수 정규화 (0-100 → 0-10), WF2 Pipeline Gate 2에 validate_phase2_output.py 강제

## 참고 문헌

학술적 기반:
- [WISDOM Framework](https://arxiv.org/html/2409.15340v1)
- [Real-Time AI Delphi](https://www.sciencedirect.com/science/article/pii/S0016328725001661)
- [Cross-Impact Analysis](https://onlinelibrary.wiley.com/doi/full/10.1002/ffo2.165)
- [Millennium Project Futures Research Methodology](https://www.millennium-project.org/publications/futures-research-methodology-version-3-0-2/)

## 라이선스

내부 사용 전용.

## 지원

문제 발생 시:
1. `env-scanning/logs/` 로그 확인
2. `logs/quality-metrics/` 품질 지표 검토
3. `logs/workflow-status.json` 오케스트레이터 상태 확인
