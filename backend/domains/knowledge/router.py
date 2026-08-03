from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import verify_api_key
from db.connection import get_connection
from db.schema import initialize_schema
from config import DB_PATH
from domains.knowledge.db import get_all_entities, get_entity_full, get_or_create_entity
from domains.knowledge.search import semantic_search
from orchestrator.embedder import embed


router = APIRouter(prefix="/knowledge", tags=["knowledge"],
                   dependencies=[Depends(verify_api_key)])


def _conn():
    c = get_connection(DB_PATH)
    initialize_schema(c)
    return c


class FactCreate(BaseModel):
    user_id: int = 1
    text: str


@router.post("/facts")
def save_fact(body: FactCreate):
    from domains.knowledge.tools import add_fact
    conn = _conn()
    result = add_fact(conn, body.user_id, body.text)
    conn.close()
    return {"result": result}


@router.get("/search")
def search(q: str, user_id: int = 1, top_n: int = 5):
    conn = _conn()
    emb = embed(q)
    results = semantic_search(conn, emb, user_id, top_n=top_n)
    conn.close()
    return results


@router.get("/entities")
def list_entities(user_id: int = 1):
    conn = _conn()
    entities = [dict(e) for e in get_all_entities(conn, user_id)]
    conn.close()
    return entities


@router.get("/entity/{name}")
def get_entity(name: str, user_id: int = 1):
    conn = _conn()
    row = conn.execute("SELECT id FROM entities WHERE user_id=? AND name=? COLLATE NOCASE",
                       (user_id, name)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Entity not found")
    full = get_entity_full(conn, user_id, row["id"])
    conn.close()
    return full


@router.delete("/facts/{fact_id}")
def delete_fact(fact_id: int, user_id: int = 1):
    conn = _conn()
    cur = conn.execute("DELETE FROM facts WHERE id=? AND user_id=?", (fact_id, user_id))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "Fact not found")
    return {"ok": True}
