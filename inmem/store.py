"""MemoryStore (V1.1) — SQLite belief store with provenance, FTS5 full-text index, and an
embedding cache.

New in V1.1:
  * FTS5 virtual table for fast BM25 candidate retrieval (replaces scanning every active row),
    with a graceful fallback flag (`fts_enabled`) when FTS5 isn't compiled in.
  * Cached embeddings (vector + embedder signature) so recall never re-embeds the whole store.
Schema bumps to v2; existing v1 databases are migrated in place (additive, non-destructive).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from inmem.vietnamese import tokenize

SCHEMA_VERSION = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fts_text(norm_text: str) -> str:
    return " ".join(tokenize(norm_text))


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
    tags: list = None  # type: ignore
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
    supersedes TEXT,
    embedding TEXT,
    embedder_sig TEXT
);
CREATE INDEX IF NOT EXISTS idx_mem_active ON memories(valid_to);
CREATE INDEX IF NOT EXISTS idx_mem_hash ON memories(content_hash);
CREATE INDEX IF NOT EXISTS idx_mem_scope ON memories(scope);
"""

_FTS_DDL = "CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(mem_id UNINDEXED, fts_text);"


class MemoryStore:
    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._bulk = False
        self.conn.executescript(_DDL)
        self.fts_enabled = self._init_fts()
        self._migrate()
        cur = self.conn.execute("SELECT version FROM schema_version LIMIT 1")
        if cur.fetchone() is None:
            self.conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        else:
            self.conn.execute("UPDATE schema_version SET version=?", (SCHEMA_VERSION,))
        self.conn.commit()

    def _commit(self) -> None:
        if not self._bulk:
            self.conn.commit()

    @contextmanager
    def bulk(self):
        """Defer commits for fast bulk ingestion: `with store.bulk(): ...`. Commits once at exit."""
        self._bulk = True
        try:
            yield self
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self._bulk = False

    def _init_fts(self) -> bool:
        try:
            self.conn.executescript(_FTS_DDL)
            return True
        except sqlite3.OperationalError:
            return False  # FTS5 not compiled in -> retrieval falls back to in-memory BM25

    def _migrate(self) -> None:
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(memories)").fetchall()}
        for col in ("embedding", "embedder_sig"):
            if col not in cols:
                self.conn.execute(f"ALTER TABLE memories ADD COLUMN {col} TEXT")
        if self.fts_enabled:
            n = self.conn.execute("SELECT COUNT(*) FROM mem_fts").fetchone()[0]
            tot = self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            if n == 0 and tot > 0:  # backfill FTS from an older db
                for r in self.conn.execute("SELECT id, norm_text FROM memories").fetchall():
                    self.conn.execute("INSERT INTO mem_fts (mem_id, fts_text) VALUES (?, ?)",
                                      (r["id"], _fts_text(r["norm_text"])))
        self.conn.commit()

    # ---- writes -------------------------------------------------------------
    def remember(self, content: str, norm_text: str, content_hash: str, *,
                 category: str = "fact", salience: float = 0.5, confidence: float = 0.7,
                 trust: float = 0.7, scope: str = "global", tags: list | None = None,
                 pinned: bool = False, sensitive: bool = False,
                 source_event_id: str | None = None, supersedes: str | None = None) -> str:
        mem_id = uuid.uuid4().hex[:16]
        now = _now()
        mem = Memory(id=mem_id, content=content, norm_text=norm_text, content_hash=content_hash,
                     category=category, salience=salience, confidence=confidence, trust=trust,
                     scope=scope, tags=tags or [], pinned=pinned, sensitive=sensitive,
                     source_event_id=source_event_id, created_at=now, valid_from=now,
                     valid_to=None, supersedes=supersedes)
        row = mem.to_row()
        row["embedding"] = None
        row["embedder_sig"] = None
        cols = ",".join(row.keys())
        ph = ",".join("?" for _ in row)
        self.conn.execute(f"INSERT INTO memories ({cols}) VALUES ({ph})", list(row.values()))
        if self.fts_enabled:
            self.conn.execute("INSERT INTO mem_fts (mem_id, fts_text) VALUES (?, ?)",
                              (mem_id, _fts_text(norm_text)))
        if supersedes:
            self.conn.execute("UPDATE memories SET valid_to=? WHERE id=? AND valid_to IS NULL",
                              (now, supersedes))
        self._commit()
        return mem_id

    def supersede(self, old_id: str, new_id: str) -> None:
        self.conn.execute("UPDATE memories SET valid_to=? WHERE id=? AND valid_to IS NULL",
                          (_now(), old_id))
        self.conn.execute("UPDATE memories SET supersedes=? WHERE id=?", (old_id, new_id))
        self._commit()

    def touch(self, mem_id: str) -> None:
        self.conn.execute("UPDATE memories SET freq = freq + 1 WHERE id=?", (mem_id,))
        self._commit()

    def set_embedding(self, mem_id: str, vec: list, sig: str) -> None:
        self.conn.execute("UPDATE memories SET embedding=?, embedder_sig=? WHERE id=?",
                          (json.dumps(vec), sig, mem_id))
        self._commit()

    def get_embedding(self, mem_id: str, sig: str) -> list | None:
        r = self.conn.execute("SELECT embedding, embedder_sig FROM memories WHERE id=?",
                              (mem_id,)).fetchone()
        if r is None or r["embedding"] is None or r["embedder_sig"] != sig:
            return None
        return json.loads(r["embedding"])

    # ---- reads --------------------------------------------------------------
    def get(self, mem_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM memories WHERE id=?", (mem_id,)).fetchone()

    def find_hash(self, content_hash: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM memories WHERE content_hash=? AND valid_to IS NULL", (content_hash,)
        ).fetchone()

    def active(self, scope: str | None = None) -> list:
        if scope:
            q = "SELECT * FROM memories WHERE valid_to IS NULL AND scope IN (?, 'global')"
            return list(self.conn.execute(q, (scope,)).fetchall())
        return list(self.conn.execute("SELECT * FROM memories WHERE valid_to IS NULL").fetchall())

    def fts_candidates(self, query: str, *, limit: int = 200, scope: str | None = None) -> list:
        """Return (mem_id, bm25_score) for ACTIVE memories matching the query via FTS5.
        Lower bm25 = better; caller may treat the returned order as the ranking."""
        if not self.fts_enabled:
            return []
        terms = tokenize(query)
        if not terms:
            return []
        match = " OR ".join('"' + t.replace('"', '') + '"' for t in terms)
        try:
            rows = self.conn.execute(
                "SELECT mem_id, bm25(mem_fts) AS score FROM mem_fts "
                "WHERE mem_fts MATCH ? ORDER BY score LIMIT ?", (match, limit * 2)
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        out = []
        for r in rows:
            row = self.get(r["mem_id"])
            if row is None or row["valid_to"] is not None:
                continue
            if scope and row["scope"] not in (scope, "global"):
                continue
            out.append((r["mem_id"], r["score"]))
            if len(out) >= limit:
                break
        return out

    def all(self) -> list:
        return list(self.conn.execute("SELECT * FROM memories").fetchall())

    def stats(self) -> dict:
        c = self.conn.execute
        total = c("SELECT COUNT(*) FROM memories").fetchone()[0]
        active = c("SELECT COUNT(*) FROM memories WHERE valid_to IS NULL").fetchone()[0]
        pinned = c("SELECT COUNT(*) FROM memories WHERE pinned=1").fetchone()[0]
        sensitive = c("SELECT COUNT(*) FROM memories WHERE sensitive=1").fetchone()[0]
        cached = c("SELECT COUNT(*) FROM memories WHERE embedding IS NOT NULL").fetchone()[0]
        by_cat = {r[0]: r[1] for r in c(
            "SELECT category, COUNT(*) FROM memories WHERE valid_to IS NULL GROUP BY category"
        ).fetchall()}
        return {"total": total, "active": active, "superseded": total - active,
                "pinned": pinned, "sensitive": sensitive, "by_category": by_cat,
                "embeddings_cached": cached, "fts_enabled": self.fts_enabled,
                "schema_version": SCHEMA_VERSION}

    def close(self) -> None:
        self.conn.close()
