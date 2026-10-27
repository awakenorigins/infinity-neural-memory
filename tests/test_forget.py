"""Tests for deliberate erasure (`forget`) — the ONLY deletion path in Infinity Neural Memory.

Proves: forget removes from store + FTS, logs a tombstone, and that automatic mechanisms
(supersession) never delete — only an explicit forget does.
"""

from __future__ import annotations

from inmem.brain import Brain
from inmem.store import MemoryStore


def test_forget_removes_from_store():
    s = MemoryStore()
    mid = s.remember("ephemeral fact", "ephemeral fact", "h1")
    assert s.get(mid) is not None
    assert s.forget(mid, reason="test") is True
    assert s.get(mid) is None                      # gone for good
    assert len(s.all()) == 0

def test_forget_removes_from_fts_index():
    s = MemoryStore()
    mid = s.remember("FalkorDB graph database", "falkordb graph database", "h1")
    assert any(i == mid for i, _ in s.fts_candidates("graph"))
    s.forget(mid, reason="secret leaked")
    assert all(i != mid for i, _ in s.fts_candidates("graph"))   # not retrievable anymore

def test_forget_nonexistent_returns_false():
    s = MemoryStore()
    assert s.forget("does-not-exist") is False

def test_brain_forget_logs_tombstone_without_content(tmp_path):
    b = Brain(timeline_dir=str(tmp_path / "tl"))   # isolated timeline for an exact count
    r = b.remember("api usage note about kestrels", category="fact")
    assert b.store.get(r.memory_id) is not None
    assert b.forget(r.memory_id, reason="right-to-forget request", actor="alice") is True
    assert b.store.get(r.memory_id) is None
    events = b.timeline.read()
    tombstones = [e for e in events if e.get("type") == "forget"]
    assert len(tombstones) == 1
    t = tombstones[0]
    assert t["mem_id"] == r.memory_id
    assert t["reason"] == "right-to-forget request" and t["actor"] == "alice"
    assert "content" not in t                       # the act is logged; the content is erased

def test_supersede_never_deletes_only_forget_does():
    b = Brain()
    first = b.remember("Use SQLite for storage layer of the project")
    second = b.remember("Không dùng SQLite nữa, thay bằng FalkorDB cho storage layer")
    # whatever the admission decided, BOTH rows still physically exist (no deletion by supersede)
    assert b.store.get(first.memory_id) is not None
    # only an explicit forget removes one
    b.forget(first.memory_id, reason="cleanup")
    assert b.store.get(first.memory_id) is None
    assert b.store.get(second.memory_id) is not None

def test_recall_excludes_forgotten():
    b = Brain()
    keep = b.remember("Citadel uses Keycloak OAuth")
    drop = b.remember("Temporary debug note mentioning Keycloak")
    b.forget(drop.memory_id, reason="noise")
    hits = b.recall("Keycloak OAuth")
    ids = [h.memory["id"] for h in hits]
    assert drop.memory_id not in ids
    assert keep.memory_id in ids
