"""Tests for V1 Final additions: PII scrub, InjectionGate, PreferencePrior, Brain wiring.
Pure stdlib. Every new capability is covered here."""

from __future__ import annotations

from inmem.pii import PiiScrubber
from inmem.inject_gate import InjectionGate
from inmem.brain import Brain


# ---------------------------------------------------------------- PII
def test_pii_scrubs_email_and_winpath():
    s = PiiScrubber()
    res = s.scrub("contact john.doe@gmail.com from C:\\Users\\nacha\\secret.md")
    assert "john.doe@gmail.com" not in res.clean
    assert "C:\\Users\\nacha" not in res.clean
    assert "email" in res.found and "win_userpath" in res.found

def test_pii_allows_public_placeholder_email():
    s = PiiScrubber()
    res = s.scrub("write to user@example.com please")
    assert res.clean == "write to user@example.com please"
    assert res.found == []

def test_pii_scrubs_ipv4_and_unix_home():
    s = PiiScrubber()
    res = s.scrub("server 192.168.1.50 path /home/nacha/data")
    assert "192.168.1.50" not in res.clean
    assert "/home/nacha" not in res.clean
    assert "ipv4" in res.found and "unix_userpath" in res.found


# ------------------------------------------------------- InjectionGate
def test_inject_gate_admits_relevant_fresh():
    b = Brain()
    b.remember("FalkorDB chosen for graph-native queries", category="decision")
    row = b.store.active()[0]
    d = b.inject_gate.evaluate("graph native database falkordb", row)
    assert d.admit is True and d.relevance > 0

def test_inject_gate_blocks_superseded():
    b = Brain()
    r1 = b.remember("Use SQLite for storage", category="decision")
    r2 = b.remember("Use FalkorDB for storage now", category="decision")
    b.store.supersede(r1.memory_id, r2.memory_id)
    old = b.store.get(r1.memory_id)
    d = b.inject_gate.evaluate("storage database", old)
    assert d.superseded is True and d.admit is False

def test_inject_gate_pinned_floor():
    b = Brain()
    b.remember("Quy tắc: luôn redact secret", category="instruction", pinned=True)
    row = [r for r in b.store.active() if r["pinned"]][0]
    # even a low-overlap query admits a pinned, non-sensitive rule
    d = b.inject_gate.evaluate("xyz unrelated", row)
    assert d.admit is True and "pinned (rule/identity)" in d.reasons

def test_recall_for_context_filters():
    b = Brain()
    b.remember("FalkorDB chosen for graph-native queries", category="decision")
    b.remember("Nấng thích trà sữa trân châu", category="preference")
    ctx = b.recall_for_context("graph database falkordb", top_k=3)
    assert ctx, "expected at least one admitted memory"
    top_hit, decision = ctx[0]
    assert "FalkorDB" in top_hit.memory["content"]
    assert decision.admit is True


# ---------------------------------------------------- PreferencePrior
def test_preference_prior_ranks_with_evidence():
    b = Brain()
    b.remember("Opus 4.6 cho depth tốt, viết truyện pass", category="decision", salience=0.7)
    b.remember("Sonnet thiếu depth, fail cho novel", category="error", salience=0.6)
    ranking = b.prefer(["Opus 4.6", "Sonnet"], context="viết truyện depth")
    assert ranking[0].option == "Opus 4.6"
    assert ranking[0].prior_score > ranking[-1].prior_score
    # influence is inspectable
    assert ranking[0].visible_when_asked is True
    assert ranking[0].reason_sources  # at least one supporting memory id

def test_preference_prior_neutral_without_evidence():
    b = Brain()
    b.remember("Nấng thích cà phê", category="preference")
    ranking = b.prefer(["OptionX", "OptionY"])
    # no decisive evidence -> neutral, and reasons say so
    assert all(abs(o.prior_score - 0.5) < 1e-9 for o in ranking)
    assert any("neutral prior" in r for o in ranking for r in o.reasons)
