import pytest
from unittest.mock import patch, MagicMock
from domains.health.renpho import sync_renpho_weight
from domains.health.db import get_latest_weight


FAKE_MEASUREMENT = {
    "timeStamp": 1755302400,  # 2026-08-15 08:00:00 UTC
    "localCreatedAt": "2026-08-15 07:00:00",
    "weight": 84.6,
    "bodyfat": 16.1,
    "muscle": 54.2,
    "bmi": 28.3,
}


def test_sync_renpho_weight_upserts(conn):
    mock_client = MagicMock()
    mock_client.get_all_measurements.return_value = [FAKE_MEASUREMENT]
    with patch("domains.health.renpho._make_client", return_value=mock_client):
        result = sync_renpho_weight(conn, user_id=1)
    assert result is not None
    assert result["weight_kg"] == 84.6
    assert result["bodyfat_pct"] == 16.1
    assert result["date"] == "2026-08-15"
    latest = get_latest_weight(conn, 1)
    assert latest["weight_kg"] == 84.6


def test_sync_renpho_weight_empty_measurements(conn):
    mock_client = MagicMock()
    mock_client.get_all_measurements.return_value = []
    with patch("domains.health.renpho._make_client", return_value=mock_client):
        result = sync_renpho_weight(conn, user_id=1)
    assert result is None


def test_sync_renpho_weight_missing_credentials(conn):
    with patch("domains.health.renpho.RENPHO_EMAIL", ""), \
         patch("domains.health.renpho.RENPHO_PASSWORD", ""):
        result = sync_renpho_weight(conn, user_id=1)
    assert result is None


def test_sync_renpho_weight_client_error(conn):
    mock_client = MagicMock()
    mock_client.get_all_measurements.side_effect = Exception("network error")
    with patch("domains.health.renpho._make_client", return_value=mock_client):
        result = sync_renpho_weight(conn, user_id=1)
    assert result is None
