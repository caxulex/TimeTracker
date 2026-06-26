# AI Project Health Confidence Cap Proposal (2026-06-19)

Scope: proposal only. No service/schema/frontend code changes were made.

## 1) Current score, status, and insight assembly

The project-health response is assembled in `backend/app/ai/services/reporting_service.py` after the insufficient-data branch:

```python
# Generate health score (0-100)
health_score = self._calculate_health_score(metrics)

# Generate insights
insights = []
...
completion_measured = bool(metrics.get("completion_measured", metrics.get("total_tasks", 0) > 0))
if completion_measured and metrics.get("task_completion_rate", 0) < 0.3:
    insights.append(...)
...
if not insights:
    if completion_measured:
        insights.append(... "Stable Health Signals" ...)
    else:
        insights.append(... "Completion Not Tracked" ...)

return {
    "health_score": health_score,
    "health_status": self._get_health_status(health_score),
    "insufficient_data": False,
    "metrics": metrics,
    "insights": [i.to_dict() for i in insights],
}
```

The score formula itself is:

```python
def _calculate_health_score(self, metrics: Dict[str, Any]) -> int:
    score = 100
    completion_measured = bool(metrics.get("completion_measured", metrics.get("total_tasks", 0) > 0))
    if completion_measured:
        completion_rate = metrics.get("task_completion_rate", 0.5)
        score -= max(0, (0.5 - completion_rate) * 40)

    trend = metrics.get("activity_trend", "stable")
    if trend == "decreasing":
        score -= 15
    elif trend == "new":
        score -= 5

    contributors = metrics.get("contributor_count", 1)
    if contributors == 1:
        score -= 10

    return max(0, min(100, int(score)))
```

Status thresholds are:

```python
if score >= 80:
    return "healthy"
elif score >= 60:
    return "moderate"
elif score >= 40:
    return "at_risk"
else:
    return "critical"
```

Confirmed available fields: `completion_measured` is already computed in `_gather_project_metrics()`, and `this_week_hours` is also already gathered there.

## 2) Exact insertion point for the cap

The cap should be inserted immediately after `health_score = self._calculate_health_score(metrics)` and before the return-time status derivation.

That is the smallest safe point because:
- the raw score is already finalized,
- the cap only lowers score,
- status can then be derived from the capped score,
- insight copy can be adjusted in the same branch before the response dict is built.

## 3) CAP=75 status mapping

`75` maps to `moderate` under the current thresholds because `75 >= 60` and `< 80`.

So a capped score of 75 is an explicit non-healthy result while still staying in the moderate band.

## 4) Re-score of TEEMA, Development, and Aloha

I could not re-query the live database from this workspace because the configured PostgreSQL port refused connections and Docker is unavailable locally. So the exact live numbers below are limited to what the repo already documents plus formula-based inference. The key control-plane conclusion still holds: only TEEMA is a candidate for the cap.

Observed / inferred outcomes under the proposed rule:

| Project | Current state | Proposed cap applies? | Before | After | Status change |
| --- | --- | --- | --- | --- | --- |
| TEEMA | low-confidence: completion not measured and this_week_hours is below the floor | Yes | Healthy / 80 | Moderate / 75 | Yes |
| Development | higher-activity project; not low-confidence because this_week_hours is above the floor | No | unchanged | unchanged | No |
| Aloha | insufficient_data | No | no score / no status | no score / no status | No |

What I can confirm from the repository evidence:
- TEEMA is the project the prior audit explicitly called out as `Healthy 80` despite thin signal.
- Development is the 435h example mentioned in the fairness audit and is not the thin-signal case the cap is meant to address.
- Aloha is the sparse-data project and remains governed by the existing insufficient-data branch.

Net result: the cap is intended to change only TEEMA, and the proposal preserves that behavior.

## 5) Honest headline insight copy for the capped case

Recommended headline insight:

"Low-confidence assessment: this week’s activity is below the confidence floor and completion is not yet measured, so the health score is capped at 75 until more signal is available."

That copy is explicit about why the cap exists, does not claim stronger evidence than the data provides, and avoids sounding like a failure state.

## 6) Frontend field impact

Default recommendation: no new schema field.

The existing `insights` payload is enough to carry the cap explanation, so this can stay a service-logic change rather than a contract change. The frontend already renders insight text, so the capped-state explanation can live in the existing insight string without adding a dedicated `confidence_capped` flag.

Only add a new field if you later want a distinct visual badge or a separate disclosure panel. For the initial change, that is not necessary.

## Proposed defaults

- `FLOOR = this_week_hours < 5`
- `CAP = 75`
- `low_confidence = (completion_measured is False) AND (this_week_hours < FLOOR)`
- Apply the cap only when `insufficient_data` is `False`

These defaults are feasible with the current service shape and keep the change localized to scoring/response assembly.
