from abc import ABC, abstractmethod
import sqlite3


class BaseDomain(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def tools(self) -> dict: ...

    @abstractmethod
    def build_system_prompt(self) -> str: ...

    def inject_context(self, conn: sqlite3.Connection, user_id: int, message: str) -> str:
        return ""
