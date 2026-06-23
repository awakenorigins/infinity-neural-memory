"""End-to-end demo of Infinity Neural Memory V1.

Run:  python examples/demo.py
Uses a throwaway temp dir, so it leaves nothing behind. Every line below exercises a real,
tested capability — no mocks, no external services.
"""

from __future__ import annotations

import tempfile

from inmem.brain import Brain
from inmem.bridge import DryRunBridge, sync_timeline


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        brain = Brain(db_path=":memory:", timeline_dir=td + "/timeline")

        print("== 1. Remember (goes through the AdmissionGate) ==")
        r = brain.remember("Chọn FalkorDB vì graph-native tốt hơn SQLite", category="decision")
        print("   inserted:", r.memory_id, "| reasons:", r.admission.reasons)

        print("\n== 2. A secret is BLOCKED, never persisted ==")
        s = brain.remember("prod api_key: sk-abcdefghijklmnopqrstuvwx")
        print("   memory_id:", s.memory_id, "| action:", s.admission.action,
              "| reasons:", s.admission.reasons)

        print("\n== 3. A rule (pinned), then a duplicate is skipped ==")
        brain.remember("Quy tắc: không bao giờ deploy prod thứ sáu",
                       category="instruction", salience=0.9, pinned=True)
        dup = brain.remember("Chọn FalkorDB vì graph-native tốt hơn SQLite", category="decision")
        print("   duplicate action:", dup.admission.action)

        print("\n== 4. Log an exchange (timeline + auto-extract, with redaction) ==")
        brain.log_exchange("Ch101 hoàn thành, score 72/80", "ok", session_id="s1")
        brain.log_exchange("token sk-abcdefghijklmnopqrstuvwx bị lộ", "đã xử lý", session_id="s1")

        print("\n== 5. Hybrid recall (BM25 + vector + RRF) ==")
        for h in brain.recall("graph database", top_k=3):
            print(f"   [{h.score:.3f}] ({h.memory['category']}) {h.memory['content']}")

        print("\n== 6. Pre-action gate: 'have we failed/ruled against this?' ==")
        v = brain.pre_action("deploy", "prod")
        print("   proceed:", v.proceed, "| risk:", v.risk)
        for w in v.warnings:
            print("   -", w)

        print("\n== 7. Honest external sync (dry-run reports the truth) ==")
        report = sync_timeline(brain.timeline, DryRunBridge())
        print("   mode:", report.mode, "| attempted:", report.attempted, "| written:", report.written)

        print("\n== 8. Daily digest (real counts) ==")
        print(brain.digest_text())

        print("\n== 9. Injection gate: only safe + relevant memories reach context ==")
        for hit, decision in brain.recall_for_context("graph database falkordb", top_k=3):
            print(f"   admit[{decision.score:.2f}] {hit.memory['content'][:50]} | {decision.reasons}")

        print("\n== 10. Explainable Preference Prior (V4, with a reason ledger) ==")
        brain.remember("Opus 4.6 depth tốt cho novel, pass", category="decision", salience=0.7)
        brain.remember("Sonnet thiếu depth, fail cho novel", category="error", salience=0.6)
        for opt in brain.prefer(["Opus 4.6", "Sonnet"], context="viết truyện depth"):
            print(f"   {opt.option}: prior={opt.prior_score} (support={opt.support_count})")
            for r in opt.reasons:
                print(f"       {r}")


if __name__ == "__main__":
    main()
