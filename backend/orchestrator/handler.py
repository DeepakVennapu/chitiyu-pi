# backend/orchestrator/handler.py
from __future__ import annotations
import json, logging, re, time
import sqlite3

from orchestrator.llm import call_claude
from orchestrator.classifier import classify
from orchestrator.tier1 import try_tier1
from domains.base import BaseDomain
from domains.health.domain import HealthDomain
from domains.tasks.domain import TasksDomain
from domains.knowledge.domain import KnowledgeDomain
from domains.journal.domain import JournalDomain
from config import DISPATCH_MODEL, POLISH_MODEL

logger = logging.getLogger(__name__)

MAX_ROUNDS = 10
TIMEOUT_SECONDS = 120
FALLBACK = "This took too long. Try breaking it into smaller steps."
POLISH_SYSTEM = ("You are a helpful assistant. Polish the draft reply into natural, "
                 "concise prose. Output only the reply — no preamble, no labels.")

_DOMAIN_MAP: dict[str, type[BaseDomain]] = {
    "health": HealthDomain,
    "tasks": TasksDomain,
    "knowledge": KnowledgeDomain,
    "journal": JournalDomain,
}


def _format_history(history: list) -> str:
    if not history:
        return ""
    lines = [f"{'User' if h['role']=='user' else 'Assistant'}: {h['content']}" for h in history]
    return "Recent conversation:\n" + "\n".join(lines) + "\n\n"


def _extract_tool_call(text: str) -> dict | None:
    m = re.search(r'\{[^{}]*"tool"\s*:', text)
    if not m:
        return None
    try:
        end = text.rindex("}", m.start()) + 1
        parsed = json.loads(text[m.start():end])
        return parsed if "tool" in parsed else None
    except (json.JSONDecodeError, ValueError):
        return None


def handle_message(conn: sqlite3.Connection, user_id: int,
                   message: str, history: list) -> str:
    tier1 = try_tier1(conn, user_id, message)
    if tier1 is not None:
        return tier1

    domain_name = classify(message)
    domain_cls = _DOMAIN_MAP.get(domain_name)
    if domain_cls is None:
        domain = KnowledgeDomain()
    else:
        domain = domain_cls()

    # Orchestrator pre-fetch: semantic search across knowledge domain (spec section 6.2)
    # Inject top 3-5 relevant facts before routing to any domain
    knowledge_context = ""
    try:
        from orchestrator.embedder import embed
        from domains.knowledge.search import semantic_search
        emb = embed(message)
        facts = semantic_search(conn, emb, user_id, top_n=5)
        if facts:
            knowledge_context = "Relevant context from memory:\n" + "\n".join(
                f"• {f['content']}" for f in facts
            )
    except Exception:
        pass

    domain_context = domain.inject_context(conn, user_id, message)
    context_block = "\n\n".join(filter(None, [knowledge_context, domain_context]))
    system_prompt = domain.build_system_prompt()
    history_block = _format_history(history)

    messages = [{"role": "user", "content": message}]
    start = time.time()
    rounds = 0
    last_plain = None

    while rounds < MAX_ROUNDS:
        if time.time() - start > TIMEOUT_SECONDS:
            return FALLBACK
        parts = []
        if context_block:
            parts.append(context_block)
        if history_block:
            parts.append(history_block)
        for msg in messages:
            role = "User" if msg["role"] == "user" else ("Assistant" if msg["role"] == "assistant" else "Tool result")
            parts.append(f"{role}: {msg['content']}")
        prompt = "\n".join(parts)
        try:
            remaining = max(30, TIMEOUT_SECONDS - (time.time() - start))
            response = call_claude(prompt, system_prompt=system_prompt,
                                   model=DISPATCH_MODEL, timeout=remaining)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return "Something went wrong. Please try again."
        rounds += 1
        parsed = _extract_tool_call(response.strip())
        if parsed:
            tool_name = parsed.get("tool")
            tool_args = parsed.get("args", {})
            domain_tools = domain.tools
            if tool_name not in domain_tools:
                return "I'm not sure how to do that."
            try:
                tool_result = domain_tools[tool_name](conn, user_id, **tool_args)
            except Exception as e:
                logger.warning("Tool %s failed: %s", tool_name, e)
                tool_result = f"tool error: {e}"
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "tool_result", "content": tool_result})
            continue
        last_plain = response
        break
    else:
        return FALLBACK

    if not last_plain or not last_plain.strip():
        return "Something went wrong. Please try again."

    polish_prompt = (f"User: {message}\n\nDraft reply: {last_plain.strip()}\n\n"
                     "Polish into a natural, concise reply. Keep all facts and numbers exactly.")
    try:
        remaining = max(30, TIMEOUT_SECONDS - (time.time() - start))
        return call_claude(polish_prompt, system_prompt=POLISH_SYSTEM,
                           model=POLISH_MODEL, timeout=remaining)
    except Exception:
        return last_plain
