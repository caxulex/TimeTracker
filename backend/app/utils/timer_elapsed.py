"""Helpers for computing the display elapsed-time of a running TimeEntry.

The "Who's Working Now" panel and the local timer widget must agree on the
elapsed value, including while the user is on break (entry.is_paused = True,
entry.paused_at = <moment of pause>). When paused, elapsed must freeze at
the pause moment; once resumed, the just-elapsed break duration is folded
into entry.pause_seconds so subsequent (now - start_time) - pause_seconds
arithmetic remains correct across any number of pause/resume cycles.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def compute_display_elapsed_seconds(entry: Any, now: datetime | None = None) -> int:
    """Return the elapsed seconds to surface in active-timer payloads.

    Accepts any object exposing ``start_time``, ``is_paused``, ``paused_at``
    and ``pause_seconds`` (TimeEntry ORM rows in practice).

    - While paused (``is_paused`` and ``paused_at`` not null): freeze at
      ``(paused_at - start_time) - pause_seconds``.
    - Otherwise: ``(now - start_time) - pause_seconds``.

    The result is clamped to ``>= 0`` to defend against clock skew.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    start = entry.start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    is_paused = bool(getattr(entry, "is_paused", False))
    paused_at = getattr(entry, "paused_at", None)
    if is_paused and paused_at is not None:
        end_ref = paused_at
        if end_ref.tzinfo is None:
            end_ref = end_ref.replace(tzinfo=timezone.utc)
    else:
        end_ref = now

    pause_seconds = int(getattr(entry, "pause_seconds", 0) or 0)
    elapsed = int((end_ref - start).total_seconds()) - pause_seconds
    return max(elapsed, 0)


def compute_state_elapsed_seconds(
    state_started_at: datetime, now: datetime | None = None
) -> int:
    """Return ``(now - state_started_at)`` in whole seconds, clamped to >= 0.

    Used by the "Who's Working Now" panel to display the duration of the
    user's CURRENT activity state (work / break / meeting) — i.e. the
    elapsed time since the active SessionBreak / SessionMeeting started,
    or since the running TimeEntry started while ``working``.

    Unlike :func:`compute_display_elapsed_seconds`, this helper does NOT
    subtract any pause_seconds: it is a pure "seconds since this state
    began" reading.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    s = state_started_at
    if s.tzinfo is None:
        s = s.replace(tzinfo=timezone.utc)
    return max(int((now - s).total_seconds()), 0)
