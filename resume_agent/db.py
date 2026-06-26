from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ParseResult


DEFAULT_DB_PATH = "data/resumes.sqlite3"


class ResumeRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("RESUME_DB_PATH") or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def save(self, result: ParseResult, source_filename: str = "") -> int:
        payload = result.to_dict()
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO parsed_resumes (
                    source_filename,
                    name,
                    email,
                    phone,
                    parser,
                    model,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_filename,
                    result.name,
                    result.email,
                    result.phone,
                    result.parser,
                    result.model,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def get(self, resume_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, source_filename, payload_json, created_at
                FROM parsed_resumes
                WHERE id = ?
                """,
                (resume_id,),
            ).fetchone()

        if row is None:
            return None

        payload = json.loads(row["payload_json"])
        return {
            "id": row["id"],
            "source_filename": row["source_filename"],
            "created_at": row["created_at"],
            "result": payload,
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS parsed_resumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_filename TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    parser TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_parsed_resumes_email
                ON parsed_resumes(email)
                """
            )
