"""inmem CLI — thin wrapper over Brain. Honest, scriptable, no hidden behavior.

    python -m inmem.cli remember "Chọn Opus 4.6 vì depth" --category decision --pin
    python -m inmem.cli recall "model viết truyện"
    python -m inmem.cli log --user "Ch101 xong, score 72/80" --agent "ok"
    python -m inmem.cli preaction --action deploy --target prod
    python -m inmem.cli digest
    python -m inmem.cli stats
    python -m inmem.cli sync            # dry-run by default (honest)
"""

from __future__ import annotations

import argparse
import json
import os

from inmem.brain import Brain
from inmem.bridge import DryRunBridge, SubprocessBridge, sync_timeline

DB = os.environ.get("INMEM_DB", os.path.expanduser("~/.inmem/memory.db"))
TL = os.environ.get("INMEM_TIMELINE", os.path.expanduser("~/.inmem/timeline"))


def _brain() -> Brain:
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    return Brain(db_path=DB, timeline_dir=TL)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="inmem", description="Infinity Neural Memory V1")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("remember"); r.add_argument("content")
    r.add_argument("--category", default="fact"); r.add_argument("--salience", type=float, default=0.5)
    r.add_argument("--confidence", type=float, default=0.7); r.add_argument("--scope", default="global")
    r.add_argument("--pin", action="store_true")

    q = sub.add_parser("recall"); q.add_argument("query")
    q.add_argument("--top", type=int, default=5); q.add_argument("--scope", default=None)

    lg = sub.add_parser("log"); lg.add_argument("--user", required=True); lg.add_argument("--agent", default="")
    lg.add_argument("--session", default="cli")

    pa = sub.add_parser("preaction"); pa.add_argument("--action", required=True); pa.add_argument("--target", default="")

    sub.add_parser("digest")
    sub.add_parser("stats")
    sy = sub.add_parser("sync"); sy.add_argument("--real", action="store_true", help="use nmem CLI if installed")

    args = p.parse_args(argv)
    b = _brain()

    if args.cmd == "remember":
        res = b.remember(args.content, category=args.category, salience=args.salience,
                         confidence=args.confidence, scope=args.scope, pinned=args.pin)
        print(json.dumps({"memory_id": res.memory_id, "action": res.admission.action,
                          "reasons": res.admission.reasons}, ensure_ascii=False, indent=2))
    elif args.cmd == "recall":
        hits = b.recall(args.query, top_k=args.top, scope=args.scope)
        for h in hits:
            print(f"[{h.score:.3f}] ({h.memory['category']}) {h.memory['content']}")
        if not hits:
            print("(no matches)")
    elif args.cmd == "log":
        res = b.log_exchange(args.user, args.agent, session_id=args.session)
        print(json.dumps({"extracted": len(res),
                          "admitted": sum(1 for x in res if x.memory_id)}, ensure_ascii=False))
    elif args.cmd == "preaction":
        v = b.pre_action(args.action, args.target)
        print(json.dumps({"proceed": v.proceed, "risk": v.risk, "warnings": v.warnings},
                         ensure_ascii=False, indent=2))
    elif args.cmd == "digest":
        print(b.digest_text())
    elif args.cmd == "stats":
        print(json.dumps(b.stats(), ensure_ascii=False, indent=2))
    elif args.cmd == "sync":
        bridge = SubprocessBridge() if args.real else DryRunBridge()
        rep = sync_timeline(b.timeline, bridge)
        print(json.dumps(rep.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
