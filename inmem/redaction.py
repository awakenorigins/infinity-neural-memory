"""Redaction — scrub secrets before ANY logging or storage. (Mula P0)

Both audits flagged that raw user/agent text was being logged verbatim, and a memory
backup contained plaintext SSH passwords / API keys. This module makes secret-scrubbing
a hard precondition of every write path (timeline + store).

Contract:
    Redactor().redact(text) -> RedactResult(clean, found, original_sha256)

`clean` is safe to persist. `found` lists the *types* detected (never the values).
`original_sha256` lets you prove two raw inputs were identical without keeping the raw text.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# (label, compiled pattern). Order matters: most specific first.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("telegram_bot_token", re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{30,}\b")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/\-]{12,}=*", re.I)),
    ("password_kv", re.compile(r"""(?ix)
        \b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|token)\b
        \s*[:=]\s*
        (?:"([^"]{3,})"|'([^']{3,})'|([^\s"',;]{3,}))
        """)),
    ("url_credential", re.compile(r"\b([a-z][a-z0-9+.\-]*://)[^\s/@:]+:[^\s/@]{2,}@")),
]

_PLACEHOLDER = "[REDACTED:{label}]"


@dataclass
class RedactResult:
    clean: str
    found: list[str] = field(default_factory=list)
    original_sha256: str = ""

    @property
    def is_sensitive(self) -> bool:
        return bool(self.found)


class Redactor:
    """Deterministic, stdlib-only secret scrubber."""

    def __init__(self, extra_patterns: list[tuple[str, re.Pattern]] | None = None) -> None:
        self.patterns = list(_PATTERNS)
        if extra_patterns:
            self.patterns = list(extra_patterns) + self.patterns

    def redact(self, text: str) -> RedactResult:
        if text is None:
            return RedactResult(clean="", found=[], original_sha256=_sha(""))
        original = str(text)
        sha = _sha(original)
        found: list[str] = []
        clean = original
        for label, pat in self.patterns:
            if label == "password_kv":
                # keep the key name; mask the value (quoted or unquoted), preserving quotes
                def _mask_pw(m: re.Match) -> str:
                    found.append(label)
                    quoted = m.group(2) is not None or m.group(3) is not None
                    placeholder = _PLACEHOLDER.format(label="secret")
                    return f"{m.group(1)}=" + (f'"{placeholder}"' if quoted else placeholder)
                clean, n = pat.subn(_mask_pw, clean)
            elif label == "url_credential":
                # preserve scheme + '@host', mask only the user:pass
                def _mask_url(m: re.Match) -> str:
                    found.append(label)
                    return m.group(1) + _PLACEHOLDER.format(label="credential") + "@"
                clean, n = pat.subn(_mask_url, clean)
            else:
                def _repl(_m: re.Match, _label=label) -> str:
                    found.append(_label)
                    return _PLACEHOLDER.format(label=_label)
                clean, n = pat.subn(_repl, clean)
        # de-duplicate while preserving order
        seen: set[str] = set()
        uniq = [f for f in found if not (f in seen or seen.add(f))]
        return RedactResult(clean=clean, found=uniq, original_sha256=sha)


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
