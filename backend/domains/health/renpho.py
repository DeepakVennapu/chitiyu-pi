import logging
from datetime import datetime
from config import RENPHO_EMAIL, RENPHO_PASSWORD

logger = logging.getLogger(__name__)


def _make_client():
    from renpho import RenphoClient
    client = RenphoClient(RENPHO_EMAIL, RENPHO_PASSWORD)
    client.login()
    return client


def sync_renpho_weight(conn, user_id: int = 1) -> dict | None:
    """Fetch latest Renpho measurement and upsert into weight_logs. Returns row dict or None."""
    if not RENPHO_EMAIL or not RENPHO_PASSWORD:
        logger.warning("Renpho credentials not configured — skipping sync")
        return None
    try:
        client = _make_client()
        measurements = client.get_all_measurements()
        if not measurements:
            logger.info("Renpho returned no measurements")
            return None

        latest = sorted(measurements, key=lambda m: m["timeStamp"], reverse=True)[0]

        # localCreatedAt is "YYYY-MM-DD HH:MM:SS" in the scale's local timezone
        recorded_at = latest.get("localCreatedAt", "")
        date = recorded_at[:10] if recorded_at else datetime.now().strftime("%Y-%m-%d")

        weight_kg = latest.get("weight")
        if weight_kg is None:
            logger.warning("Renpho measurement missing weight field")
            return None

        bodyfat_pct = latest.get("bodyfat")
        muscle_kg = latest.get("muscle")
        bmi = latest.get("bmi")

        from domains.health.db import upsert_weight_log
        upsert_weight_log(conn, user_id, date, recorded_at, weight_kg,
                          bodyfat_pct, muscle_kg, bmi, source="renpho")

        logger.info("Renpho sync: %.1f kg on %s", weight_kg, date)
        return {
            "date": date,
            "recorded_at": recorded_at,
            "weight_kg": weight_kg,
            "bodyfat_pct": bodyfat_pct,
            "muscle_kg": muscle_kg,
            "bmi": bmi,
            "source": "renpho",
        }
    except Exception as exc:
        logger.error("Renpho sync failed: %s", exc)
        return None
