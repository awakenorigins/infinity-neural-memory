"""Vietnamese NLP — the differentiator re-ported as a real, tested module.

V1.0 fork had this; V3.x dropped it when the engine was swapped. Here it is again,
self-contained and offline. Used by retrieval to tokenize and tone-fold so that
"quyet dinh" matches "quyết định" and common compounds stay together.

Public API:
    strip_tones(text) -> str          # tone- and diacritic-folded
    normalize(text) -> str            # lowercase + tone-fold + whitespace collapse
    tokenize(text) -> list[str]       # compound-aware tokens (folded)
    detect_compounds(text) -> list[str]
    is_cjk(text) -> bool
"""

from __future__ import annotations

import re
import unicodedata

# A solid, extensible seed of common Vietnamese compounds (từ ghép). Not exhaustive —
# add domain terms via COMPOUNDS.update(...). Stored tone-folded for matching.
_COMPOUND_SOURCE = [
    "quyết định", "kiến trúc", "phát triển", "công việc", "dự án", "kết quả",
    "bài học", "kinh nghiệm", "vấn đề", "giải pháp", "mục tiêu", "chiến lược",
    "phiên bản", "tính năng", "hệ thống", "bộ nhớ", "thần kinh", "trí tuệ",
    "nhân tạo", "mô hình", "dữ liệu", "cơ sở", "người dùng", "khách hàng",
    "sản phẩm", "thị trường", "tài liệu", "báo cáo", "đánh giá", "kiểm thử",
    "triển khai", "cài đặt", "cấu hình", "lỗi sai", "sửa lỗi", "hoàn thành",
    "bắt đầu", "tiếp tục", "ưu tiên", "quan trọng", "bảo mật", "an toàn",
    "tự động", "thủ công", "hôm nay", "hôm qua", "ngày mai", "tuần trước",
    "công nghệ", "lập trình", "phần mềm", "phần cứng", "tối ưu", "hiệu suất",
]

COMPOUNDS: set[str] = set()

_TONE_MAP = str.maketrans({"đ": "d", "Đ": "D"})
_TOKEN_RE = re.compile(r"[0-9a-zA-Zà-ỹÀ-Ỹ_]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")


def strip_tones(text: str) -> str:
    """Remove Vietnamese tone marks and fold đ→d. NFD decompose then drop combining marks."""
    if not text:
        return ""
    nfd = unicodedata.normalize("NFD", text)
    no_marks = "".join(c for c in nfd if not unicodedata.combining(c))
    return no_marks.translate(_TONE_MAP)


def normalize(text: str) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", strip_tones(text).lower()).strip()


def detect_compounds(text: str) -> list[str]:
    """Return folded compounds present in text (bigram greedy over folded tokens)."""
    _ensure_compounds()
    toks = [m.group(0).lower() for m in _TOKEN_RE.finditer(strip_tones(text))]
    out: list[str] = []
    i = 0
    while i < len(toks) - 1:
        bigram = toks[i] + " " + toks[i + 1]
        if bigram in COMPOUNDS:
            out.append(bigram)
            i += 2
        else:
            i += 1
    return out


def tokenize(text: str) -> list[str]:
    """Compound-aware tokenizer. Folds tones, joins known bigrams with '_'."""
    _ensure_compounds()
    toks = [m.group(0).lower() for m in _TOKEN_RE.finditer(strip_tones(text))]
    out: list[str] = []
    i = 0
    while i < len(toks):
        if i < len(toks) - 1 and (toks[i] + " " + toks[i + 1]) in COMPOUNDS:
            out.append(toks[i] + "_" + toks[i + 1])
            i += 2
        else:
            out.append(toks[i])
            i += 1
    return out


def is_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _ensure_compounds() -> None:
    if not COMPOUNDS:
        COMPOUNDS.update(strip_tones(c).lower() for c in _COMPOUND_SOURCE)
