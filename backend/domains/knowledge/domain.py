import sqlite3

from domains.base import BaseDomain
from domains.knowledge.tools import add_fact, query_memory, delete_entity
from domains.knowledge.search import semantic_search
from orchestrator.embedder import embed


_SYSTEM = """\
You are a personal knowledge assistant. Help the user save and retrieve facts.
Available tools: add_fact, query_memory, delete_entity
Respond with JSON to call a tool: {"tool": "name", "args": {...}}
If no tool is needed, reply in plain text."""


class KnowledgeDomain(BaseDomain):
    name = "knowledge"

    @property
    def tools(self) -> dict:
        return {"add_fact": add_fact, "query_memory": query_memory, "delete_entity": delete_entity}

    def build_system_prompt(self) -> str:
        return _SYSTEM

    def inject_context(self, conn: sqlite3.Connection, user_id: int, message: str) -> str:
        try:
            emb = embed(message)
            results = semantic_search(conn, emb, user_id, top_n=3)
            if results:
                lines = [r["content"] for r in results]
                return "Relevant memory:\n" + "\n".join(f"• {l}" for l in lines)
        except Exception:
            pass
        return ""
