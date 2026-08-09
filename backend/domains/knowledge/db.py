import sqlite3


def get_or_create_entity(conn: sqlite3.Connection, user_id: int, name: str, entity_type: str = "generic") -> int:
    row = conn.execute(
        "SELECT id FROM entities WHERE user_id=? AND name=? COLLATE NOCASE",
        (user_id, name)
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO entities(user_id, name, type) VALUES (?,?,?)",
        (user_id, name, entity_type)
    )
    conn.commit()
    return cur.lastrowid


def insert_fact(conn: sqlite3.Connection, user_id: int, entity_id: int, content: str) -> int:
    cur = conn.execute(
        "INSERT INTO facts(user_id, entity_id, content) VALUES (?,?,?)",
        (user_id, entity_id, content)
    )
    conn.commit()
    return cur.lastrowid


def store_embedding(conn: sqlite3.Connection, fact_id: int, embedding) -> None:
    try:
        conn.execute("INSERT OR REPLACE INTO vec_facts(fact_id, embedding) VALUES (?,?)",
                     (fact_id, embedding.tobytes()))
        conn.commit()
    except Exception:
        pass


def get_entity_full(conn: sqlite3.Connection, user_id: int, entity_id: int) -> dict:
    entity = dict(conn.execute("SELECT * FROM entities WHERE id=? AND user_id=?",
                               (entity_id, user_id)).fetchone() or {})
    if entity:
        entity["facts"] = [dict(r) for r in conn.execute(
            "SELECT * FROM facts WHERE entity_id=? AND user_id=? ORDER BY created_at DESC",
            (entity_id, user_id)
        ).fetchall()]
    return entity


def delete_entity_by_name(conn: sqlite3.Connection, user_id: int, name: str) -> bool:
    row = conn.execute("SELECT id FROM entities WHERE user_id=? AND name=? COLLATE NOCASE",
                       (user_id, name)).fetchone()
    if not row:
        return False
    conn.execute("DELETE FROM entities WHERE id=? AND user_id=?", (row["id"], user_id))
    conn.commit()
    return True


def get_all_entities(conn: sqlite3.Connection, user_id: int) -> list:
    return conn.execute(
        """SELECT e.*, COUNT(f.id) AS fact_count
           FROM entities e
           LEFT JOIN facts f ON f.entity_id = e.id AND f.user_id = e.user_id
           WHERE e.user_id = ?
           GROUP BY e.id
           ORDER BY e.name""",
        (user_id,)
    ).fetchall()
