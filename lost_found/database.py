"""SQLite locally and PostgreSQL on Render, behind one small data layer."""
import json
import sqlite3
from pathlib import Path


class Database:
    def __init__(self, database_path):
        database_path = str(database_path)
        self.is_postgres = database_path.startswith(("postgres://", "postgresql://"))
        if self.is_postgres:
            # Render can provide postgres:// while psycopg expects postgresql://.
            self.dsn = database_path.replace("postgres://", "postgresql://", 1) if database_path.startswith("postgres://") else database_path
            self.path = None
        else:
            self.path = Path(database_path)
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def connect(self):
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row
            return psycopg.connect(self.dsn, row_factory=dict_row)
        connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _execute(self, connection, query, parameters=()):
        if self.is_postgres:
            query = query.replace("?", "%s")
        return connection.execute(query, parameters)

    def transaction(self):
        """Close the connection as well as committing or rolling back work."""
        from contextlib import contextmanager

        @contextmanager
        def managed():
            connection = self.connect()
            try:
                with connection:
                    yield connection
            finally:
                connection.close()
        return managed()

    def _create_tables(self):
        with self.transaction() as connection:
            self._execute(connection, """CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE, salt TEXT NOT NULL,
                password_hash TEXT NOT NULL, created_at TEXT NOT NULL
            )""")
            self._execute(connection, """CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at BIGINT NOT NULL
            )""")
            self._execute(connection, """CREATE TABLE IF NOT EXISTS user_data (
                user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                payload TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")

    def create_user(self, user_id, name, email, salt, password_hash, created_at):
        with self.transaction() as connection:
            self._execute(connection, "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                          (user_id, name, email, salt, password_hash, created_at))
            empty_data = json.dumps({"lost": [], "found": [], "matches": [], "activity": []})
            self._execute(connection, "INSERT INTO user_data VALUES (?, ?, ?)", (user_id, empty_data, created_at))

    def get_user_by_email(self, email):
        with self.transaction() as connection:
            row = self._execute(connection, "SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id):
        with self.transaction() as connection:
            row = self._execute(connection, "SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def create_session(self, token_hash, user_id, expires_at):
        with self.transaction() as connection:
            self._execute(connection, "INSERT INTO sessions VALUES (?, ?, ?)", (token_hash, user_id, expires_at))

    def get_session_user(self, token_hash, now):
        with self.transaction() as connection:
            row = self._execute(connection, """SELECT u.id, u.name, u.email FROM sessions s
                JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at >= ?""",
                (token_hash, now)).fetchone()
            return dict(row) if row else None

    def delete_session(self, token_hash):
        with self.transaction() as connection:
            self._execute(connection, "DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def read_user_data(self, user_id):
        with self.transaction() as connection:
            row = self._execute(connection, "SELECT payload FROM user_data WHERE user_id = ?", (user_id,)).fetchone()
            return json.loads(row["payload"]) if row else {"lost": [], "found": [], "matches": [], "activity": []}

    def save_user_data(self, user_id, payload, updated_at):
        encoded = json.dumps(payload, ensure_ascii=False)
        with self.transaction() as connection:
            self._execute(connection, """INSERT INTO user_data VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET payload = excluded.payload,
                updated_at = excluded.updated_at""", (user_id, encoded, updated_at))
