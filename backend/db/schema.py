import sqlite3


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entities (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            name       TEXT NOT NULL,
            type       TEXT NOT NULL CHECK(type IN ('person','project','vendor','place','concept','generic')),
            aliases    TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS facts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            entity_id  INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS fields (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            entity_id  INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            key        TEXT NOT NULL,
            value      TEXT NOT NULL,
            type       TEXT NOT NULL DEFAULT 'text',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(entity_id, key)
        );
        CREATE TABLE IF NOT EXISTS relationships (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL DEFAULT 1,
            from_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            label          TEXT NOT NULL,
            to_entity_id   INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            created_at     TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            entity_id  INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            title      TEXT NOT NULL,
            event_date TEXT NOT NULL,
            recurrence TEXT NOT NULL DEFAULT 'none' CHECK(recurrence IN ('none','annual')),
            notes      TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL DEFAULT 1,
            title        TEXT NOT NULL,
            due_at       TEXT,
            completed_at TEXT,
            priority     INTEGER NOT NULL DEFAULT 0,
            tags         TEXT NOT NULL DEFAULT '[]',
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS recipes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL DEFAULT 1,
            name         TEXT NOT NULL,
            calories     INTEGER NOT NULL,
            protein      REAL NOT NULL,
            fat          REAL,
            carbs        REAL,
            serving_unit TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS meals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL DEFAULT 1,
            logged_at   TEXT NOT NULL DEFAULT (datetime('now')),
            description TEXT NOT NULL,
            calories    INTEGER NOT NULL,
            protein     REAL NOT NULL,
            fat         REAL,
            carbs       REAL,
            source      TEXT NOT NULL DEFAULT 'text',
            recipe_id   INTEGER REFERENCES recipes(id)
        );
        CREATE TABLE IF NOT EXISTS meal_recipes (
            meal_id    INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
            recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
            servings   REAL NOT NULL DEFAULT 1.0,
            PRIMARY KEY (meal_id, recipe_id)
        );
        CREATE TABLE IF NOT EXISTS health_metrics (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL DEFAULT 1,
            date             TEXT NOT NULL,
            steps            INTEGER,
            sleep_deep_mins  INTEGER,
            sleep_total_mins INTEGER,
            resting_hr       INTEGER,
            UNIQUE(user_id, date)
        );
        CREATE TABLE IF NOT EXISTS journal_entries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            date       TEXT NOT NULL,
            raw_text   TEXT NOT NULL,
            summary    TEXT,
            retro_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, date)
        );
        CREATE TABLE IF NOT EXISTS pending_state (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            type       TEXT NOT NULL,
            payload    TEXT NOT NULL DEFAULT '{}',
            sent_at    TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, type)
        );
        CREATE TABLE IF NOT EXISTS notification_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL DEFAULT 1,
            domain       TEXT NOT NULL,
            event_type   TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            delivered_at TEXT
        );
    """)
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_facts USING vec0(
                fact_id INTEGER PRIMARY KEY,
                embedding FLOAT[384]
            );
        """)
    except Exception:
        pass
    conn.commit()
