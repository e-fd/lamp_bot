"""SQLite-хранилище: история сообщений по user_id, роли и времени + заявки."""
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH, log

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    role     TEXT    NOT NULL,          -- user | bot
    text     TEXT    NOT NULL,
    intent   TEXT,
    sentiment REAL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, created_at);

CREATE TABLE IF NOT EXISTS orders (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    name     TEXT,
    phone    TEXT,
    product  TEXT,
    created_at TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, path=DB_PATH):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        log.info("База истории готова: %s", self.path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def save_message(self, user_id: int, role: str, text: str,
                     intent: str | None = None, sentiment: float | None = None) -> None:
        self.conn.execute(
            "INSERT INTO messages (user_id, role, text, intent, sentiment, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, role, text, intent, sentiment, self._now()),
        )
        self.conn.commit()

    def history(self, user_id: int, limit: int = 10) -> list[tuple[str, str]]:
        rows = self.conn.execute(
            "SELECT role, text FROM messages WHERE user_id = ?"
            " ORDER BY id DESC LIMIT ?", (user_id, limit),
        ).fetchall()
        return list(reversed(rows))

    def save_order(self, user_id: int, name: str, phone: str, product: str) -> int:
        cursor = self.conn.execute(
            "INSERT INTO orders (user_id, name, phone, product, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, name, phone, product, self._now()),
        )
        self.conn.commit()
        log.info("ЗАЯВКА #%s | user=%s | %s | %s | %s",
                 cursor.lastrowid, user_id, name, phone, product)
        return cursor.lastrowid

    def close(self) -> None:
        self.conn.close()
