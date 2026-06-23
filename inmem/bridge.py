"""Bridge — OPTIONAL adapter to an external graph engine (e.g. neural-memory / nmem CLI).

Fixes the V3.3 timeline_sync dishonesty: there is no code path that increments a
"synced" counter while only simulating. A bridge always reports its real mode.

  * DryRunBridge (default): records intended writes in-memory, performs NO external I/O,
    and reports mode="dry-run". Honest by construction.
  * SubprocessBridge: shells out to a real `nmem` CLI if installed; reports actual success.

The core memory system does NOT require any bridge. This is purely additive.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SyncReport:
    mode: str
    attempted: int = 0
    written: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class NeuralBridge(Protocol):
    mode: str
    def remember(self, content: str, *, category: str, salience: float) -> bool: ...


class DryRunBridge:
    """Default. Does not write anywhere external. Tells the truth about it."""
    mode = "dry-run"
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def remember(self, content: str, *, category: str = "fact", salience: float = 0.5) -> bool:
        self.calls.append({"content": content, "category": category, "salience": salience})
        return False  # nothing was actually persisted externally


class SubprocessBridge:
    """Real adapter: pipes content to `nmem remember --stdin`. Available only if nmem exists."""
    mode = "subprocess"
    def __init__(self, binary: str = "nmem") -> None:
        self.binary = binary
        self.available = shutil.which(binary) is not None

    def remember(self, content: str, *, category: str = "fact", salience: float = 0.5) -> bool:  # pragma: no cover
        if not self.available:
            return False
        try:
            proc = subprocess.run(
                [self.binary, "remember", "--stdin", "--type", category, "--salience", str(salience)],
                input=content.encode("utf-8"), capture_output=True, timeout=15,
            )
            return proc.returncode == 0
        except Exception:
            return False


def sync_timeline(timeline, bridge: NeuralBridge, date_str: str | None = None,
                  min_salience: float = 0.5) -> SyncReport:
    """Push extracted facts from the timeline into an external engine via `bridge`.
    The report's `mode` field always reflects what really happened."""
    report = SyncReport(mode=bridge.mode)
    for ev in timeline.read(date_str):
        if ev.get("type") != "extract":
            continue
        for fact in ev.get("facts", []):
            if fact.get("sal", 0.0) < min_salience:
                report.skipped += 1
                continue
            report.attempted += 1
            ok = bridge.remember(fact.get("text", ""), category=fact.get("cat", "fact"),
                                 salience=fact.get("sal", 0.5))
            if ok:
                report.written += 1
            else:
                report.skipped += 1
    return report
