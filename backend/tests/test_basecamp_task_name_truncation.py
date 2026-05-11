"""Unit tests for ``_truncate_task_name`` in basecamp_service.

The helper formats a Task name as ``"[list_title] todo_content"`` and
ensures the result fits in ``tasks.name`` ``VARCHAR(255)``. Production
hit ``StringDataRightTruncationError`` on real Basecamp to-dos whose
combined length exceeded 255 chars (see v3.0.2 fix).
"""
from __future__ import annotations

from app.services.basecamp_service import _truncate_task_name

ELLIPSIS = "\u2026"


def test_short_name_unchanged():
    out = _truncate_task_name("Sprint A", "Write docs")
    assert out == "[Sprint A] Write docs"
    assert len(out) <= 255


def test_exactly_255_chars_unchanged():
    # Build content so total length is exactly 255.
    list_title = "List"
    prefix = f"[{list_title}] "  # 7 chars
    content = "x" * (255 - len(prefix))
    out = _truncate_task_name(list_title, content)
    assert out == prefix + content
    assert len(out) == 255
    # No ellipsis should have been appended at the boundary.
    assert not out.endswith(ELLIPSIS)


def test_256_chars_truncates_content():
    list_title = "List"
    prefix = f"[{list_title}] "
    content = "x" * (256 - len(prefix))  # full length would be 256
    out = _truncate_task_name(list_title, content)
    assert len(out) <= 255
    assert out.startswith(prefix)
    assert out.endswith(ELLIPSIS)


def test_very_long_content_truncates_to_255():
    out = _truncate_task_name("L", "a" * 5000)
    assert len(out) == 255
    assert out.startswith("[L] ")
    assert out.endswith(ELLIPSIS)


def test_truncation_ends_with_ellipsis():
    out = _truncate_task_name("Sprint", "y" * 500)
    assert out[-1] == ELLIPSIS
    # Must be the single Unicode codepoint, not three ASCII dots.
    assert out[-1] != "."
    assert not out.endswith("...")
    assert len(out) <= 255


def test_very_long_list_title_alone_exceeds_255():
    # list_title alone > 250 chars: even "[list_title] \u2026" exceeds 255.
    long_title = "T" * 300
    out = _truncate_task_name(long_title, "anything here")
    assert len(out) == 255
    assert out.startswith("[")
    assert out.endswith(f"] {ELLIPSIS}")
    # The list_title portion was truncated.
    assert "T" * 300 not in out


def test_empty_content_uses_just_prefix():
    out = _truncate_task_name("MyList", "")
    assert out == "[MyList] "
    assert len(out) <= 255
    assert ELLIPSIS not in out


def test_unicode_content_handled_correctly():
    # Mix of CJK + emoji in the content; len() counts codepoints, which
    # matches PostgreSQL VARCHAR(255) semantics.
    content = ("\u4e2d\u6587\u6d4b\u8bd5\U0001f600" * 60)  # 300 codepoints
    out = _truncate_task_name("L", content)
    assert len(out) <= 255
    assert out.startswith("[L] ")
    assert out.endswith(ELLIPSIS)
    # Short unicode content is preserved verbatim.
    short = _truncate_task_name("List", "\u4e2d\u6587 \U0001f600")
    assert short == "[List] \u4e2d\u6587 \U0001f600"
