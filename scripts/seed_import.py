"""Seed importer — ingest a directory of markdown memory into the store, SAFELY.

Every chunk passes through PII scrub (emails / IPs / user-home paths) AND the write-side
AdmissionGate (secret block + dedupe + confidence). This is how you bootstrap the brain from
a private corpus without leaking — the exact gap the lab audit found in the gp seed.

    python scripts/seed_import.py --source seed/sample --db /tmp/inm.db --timeline /tmp/inm-tl
    python scripts/seed_import.py --source <your-private-dir> --check    # dry-run report only
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import re
import sys
from pathlib import Path

# allow running from repo root without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inmem.brain import Brain
from inmem.pii import PiiScrubber

_HEADER = re.compile(r"^#{1,6}\s+(.*)$", re.M)


def _chunks(text: str) -> list[tuple[str, str]]:
    """Split a markdown doc into (heading, body) chunks by headers; fallback to whole doc."""
    parts: list[tuple[str, str]] = []
    matches = list(_HEADER.finditer(text))
    if not matches:
        body = text.strip()
        return [("", body)] if body else []
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            parts.append((heading, body))
    return parts


def _category(filename: str, heading: str) -> str:
    h = f"{filename} {heading}".lower()
    if any(k in h for k in ("rule", "quy tắc", "protocol", "persona", "identity")):
        return "instruction"
    if any(k in h for k in ("decision", "chọn", "quyết định")):
        return "decision"
    if any(k in h for k in ("workflow", "plan", "roadmap", "forge")):
        return "workflow"
    if any(k in h for k in ("bug", "error", "lỗi", "debug")):
        return "error"
    return "reference"


def run(source: str, db: str, timeline: str, *, check: bool, max_chars: int) -> dict:
    scrubber = PiiScrubber()
    brain = None if check else Brain(db_path=db, timeline_dir=timeline)
    report = {"files": 0, "chunks": 0, "admitted": 0, "skipped": 0,
              "blocked_secret": 0, "pii_scrubbed": 0, "pii_labels": {}}
    src = Path(source)
    files = sorted(src.rglob("*.md"))
    _ctx = brain.store.bulk() if brain is not None else nullcontext()
    with _ctx:
      for f in files:
        report["files"] += 1
        raw = f.read_text(encoding="utf-8", errors="ignore")
        for heading, body in _chunks(raw):
            report["chunks"] += 1
            scrub = scrubber.scrub(body[:max_chars])
            if scrub.is_pii:
                report["pii_scrubbed"] += 1
                for lbl in scrub.found:
                    report["pii_labels"][lbl] = report["pii_labels"].get(lbl, 0) + 1
            if check:
                continue
            cat = _category(f.name, heading)
            res = brain.remember(scrub.clean, category=cat, salience=0.5, confidence=0.6,
                                 scope=f.stem, tags=[f.stem])
            if res.memory_id is None and res.admission.action == "block":
                report["blocked_secret"] += 1
            elif res.memory_id is None:
                report["skipped"] += 1
            else:
                report["admitted"] += 1
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Safely import a markdown memory corpus.")
    ap.add_argument("--source", required=True)
    ap.add_argument("--db", default="seed-import.db")
    ap.add_argument("--timeline", default="timeline")
    ap.add_argument("--check", action="store_true", help="dry-run: report PII/secret findings only")
    ap.add_argument("--max-chars", type=int, default=2000)
    args = ap.parse_args()
    report = run(args.source, args.db, args.timeline, check=args.check, max_chars=args.max_chars)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
