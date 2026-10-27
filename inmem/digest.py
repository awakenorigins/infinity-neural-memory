"""Digest — compute a daily summary from the timeline + store, and notify honestly.

Fixes the V3.3 daily_digest dishonesty: there is NO function that prints to console while
claiming it "sent a Telegram DM". Notifiers declare their channel and whether delivery is
real. ConsoleNotifier is the honest default; WebhookNotifier performs a real HTTP POST.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

_TZ = timezone(timedelta(hours=7))


@dataclass
class DeliveryResult:
    channel: str
    delivered: bool
    detail: str = ""


class ConsoleNotifier:
    channel = "console"
    def send(self, text: str) -> DeliveryResult:
        print(text)
        return DeliveryResult(channel="console", delivered=True, detail="printed to stdout")


class WebhookNotifier:
    """Real delivery via HTTP POST {"text": ...}. delivered reflects the actual response."""
    channel = "webhook"
    def __init__(self, url: str, timeout: float = 5.0) -> None:
        self.url = url
        self.timeout = timeout

    def send(self, text: str) -> DeliveryResult:  # pragma: no cover - network
        data = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                ok = 200 <= resp.status < 300
                return DeliveryResult(channel="webhook", delivered=ok, detail=f"HTTP {resp.status}")
        except Exception as e:
            return DeliveryResult(channel="webhook", delivered=False, detail=f"error: {e}")


def compute_digest(timeline, store, date_str: str | None = None) -> dict:
    date_str = date_str or datetime.now(_TZ).strftime("%Y-%m-%d")
    events = timeline.read(date_str)
    by_type: dict[str, int] = {}
    for e in events:
        by_type[e.get("type", "?")] = by_type.get(e.get("type", "?"), 0) + 1
    extracted: dict[str, int] = {}
    for e in events:
        if e.get("type") == "extract":
            for f in e.get("facts", []):
                extracted[f.get("cat", "fact")] = extracted.get(f.get("cat", "fact"), 0) + 1
    redacted_events = sum(1 for e in events if e.get("redacted"))
    st = store.stats()
    return {
        "date": date_str,
        "events_total": len(events),
        "events_by_type": by_type,
        "facts_extracted": extracted,
        "redactions": redacted_events,
        "store": st,
    }


def render_digest(d: dict) -> str:
    lines = [
        "🧠 INFINITY NEURAL MEMORY — Daily Digest",
        f"📅 {d['date']}",
        "",
        f"📝 Timeline: {d['events_total']} events  {d['events_by_type']}",
        f"📥 Facts extracted: {sum(d['facts_extracted'].values())}  {d['facts_extracted']}",
        f"🔒 Redactions today: {d['redactions']}",
        f"🗄️  Store: {d['store']['active']} active / {d['store']['total']} total"
        f" · pinned {d['store']['pinned']} · sensitive {d['store']['sensitive']}",
        f"   by category: {d['store']['by_category']}",
    ]
    return "\n".join(lines)
