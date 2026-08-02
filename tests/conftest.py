import pytest
import sqlite3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from db.connection import get_connection
from db.schema import initialize_schema


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    initialize_schema(c)
    yield c
    c.close()


@pytest.fixture
def user_id():
    return 1
