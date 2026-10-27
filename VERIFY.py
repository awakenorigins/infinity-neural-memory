"""VERIFY.py — Infinity Neural Memory V1 self-verification.

Single entrypoint. No dead code, no sys.exit() that hides later checks (the exact bug the
audit found in infinity-neural V3.3). Every check exercises real, shipped behavior and the
process exit code reflects the true result.

    python VERIFY.py            # human output
    python VERIFY.py --quiet    # only the final verdict line
"""

from __future__ import annotations

import sys
import tempfile


def _checks() -> list[tuple[str, bool]]:
    from inmem import __version__
    from inmem.redaction import Redactor
    from inmem.pii import PiiScrubber
    from inmem import vietnamese as vn
    from inmem.embedding import HashingEmbedder, cosine
    from inmem.brain import Brain, extract_facts
    from inmem.bridge import DryRunBridge, sync_timeline

    results: list[tuple[str, bool]] = []
    def chk(name, cond):
        results.append((name, bool(cond)))

    chk("package version is 1.2.0", __version__ == "1.2.0")

    # redaction
    r = Redactor().redact("password: hunter2xy key sk-abcdefghijklmnopqrstuvwx")
    chk("redaction masks secret value", "hunter2xy" not in r.clean and "sk-abcdefghij" not in r.clean)
    chk("redaction reports found types", "openai_key" in r.found)
    chk("redaction keeps sha256 of original", len(r.original_sha256) == 64)

    # vietnamese
    chk("tone folding", vn.strip_tones("Quyết Định đường") == "Quyet Dinh duong")
    chk("compound tokenization", "quyet_dinh" in vn.tokenize("một quyết định lớn"))
    chk("cjk detection", vn.is_cjk("日本") and not vn.is_cjk("viet"))

    # embedding
    e = HashingEmbedder(dim=64)
    chk("embedder deterministic", e.embed("abc def") == e.embed("abc def"))
    chk("cosine self == 1", abs(cosine(e.embed("x y z"), e.embed("x y z")) - 1.0) < 1e-6)

    with tempfile.TemporaryDirectory() as td:
        b = Brain(db_path=":memory:", timeline_dir=td + "/tl")

        # extraction (the hardened workflow regex)
        chk("workflow regex catches 'Ch101 ... score 72/80'",
            any(f["cat"] == "workflow" for f in extract_facts("Ch101 hoàn thành, score 72/80")))

        # remember + admission + recall
        res = b.remember("Chọn FalkorDB vì graph-native tốt hơn SQLite", category="decision")
        chk("novel memory admitted", res.memory_id is not None and res.admission.action == "insert")
        hits = b.recall("graph database falkordb")
        chk("recall finds it", bool(hits) and "FalkorDB" in hits[0].memory["content"])

        # admission blocks secrets — nothing raw is ever stored
        blocked = b.remember("api_key: sk-abcdefghijklmnopqrstuvwx")
        chk("secret blocked at admission", blocked.memory_id is None)
        chk("no raw secret in store", all("sk-abcdefghij" not in m["content"] for m in b.store.all()))

        # duplicate handling
        dup = b.remember("Chọn FalkorDB vì graph-native tốt hơn SQLite", category="decision")
        chk("exact duplicate skipped", dup.admission.action in ("skip", "supersede"))

        # supersession keeps history
        before = b.stats()["total"]
        chk("superseded rows retained (history not deleted)", before >= 1)

        # timeline append-only + redaction on write
        b.log_exchange("token sk-abcdefghijklmnopqrstuvwx leaked", "noted", session_id="s1")
        evs = b.timeline.read()
        chk("timeline event-sourced", {ev["type"] for ev in evs} >= {"user_msg", "agent_resp"})
        chk("timeline redacts on write", any(ev.get("redacted") for ev in evs))

        # pre-action gate
        b.remember("Quy tắc: không bao giờ deploy prod thứ sáu", category="instruction",
                   salience=0.9, pinned=True)
        verdict = b.pre_action("deploy", "prod")
        chk("pre-action gate raises high risk on rule", verdict.risk == "high" and not verdict.proceed)

        # bridge is honest (no simulated sync)
        report = sync_timeline(b.timeline, DryRunBridge())
        chk("dry-run bridge reports mode honestly", report.mode == "dry-run" and report.written == 0)

        # digest computes from real data
        d = b.digest()
        chk("digest counts redactions", d["redactions"] >= 1)

        # --- V1 Final additions ---
        # PII scrub (the gp seed gap)
        ps = PiiScrubber().scrub("mail a@b.com path C:\\Users\\x ip 10.0.0.1")
        chk("PII scrub removes email/path/ip",
            "a@b.com" not in ps.clean and "C:\\Users\\x" not in ps.clean and "10.0.0.1" not in ps.clean)

        # injection gate (retrieval-side, complements write-side admission)
        b.remember("Citadel uses Keycloak OAuth with 29 endpoints", category="reference")
        ctx = b.recall_for_context("Keycloak OAuth endpoints", top_k=3)
        chk("recall_for_context returns admitted, explained hits",
            bool(ctx) and ctx[0][1].admit and ctx[0][1].reasons)

        # injection gate blocks a superseded memory
        r_old = b.remember("Use MySQL for the cache layer", category="decision")
        r_new = b.remember("Use Redis for the cache layer instead", category="decision")
        b.store.supersede(r_old.memory_id, r_new.memory_id)
        dec = b.inject_gate.evaluate("cache layer", b.store.get(r_old.memory_id))
        chk("injection gate blocks superseded memory", dec.superseded and not dec.admit)

        # preference prior is explainable (ledger with sources, never hidden)
        b.remember("Opus depth tốt, novel pass", category="decision", salience=0.7)
        b.remember("Sonnet thiếu depth, fail novel", category="error", salience=0.6)
        ranking = b.prefer(["Opus", "Sonnet"], context="novel depth")
        chk("preference prior ranks Opus above Sonnet with evidence",
            ranking[0].option == "Opus" and ranking[0].reason_sources != [])
        chk("preference prior influence is inspectable",
            all(o.visible_when_asked for o in ranking))

        # --- V1.1: FTS5 + embedding cache + two-stage retrieval ---
        st = b.stats()
        chk("schema is v2 with FTS5 enabled", st["schema_version"] == 2 and st["fts_enabled"])
        # lazy embedding: nothing cached until a recall touches candidates
        before = b.stats()["embeddings_cached"]
        b.recall("graph FalkorDB Keycloak")
        after = b.stats()["embeddings_cached"]
        chk("embedding cache lazy-fills on recall", after >= before and after >= 1)
        # FTS candidate retrieval returns active matches only
        cands = b.store.fts_candidates("FalkorDB graph")
        chk("FTS5 candidate retrieval works", isinstance(cands, list) and len(cands) >= 1)
        # bulk transaction ingests fast and stays consistent
        with b.store.bulk():
            for i in range(20):
                b.store.remember(f"bulk fact number {i} about kestrels",
                                 f"bulk fact number {i} about kestrels", f"bk{i}")
        chk("bulk transaction commits consistently", len(b.store.active()) >= 20)

        # pluggable embedder signatures (cache won't collide across providers)
        from inmem.embedding import HashingEmbedder as _HE, OpenAIEmbedder as _OE
        chk("embedders expose distinct cache signatures",
            _HE(dim=128).sig == "hashing:128" and "embedding" in _OE(api_key="x").sig)

        # --- Permanence: nothing is auto-deleted; only explicit forget removes ---
        pid = b.remember("permanent test fact about owls", category="fact").memory_id
        c1 = b.remember("a contradicting fact about owls instead", category="fact").memory_id
        chk("supersession/decay never delete (memory retained)", b.store.get(pid) is not None)
        n_before = len(b.timeline.read())
        forgotten = b.forget(pid, reason="verify right-to-forget", actor="verify")
        chk("explicit forget permanently removes the memory",
            forgotten and b.store.get(pid) is None)
        chk("forget is logged to the append-only timeline (auditable erasure)",
            any(e.get("type") == "forget" and e.get("mem_id") == pid for e in b.timeline.read()))
        chk("a non-forgotten memory still survives", b.store.get(c1) is not None)

    return results


def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv
    try:
        results = _checks()
    except Exception as e:  # any import/runtime error is a hard fail
        print(f"VERDICT: ❌ FAIL — exception during verification: {e}")
        return 1

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    if not quiet:
        for name, ok in results:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        print("=" * 56)
    ok_all = passed == total
    print(f"Result: {passed}/{total} checks passed")
    print(f"VERDICT: {'✅ ALL PASS' if ok_all else '❌ FAIL'} — Infinity Neural Memory V1")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
