"""Build the FAISS template index from src/rag/templates.py using Gemini embeddings.

Usage:  python scripts/build_index.py
Output: indexes/sql_index.faiss, indexes/metadata.pkl
"""
import pickle
import sys
from pathlib import Path

import faiss

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import GEMINI_EMBEDDING_MODEL  # noqa: E402
from src.llm.gemini import embed_texts  # noqa: E402
from src.rag.retriever import INDEX_DIR, INDEX_PATH, METADATA_PATH  # noqa: E402
from src.rag.templates import SQL_TEMPLATES  # noqa: E402
from src.security.firewall import sql_firewall  # noqa: E402


def build_metadata() -> list[dict]:
    rows: list[dict] = []
    seen_questions: dict[str, str] = {}
    for template in SQL_TEMPLATES:
        result = sql_firewall(template["sql"])
        if not result.ok:
            raise ValueError(f"Template {template['id']} rejected by firewall: {result.message}")
        texts = [template.get("description", "")] + list(template.get("example_questions") or [])
        for question in texts:
            question = (question or "").strip()
            if not question:
                continue
            key = question.lower()
            if key in seen_questions and seen_questions[key] != template["id"]:
                raise ValueError(
                    f"Duplicate example question '{question}' in {template['id']} and {seen_questions[key]}"
                )
            seen_questions[key] = template["id"]
            rows.append({"template_id": template["id"], "question": question, "template": template})
    return rows


def main() -> None:
    metadata = build_metadata()
    vectors = embed_texts([m["question"] for m in metadata], task_type="RETRIEVAL_DOCUMENT")

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))
    with METADATA_PATH.open("wb") as fh:
        pickle.dump(
            {"embedding_model": GEMINI_EMBEDDING_MODEL, "templates": SQL_TEMPLATES, "metadata": metadata},
            fh,
        )
    print(f"Built FAISS index: {len(SQL_TEMPLATES)} templates, {len(metadata)} rows, dim={vectors.shape[1]}")
    print(f"  {INDEX_PATH}\n  {METADATA_PATH}")


if __name__ == "__main__":
    main()
