"""Gemini access: chat completions (LangChain) and embeddings (google-genai)."""
import hashlib
import re
import time
from typing import List

import numpy as np
from google import genai

from src.config import GEMINI_API_KEY, GEMINI_EMBEDDING_MODEL, GEMINI_LLM_MODEL, get_llm, llm_cache, require_env
from src.observability.telemetry import current_session_id, log_event, log_llm_call

_client: genai.Client | None = None
EMBED_BATCH = 100


def get_genai_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=require_env(GEMINI_API_KEY, "GEMINI_API_KEY"))
    return _client


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def embed_texts(texts: List[str], task_type: str | None = None) -> np.ndarray:
    """L2-normalised Gemini embeddings (so inner product == cosine similarity)."""
    client = get_genai_client()
    out: list = []
    config = genai.types.EmbedContentConfig(task_type=task_type) if task_type else None
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start:start + EMBED_BATCH]
        response = client.models.embed_content(model=GEMINI_EMBEDDING_MODEL, contents=batch, config=config)
        out.extend(e.values for e in response.embeddings)
    return _normalize(np.array(out, dtype=np.float32))


def strip_sql_fences(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^```(?:sql)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text.rstrip(";").strip()


def _cache_key(prompt: str, node: str) -> str:
    normalized = re.sub(r"\s+", " ", prompt.strip())
    return hashlib.sha256(f"{GEMINI_LLM_MODEL}:{node}:{normalized}".encode()).hexdigest()


def call_llm(prompt: str, node: str) -> str:
    start = time.time()
    key = _cache_key(prompt, node)
    if key in llm_cache:
        log_event({"type": "llm_cache_hit", "node": node})
        return llm_cache[key]

    try:
        response = get_llm().invoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        latency_ms = round((time.time() - start) * 1000, 2)

        usage = getattr(response, "usage_metadata", None) or {}
        prompt_tokens = int(usage.get("input_tokens") or len(prompt) // 4)
        completion_tokens = int(usage.get("output_tokens") or len(content) // 4)
        total_tokens = prompt_tokens + completion_tokens
        estimated_cost = round(prompt_tokens / 1e6 * 0.30 + completion_tokens / 1e6 * 2.50, 6)

        llm_cache[key] = content
        log_event({
            "type": "llm_call", "node": node, "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "total_tokens": total_tokens, "estimated_cost": estimated_cost, "cache_hit": False,
        })
        log_llm_call({
            "session_id": current_session_id(), "user_query": prompt[:180], "node": node,
            "model": GEMINI_LLM_MODEL, "latency_ms": latency_ms, "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens, "total_tokens": total_tokens,
            "estimated_cost": estimated_cost,
        })
        return content
    except Exception as exc:
        log_event({"type": "llm_error", "node": node, "error": str(exc)[:300]})
        raise
