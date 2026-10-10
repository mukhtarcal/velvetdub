"""Viewer corrections ("this was missed", "this shouldn't have been filtered").

Kept in SQLite so they can later be used to tune detection thresholds.
"""

import sqlite3
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class CorrectionKind(StrEnum):
    MISSED = "missed"  # something should have been filtered and wasn't
    WRONG = "wrong"  # something was filtered that should not have been


class Correction(BaseModel):
    id: int | None = None
    owner_id: str
    title_id: str
    kind: CorrectionKind
    at_seconds: float = Field(ge=0)
    category: str | None = None
    event_id: str | None = None
    note: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CorrectionRepository(ABC):
    @abstractmethod
    def add(self, correction: Correction) -> Correction: ...

    @abstractmethod
    def list(self, owner_id: str, title_id: str) -> list[Correction]: ...


class SqliteCorrectionRepository(CorrectionRepository):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id TEXT NOT NULL,
                    title_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    at_seconds REAL NOT NULL,
                    category TEXT,
                    event_id TEXT,
                    note TEXT,
                    created_at TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        # One short-lived connection per call keeps this safe across the server's threads.
        return sqlite3.connect(self._db_path)

    def add(self, correction: Correction) -> Correction:
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO corrections (owner_id, title_id, kind, at_seconds, category,"
                " event_id, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    correction.owner_id,
                    correction.title_id,
                    correction.kind.value,
                    correction.at_seconds,
                    correction.category,
                    correction.event_id,
                    correction.note,
                    correction.created_at.isoformat(),
                ),
            )
            return correction.model_copy(update={"id": cursor.lastrowid})

    def list(self, owner_id: str, title_id: str) -> list[Correction]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, owner_id, title_id, kind, at_seconds, category, event_id, note,"
                " created_at FROM corrections WHERE owner_id = ? AND title_id = ? ORDER BY id",
                (owner_id, title_id),
            ).fetchall()
        return [
            Correction(
                id=r[0],
                owner_id=r[1],
                title_id=r[2],
                kind=CorrectionKind(r[3]),
                at_seconds=r[4],
                category=r[5],
                event_id=r[6],
                note=r[7],
                created_at=datetime.fromisoformat(r[8]),
            )
            for r in rows
        ]
