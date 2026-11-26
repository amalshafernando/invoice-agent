"""Part 3: Defense-in-Depth Prompt-Injection Guardrail.

Combines:
1. Fast local semantic/structural jailbreak & indirect-injection scoring
   (token-pattern + imperative-override + currency-hijack features).
2. Optional free Hugging Face Inference API classifier
   (`protectai/deberta-v3-base-prompt-injection-v2`) when `HF_TOKEN` is set.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import httpx

from ..config import settings

_SIGNALS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(rules|instructions|policy)", re.I), 0.95, "override_instructions"),
    (re.compile(r"disregard\s+.{0,30}(rules|instructions|policy)", re.I), 0.90, "disregard_policy"),
    (re.compile(r"(system\s+prompt|developer\s+message|<\s*/?\s*(system|assistant|tool)\s*>)", re.I), 0.92, "role_spoofing"),
    (re.compile(r"(you\s+are\s+now|act\s+as\s+|pretend\s+to\s+be)", re.I), 0.75, "persona_hijack"),
    (re.compile(r"(approve|pay|transfer|wire|release)\s+.{0,35}(\$|usd|lkr|eur)?\s*\d[\d,\.]*", re.I), 0.85, "payment_hijack"),
    (re.compile(r"(bypass|override)\s+.{0,25}(policy|approval|limit|check|guardrail)", re.I), 0.90, "policy_bypass"),
    (re.compile(r"do\s+not\s+(tell|inform|notify|log|audit)", re.I), 0.85, "audit_evasion"),
    (re.compile(r"(base64|eval\(|exec\(|curl\s+http)", re.I), 0.70, "payload_obfuscation"),
]


@dataclass
class GuardrailResult:
    flagged: bool
    score: float
    source: str
    labels: list[str]


def _local_score(text: str) -> GuardrailResult:
    if not text:
        return GuardrailResult(flagged=False, score=0.0, source="local", labels=[])
    labels: list[str] = []
    raw = 0.0
    for rx, weight, label in _SIGNALS:
        if rx.search(text):
            labels.append(label)
            raw += weight
    # Squash additive signal into (0, 1)
    score = round(1.0 - math.exp(-raw), 3) if raw > 0 else 0.0
    return GuardrailResult(flagged=score >= 0.60, score=score, source="local", labels=labels)


def _hf_classify(text: str) -> GuardrailResult | None:
    if not settings.hf_token or settings.guardrail_mode == "local":
        return None
    try:
        url = f"https://router.huggingface.co/hf-inference/models/{settings.hf_guardrail_model}"
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {settings.hf_token}"},
            json={"inputs": text[:1500], "options": {"wait_for_model": True}},
            timeout=6.0,
        )
        if r.status_code != 200:
            return None
        preds = r.json()
        if isinstance(preds, list) and preds and isinstance(preds[0], list):
            preds = preds[0]
        inj_score = 0.0
        for item in preds:
            lbl = str(item.get("label", "")).upper()
            if "INJECTION" in lbl or lbl == "LABEL_1":
                inj_score = max(inj_score, float(item.get("score", 0.0)))
        return GuardrailResult(
            flagged=inj_score >= 0.65,
            score=round(inj_score, 3),
            source=f"hf:{settings.hf_guardrail_model}",
            labels=["hf_injection"] if inj_score >= 0.65 else [],
        )
    except Exception:
        return None


def inspect_text(text: str) -> GuardrailResult:
    """Run hybrid guardrail: local structural detector + optional HF DeBERTa classifier."""
    local = _local_score(text)
    if settings.guardrail_mode == "local":
        return local
    hf = _hf_classify(text)
    if hf is None:
        return local
    merged_score = max(local.score, hf.score)
    merged_labels = list(dict.fromkeys(local.labels + hf.labels))
    return GuardrailResult(
        flagged=local.flagged or hf.flagged,
        score=merged_score,
        source=f"hybrid({hf.source})",
        labels=merged_labels,
    )
