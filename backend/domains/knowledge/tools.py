import json
import re
import sqlite3

from orchestrator.llm import call_claude
from orchestrator.embedder import embed
from domains.knowledge.db import (
    get_or_create_entity, insert_fact, store_embedding,
    delete_entity_by_name, get_entity_full
)
from domains.knowledge.search import semantic_search
from config import DISPATCH_MODEL


_EXTRACT_PROMPT = """\
Extract the subject entity and fact from this statement.
Reply with JSON only: {{"entity": "<name>", "entity_type": "<person|project|vendor|place|concept|generic>", "fact": "<fact text>"}}
Statement: {text}"""


def add_fact(conn: sqlite3.Connection, user_id: int, text: str) -> str:
    raw = call_claude(_EXTRACT_PROMPT.format(text=text), model=DISPATCH_MODEL, timeout=20)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        return "Couldn't parse the fact. Try: 'Remember that [person] is [fact]'."
    data = json.loads(m.group())
    entity_id = get_or_create_entity(conn, user_id, data["entity"], data.get("entity_type", "generic"))
    fact_id = insert_fact(conn, user_id, entity_id, data["fact"])
    emb = embed(data["fact"])
    store_embedding(conn, fact_id, emb)
    return f"Saved: {data['entity']} — {data['fact']}"


def query_memory(conn: sqlite3.Connection, user_id: int, query: str) -> str:
    emb = embed(query)
    results = semantic_search(conn, emb, user_id, top_n=5)
    if not results:
        return "Nothing found in memory for that query."
    lines = [f"• {r['content']}" for r in results]
    return "From memory:\n" + "\n".join(lines)


def delete_entity(conn: sqlite3.Connection, user_id: int, name: str) -> str:
    ok = delete_entity_by_name(conn, user_id, name)
    if ok:
        return f"Deleted all records for '{name}'."
    return f"No entity found with name '{name}'."
