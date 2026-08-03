from domains.knowledge.db import (
    get_or_create_entity, insert_fact, delete_entity_by_name, get_entity_full
)


def test_create_entity(conn, user_id):
    eid = get_or_create_entity(conn, user_id, "Bunny", "person")
    assert eid > 0


def test_idempotent_entity(conn, user_id):
    eid1 = get_or_create_entity(conn, user_id, "Bunny", "person")
    eid2 = get_or_create_entity(conn, user_id, "Bunny", "person")
    assert eid1 == eid2


def test_insert_and_retrieve_fact(conn, user_id):
    eid = get_or_create_entity(conn, user_id, "Bunny", "person")
    insert_fact(conn, user_id, eid, "Bunny is a golden retriever")
    full = get_entity_full(conn, user_id, eid)
    assert len(full["facts"]) == 1
    assert "golden retriever" in full["facts"][0]["content"]


def test_delete_entity(conn, user_id):
    get_or_create_entity(conn, user_id, "TempEntity", "generic")
    assert delete_entity_by_name(conn, user_id, "TempEntity") is True
    assert delete_entity_by_name(conn, user_id, "TempEntity") is False


def test_user_isolation(conn):
    eid = get_or_create_entity(conn, 1, "Alice", "person")
    full = get_entity_full(conn, 2, eid)
    assert full == {}
