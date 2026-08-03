import re

_DONE_RE = re.compile(r"^/done\s+(\d+)$", re.IGNORECASE)
_LIST_PATTERNS = {"/todos","show my tasks","show tasks","what's on my list",
                  "whats on my list","list my tasks","list tasks","my tasks",
                  "my reminders","show my reminders"}
_HOME_STATUS_PATTERNS = {"home status","ha status","house status",
                         "what's the status","whats the status"}
_RESTART_HA_PATTERNS = {"restart home assistant","restart ha",
                        "reboot home assistant","reboot ha"}
_LOCK_DOOR_PATTERNS = {"lock the front door","lock front door",
                       "lock the door","lock door"}

def try_tier1(conn, user_id: int, message: str) -> str | None:
    msg = message.strip()
    msg_lower = msg.lower()
    m = _DONE_RE.match(msg)
    if m:
        from domains.tasks.tools import mark_task_done
        return mark_task_done(conn, user_id, task_id=int(m.group(1)))
    if msg_lower in _LIST_PATTERNS:
        from domains.tasks.tools import list_tasks
        return list_tasks(conn, user_id)
    if msg_lower in _HOME_STATUS_PATTERNS:
        from integrations.ha.client import ha_status
        return ha_status()
    if msg_lower in _RESTART_HA_PATTERNS:
        from integrations.ha.client import ha_restart
        return ha_restart()
    if msg_lower in _LOCK_DOOR_PATTERNS:
        from integrations.ha.client import ha_lock
        return ha_lock()
    garage = _match_garage(msg_lower)
    if garage:
        door, action = garage
        from integrations.ha.client import ha_garage
        return ha_garage(door=door, action=action)
    return None

def _match_garage(msg: str):
    if "garage" not in msg:
        return None
    action = "close" if ("close" in msg or "shut" in msg) else ("open" if "open" in msg else None)
    if not action:
        return None
    door = "single" if "single" in msg else "double"
    return door, action
