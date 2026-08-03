import time
from orchestrator.history import HistoryManager

def test_append_and_get():
    h = HistoryManager()
    h.append("user", "hello")
    h.append("assistant", "hi")
    turns = h.get()
    assert len(turns) == 2
    assert turns[0]["role"] == "user"

def test_max_turns_trim():
    h = HistoryManager(max_turns=3)
    for i in range(5):
        h.append("user", f"msg {i}")
    assert len(h.get()) == 3

def test_expiry_clears_history():
    h = HistoryManager(expiry_seconds=1)
    h.append("user", "hello")
    h._last_ts = time.time() - 2
    assert h.get() == []

def test_clear():
    h = HistoryManager()
    h.append("user", "hello")
    h.clear()
    assert h.get() == []
