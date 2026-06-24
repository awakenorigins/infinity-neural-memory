"""Infinity Neural Memory (inmem) — V1.0.0

A self-contained, honest, testable memory nervous system for long-running agents.
Distilled from infinity-neural (event-sourced timeline, instinct protocol, Vietnamese NLP)
and library-memo (hybrid RRF retrieval, self-contained discipline, admission concept).

Design law: ship only what runs. No phantom API. Every public claim has a passing test.
Zero hard external dependencies — pure Python stdlib. Embeddings/notifiers are pluggable.
"""

from __future__ import annotations

__version__ = "1.2.0"
__all__ = [
    "__version__",
    "Redactor",
    "PiiScrubber",
    "MemoryStore",
    "Memory",
    "Timeline",
    "HashingEmbedder",
    "hybrid_search",
    "AdmissionGate",
    "InjectionGate",
    "PreActionGate",
    "PreferencePrior",
    "compute_digest",
    "ConsoleNotifier",
    "DryRunBridge",
    "Brain",
]

from inmem.redaction import Redactor
from inmem.pii import PiiScrubber
from inmem.store import MemoryStore, Memory
from inmem.timeline import Timeline
from inmem.embedding import HashingEmbedder
from inmem.retrieval import hybrid_search
from inmem.admission import AdmissionGate
from inmem.inject_gate import InjectionGate
from inmem.preaction import PreActionGate
from inmem.preference_prior import PreferencePrior
from inmem.digest import compute_digest, ConsoleNotifier
from inmem.bridge import DryRunBridge
from inmem.brain import Brain
