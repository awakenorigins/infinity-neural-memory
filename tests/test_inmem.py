"""Full test suite for Infinity Neural Memory V1. Pure stdlib — runs anywhere.
Every public capability has a test here; if it isn't tested, it isn't claimed.
"""

from __future__ import annotations

import json
import pytest

from inmem.redaction import Redactor
from inmem import vietnamese as vn
from inmem.embedding import HashingEmbedder, cosine
from inmem.store import MemoryStore
from inmem.timeline import Timeline
from inmem.retrieval import hybrid_search
from inmem.admission import AdmissionGate
from inmem.preaction import PreActionGate
from inmem.brain import Brain, extract_facts
from inmem.bridge import DryRunBridge, sync_timeline
from inmem.digest import compute_digest, render_digest, ConsoleNotifier


# ---------------------------------------------------------------- redaction
def test_redaction_masks_secrets_and_keeps_hash():
    r = Redactor()
    res = r.redact("my key is sk-abcdefghijklmnopqrstuvwx and password: hunter2xy")
    assert "sk-abcdefghij" not in res.clean
    assert "hunter2xy" not in res.clean
    assert "openai_key" in res.found
    assert "password_kv" in res.found
    assert len(res.original_sha256) == 64

def test_redaction_clean_text_untouched():
    r = Redactor()
    res = r.redact("hôm nay forge chương 101 xong")
    assert res.found == []
    assert res.clean == "hôm nay forge chương 101 xong"

def test_redaction_github_and_jwt():
    r = Redactor()
    res = r.redact("token ghp_0123456789abcdefghijklmnopqrstuvwx jwt "
                   "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N")
    assert "github_token" in res.found and "jwt" in res.found


# --------------------------------------------------------------- vietnamese
def test_strip_tones():
    assert vn.strip_tones("Quyết Định") == "Quyet Dinh"
    assert vn.strip_tones("đường") == "duong"

def test_tokenize_compounds():
    toks = vn.tokenize("một quyết định kiến trúc quan trọng")
    assert "quyet_dinh" in toks
    assert "kien_truc" in toks

def test_is_cjk():
    assert vn.is_cjk("日本語") is True
    assert vn.is_cjk("tiếng việt") is False


# --------------------------------------------------------------- embedding
def test_embedder_deterministic_and_normalized():
    e = HashingEmbedder(dim=128)
    v1 = e.embed("quyết định kiến trúc")
    v2 = e.embed("quyết định kiến trúc")
    assert v1 == v2
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-6

def test_cosine_self_is_one():
    e = HashingEmbedder()
    v = e.embed("hello world memory")
    assert cosine(v, v) == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------------------------- store
def test_store_remember_and_active():
    s = MemoryStore()
    mid = s.remember("x", "x", "h1", category="fact")
    assert s.get(mid) is not None
    assert len(s.active()) == 1

def test_store_supersede_marks_old_inactive():
    s = MemoryStore()
    old = s.remember("old fact", "old fact", "h1")
    new = s.remember("new fact", "new fact", "h2")
    s.supersede(old, new)
    active_ids = {r["id"] for r in s.active()}
    assert new in active_ids and old not in active_ids
    assert s.get(new)["supersedes"] == old

def test_store_scope_isolation():
    s = MemoryStore()
    s.remember("g", "g", "h1", scope="global")
    s.remember("p", "p", "h2", scope="projectA")
    s.remember("q", "q", "h3", scope="projectB")
    ids = {r["norm_text"] for r in s.active(scope="projectA")}
    assert ids == {"g", "p"}  # sees own scope + global, not projectB


# ---------------------------------------------------------------- timeline
def test_timeline_append_read_and_redacts(tmp_path):
    tl = Timeline(str(tmp_path / "tl"))
    tl.append({"type": "user_msg", "content": "key sk-abcdefghijklmnopqrstuvwx here"})
    tl.append({"type": "agent_resp", "content": "ok"})
    evs = tl.read()
    assert len(evs) == 2
    assert "sk-abcdefghij" not in evs[0]["content"]
    assert evs[0]["redacted"] == ["openai_key"]
    assert len(evs[0]["content_sha256"]) == 64

def test_timeline_after_ts_filter(tmp_path):
    tl = Timeline(str(tmp_path / "tl"))
    a = tl.append({"type": "x", "content": "a"})
    tl.append({"type": "x", "content": "b"})
    later = tl.read(after_ts=a["ts"])
    assert [e["content"] for e in later] == ["b"]


# --------------------------------------------------------------- retrieval
def test_hybrid_search_finds_relevant():
    s = MemoryStore()
    e = HashingEmbedder()
    s.remember("Chọn FalkorDB vì graph-native", vn.normalize("Chọn FalkorDB vì graph-native"), "h1", category="decision")
    s.remember("Nấng thích lazy recall vì token cost", vn.normalize("Nấng thích lazy recall vì token cost"), "h2", category="preference")
    s.remember("Citadel dùng Keycloak OAuth", vn.normalize("Citadel dùng Keycloak OAuth"), "h3", category="reference")
    hits = hybrid_search(s, "graph database falkordb", top_k=2, embedder=e)
    assert hits and hits[0].memory["content_hash"] == "h1"

def test_pinned_boost_changes_order():
    s = MemoryStore()
    s.remember("alpha note about cats", "alpha note about cats", "h1")
    s.remember("beta note about cats", "beta note about cats", "h2", pinned=True)
    hits = hybrid_search(s, "note about cats", top_k=2)
    assert hits[0].memory["pinned"] == 1


# --------------------------------------------------------------- admission
def test_admission_blocks_secret():
    s = MemoryStore()
    g = AdmissionGate()
    res = g.evaluate(s, "the prod password: superSecret123")
    assert res.admit is False and res.action == "block" and res.sensitive

def test_admission_blocks_low_confidence():
    s = MemoryStore()
    g = AdmissionGate(min_confidence=0.5)
    res = g.evaluate(s, "maybe something", confidence=0.2)
    assert res.admit is False and "confidence" in " ".join(res.reasons)

def test_admission_skips_exact_duplicate():
    s = MemoryStore()
    g = AdmissionGate()
    r = Redactor().redact("same content here")
    s.remember(r.clean, vn.normalize(r.clean), r.original_sha256)
    res = g.evaluate(s, "same content here")
    assert res.action == "skip" and res.duplicate_of is not None

def test_admission_inserts_novel():
    s = MemoryStore()
    g = AdmissionGate()
    res = g.evaluate(s, "a totally novel confident statement about kestrels")
    assert res.admit and res.action == "insert"


# --------------------------------------------------------------- pre-action
def test_preaction_flags_past_failure():
    b = Brain()
    b.remember("Deploy auth service crash vì thiếu env var", category="error", salience=0.6)
    v = b.pre_action("deploy", "auth service")
    assert v.risk in ("medium", "high")
    assert any("past failure" in w for w in v.warnings)

def test_preaction_high_risk_on_rule():
    b = Brain()
    b.remember("Quy tắc: không bao giờ deploy thẳng lên prod thứ sáu", category="instruction", salience=0.9, pinned=True)
    v = b.pre_action("deploy", "prod")
    assert v.risk == "high" and v.proceed is False

def test_preaction_low_risk_when_clean():
    b = Brain()
    b.remember("Nấng thích trà sữa", category="preference")
    v = b.pre_action("refactor", "logging module")
    assert v.risk == "low" and v.proceed is True


# ------------------------------------------------------------------- brain
def test_extract_facts_workflow_regex_fix():
    # the exact case the audit said V3.3 missed
    facts = extract_facts("Ch101 hoàn thành, score 72/80")
    cats = {f["cat"] for f in facts}
    assert "workflow" in cats

def test_brain_log_exchange_writes_timeline_and_store():
    b = Brain()
    res = b.log_exchange("Chọn Opus 4.6 vì Sonnet thiếu depth", "Đã ghi nhận.", session_id="s1")
    assert any(r.memory_id for r in res)
    evs = b.timeline.read()
    assert {e["type"] for e in evs} >= {"user_msg", "agent_resp", "extract"}
    assert b.stats()["active"] >= 1

def test_brain_remember_then_recall():
    b = Brain()
    b.remember("FalkorDB chosen for graph-native queries", category="decision")
    hits = b.recall("graph native database")
    assert hits and "FalkorDB" in hits[0].memory["content"]

def test_brain_secret_never_persisted():
    b = Brain()
    res = b.remember("api_key: sk-abcdefghijklmnopqrstuvwx")
    assert res.memory_id is None  # blocked by admission
    # and nothing with the raw secret exists
    assert all("sk-abcdefghij" not in r["content"] for r in b.store.all())


# ------------------------------------------------------------------ bridge
def test_dryrun_bridge_is_honest():
    b = Brain()
    b.log_exchange("Chọn X vì Y", "ok", session_id="s1")
    bridge = DryRunBridge()
    report = sync_timeline(b.timeline, bridge)
    assert report.mode == "dry-run"
    assert report.written == 0           # honest: nothing actually persisted externally
    assert report.attempted >= 1
    assert len(bridge.calls) == report.attempted


# ------------------------------------------------------------------ digest
def test_digest_counts_and_renders():
    b = Brain()
    b.log_exchange("Quy tắc: luôn dùng Opus", "ok", session_id="s1")
    b.log_exchange("api_key: sk-abcdefghijklmnopqrstuvwx", "ok", session_id="s1")
    d = compute_digest(b.timeline, b.store)
    assert d["events_total"] >= 4
    assert d["redactions"] >= 1
    text = render_digest(d)
    assert "Daily Digest" in text

def test_console_notifier_reports_delivery(capsys):
    n = ConsoleNotifier()
    res = n.send("hello")
    assert res.channel == "console" and res.delivered is True
    assert "hello" in capsys.readouterr().out
