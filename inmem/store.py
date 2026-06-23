"""MemoryStore — deterministic SQLite projection of memory with first-class provenance.

Borrows temporal-validity + provenance from Graphiti/Zep and supersession from the
infinity engine, made concrete and testable. Every memory carries:
    source_event_id, created_at, valid_from, valid_to, supersedes, confidence, trust,
    pinned, tier, scope, sensitive.

This is the "what is true now" brain. The append-only Timeline is the "what happened"
ground truth. Rebuild-from-timeline is possible because every row links to source_event_id.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Memory:
    id: str
    content: str
    norm_text: str
    content_hash: str
    category: str = "fact"
    salience: float = 0.5
    confidence: float = 0.7
    trust: float = 0.7
    scope: str = "global"
    tags: list[str] = None  # type: ignore
    pinned: bool = False
    sensitive: bool = False
    tier: int = 0
    freq: int = 0
    source_event_id: str | None = None
    created_at: str = ""
    valid_from: str = ""
    valid_to: str | None = None
    supersedes: str | None = None

    def to_row(self) -> dict:
        d = asdict(self)
        d["tags"] = json.dumps(self.tags or [], ensure_ascii=False)
        d["pinned"] = int(self.pinned)
        d["sensitive"] = int(self.sensitive)
        return d


_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER);
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    norm_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'fact',
    salience REAL NOT NULL DEFAULT 0.5,
    confidence REAL NOT NULL DEFAULT 0.7,
    trust REAL NOT NULL DEFAULT 0.7,
    scope TEXT NOT NULL DEFAULT 'global',
    tags TEXT NOT NULL DEFAULT '[]',
    pinned INTEGER NOT NULL DEFAULT 0,
    sensitive INTEGER NOT NULL DEFAULT 0,
    tier INTEGER NOT NULL DEFAULT 0,
    freq INTEGER NOT NULL DEFAULT 0,
    source_event_id TEXT,
    created_at TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    supersedes TEXT
);
CREATE INDEX IF NOT EXISTS idx_mem_active ON memories(valid_to);
CREATE INDEX IF NOT EXISTS idx_mem_hash ON memories(content_hash);
CREATE INDEX IF NOT EXISTS idx_mem_scope ON memories(scope);
"""


class MemoryStore:
    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_DDL)
        cur = self.conn.execute("SELECT version FROM schema_version LIMIT 1")
        if cur.fetchone() is None:
            self.conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        self.conn.commit()

    # ---- writes -------------------------------------------------------------
    def remember(
        self,
        content: str,
        norm_text: str,
        content_hash: str,
        *,
        category: str = "fact",
        salience: float = 0.5,
        confidence: float = 0.7,
        trust: float = 0.7,
        scope: str = "global",
        tags: list[str] | None = None,
        pinned: bool = False,
        sensitive: bool = False,
        source_event_id: str | None = None,
        supersedes: str | None = None,
    ) -> str:
        mem_id = uuid.uuid4().hex[:16]
        now = _now()
        mem = Memory(
            id=mem_id, content=content, norm_text=norm_text, content_hash=content_hash,
            category=category, salience=salience, confidence=confidence, trust=trust,
            scope=scope, tags=tags or [], pinned=pinned, sensitive=sensitive,
            source_event_id=source_event_id, created_at=now, valid_from=now,
            valid_to=None, supersedes=supersedes,
        )
        row = mem.to_row()
        cols = ",".join(row.keys())
        ph = ",".join("?" for _ in row)
        self.conn.execute(f"INSERT INTO memories ({cols}) VALUES ({ph})", list(row.values()))
        if supersedes:
            self.conn.execute(
                "UPDATE memories SET valid_to=? WHERE id=? AND valid_to IS NULL",
                (now, supersedes),
            )
        self.conn.commit()
        return mem_id

    def supersede(self, old_id: str, new_id: str) -> None:
        self.conn.execute(
            "UPDATE memories SET valid_to=? WHERE id=? AND valid_to IS NULL", (_now(), old_id)
        )
        self.conn.execute("UPDATE memories SET supersedes=? WHERE id=?", (old_id, new_id))
        self.conn.commit()

    def touch(self, mem_id: str) -> None:
        self.conn.execute("UPDATE memories SET freq = freq + 1 WHERE id=?", (mem_id,))
        self.conn.commit()

    # ---- reads --------------------------------------------------------------
    def get(self, mem_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM memories WHERE id=?", (mem_id,)).fetchone()

    def find_hash(self, content_hash: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM memories WHERE content_hash=? AND valid_to IS NULL", (content_hash,)
        ).fetchone()

    def active(self, scope: str | None = None) -> list[sqlite3.Row]:
        if scope:
            q = "SELECT * FROM memories WHERE valid_to IS NULL AND scope IN (?, 'global')"
            return list(self.conn.execute(q, (scope,)).fetchall())
        return list(self.conn.execute("SELECT * FROM memories WHERE valid_to IS NULL").fetchall())

    def all(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM memories").fetchall())

    def stats(self) -> dict:
        c = self.conn.execute
        total = c("SELECT COUNT(*) FROM memories").fetchone()[0]
        active = c("SELECT COUNT(*) FROM memories WHERE valid_to IS NULL").fetchone()[0]
        pinned = c("SELECT COUNT(*) FROM memories WHERE pinned=1").fetchone()[0]
        sensitive = c("SELECT COUNT(*) FROM memories WHERE sensitive=1").fetchone()[0]
        by_cat = {r[0]: r[1] for r in c(
            "SELECT category, COUNT(*) FROM memories WHERE valid_to IS NULL GROUP BY category"
        ).fetchall()}
        return {
            "total": total, "active": active, "superseded": total - active,
            "pinned": pinned, "sensitive": sensitive, "by_category": by_cat,
            "schema_version": SCHEMA_VERSION,
        }

    def close(self) -> None:
        self.conn.close()
