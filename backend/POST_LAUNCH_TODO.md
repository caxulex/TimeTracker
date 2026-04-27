
## Timer-domain findings session (prep/production-readiness, B1/B3/B10/B14/B20)

- `backend/app/routers/time_entries.py:list_time_entries` stores naive UTC datetimes and mixes them with timezone-aware request filters. The B20 half-open range fix in this session lands on top of that ambiguity; the proper timezone-aware rewrite is Prompt 4's scope.
- `backend/app/routers/reports.py:~310` already uses the half-open form but on the same naive-vs-aware datetimes; will need the same Prompt 4 treatment.
- `backend/app/routers/time_entries.py:get_timer_status` orphan-detection path still queries `WorkSession.ended_at IS NULL` to decide orphan status. When `TIMER_ORPHAN_AUTOCLOSE_ON_READ=False` we now only log; an out-of-band reconciliation job should own that cleanup (no fix needed here).
- `frontend/src/stores/timerStore.ts` (not inspected in depth) likely still assumes the minimum-60s semantics for computed durations. Verify before Prompt 4 UI work.
