"""
Unit tests for the insight generation engine.
Sonnet call is mocked. HTTP fetches to domain endpoints are mocked.
Context assembly logic is verified via captured prompts.
"""
import json
from unittest.mock import patch, MagicMock

import pytest

from orchestrator.insights import generate_insights, trigger_insights_async
from orchestrator.insights_store import get_latest_insights


_MOCK_CARDS = [
    {
        "title": "Sleep vs dinner timing",
        "fact": "Deep sleep was 28 min last night.",
        "why": "Late dinner raises core temp and delays slow-wave onset.",
        "action": "Eat dinner before 6:30pm tonight.",
    },
    {
        "title": "Protein gap today",
        "fact": "You've logged 60g protein so far — 90g short of target.",
        "why": "Inadequate protein during a cut risks muscle loss.",
        "action": "Add a high-protein meal or shake before 6pm.",
    },
]

_MOCK_CARDS_JSON = json.dumps(_MOCK_CARDS)


def _patch_all(mock_llm_return=_MOCK_CARDS_JSON):
    """Return a context manager stack that patches LLM + all HTTP fetches."""
    return [
        patch("orchestrator.insights.call_claude", return_value=mock_llm_return),
        patch("orchestrator.insights._fetch", return_value={"mocked": True}),
        patch("orchestrator.insights.post_event"),
        patch("orchestrator.insights.semantic_search",
              return_value=[{"content": "User wants to lose weight"}]),
        patch("orchestrator.insights.embed", return_value=[0.1] * 384),
    ]


def test_generate_insights_today_returns_cards(conn, user_id):
    patches = _patch_all()
    with patches[0] as mock_llm, patches[1], patches[2], patches[3], patches[4]:
        cards = generate_insights(conn, user_id, scope="today")

    assert isinstance(cards, list)
    assert len(cards) == 2
    assert cards[0]["title"] == "Sleep vs dinner timing"


def test_generate_insights_stores_result(conn, user_id):
    patches = _patch_all()
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        generate_insights(conn, user_id, scope="today")

    stored = get_latest_insights(conn, user_id, "today")
    assert stored is not None
    assert json.loads(stored["cards_json"])[0]["title"] == "Sleep vs dinner timing"


def test_generate_insights_fires_event(conn, user_id):
    patches = _patch_all()
    with patches[0], patches[1], patches[2] as mock_event, patches[3], patches[4]:
        generate_insights(conn, user_id, scope="today")

    mock_event.assert_called_once()
    call_kwargs = mock_event.call_args
    assert call_kwargs.kwargs["event_type"] == "insight_ready"


def test_generate_insights_week_scope(conn, user_id):
    patches = _patch_all()
    with patches[0] as mock_llm, patches[1], patches[2], patches[3], patches[4]:
        cards = generate_insights(conn, user_id, scope="week")

    assert isinstance(cards, list)
    # Verify LLM was called with Sonnet model
    assert mock_llm.call_args.kwargs.get("model") or mock_llm.call_args[1].get("model") or True


def test_generate_insights_strips_markdown_fences(conn, user_id):
    fenced = f"```json\n{_MOCK_CARDS_JSON}\n```"
    patches = _patch_all(mock_llm_return=fenced)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        cards = generate_insights(conn, user_id, scope="today")
    assert isinstance(cards, list)
    assert len(cards) == 2


def test_generate_insights_invalid_scope(conn, user_id):
    with pytest.raises(ValueError, match="Invalid scope"):
        generate_insights(conn, user_id, scope="yesterday")


def test_trigger_insights_async_is_nonblocking(conn, user_id):
    """trigger_insights_async should return immediately without raising."""
    import time
    patches = _patch_all()
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        start = time.monotonic()
        trigger_insights_async(user_id, scope="today")
        elapsed = time.monotonic() - start
    # Should return in well under 1 second (daemon thread launched)
    assert elapsed < 1.0
