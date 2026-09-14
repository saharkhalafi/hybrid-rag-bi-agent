"""FAISS retrieval over Gemini embeddings of SQL-template example questions."""
import pickle
from pathlib import Path
from typing import Dict, List

import faiss

from src.config import GEMINI_EMBEDDING_MODEL, logger
from src.llm.gemini import embed_texts
from src.rag.templates import get_template

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_DIR = PROJECT_ROOT / "indexes"
INDEX_PATH = INDEX_DIR / "sql_index.faiss"
METADATA_PATH = INDEX_DIR / "metadata.pkl"


class SQLTemplateRetriever:
    def __init__(self, index_path: Path = INDEX_PATH, metadata_path: Path = METADATA_PATH):
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.index = None
        self.metadata: List[Dict] = []
        self.templates: List[Dict] = []
        self.embedding_model: str | None = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        if not (self.index_path.exists() and self.metadata_path.exists()):
            return
        try:
            self.index = faiss.read_index(str(self.index_path))
            with self.metadata_path.open("rb") as fh:
                data = pickle.load(fh)
            self.metadata = data.get("metadata", [])
            self.templates = data.get("templates", [])
            self.embedding_model = data.get("embedding_model")
            self._loaded = bool(self.metadata) and self.index is not None
            if self.embedding_model and self.embedding_model != GEMINI_EMBEDDING_MODEL:
                logger.warning(
                    "Index built with %s but runtime uses %s; rebuild with scripts/build_index.py",
                    self.embedding_model, GEMINI_EMBEDDING_MODEL,
                )
        except Exception as exc:
            logger.error("Retriever load failed: %s", exc)

    def reload(self) -> None:
        self._loaded = False
        self._load()

    def is_available(self) -> bool:
        self._load()
        return self._loaded

    def retrieve_templates(self, query: str, top_k: int = 5) -> List[Dict]:
        if not query or not self.is_available():
            return []
        vector = embed_texts([query], task_type="RETRIEVAL_QUERY")
        scores, indices = self.index.search(vector, min(top_k * 3, len(self.metadata)))

        results: List[Dict] = []
        seen: set = set()
        for score, idx in zip(scores[0], indices[0]):
            idx = int(idx)
            if idx < 0 or idx >= len(self.metadata):
                continue
            item = self.metadata[idx]
            template = item.get("template") or {}
            template_id = template.get("id") or item.get("template_id")
            if template_id in seen:
                continue
            # Prefer the live template definition (carries routing metadata) over the pickled copy.
            template = get_template(template_id) or template
            seen.add(template_id)
            results.append({
                "score": float(score),
                "template": template,
                "template_id": template_id,
                "matched_question": item.get("question"),
            })
            if len(results) >= top_k:
                break
        return results


retriever = SQLTemplateRetriever()


def is_available() -> bool:
    return retriever.is_available()


def retrieve_templates(query: str, top_k: int = 5) -> List[Dict]:
    return retriever.retrieve_templates(query, top_k=top_k)
