"""PII scrubbing — the layer the gp seed corpus was missing.

The lab audit found the redacted seed still leaked 3 emails and a `C:\\Users\\<name>` path.
Redaction handles *secrets*; this handles *personally identifying information*: emails, IPv4,
and OS user-home paths that leak a username. Used by the seed importer and available standalone.

    PiiScrubber().scrub(text) -> ScrubResult(clean, found)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("ipv4", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    ("win_userpath", re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"']+", re.I)),
    ("unix_userpath", re.compile(r"/(?:home|Users)/[A-Za-z0-9_.\-]+")),
]

_PLACEHOLDER = "[PII:{label}]"
# don't scrub obviously-public / placeholder addresses
_EMAIL_ALLOW = re.compile(r"@(?:example\.|email\.|noreply|users\.noreply\.github)", re.I)


@dataclass
class ScrubResult:
    clean: str
    found: list[str] = field(default_factory=list)

    @property
    def is_pii(self) -> bool:
        return bool(self.found)


class PiiScrubber:
    def __init__(self, scrub_unix_home: bool = True) -> None:
        self.patterns = [p for p in _PATTERNS
                         if scrub_unix_home or p[0] != "unix_userpath"]

    def scrub(self, text: str) -> ScrubResult:
        if not text:
            return ScrubResult(clean="", found=[])
        found: list[str] = []
        clean = text
        for label, pat in self.patterns:
            def _repl(m: re.Match, _label=label) -> str:
                if _label == "email" and _EMAIL_ALLOW.search(m.group(0)):
                    return m.group(0)
                found.append(_label)
                return _PLACEHOLDER.format(label=_label)
            clean = pat.sub(_repl, clean)
        seen: set[str] = set()
        uniq = [f for f in found if not (f in seen or seen.add(f))]
        return ScrubResult(clean=clean, found=uniq)
