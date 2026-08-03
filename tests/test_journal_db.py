from domains.journal.db import upsert_entry, get_entry, get_recent


def test_insert_and_retrieve(conn, user_id):
    upsert_entry(conn, user_id, "2026-08-02", "Good day today.")
    entry = get_entry(conn, user_id, "2026-08-02")
    assert entry["raw_text"] == "Good day today."


def test_upsert_updates(conn, user_id):
    upsert_entry(conn, user_id, "2026-08-02", "First text")
    upsert_entry(conn, user_id, "2026-08-02", "Updated text")
    entry = get_entry(conn, user_id, "2026-08-02")
    assert entry["raw_text"] == "Updated text"


def test_get_recent(conn, user_id):
    for d in ["2026-08-01","2026-08-02","2026-08-03"]:
        upsert_entry(conn, user_id, d, f"Entry {d}")
    recent = get_recent(conn, user_id, limit=2)
    assert len(recent) == 2
    assert recent[0]["date"] == "2026-08-03"
