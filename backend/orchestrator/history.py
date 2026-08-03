import time

class HistoryManager:
    def __init__(self, max_turns: int = 10, expiry_seconds: int = 1800):
        self._turns: list[dict] = []
        self._last_ts: float = time.time()
        self._max_turns = max_turns
        self._expiry_seconds = expiry_seconds

    def append(self, role: str, content: str) -> None:
        self._last_ts = time.time()
        self._turns.append({"role": role, "content": content})

    def get(self) -> list[dict]:
        if time.time() - self._last_ts > self._expiry_seconds:
            self._turns = []
        return self._turns[-self._max_turns:]

    def clear(self) -> None:
        self._turns = []
        self._last_ts = time.time()
