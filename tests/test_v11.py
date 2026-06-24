"""Tests for V1.1: FTS5 candidate retrieval, embedding cache, BM25 fallback, schema migration,
and pluggable embedder signatures. Pure stdlib (no network)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from inmem.brain import Brain
from inmem.store import MemoryStore, _fts_text
from inmem.embedding import HashingEmbedder
from inmem.retrieval import hybrid_search


# ---- FTS5 + store ------------------------------------------------------------
def test_store_reports_fts_enabled():
    s = MemoryStore()
    assert s.stats()["fts_enabled"] is True  # SQLite in CI has FTS5
    assert s.stats()["schema_version"] == 2

def test_fts_candidates_returns_active_matches():
    s = MemoryStore()
    a = s.remember("FalkorDB graph native database", "falkordb graph native database", "h1")
    s.remember("trà sữa trân châu ngon", "tra sua tran chau ngon", "h2")
    cands = s.fts_candidates("graph database")
    ids = [i for i, _ in cands]
    assert a in ids and len(ids) >= 1

def test_fts_excludes_superseded():
    s = MemoryStore()
    old = s.remember("use mysql for cache", "use mysql for cache", "h1")
    new = s.remember("use redis for cache now", "use redis for cache now", "h2")
    s.supersede(old, new)
    ids = [i for i, _ in s.fts_candidates("cache")]
    assert old not in ids and new in ids


# ---- embedding cache ---------------------------------------------------------
def test_embedding_cached_after_recall_lazy():
    b = Brain()  # default lazy
    b.remember("Citadel uses Keycloak OAuth", category="reference")
    assert b.stats()["embeddings_cached"] == 0  # not embedded at write
    b.recall("Keycloak OAuth")                    # lazy-fills the cache for candidates
    assert b.stats()["embeddings_cached"] >= 1

def test_eager_embed_caches_on_write():
    b = Brain(eager_embed=True)
    b.remember("Citadel uses Keycloak OAuth", category="reference")
    assert b.stats()["embeddings_cached"] >= 1

def test_get_embedding_respects_signature():
    s = MemoryStore()
    mid = s.remember("hello world", "hello world", "h1")
    e = HashingEmbedder(dim=64)
    s.set_embedding(mid, e.embed("hello world"), e.sig)
    assert s.get_embedding(mid, e.sig) is not None
    assert s.get_embedding(mid, "different-sig") is None  # invalidated on embedder change

def test_recall_finds_relevant_with_cache():
    b = Brain()
    b.remember("FalkorDB chosen for graph-native queries", category="decision")
    b.remember("Nấng thích trà sữa", category="preference")
    hits = b.recall("graph database falkordb")
    assert hits and "FalkorDB" in hits[0].memory["content"]


# ---- BM25 fallback when FTS disabled ----------------------------------------
def test_bm25_fallback_when_fts_disabled():
    s = MemoryStore()
    s.fts_enabled = False  # simulate an environment without FTS5
    s.remember("FalkorDB graph native", "falkordb graph native", "h1")
    s.remember("unrelated trà sữa", "unrelated tra sua", "h2")
    hits = hybrid_search(s, "graph native", embedder=HashingEmbedder())
    assert hits and "FalkorDB" in hits[0].memory["content"]


# ---- migration from a v1 database -------------------------------------------
def test_migration_from_v1_schema():
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "old.db")
        # build a minimal v1-style db: no embedding cols, no mem_fts
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE schema_version (version INTEGER)")
        conn.execute("INSERT INTO schema_version VALUES (1)")
        conn.execute("""CREATE TABLE memories (
            id TEXT PRIMARY KEY, content TEXT, norm_text TEXT, content_hash TEXT,
            category TEXT DEFAULT 'fact', salience REAL DEFAULT 0.5, confidence REAL DEFAULT 0.7,
            trust REAL DEFAULT 0.7, scope TEXT DEFAULT 'global', tags TEXT DEFAULT '[]',
            pinned INTEGER DEFAULT 0, sensitive INTEGER DEFAULT 0, tier INTEGER DEFAULT 0,
            freq INTEGER DEFAULT 0, source_event_id TEXT, created_at TEXT, valid_from TEXT,
            valid_to TEXT, supersedes TEXT)""")
        conn.execute("""INSERT INTO memories (id, content, norm_text, content_hash, created_at,
            valid_from) VALUES ('old1', 'FalkorDB graph', 'falkordb graph', 'h1', '2026-01-01', '2026-01-01')""")
        conn.commit(); conn.close()

        # open with V1.1 store -> should migrate (add cols, create+backfill FTS, bump version)
        s = MemoryStore(path)
        assert s.stats()["schema_version"] == 2
        cols = {r[1] for r in s.conn.execute("PRAGMA table_info(memories)").fetchall()}
        assert "embedding" in cols and "embedder_sig" in cols
        # FTS backfilled -> old row is searchable
        ids = [i for i, _ in s.fts_candidates("graph")]
        assert "old1" in ids


# ---- pluggable embedder signature -------------------------------------------
def test_embedder_signatures_differ():
    from inmem.embedding import OpenAIEmbedder, OllamaEmbedder
    assert HashingEmbedder(dim=256).sig == "hashing:256"
    assert "text-embedding-3-small" in OpenAIEmbedder(api_key="x").sig
    assert "nomic-embed-text" in OllamaEmbedder().sig
    # all three distinct -> cache won't collide across providers
    sigs = {HashingEmbedder().sig, OpenAIEmbedder(api_key="x").sig, OllamaEmbedder().sig}
    assert len(sigs) == 3

def test_custom_embedder_injection():
    b = Brain(embedder=HashingEmbedder(dim=64))
    assert b.embedder.dim == 64 and b.embedder.sig == "hashing:64"
    b.remember("graph database", category="fact")
    assert b.recall("graph database")
