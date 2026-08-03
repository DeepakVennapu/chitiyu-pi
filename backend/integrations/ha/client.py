import requests
import logging
from config import HA_URL, HA_TOKEN

logger = logging.getLogger(__name__)
_HEADERS = lambda: {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}


def _call(method: str, path: str, json=None) -> dict:
    url = f"{HA_URL}/api/{path}"
    try:
        r = requests.request(method, url, headers=_HEADERS(), json=json, timeout=10)
        r.raise_for_status()
        return r.json() if r.content else {}
    except Exception as e:
        logger.warning("HA call failed %s %s: %s", method, path, e)
        raise


def ha_status() -> str:
    try:
        data = _call("GET", "states/binary_sensor.front_door")
        return f"Front door: {data.get('state','unknown')}"
    except Exception:
        return "Couldn't reach Home Assistant."


def ha_lock() -> str:
    try:
        _call("POST", "services/lock/lock",
              {"entity_id": "lock.front_door_lock"})
        return "Front door locked."
    except Exception:
        return "Couldn't lock the door. Check HA connection."


def ha_garage(door: str = "double", action: str = "open") -> str:
    entity = "cover.double_garage_door" if door == "double" else "cover.single_garage_door"
    service = "cover/open_cover" if action == "open" else "cover/close_cover"
    try:
        _call("POST", f"services/{service}", {"entity_id": entity})
        return f"{door.title()} garage {action}ed."
    except Exception:
        return f"Couldn't {action} the {door} garage. Check HA."


def ha_restart() -> str:
    try:
        _call("POST", "services/homeassistant/restart")
        return "Home Assistant restart triggered."
    except Exception:
        return "Couldn't restart HA."
