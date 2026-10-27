"""Timeline — append-only, event-sourced ground truth (JSONL, one file/day).

Distilled from infinity-neural V3.3's session logger, with the two fixes both audits
demanded:
  * REDACTION on every write (no raw secrets ever hit disk).        (Mula P0)
  * FILE LOCK around append (concurrent sub-agents won't interleave). (Mula P1)
  * symlink LATEST has a copy fallback for Windows/locked-down FS.    (Mula P1)

Events are immutable. Never edit, never delete. The MemoryStore is a *projection* of
this log, so a corrupted projection can always be rebuilt from the timeline.
"""

from __future__ import annotations

import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from inmem.redaction import Redactor

try:  # POSIX advisory lock; degrade gracefully where unavailable
    import fcntl
    _HAVE_FCNTL = True
except Exception:  # pragma: no cover - platform dependent
    _HAVE_FCNTL = False

_TZ = timezone(timedelta(hours=7))  # default GMT+7; override via tz arg
MAX_CONTENT = 2000


@contextmanager
def _locked(fh):
    if _HAVE_FCNTL:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    else:  # pragma: no cover
        yield


class Timeline:
    def __init__(self, directory: str, tz: timezone = _TZ, redactor: Redactor | None = None) -> None:
        self.dir = Path(directory)
        self.tz = tz
        self.redactor = redactor or Redactor()
        self.dir.mkdir(parents=True, exist_ok=True)

    def _now(self) -> datetime:
        return datetime.now(self.tz)

    def _path(self, date_str: str | None = None) -> Path:
        date_str = date_str or self._now().strftime("%Y-%m-%d")
        return self.dir / f"TIMELINE-{date_str}.jsonl"

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        """Append one event. `content` (if present) is redacted; raw hash kept for dedupe."""
        ev = dict(event)
        ev.setdefault("ts", self._now().isoformat())
        if "content" in ev and isinstance(ev["content"], str):
            r = self.redactor.redact(ev["content"][:MAX_CONTENT])
            ev["content"] = r.clean
            ev["content_sha256"] = r.original_sha256
            if r.found:
                ev["redacted"] = r.found
        path = self._path()
        with open(path, "a", encoding="utf-8") as fh:
            with _locked(fh):
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        self._update_latest(path)
        return ev

    def _update_latest(self, path: Path) -> None:
        latest = self.dir / "TIMELINE-LATEST.jsonl"
        try:
            if latest.is_symlink() or latest.exists():
                latest.unlink()
            latest.symlink_to(path.name)
        except OSError:  # symlinks unsupported/locked -> copy
            try:
                shutil.copyfile(path, latest)
            except OSError:
                pass

    def read(self, date_str: str | None = None, after_ts: str | None = None) -> list[dict]:
        path = self._path(date_str)
        if not path.exists():
            return []
        out: list[dict] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if after_ts and ev.get("ts", "") <= after_ts:
                    continue
                out.append(ev)
        return out
