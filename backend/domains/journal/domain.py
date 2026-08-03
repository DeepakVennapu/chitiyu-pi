import sqlite3
from domains.base import BaseDomain
from domains.journal.tools import save_journal_entry

_SYSTEM = """\
You are a personal journal assistant. Help the user capture their day.
Available tools: save_journal_entry
Respond with JSON: {"tool": "save_journal_entry", "args": {"text": "<full entry>"}}"""


class JournalDomain(BaseDomain):
    name = "journal"

    @property
    def tools(self) -> dict:
        return {"save_journal_entry": save_journal_entry}

    def build_system_prompt(self) -> str:
        return _SYSTEM
