import streamlit as st
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class SQLTemplateRetriever:

    def __init__(self, index_path, meta_path):

        self.index = faiss.read_index(index_path)

        with open(meta_path, "rb") as f:
            data = pickle.load(f)

        self.templates = data.get("templates", [])

        # 🚀 LOAD MODEL ONLY ONCE
        self.model = SentenceTransformer(
            "intfloat/multilingual-e5-base",
            device="cpu"
        )

    def get_best_match(self, query: str):
        query_emb = self.model.encode(
            [f"query: {query}"],
            normalize_embeddings=True
        ).astype(np.float32)

        scores, idxs = self.index.search(query_emb, 1)

        score = float(scores[0][0])
        idx = int(idxs[0][0])

        if idx < 0 or idx >= len(self.templates):
            return 0.0, None

        return score, self.templates[idx]


# =========================
# STREAMLIT CACHED LOADER (IMPORTANT)
# =========================
@st.cache_resource(show_spinner="Loading retriever...")
def load_retriever():
    return SQLTemplateRetriever(
        index_path="sql_index.faiss",
        meta_path="metadata.pkl"
    )

retriever = load_retriever()