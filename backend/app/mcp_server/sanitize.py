"""Tool output = UNTRUSTED data. Heuristic layer only; the real defences are
architectural (quarantined extractor, deterministic policy, least privilege)."""
import re
import unicodedata
from typing import Any

from .guardrail import inspect_text

MAX_STR = 500
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier)? ?(rules|instructions|policy|policies)",
    r"disregard .{0,30}(rules|instructions|policy)",
    r"you are now", r"system prompt", r"developer message",
    r"approve .{0,40}\$?\s?\d[\d,\.]*", r"(pay|payment|transfer) .{0,30}\d",
    r"override .{0,20}(policy|approval|limit)", r"<\s*/?\s*(system|assistant|tool)\s*>",
    r"do not (tell|inform|notify)", r"bypass",
]
_RX = [re.compile(p, re.I) for p in PATTERNS]
REDACTED = "[REDACTED:suspected-injection]"


def clean_string(s: str, findings: list[str]) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_ZERO_WIDTH)   # defeat homoglyph/hidden tricks
    s = _CTRL.sub("", s)
    gr = inspect_text(s)
    if gr.flagged:
        findings.extend(f"guardrail:{lbl}({gr.score})" for lbl in gr.labels)
    for rx in _RX:
        if rx.search(s):
            findings.append(rx.pattern)
            s = rx.sub(REDACTED, s)
    if gr.flagged and REDACTED not in s:
        s = f"{REDACTED} {s}"
    return s[:MAX_STR]


def sanitize(obj: Any, findings: list[str] | None = None) -> tuple[Any, list[str]]:
    findings = [] if findings is None else findings
    if isinstance(obj, str):
        return clean_string(obj, findings), findings
    if isinstance(obj, list):
        return [sanitize(x, findings)[0] for x in obj], findings
    if isinstance(obj, dict):
        return {k: sanitize(v, findings)[0] for k, v in obj.items()}, findings
    return obj, findings
