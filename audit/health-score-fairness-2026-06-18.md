# AI Health Score Fairness Investigation (2026-06-18)

Scope:
- Tenant: SMC (`company_id=2`)
- Focus area: project health scoring behavior in `backend/app/ai/services/reporting_service.py`
- Supporting checks: API schemas and frontend normalization path for displayed recommendations

This document reports findings only. No service/schema/frontend code changes were made.

---

## A) Health-score formula (inputs + weights)

Source: `backend/app/ai/services/reporting_service.py`, `_calculate_health_score()`.

```python
def _calculate_health_score(self, metrics: Dict[str, Any]) -> int:
    """Calculate project health score (0-100)."""
    score = 100

    # Task completion rate impacts score
    completion_rate = metrics.get("task_completion_rate", 0.5)
    score -= max(0, (0.5 - completion_rate) * 40)

    # Activity trend
    trend = metrics.get("activity_trend", "stable")
    if trend == "decreasing":
        score -= 15
    elif trend == "new":
        score -= 5

    # Contributor diversity
    contributors = metrics.get("contributor_count", 1)
    if contributors == 1:
        score -= 10

    return max(0, min(100, int(score)))
```

Observed formula contributions:
- Base score: `100`
- Completion penalty: `max(0, (0.5 - completion_rate) * 40)`
  - Equivalent interpretation: completion below 50% reduces score up to 20 points (at 0%).
  - Completion above 50% gives no bonus.
- Trend penalty:
  - `decreasing`: `-15`
  - `new`: `-5`
  - `stable`/`increasing`: `0`
- Contributor penalty:
  - exactly 1 contributor: `-10`
  - 2+ contributors: `0`
- Final clamp/cast: `int`, then `[0, 100]` bounds.

Notably absent from score formula:
- `total_hours`
- `this_week_hours`
- `last_week_hours`
- `days_with_activity`

Conclusion: absolute activity volume does not directly increase score.

---

## B) Score -> status thresholds

Source: `backend/app/ai/services/reporting_service.py`, `_get_health_status()`.

```python
def _get_health_status(self, score: int) -> str:
    """Convert health score to status."""
    if score >= 80:
        return "healthy"
    elif score >= 60:
        return "moderate"
    elif score >= 40:
        return "at_risk"
    else:
        return "critical"
```

Threshold mapping:
- `80-100`: `healthy`
- `60-79`: `moderate`
- `40-59`: `at_risk`
- `0-39`: `critical`

---

## C) How completion (0%) is computed and why 435h can still show 0%

Source: `backend/app/ai/services/reporting_service.py`, `_gather_project_metrics()`.

```python
tasks_result = await self.db.execute(
    select(
        func.count().label("total"),
        func.sum(func.cast(Task.status == "DONE", Integer)).label("completed")
    )
    .where(Task.project_id == project_id)
)
task_stats = tasks_result.fetchone()

if task_stats and task_stats.total > 0:
    metrics["total_tasks"] = task_stats.total
    metrics["completed_tasks"] = task_stats.completed or 0
    metrics["task_completion_rate"] = round((task_stats.completed or 0) / task_stats.total, 2)
else:
    metrics["total_tasks"] = 0
    metrics["completed_tasks"] = 0
    metrics["task_completion_rate"] = 0
```

Completion mechanics:
- Numerator: count of tasks with `Task.status == "DONE"`.
- Denominator: count of all tasks for that project (`Task.project_id == project_id`).
- Rounding: 2 decimals.
- If no tasks exist (`total == 0`) completion is forced to `0`.

Important implications:
- Time entries/hours are independent from task completion.
- A project can log many hours (e.g., 435h) and still show `0%` if:
  - it has zero tasks, or
  - tasks exist but none have status exactly `"DONE"`.

Status contract check:
- Task model comment indicates expected statuses include `TODO`, `IN_PROGRESS`, `DONE`.
- Basecamp sync logic also maps completed todos to `"DONE"`.

So the 0% result is structurally plausible without a scoring bug if task lifecycle completion is not represented in `tasks.status` as `DONE`.

---

## D) Trend vs absolute-activity weighting

Confirmed behavior:
- Trend (`activity_trend`) can reduce score (`-15` decreasing, `-5` new).
- Absolute hours are not used in `_calculate_health_score()`.

Trend derivation in metrics gathering:

```python
if last_week > 0:
    if this_week > last_week * 1.1:
        metrics["activity_trend"] = "increasing"
    elif this_week < last_week * 0.9:
        metrics["activity_trend"] = "decreasing"
    else:
        metrics["activity_trend"] = "stable"
else:
    metrics["activity_trend"] = "new"
```

Interpretation for anomaly #1:
- A high-hour project with declining trend gets penalized (`-15`).
- A low-hour but stable project avoids that penalty.
- Since total/weekly hours are not rewarded in score, stable low activity can outscore declining high activity.

This directly explains why TEEMA (flat low activity) can score higher than Development (higher but decreasing activity).

---

## E) Recommendation generation: static vs derived (file + line context)

### In project-health path (`generate_project_health`)

Project health builds recommendations via hardcoded insight action items for low completion:

```python
if metrics.get("task_completion_rate", 0) < 0.3:
    insights.append(Insight(
        type=InsightType.PROJECT_HEALTH,
        title="Low Task Completion",
        description=f"Only {metrics.get('task_completion_rate', 0)*100:.0f}% of tasks completed",
        severity=InsightSeverity.WARNING,
        action_items=["Review blocked tasks", "Reassess task priorities"]
    ))
```

For sufficient-data responses, the return payload includes:
- `health_score`, `health_status`, `metrics`, `insights`, `generated_at`
- and does **not** include a top-level `recommendations` field.

### Generic recommendation helper exists but is not used in project-health

`_generate_recommendations()` does merge insight action items + some metric-based generic items, but `generate_project_health()` does not call it.

```python
def _generate_recommendations(...):
    recommendations = []
    for insight in insights:
        if insight.action_items:
            recommendations.extend(insight.action_items)
    ...
```

### Why UI still shows recommendations in healthy/moderate cards

Frontend normalization in `frontend/src/components/ai/ProjectHealthCard.tsx` derives recommendations from `insights[].action_items` and merges with `data.recommendations`:

```ts
const recommendations = Array.from(
  new Set((data.insights || []).flatMap((insight) => insight.action_items || []).filter(Boolean)),
);
...
recommendations: Array.from(new Set([...(data.recommendations || []), ...recommendations]))
```

So the repeated pair (`"Review blocked tasks"`, `"Reassess task priorities"`) is effectively static for any project where low-completion insight is present, regardless of overall status bucket.

---

## Explicit explanation of the 4 reported anomalies

1. TEEMA scoring higher than Development despite lower activity:
- Expected from current formula. Trend penalty (`decreasing`) is applied; absolute hours are not rewarded.

2. Completion at 0% across projects including 435h Development:
- Completion is task-status based, not hours-based.
- `0%` occurs when no project tasks exist or none are `DONE`.

3. TEEMA showing `Healthy 80` while insight says `Only 0% of tasks completed`:
- Not contradictory under current logic.
- 0% completion alone gives up to `-20`; with stable trend and 2+ contributors, score can still remain `>=80`.

4. Identical recommendations across different statuses:
- In project health, recommendations are hardcoded in low-completion insight action_items.
- Frontend surfaces these action items as displayed recommendations.

---

## PR Description Draft (A-E summary)

Title:
- Audit: AI Health Score Fairness Investigation (2026-06-18)

Summary:
- Added audit findings document at `audit/health-score-fairness-2026-06-18.md`.
- No production code changes in backend/app/ai service, schemas, or frontend.

Findings (A-E):
- A. Health score formula starts at 100 and applies only penalties for low completion (`up to -20`), decreasing/new trend (`-15`/`-5`), and single contributor (`-10`); no direct weighting for absolute hours.
- B. Status thresholds are `healthy >=80`, `moderate >=60`, `at_risk >=40`, else `critical`.
- C. Completion is computed as `DONE tasks / total tasks` per project; if no tasks (or no `DONE`) it resolves to 0%, independent of logged hours.
- D. Trend is penalized while absolute activity is unweighted, so stable low-activity projects can outscore high-activity declining projects.
- E. Project-health recommendations are effectively static for low completion via hardcoded insight action items (`Review blocked tasks`, `Reassess task priorities`), and frontend also derives displayed recommendations from `insights[].action_items`.