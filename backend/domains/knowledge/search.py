import sqlite3
import numpy as np


def semantic_search(conn: sqlite3.Connection, embedding: np.ndarray,
                    user_id: int, top_n: int = 5) -> list:
    try:
        rows = conn.execute(
            """SELECT f.id, f.content, f.entity_id,
                      vec_distance_cosine(v.embedding, ?) AS distance
               FROM vec_facts v
               JOIN facts f ON f.id = v.fact_id
               WHERE f.user_id = ?
               ORDER BY distance ASC LIMIT ?""",
            (embedding.tobytes(), user_id, top_n)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        # sqlite-vec not available — fall back to empty
        return []
