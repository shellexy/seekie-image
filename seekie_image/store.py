"""SQLite：对话和每一次生成记录。图片本体放在磁盘上，这里只记文件名。"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    prompt      TEXT NOT NULL,
    params      TEXT NOT NULL,
    refs        TEXT NOT NULL DEFAULT '[]',
    images      TEXT NOT NULL DEFAULT '[]',
    status      TEXT NOT NULL,
    error       TEXT,
    created_at  REAL NOT NULL,
    finished_at REAL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
"""


def _now() -> float:
    return time.time()


def _message(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "prompt": row["prompt"],
        "params": json.loads(row["params"]),
        "refs": json.loads(row["refs"]),
        "images": json.loads(row["images"]),
        "status": row["status"],
        "error": row["error"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }


class Store:
    def __init__(self, path: Path):
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _all(self, sql: str, args=()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def _run(self, sql: str, args=()) -> int:
        with self._lock:
            return self._db.execute(sql, args).rowcount

    # ---- 对话 ----

    def create_session(self, title: str) -> dict:
        sid, now = uuid.uuid4().hex, _now()
        self._run("INSERT INTO sessions VALUES (?,?,?,?)", (sid, title, now, now))
        return self.session(sid)

    def session(self, sid: str) -> dict | None:
        rows = self._all("SELECT * FROM sessions WHERE id=?", (sid,))
        return self._session(rows[0]) if rows else None

    def sessions(self) -> list[dict]:
        rows = self._all("SELECT * FROM sessions ORDER BY updated_at DESC")
        return [self._session(row) for row in rows]

    def _session(self, row: sqlite3.Row) -> dict:
        thumb = None
        done = self._all(
            "SELECT images FROM messages WHERE session_id=? AND status='done' "
            "ORDER BY created_at DESC LIMIT 1",
            (row["id"],),
        )
        if done:
            images = json.loads(done[0]["images"])
            if images:
                thumb = images[0]["thumb"]
        pending = self._all(
            "SELECT COUNT(*) AS n FROM messages WHERE session_id=? AND status='pending'",
            (row["id"],),
        )[0]["n"]
        return {
            "id": row["id"],
            "title": row["title"],
            "updated_at": row["updated_at"],
            "thumb": thumb,
            "pending": pending,
        }

    def rename_session(self, sid: str, title: str) -> None:
        self._run("UPDATE sessions SET title=? WHERE id=?", (title, sid))

    def delete_session(self, sid: str) -> None:
        self._run("DELETE FROM sessions WHERE id=?", (sid,))

    # ---- 生成记录 ----

    def add_message(self, session_id: str, prompt: str, params: dict, refs: list) -> dict:
        mid, now = uuid.uuid4().hex, _now()
        dump = lambda value: json.dumps(value, ensure_ascii=False)
        with self._lock:
            self._run(
                "INSERT INTO messages (id, session_id, prompt, params, refs, status, created_at) "
                "VALUES (?,?,?,?,?,'pending',?)",
                (mid, session_id, prompt, dump(params), dump(refs), now),
            )
            self._run("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        return self.message(mid)

    def message(self, mid: str) -> dict | None:
        rows = self._all("SELECT * FROM messages WHERE id=?", (mid,))
        return _message(rows[0]) if rows else None

    def messages(self, session_id: str) -> list[dict]:
        rows = self._all(
            "SELECT * FROM messages WHERE session_id=? ORDER BY created_at", (session_id,)
        )
        return [_message(row) for row in rows]

    def finish_message(self, mid: str, status: str, *, images=None, error=None) -> bool:
        """只更新仍在 pending 的记录：用户取消之后，迟到的结果不会把状态改回去。"""
        changed = self._run(
            "UPDATE messages SET status=?, images=?, error=?, finished_at=? "
            "WHERE id=? AND status='pending'",
            (status, json.dumps(images or [], ensure_ascii=False), error, _now(), mid),
        )
        return changed > 0

    def delete_message(self, mid: str) -> None:
        self._run("DELETE FROM messages WHERE id=?", (mid,))

    def fail_stale_pending(self, reason: str) -> None:
        self._run(
            "UPDATE messages SET status='error', error=?, finished_at=? WHERE status='pending'",
            (reason, _now()),
        )

    def referenced_files(self) -> set[str]:
        names: set[str] = set()
        for row in self._all("SELECT refs, images FROM messages"):
            for item in json.loads(row["refs"]) + json.loads(row["images"]):
                names.add(item["file"])
                names.add(item["thumb"])
        return names
