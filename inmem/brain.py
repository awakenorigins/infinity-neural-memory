"""Brain — the high-level facade that composes every part into one honest API.

    brain = Brain(db_path, timeline_dir)
    brain.remember("Chọn Opus 4.6 vì Sonnet thiếu depth", category="decision")
    brain.recall("model nào dùng cho viết truyện")
    brain.log_exchange(user_msg, agent_resp, session_id="s1")
    brain.pre_action("deploy", "auth service")
    brain.digest()

Every write flows through redaction (timeline) + the AdmissionGate (store). Nothing here
references a phantom API; it runs on stdlib + the inmem modules only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from inmem.admission import AdmissionGate, AdmissionResult
from inmem.digest import compute_digest, render_digest
from inmem.embedding import HashingEmbedder
from inmem.inject_gate import InjectionGate, InjectionDecision
from inmem.preaction import PreActionGate, PreActionVerdict
from inmem.preference_prior import PreferencePrior, OptionPrior
from inmem.redaction import Redactor
from inmem.retrieval import hybrid_search, Hit
from inmem.store import MemoryStore
from inmem.timeline import Timeline
from inmem.vietnamese import normalize

# ---- fact extraction (pattern-based, zero-LLM). Regexes hardened per audit feedback. ----
_DECISION = [
    re.compile(r"chọn\s+.+?\s+(vì|thay vì|thay cho)", re.I),
    re.compile(r"quyết định\s+(dùng|chọn|bỏ|thay)", re.I),
    re.compile(r"(switch to|chuyển sang)\s+\S+", re.I),
]
_INSTRUCTION = [
    re.compile(r"\b(luôn|always|không bao giờ|never|đừng|cấm)\b.{4,}", re.I),
    re.compile(r"\bquy tắc\b\s*[:\-]", re.I),
    re.compile(r"\b(từ giờ|from now)\b.{4,}", re.I),
]
_WORKFLOW = [
    re.compile(r"(ch(?:ương)?\s*\d+).{0,40}(hoàn thành|done|complete|xong|pass|fail)", re.I),
    re.compile(r"(hoàn thành|done|complete|xong|pass|fail).{0,40}(ch(?:ương)?\s*\d+)", re.I),
    re.compile(r"\bscore\s*\d+\s*/\s*\d+\b", re.I),
    re.compile(r"(phase|giai đoạn)\s*\d+", re.I),
]
_ERROR = [re.compile(r"\b(lỗi|bug|error|fail|crash|rework|vỡ|hỏng)\b", re.I)]
_FACT = [
    re.compile(r"\b(tao|tôi|mình|i)\s+(là|am|thích|like|ghét|hate|có|have)\b", re.I),
    re.compile(r"\b(project|dự án)\s+\S+", re.I),
]


def extract_facts(user_msg: str, agent_resp: str = "") -> list[dict]:
    combined = f"{user_msg} {agent_resp}"
    out: list[dict] = []
    def hit(pats):
        return any(p.search(combined) for p in pats)
    if hit(_INSTRUCTION):
        out.append({"cat": "instruction", "text": user_msg[:200], "sal": 0.9, "conf": 0.85})
    if hit(_DECISION):
        out.append({"cat": "decision", "text": user_msg[:200], "sal": 0.75, "conf": 0.8})
    if hit(_ERROR):
        out.append({"cat": "error", "text": user_msg[:200], "sal": 0.6, "conf": 0.7})
    if hit(_WORKFLOW):
        out.append({"cat": "workflow", "text": user_msg[:200], "sal": 0.5, "conf": 0.7})
    if hit(_FACT) and not out:
        out.append({"cat": "fact", "text": user_msg[:200], "sal": 0.5, "conf": 0.65})
    return out


@dataclass
class RememberResult:
    memory_id: str | None
    admission: AdmissionResult


class Brain:
    def __init__(self, db_path: str = ":memory:", timeline_dir: str = "./timeline",
                 use_vector: bool = True) -> None:
        self.store = MemoryStore(db_path)
        self.redactor = Redactor()
        self.timeline = Timeline(timeline_dir, redactor=self.redactor)
        self.embedder = HashingEmbedder() if use_vector else None
        self.gate = AdmissionGate(embedder=self.embedder)
        self.preaction = PreActionGate(embedder=self.embedder)
        self.inject_gate = InjectionGate()
        self.prior = PreferencePrior(self)

    # ---- core ops -----------------------------------------------------------
    def remember(self, content: str, *, category: str = "fact", salience: float = 0.5,
                 confidence: float = 0.7, scope: str = "global", pinned: bool = False,
                 tags: list[str] | None = None, source_event_id: str | None = None) -> RememberResult:
        verdict = self.gate.evaluate(self.store, content, confidence=confidence, scope=scope)
        red = self.redactor.redact(content)
        if not verdict.admit:
            return RememberResult(memory_id=verdict.duplicate_of, admission=verdict)
        mem_id = self.store.remember(
            content=red.clean, norm_text=normalize(red.clean), content_hash=red.original_sha256,
            category=category, salience=salience, confidence=confidence, scope=scope,
            tags=tags or [], pinned=pinned, sensitive=red.is_sensitive,
            source_event_id=source_event_id,
            supersedes=verdict.duplicate_of if verdict.action == "supersede" else None,
        )
        return RememberResult(memory_id=mem_id, admission=verdict)

    def recall(self, query: str, *, top_k: int = 5, scope: str | None = None) -> list[Hit]:
        hits = hybrid_search(self.store, query, top_k=top_k, scope=scope, embedder=self.embedder)
        for h in hits:
            self.store.touch(h.memory["id"])
        return hits

    def recall_for_context(self, query: str, *, top_k: int = 5, scope: str | None = None
                           ) -> list[tuple[Hit, InjectionDecision]]:
        """Recall, then pass each hit through the InjectionGate. Returns only ADMITTED
        memories (safe + relevant enough to inject), each with its explainable decision."""
        out: list[tuple[Hit, InjectionDecision]] = []
        for h in self.recall(query, top_k=top_k * 2, scope=scope):
            decision = self.inject_gate.evaluate(query, h.memory)
            if decision.admit:
                out.append((h, decision))
        return out[:top_k]

    def prefer(self, options: list[str], *, context: str = "", scope: str | None = None
               ) -> list[OptionPrior]:
        """Explainable Preference Prior: rank options by past evidence, with a reason ledger."""
        return self.prior.rank(options, context=context, scope=scope)

    def log_exchange(self, user_msg: str, agent_resp: str = "", *, session_id: str = "unknown",
                     channel: str = "unknown") -> list[RememberResult]:
        u = self.timeline.append({"sid": session_id, "type": "user_msg",
                                  "content": user_msg, "channel": channel})
        self.timeline.append({"sid": session_id, "type": "agent_resp", "content": agent_resp})
        facts = extract_facts(user_msg, agent_resp)
        results: list[RememberResult] = []
        if facts:
            self.timeline.append({"sid": session_id, "type": "extract", "facts": facts})
            for f in facts:
                results.append(self.remember(
                    f["text"], category=f["cat"], salience=f["sal"], confidence=f.get("conf", 0.7),
                    source_event_id=u.get("content_sha256"),
                ))
        return results

    def pre_action(self, action: str, target: str = "", *, scope: str = "global") -> PreActionVerdict:
        return self.preaction.judge(self.store, action, target, scope=scope)

    def digest(self, date_str: str | None = None) -> dict:
        return compute_digest(self.timeline, self.store, date_str)

    def digest_text(self, date_str: str | None = None) -> str:
        return render_digest(self.digest(date_str))

    def stats(self) -> dict:
        return self.store.stats()
