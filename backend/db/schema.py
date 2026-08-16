import sqlite3


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entities (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            name       TEXT NOT NULL,
            type       TEXT NOT NULL CHECK(type IN ('person','project','vendor','place','concept','generic')),
            aliases    TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS facts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            entity_id  INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS fields (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            entity_id  INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            key        TEXT NOT NULL,
            value      TEXT NOT NULL,
            type       TEXT NOT NULL DEFAULT 'text',
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            UNIQUE(entity_id, key)
        );
        CREATE TABLE IF NOT EXISTS relationships (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL DEFAULT 1,
            from_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            label          TEXT NOT NULL,
            to_entity_id   INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            entity_id  INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            title      TEXT NOT NULL,
            event_date TEXT NOT NULL,
            recurrence TEXT NOT NULL DEFAULT 'none' CHECK(recurrence IN ('none','annual')),
            notes      TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL DEFAULT 1,
            title        TEXT NOT NULL,
            due_at       TEXT,
            completed_at TEXT,
            priority     INTEGER NOT NULL DEFAULT 0,
            tags         TEXT NOT NULL DEFAULT '[]',
            created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
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
            created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS meals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL DEFAULT 1,
            logged_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
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
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            UNIQUE(user_id, date)
        );
        CREATE TABLE IF NOT EXISTS pending_state (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            type       TEXT NOT NULL,
            payload    TEXT NOT NULL DEFAULT '{}',
            sent_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            UNIQUE(user_id, type)
        );
        CREATE TABLE IF NOT EXISTS notification_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL DEFAULT 1,
            domain       TEXT NOT NULL,
            event_type   TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            delivered_at TEXT
        );
        CREATE TABLE IF NOT EXISTS accounts (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER NOT NULL DEFAULT 1,
            name     TEXT NOT NULL,
            type     TEXT NOT NULL CHECK(type IN ('checking','savings','investment','credit','brokerage','crypto')),
            currency TEXT NOT NULL DEFAULT 'USD',
            UNIQUE(user_id, name)
        );
        -- One balance row per account per date. Upsert on (account_id, date).
        -- is_liability: true for credit cards (balance reduces net worth).
        CREATE TABLE IF NOT EXISTS account_balances (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL DEFAULT 1,
            account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            date       TEXT NOT NULL,
            balance    REAL NOT NULL,
            note       TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            UNIQUE(account_id, date)
        );
        CREATE INDEX IF NOT EXISTS idx_account_balances_user_date
            ON account_balances(user_id, date);
        -- Financial milestones: named checkpoints on a rolling timeline.
        -- target_date + expected_net_worth define the goal line.
        -- actual_net_worth is filled in when the user logs balances on/after that date.
        -- period_label groups milestones into cycles (e.g. "2026-H2", "2027-H1").
        CREATE TABLE IF NOT EXISTS financial_milestones (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER NOT NULL DEFAULT 1,
            period_label        TEXT NOT NULL,
            target_date         TEXT NOT NULL,
            expected_net_worth  REAL NOT NULL,
            actual_net_worth    REAL,
            note                TEXT,
            created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            UNIQUE(user_id, target_date)
        );
        CREATE INDEX IF NOT EXISTS idx_milestones_user_date
            ON financial_milestones(user_id, target_date);
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL DEFAULT 1,
            account_id  INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            date        TEXT NOT NULL,
            amount      REAL NOT NULL,
            category    TEXT NOT NULL DEFAULT 'uncategorized',
            description TEXT NOT NULL,
            source      TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','csv')),
            created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_transactions_user_date
            ON transactions(user_id, date);
        CREATE INDEX IF NOT EXISTS idx_transactions_user_category
            ON transactions(user_id, category);
        CREATE TABLE IF NOT EXISTS budgets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL DEFAULT 1,
            category    TEXT NOT NULL,
            amount      REAL NOT NULL,
            period      TEXT NOT NULL DEFAULT 'monthly'
                        CHECK(period IN ('monthly','weekly','biannual','annual')),
            budget_type TEXT NOT NULL DEFAULT 'discretionary'
                        CHECK(budget_type IN ('fixed','recurring','discretionary','envelope')),
            start_date  TEXT NOT NULL DEFAULT (date('now', 'localtime')),
            UNIQUE(user_id, category, period)
        );
        CREATE TABLE IF NOT EXISTS net_worth (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL DEFAULT 1,
            snapshot_date   TEXT NOT NULL,
            assets_json     TEXT NOT NULL DEFAULT '{}',
            liabilities_json TEXT NOT NULL DEFAULT '{}',
            total           REAL NOT NULL,
            UNIQUE(user_id, snapshot_date)
        );
        CREATE TABLE IF NOT EXISTS savings_goals (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL DEFAULT 1,
            name           TEXT NOT NULL,
            target_amount  REAL NOT NULL,
            current_amount REAL NOT NULL DEFAULT 0.0,
            target_date    TEXT,
            created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            UNIQUE(user_id, name)
        );
        CREATE TABLE IF NOT EXISTS insights (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL DEFAULT 1,
            scope        TEXT NOT NULL CHECK(scope IN ('today','week')),
            cards_json   TEXT NOT NULL,
            generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            UNIQUE(user_id, scope)
        );
        CREATE TABLE IF NOT EXISTS task_templates (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL DEFAULT 1,
            title        TEXT NOT NULL,
            recurrence   TEXT NOT NULL DEFAULT 'none' CHECK(recurrence IN ('none','daily','weekly','monthly','yearly')),
            anchor_date  TEXT NOT NULL,
            advance_days INTEGER NOT NULL DEFAULT 1,
            priority     INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS task_instances (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id  INTEGER NOT NULL REFERENCES task_templates(id) ON DELETE CASCADE,
            user_id      INTEGER NOT NULL DEFAULT 1,
            due_date     TEXT NOT NULL,
            completed_at TEXT,
            deleted_at   TEXT,
            created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            UNIQUE(template_id, due_date)
        );
        CREATE INDEX IF NOT EXISTS idx_task_instances_user_due
            ON task_instances(user_id, due_date);
        CREATE TABLE IF NOT EXISTS weight_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL DEFAULT 1,
            date        TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            weight_kg   REAL NOT NULL,
            bodyfat_pct REAL,
            muscle_kg   REAL,
            bmi         REAL,
            source      TEXT NOT NULL DEFAULT 'renpho',
            UNIQUE(user_id, date)
        );
        CREATE INDEX IF NOT EXISTS idx_weight_logs_user_date
            ON weight_logs(user_id, date);
        CREATE TABLE IF NOT EXISTS ingredients (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT NOT NULL,
            name_lower        TEXT NOT NULL,
            calories_per_100g REAL NOT NULL,
            protein_per_100g  REAL NOT NULL,
            fat_per_100g      REAL NOT NULL,
            carbs_per_100g    REAL NOT NULL,
            category          TEXT NOT NULL DEFAULT 'other'
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ingredients_name_lower
            ON ingredients(name_lower);
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

    # Migration: add priority column to task_templates if missing
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(task_templates)").fetchall()}
    if "priority" not in existing_cols:
        conn.execute("ALTER TABLE task_templates ADD COLUMN priority INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    # Migration: create weight_logs if missing (for existing DBs)
    existing_tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "weight_logs" not in existing_tables:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS weight_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL DEFAULT 1,
                date        TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                weight_kg   REAL NOT NULL,
                bodyfat_pct REAL,
                muscle_kg   REAL,
                bmi         REAL,
                source      TEXT NOT NULL DEFAULT 'renpho',
                UNIQUE(user_id, date)
            );
            CREATE INDEX IF NOT EXISTS idx_weight_logs_user_date
                ON weight_logs(user_id, date);
        """)
        conn.commit()

    # Migrate recipes: add serving columns if missing
    for col, typedef in [
        ("serving_grams", "INTEGER"),
        ("serving_label", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE recipes ADD COLUMN {col} {typedef}")
            conn.commit()
        except Exception:
            pass  # column already exists
