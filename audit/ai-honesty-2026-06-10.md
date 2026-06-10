# AI Honesty Audit - 2026-06-10

## Scope And Constraints
- Audit type: read-only honesty/trust audit (no implementation changes).
- Goal: verify that user-facing AI/algorithmic copy matches actual computation windows, data scope, confidence semantics, and staleness behavior.
- Areas reviewed: AI dashboard/reporting cards, forecasting cards, anomaly UI, NLP/suggestions/estimation surfaces, and backing services.

## Summary
- Total surfaces audited: 14
- Confirmed bugs: 5
- Suspicious/misaligned surfaces: 6
- Clean/acceptable surfaces: 3

### Confirmed Bugs (Top)
1. Overtime horizon mismatch (UI says 7/14/30-day horizon, backend always projects only to end of current week).
2. Anomaly cache key ignores period_days (7-day and 30-day requests can return same cached result on same date).
3. User Insights API contract does not match UI contract (panel can render blank instead of insights).
4. Project Health API contract does not match UI contract (card expects nested health object not returned by backend).
5. NLP date parsing ignores timezone argument and uses date.today() directly.

---

## Findings By Surface

## 1) AI Overtime Risk (Admin Reports)
- Surface: frontend/src/components/ai/OvertimeRiskPanel.tsx
- User-visible copy:
  - "This week", "Next 2 weeks", "This month" filters
  - "Projected" hours and risk level
- Evidence:
  - Filter labels: frontend/src/components/ai/OvertimeRiskPanel.tsx:132,133,134
  - Router forwards days_ahead: backend/app/ai/router.py:565
  - Service projects only to current week end: backend/app/ai/services/forecasting_service.py:524
  - Response period fixed to week_start-week_end: backend/app/ai/services/forecasting_service.py:568
- Issue:
  - days_ahead is accepted but not applied to projection horizon. The card wording implies multi-week/month forecasting that is not actually computed.
- Severity: High
- Suggested fix:
  - Use days_ahead to define projection end date (or relabel UI to explicit current-week projection only).

## 2) AI Anomaly Alerts (Dashboard/Admin)
- Surface: frontend/src/components/ai/AnomalyAlertPanel.tsx
- User-visible copy:
  - "No anomalies detected"
  - "All time tracking patterns appear normal"
- Evidence:
  - Positive copy: frontend/src/components/ai/AnomalyAlertPanel.tsx:323,326
  - Cache key date-only in service: backend/app/ai/services/anomaly_service.py:136
  - Cache helper key uses date + user/all only (no period_days): backend/app/ai/utils/cache_manager.py:99-106,119-126
- Issue:
  - Different period requests can resolve to same cached anomalies for that day; copy may overstate normality for the selected period.
- Severity: High
- Suggested fix:
  - Include period_days (and team scope where applicable) in anomaly cache keys, or bypass cache when period differs.

## 3) AI User Insights (Dashboard)
- Surface: frontend/src/components/ai/UserInsightsPanel.tsx
- User-visible copy:
  - "Your Insights", productivity score, patterns, achievements, recommendations.
- Evidence:
  - Panel expects object at data.insights and bails if no insights.metrics: frontend/src/components/ai/UserInsightsPanel.tsx:108,110
  - Backend returns flat payload with top-level metrics and list insights: backend/app/ai/services/reporting_service.py:522-524
- Issue:
  - Contract mismatch: UI expects nested rich insights object; backend returns a simpler structure. Panel can silently render nothing.
- Severity: Critical (functional + trust, since users see empty/missing AI section)
- Suggested fix:
  - Align backend schema to frontend expectations or adapt frontend mapper to backend shape.

## 4) AI Project Health (Latent UI Surface)
- Surface: frontend/src/components/ai/ProjectHealthCard.tsx
- User-visible copy:
  - "AI Project Health Analysis", status/score/factors/recommendations.
- Evidence:
  - UI expects data.health object: frontend/src/components/ai/ProjectHealthCard.tsx:136-137
  - Backend returns top-level health_score/health_status/metrics/insights: backend/app/ai/services/reporting_service.py:439-442
  - Frontend API type also expects nested health object: frontend/src/api/reportingServices.ts:102
- Issue:
  - Contract mismatch similar to User Insights. If surfaced, card will fail to render expected content.
- Severity: High
- Suggested fix:
  - Normalize response shape on backend or add adapter layer in reporting API client.

## 5) NLP Time Entry Parsing (Time Page)
- Surface: frontend/src/components/ai/ChatInterface.tsx + backend/app/ai/services/nlp_service.py
- User-visible copy:
  - Relative date parsing (today/yesterday/day names), confidence and clarification prompts.
- Evidence:
  - _parse_date accepts timezone but uses date.today directly: backend/app/ai/services/nlp_service.py:346,138-144,363
  - Default date fallback also uses date.today: backend/app/ai/services/nlp_service.py:245
- Issue:
  - Tenant/user timezone can be ignored for date interpretation near day boundaries; "yesterday" may resolve incorrectly.
- Severity: High
- Suggested fix:
  - Convert now to provided timezone before date keyword/day-of-week resolution.

## 6) Suggestions Scope (Time Entry Suggestions)
- Surface: backend/app/ai/services/suggestion_service.py + frontend/src/components/ai/SuggestionDropdown.tsx
- User-visible copy:
  - "AI Suggestions" and confidence/reason labels.
- Evidence:
  - Active projects loaded via non-archived global query only: backend/app/ai/services/suggestion_service.py:285
- Issue:
  - Candidate project set may include projects beyond user company/team scope if model layer does not enforce tenant filter. Trust risk: suggestions can feel irrelevant or "hallucinated" from user perspective.
- Severity: Medium
- Suggested fix:
  - Restrict active project query by requester's company/team visibility rules.

## 7) NLP Scope (Project/Task Candidate Set)
- Surface: backend/app/ai/services/nlp_service.py
- User-visible copy:
  - Clarification suggestions like "Did you mean one of these projects?"
- Evidence:
  - Fallback project/task queries are non-archived global queries: backend/app/ai/services/nlp_service.py:632,642,670,679
- Issue:
  - Same scope leakage risk as suggestions; parser can anchor to non-local project/task names.
- Severity: Medium
- Suggested fix:
  - Enforce tenant/team visibility filters for candidate lists before fuzzy match/AI assist.

## 8) Cash Flow Forecast (Admin Reports)
- Surface: frontend/src/components/ai/CashFlowChart.tsx + backend/app/ai/services/forecasting_service.py
- User-visible copy:
  - "AI Cash Flow Projection"
  - Payroll/non-payroll week sequencing
- Evidence:
  - Payroll week hardcoded as alternating index parity: backend/app/ai/services/forecasting_service.py:970
- Issue:
  - Assumes perfect bi-weekly alternation from current week, not actual payroll calendar anchors. Can mislead finance timing.
- Severity: Medium
- Suggested fix:
  - Anchor forecast to real payroll period definitions/status from payroll data model.

## 9) Forecasting Timezone Consistency
- Surface: backend/app/ai/services/forecasting_service.py
- User-visible copy:
  - Week/month period framing in overtime, budget, and related forecasts.
- Evidence:
  - Multiple date.today calls in forecasting calculations: backend/app/ai/services/forecasting_service.py:509,524,584,652,838,858,878
- Issue:
  - Forecast windows are server-date based, not tenant-local date based. Near timezone boundaries this can shift period labels and projections.
- Severity: Medium
- Suggested fix:
  - Standardize on tenant-local date helpers for period boundaries.

## 10) Task Estimation Confidence Semantics
- Surface: frontend/src/components/ai/TaskEstimationCard.tsx + backend/app/ai/services/task_estimation_service.py
- User-visible copy:
  - "XX% confidence"
- Evidence:
  - ML confidence hardcoded baseline: backend/app/ai/services/task_estimation_service.py:464
- Issue:
  - Confidence appears statistically grounded but is static/heuristic in ML path, risking over-interpretation.
- Severity: Medium
- Suggested fix:
  - Derive confidence from calibrated model error bands or nearest-neighbor support.

## 11) Team Analytics Insight Claims (API Surface)
- Surface: backend/app/ai/services/team_analytics_service.py + /api/ai/analytics/team
- User-visible copy:
  - "Workload is well-balanced", "Strong team collaboration", "Great momentum"
- Evidence:
  - Placeholder metric productive_hours_ratio=0.85: backend/app/ai/services/team_analytics_service.py:327
  - Assertive generated text templates: backend/app/ai/services/team_analytics_service.py:577,590,605
- Issue:
  - Strong qualitative claims are partly based on placeholder/heuristic metrics. Language certainty exceeds evidential rigor.
- Severity: Medium
- Suggested fix:
  - Remove placeholder-derived claims or downgrade language to "indicative" until metric is real.

## 12) Semantic Search Positioning (API Surface)
- Surface: backend/app/ai/services/semantic_search_service.py
- User-visible copy:
  - Service/doc positioning implies embeddings/semantic matching.
- Evidence:
  - Class doc claims AI embeddings: backend/app/ai/services/semantic_search_service.py:53
  - Ranking is lexical heuristic composition (Jaccard + bonuses): backend/app/ai/services/semantic_search_service.py:309-337
- Issue:
  - Capability framing can overstate actual method. User expectation mismatch risk for "semantic" quality.
- Severity: Medium
- Suggested fix:
  - Either implement embedding retrieval or reword claims to "hybrid lexical relevance".

## 13) Weekly Summary (Fixed This Session)
- Surface: backend/app/ai/services/reporting_service.py + frontend/src/components/ai/WeeklySummaryPanel.tsx
- Status:
  - Clean for core honesty target audited here.
- Evidence:
  - Same-period and now-anchored comparison context is present and label surfaced in UI.
- Severity: Clean

## 14) Burnout Risk Assessment
- Surface: backend/app/ai/services/ml_anomaly_service.py + frontend/src/components/ai/BurnoutRiskPanel.tsx
- Status:
  - Mostly clean on timezone handling compared to other surfaces.
- Evidence:
  - Company timezone conversion for day/weekend/late-hour factors is implemented in burnout flow.
- Severity: Clean (with normal heuristic-model caveats)

---

## Q1-Q9 Checklist Snapshot

- Q1 Apples-to-apples windows:
  - Pass: Weekly summary (post-fix).
  - Fail: Overtime horizon labeling vs actual projection window.

- Q2 Timezone correctness:
  - Pass: Burnout service local timezone conversion.
  - Fail: NLP date parsing and several forecasting paths using date.today().

- Q3 Filter consistency (scope/tenant/team):
  - Fail risk: suggestion and NLP candidate lists can be broader than requester scope.

- Q4 Small denominator handling:
  - Mixed: some confidence/range heuristics are hardcoded (task estimation) and can overstate certainty.

- Q5 Caching/staleness:
  - Fail: anomaly cache key omits period_days; stale cross-period responses possible.

- Q6 Cross-surface metric consistency:
  - Fail: reporting API shapes and UI expectations diverge (User Insights, Project Health).

- Q7 LLM prompt honesty:
  - Mixed: weekly summary prompt now includes same-period caution; other surfaces still have certainty-heavy copy over heuristic metrics.

- Q8 Scope correctness ("you/your"):
  - Mixed: user-facing cards mostly scoped, but backend candidate pools can violate perceived scope.

- Q9 Zero/empty handling:
  - Mixed: generally graceful empty states, but some "all normal" copy is too strong under stale cache risk.

---

## Prioritized Fix List

1. Fix Overtime horizon truthfulness:
- Implement days_ahead in projection logic or relabel UI immediately.

2. Fix anomaly cache key dimensions:
- Key by (date, period_days, user/team scope) to prevent cross-period reuse.

3. Resolve reporting contract mismatches:
- Align User Insights and Project Health backend response shape with frontend usage (or add explicit mapping layer).

4. Make NLP timezone-aware:
- Apply timezone to relative date parsing and default date assignment.

5. Enforce scope in NLP/Suggestions candidate pools:
- Filter projects/tasks by tenant/team visibility before matching/AI prompts.

6. Reduce overconfident language where heuristics are placeholders:
- Team analytics and task estimation confidence copy should be calibrated to model fidelity.

---

## Patterns To Watch

- Label-logic drift: UI labels evolve independently from backend math windows.
- Date.today() drift: server date used instead of tenant-local date.
- Cache key under-dimensioning: missing parameters in cache keys silently breaks honesty.
- Schema drift: backend and frontend evolve without shared contract tests.
- Certainty inflation: confidence and recommendation copy sounds stronger than method supports.

---

## Audit Notes
- No code changes were made as part of this audit.
- This report focuses on honesty/trust integrity, not full functional correctness or security review.