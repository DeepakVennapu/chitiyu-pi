import json
from unittest.mock import patch

import pytest

from orchestrator.retro import generate_retro


_MOCK_RETRO = {
    "wins": ["Hit 9,800 steps — close to goal", "Stayed under 1,550 kcal"],
    "misses": ["Protein only 112g — 38g short of 150g target"],
    "patterns": ["Lower protein days correlate with higher snack spend"],
    "tomorrow": ["Prep chicken for lunch", "Walk after dinner to hit step goal"],
    "summary": "Strong step day but protein needs attention. Finance was on target.",
}

_MOCK_RETRO_JSON = json.dumps(_MOCK_RETRO)


def _make_patches(retro_json=_MOCK_RETRO_JSON):
    return [
        patch("orchestrator.retro.call_claude", return_value=retro_json),
        patch("orchestrator.retro._get", return_value={"mocked": True}),
        patch("orchestrator.retro._post", return_value=True),
        patch("orchestrator.retro.semantic_search",
              return_value=[{"content": "User wants 150g protein"}]),
        patch("orchestrator.retro.embed", return_value=[0.1] * 384),
    ]


def test_generate_retro_returns_dict(conn, user_id):
    ps = _make_patches()
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        result = generate_retro(conn, user_id)

    assert isinstance(result, dict)
    assert "retro_json" in result
    assert "date" in result


def test_generate_retro_parses_sections(conn, user_id):
    ps = _make_patches()
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        result = generate_retro(conn, user_id)

    retro = json.loads(result["retro_json"])
    assert "wins" in retro
    assert "misses" in retro
    assert "patterns" in retro
    assert "tomorrow" in retro
    assert "summary" in retro


def test_generate_retro_stores_via_journal_post(conn, user_id):
    ps = _make_patches()
    with ps[0], ps[1], ps[2] as mock_post, ps[3], ps[4]:
        generate_retro(conn, user_id)

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    path, body = call_args[0]
    assert path == "/journal/entry"
    assert "retro_json" in body
    assert body["user_id"] == user_id


def test_generate_retro_strips_markdown_fences(conn, user_id):
    fenced = f"```json\n{_MOCK_RETRO_JSON}\n```"
    ps = _make_patches(retro_json=fenced)
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        result = generate_retro(conn, user_id)

    retro = json.loads(result["retro_json"])
    assert "wins" in retro


def test_generate_retro_proceeds_without_journal_entry(conn, user_id):
    """retro must complete even if the user didn't reply to the 10pm prompt."""
    ps = _make_patches()
    # Simulate journal returning None (no user reply)
    with ps[0], ps[1] as mock_get, ps[2], ps[3], ps[4]:
        mock_get.return_value = None
        result = generate_retro(conn, user_id)

    assert "retro_json" in result
