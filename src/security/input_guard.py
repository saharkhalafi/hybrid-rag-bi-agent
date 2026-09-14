"""User-input guard: normalisation, size limits, prompt-injection / DML screening, rate limiting."""
import re
import time
import unicodedata
from collections import defaultdict, deque
from dataclasses import dataclass

import ftfy

from src.config import MAX_QUESTION_CHARS, RATE_LIMIT_PER_MINUTE

INJECTION_PATTERNS = re.compile(
    r"(ignore (all|the|any) (previous|prior|above) (instructions|rules)|"
    r"disregard (the|your) (rules|instructions)|you are now|act as (a|an) |"
    r"system prompt|developer message|jailbreak|"
    r"دستورات (قبلی|بالا) را (نادیده|فراموش)|قوانین را نادیده|نقش .* را بازی کن)",
    re.IGNORECASE,
)
DML_PATTERNS = re.compile(
    r"\b(drop|delete|truncate|insert|update|alter|grant|revoke|create)\b\s+\b(table|from|into|database|schema|user|role|view|index)\b",
    re.IGNORECASE,
)
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass
class GuardResult:
    ok: bool
    question: str
    reason: str | None = None


def normalize_question(text: str) -> str:
    text = ftfy.fix_text(str(text or ""))
    text = unicodedata.normalize("NFKC", text)
    text = CONTROL_CHARS.sub("", text)
    text = text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    return re.sub(r"\s+", " ", text).strip()


def validate_question(raw: str) -> GuardResult:
    question = normalize_question(raw)
    if not question:
        return GuardResult(False, question, "Empty question")
    if len(question) > MAX_QUESTION_CHARS:
        return GuardResult(False, question, f"Question exceeds {MAX_QUESTION_CHARS} characters")
    if INJECTION_PATTERNS.search(question):
        return GuardResult(False, question, "Prompt-injection pattern detected")
    if DML_PATTERNS.search(question):
        return GuardResult(False, question, "Data-modification request is not allowed")
    return GuardResult(True, question)


class RateLimiter:
    def __init__(self, per_minute: int = RATE_LIMIT_PER_MINUTE):
        self.per_minute = per_minute
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= self.per_minute:
            return False
        bucket.append(now)
        return True


rate_limiter = RateLimiter()
