# Worker Agent Manifest (v3.5.0, 2026-03-24)

Worker agent의 활성/레거시 상태를 기록한다.
삭제하지 않는다 — 다음 스캔 실행 로그로 실사용 여부를 확인한 뒤 결정.

## ACTIVE — 오케스트레이터에서 명시적 참조 확인

| Agent | Invoking Orchestrator | Role |
|-------|----------------------|------|
| archive-loader.md | env-scan-orchestrator (Step 1.1) | Historical signals DB loading |
| archive-notifier.md | env-scan-orchestrator (Phase 3) | Archive + notification |
| database-updater.md | env-scan-orchestrator (Phase 3) | Signals DB atomic update |
| deduplication-filter.md | env-scan-orchestrator (Step 1.3) | 4-stage dedup cascade |
| discovery-alpha.md | exploration-orchestrator (Stage B) | Gap-directed source discovery |
| discovery-beta.md | exploration-orchestrator (Stage B) | Random serendipitous discovery |
| discovery-evaluator.md | exploration-orchestrator (Stage C) | Independent quality evaluation |
| multi-source-scanner.md | env-scan-orchestrator (Step 1.2) | Multi-source scanning marathon |
| news-translation-agent.md | multiglobal-news-scan-orchestrator | WF4 multilingual normalization |
| phase2-analyst.md | All 4 WF orchestrators (Step 2.1+2.2) | Unified classification + impact |
| quality-reviewer.md | All 4 WF orchestrators (L3 defense) | 3-pass semantic review |
| realtime-delphi-facilitator.md | env-scan-orchestrator (Step 1.5) | Expert panel (conditional) |
| report-merger.md | master-orchestrator (Step 5) | Integration report merge |
| source-explorer.md | exploration-orchestrator (fallback) | Single-agent exploration |
| timeline-map-composer.md | timeline-map-orchestrator (Step C2) | Timeline map assembly |
| timeline-narrative-analyst.md | timeline-map-orchestrator (Step B1+B3) | Narrative draft + refinement |
| timeline-quality-challenger.md | timeline-map-orchestrator (Step B2) | Adversarial review |
| translation-agent.md | All WF orchestrators + master | EN→KO translation |

## REFERENCE — 템플릿/참조 파일

| Agent | Purpose |
|-------|---------|
| classification-prompt-template.md | STEEPs classification prompt template |

## UNVERIFIED — 런타임 동적 호출 가능성, 삭제 전 실행 로그 확인 필요

| Agent | Possible Invoker | Notes |
|-------|------------------|-------|
| arxiv-agent.md | arxiv-scan-orchestrator (WF2) | arXiv source scanning specialist |
| blog-agent.md | env-scan-orchestrator (WF1) | Blog/tech source scanning |
| impact-analyzer.md | (superseded by phase2-analyst?) | Cross-impact analysis — verify |
| naver-alert-dispatcher.md | naver-scan-orchestrator (WF3) | Tipping Point alert dispatch |
| naver-news-crawler.md | naver-scan-orchestrator (WF3) | Naver News crawling |
| naver-pattern-detector.md | naver-scan-orchestrator (WF3) | FSSF pattern detection |
| naver-signal-detector.md | naver-scan-orchestrator (WF3) | Weak signal detection |
| news-alert-dispatcher.md | multiglobal-news-scan-orchestrator (WF4) | News alert dispatch |
| news-direct-crawler.md | multiglobal-news-scan-orchestrator (WF4) | Direct news site crawling |
| news-pattern-detector.md | multiglobal-news-scan-orchestrator (WF4) | News pattern detection |
| news-signal-detector.md | multiglobal-news-scan-orchestrator (WF4) | News signal detection |
| patent-agent.md | env-scan-orchestrator (WF1) | Patent source scanning |
| policy-agent.md | env-scan-orchestrator (WF1) | Policy/regulation scanning |
| priority-ranker.md | (superseded by phase2-analyst) | Legacy priority ranking |
| report-generator.md | (superseded by skeleton-fill) | Legacy report generation |
| scenario-builder.md | (Step 2.4 optional) | Scenario generation |
| self-improvement-analyzer.md | (Step 3.5 SIE) | Self-improvement analysis |
| signal-classifier.md | (superseded by phase2-analyst) | Legacy classification |
