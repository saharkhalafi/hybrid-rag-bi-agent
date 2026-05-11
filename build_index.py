import faiss
import pickle
import numpy as np
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SQLTemplateRetriever:

    def __init__(self, index_path: str = None, metadata_path: str = None):

        self.index_path = index_path or "sql_index.faiss"
        self.metadata_path = metadata_path or "metadata.pkl"

        # ========================= INTERNAL STATE =========================
        self._loaded = False
        self._load_failed = False

        self._index = None
        self._model = None
        self._templates = []
        self._template_ids = []

        # ========================= COMPATIBILITY ALIASES =========================
        # (THIS FIXES YOUR AttributeError)
        self.templates = []
        self.index = None
        self.model = None

    # ========================= LOAD =========================
    def _load(self):

        if self._loaded or self._load_failed:
            return

        try:
            # ---------------- MODEL ----------------
            self._model = SentenceTransformer("intfloat/multilingual-e5-base")

            # ---------------- INDEX ----------------
            self._index = faiss.read_index(self.index_path)

            # ---------------- METADATA ----------------
            with open(self.metadata_path, "rb") as f:
                data = pickle.load(f)

            self._templates = data.get("templates", [])
            self._template_ids = data.get("template_ids", [])

            # ========================= SYNC COMPAT FIELDS =========================
            # THIS FIXES YOUR app.py sidebar + legacy usage
            self.templates = self._templates
            self.index = self._index
            self.model = self._model

            self._loaded = True

            logger.info(f"✅ Retriever loaded: {len(self._templates)} templates")

        except Exception as e:
            self._load_failed = True
            logger.error(f"❌ Retriever load failed: {e}")

    # ========================= MAIN SEARCH =========================
    def get_best_match(self, query: str):

        self._load()

        if self._load_failed or not query:
            return 0.0, None

        try:
            # ========================= E5 FORMAT =========================
            query_vec = self._model.encode(
                [f"query: {query}"],
                normalize_embeddings=True
            ).astype(np.float32)

            scores, indices = self._index.search(query_vec, 1)

            score = float(scores[0][0])
            idx = int(indices[0][0])

            if idx < 0 or idx >= len(self._templates):
                return 0.0, None

            template = self._templates[idx]

            return score, template

        except Exception as e:
            logger.error(f"❌ Retrieval error: {e}")
            return 0.0, None

    # ========================= DEBUG =========================
    def debug(self, query: str):
        score, template = self.get_best_match(query)

        return {
            "score": score,
            "template_id": template.get("id") if template else None,
            "sql": template.get("sql") if template else None
        }


# ========================= GLOBAL INSTANCE =========================
retriever = SQLTemplateRetriever()