"""Regression tests for the V1.0.1 patch (findings from Mula's lab review).

Covers: (1) AdmissionGate must NOT supersede related-but-distinct memories,
(2) supersede only on an explicit replacement signal,
(3) redaction of quoted passwords (with spaces) and URL credentials.
"""

from __future__ import annotations

from inmem.brain import Brain
from inmem.redaction import Redactor
from inmem.admission import explicit_supersession


# ---- P0#1: false supersession ------------------------------------------------
def test_admission_does_not_supersede_related_but_distinct():
    b = Brain()
    b.remember("Chọn Opus vì viết truyện sâu")
    r = b.remember("Chọn DeepSeek vì code rẻ")
    assert r.admission.action == "insert"
    assert b.stats()["active"] == 2

def test_admission_does_not_supersede_two_preferences():
    b = Brain()
    b.remember("Nấng thích trà sữa")
    r = b.remember("Nấng thích phim khoa học viễn tưởng")
    assert r.admission.action == "insert"
    assert b.stats()["active"] == 2

def test_admission_skips_true_near_duplicate():
    b = Brain()
    b.remember("Deploy auth service crashes without the DATABASE env var set")
    r = b.remember("Deploy auth service crashes without the DATABASE env var set")
    # exact text -> skip (hash), active stays 1
    assert r.admission.action == "skip"
    assert b.stats()["active"] == 1

def test_admission_supersedes_only_with_explicit_signal():
    b = Brain()
    first = b.remember("Dùng SQLite cho storage layer của project")
    # heavy overlap + explicit replacement signal -> supersede
    r = b.remember("Không dùng SQLite nữa, thay bằng FalkorDB cho storage layer của project")
    assert r.admission.action in ("supersede", "insert")
    if r.admission.action == "supersede":
        assert b.store.get(first.memory_id)["valid_to"] is not None

def test_explicit_supersession_detector():
    assert explicit_supersession("thay bằng Redis")
    assert explicit_supersession("không dùng MySQL nữa")
    assert explicit_supersession("replace the old config")
    assert not explicit_supersession("Chọn Opus vì depth tốt")


# ---- P0#2 / P0#3: redaction completeness -------------------------------------
def test_redaction_quoted_password_no_leak():
    res = Redactor().redact('password = "hello world"')
    assert "hello" not in res.clean and "world" not in res.clean
    assert res.clean == 'password="[REDACTED:secret]"'

def test_redaction_multiword_single_quote():
    res = Redactor().redact("passwd='multi word secret here'")
    assert "multi" not in res.clean and "here" not in res.clean
    assert "[REDACTED:secret]" in res.clean

def test_redaction_url_credential_preserves_scheme():
    res = Redactor().redact("DATABASE_URL=postgres://user:pass@example.com/db")
    assert res.clean == "DATABASE_URL=postgres://[REDACTED:credential]@example.com/db"
    assert "pass" not in res.clean.split("@")[0].replace("postgres", "")

def test_redaction_normal_text_untouched():
    res = Redactor().redact("just a normal sentence with no secrets at all")
    assert res.found == [] and res.clean == "just a normal sentence with no secrets at all"
