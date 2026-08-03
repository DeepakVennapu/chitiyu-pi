from __future__ import annotations
import re, logging
from typing import Literal

logger = logging.getLogger(__name__)

DomainName = Literal["knowledge","health","finance","home","tasks","journal","general"]
DOMAIN_NAMES = ("knowledge","health","finance","home","tasks","journal","general")

_HEALTH_RE = re.compile(
    r"(?:\b(calories?|protein|carbs?|fat|meals?|ate|eat|eaten|eating|log\s+\d+|"
    r"nutrition|food|breakfast|lunch|dinner|snack|coffee|water|drink)\b"
    r"|had\s+(?:a\s+)?(?:coffee|tea|breakfast|lunch|dinner|snack|bite|drink|meal))",
    re.IGNORECASE,
)
_FINANCE_RE = re.compile(
    r"\b(spent|expense|budget|transaction|bought|paid|cost|money|"
    r"dollars?|\$\d|savings?|net\s+worth|invest)\b",
    re.IGNORECASE,
)
_HOME_RE = re.compile(
    r"\b(garage|door|lock|alarm|home\s+status|ha\s+status|house\s+status|"
    r"home\s+assistant|restart\s+ha|lights?|thermostat)\b",
    re.IGNORECASE,
)
_TASKS_RE = re.compile(
    r"\b(remind(?:er)?|task|todo|to-do|to do|appointment|add\s+a\s+task|"
    r"my\s+list|on\s+my\s+list|overdue|upcoming)\b",
    re.IGNORECASE,
)
_JOURNAL_RE = re.compile(
    r"\b(journal(?:ing|ed|entry)?|diary|log\s+my\s+day|end\s+of\s+day|"
    r"reflection|evening\s+summary)\b",
    re.IGNORECASE,
)
_KNOWLEDGE_RE = re.compile(
    r"\b(who\s+is|what\s+do\s+I\s+know|tell\s+me\s+about|remember\s+that|"
    r"save\s+(?:a\s+)?fact|note\s+that|delete\s+(?:all\s+)?records?\s+for|forget\s+about)\b",
    re.IGNORECASE,
)

_TIER1_RULES = [
    (_HOME_RE, "home"),
    (_JOURNAL_RE, "journal"),
    (_FINANCE_RE, "finance"),
    (_HEALTH_RE, "health"),
    (_KNOWLEDGE_RE, "knowledge"),
    (_TASKS_RE, "tasks"),
]

_LLM_PROMPT = """\
Classify the following user message into exactly one of these domains:
knowledge, health, finance, home, tasks, journal, general

Message: {message}

Respond with ONLY the single domain name (one word, lowercase). No explanation."""

def classify(message: str) -> DomainName:
    msg = message.strip().lower()
    for pattern, domain in _TIER1_RULES:
        if pattern.search(msg):
            return domain
    return _classify_llm(msg)

def _classify_llm(message: str) -> DomainName:
    try:
        from orchestrator.llm import call_claude
        from config import DISPATCH_MODEL
        raw = call_claude(_LLM_PROMPT.format(message=message),
                          model=DISPATCH_MODEL, timeout=15).strip().lower()
        if raw in DOMAIN_NAMES:
            return raw  # type: ignore
    except Exception as e:
        logger.warning("Classifier LLM fallback failed: %s", e)
    return "general"
