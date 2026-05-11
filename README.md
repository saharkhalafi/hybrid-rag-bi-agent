# 📊 Enterprise BI Agent (RAG SQL + LLM + FAISS)

An intelligent **natural language to SQL** system that converts user questions into executable PostgreSQL queries using a hybrid **Retrieval-Augmented Generation (RAG) + LLM fallback** architecture.

It combines:
- ⚡ SQL template retrieval (FAISS + embeddings)
- 🧠 LLM-based SQL generation (Gemini)
- 🔁 Reflection loop for failed queries
- 📊 Streamlit UI dashboard
- 📈 Full observability (latency, tokens, cost, success rate)

---

## 🚀 Key Features

### 🧠 Hybrid SQL Engine
- First tries semantic retrieval from SQL templates
- Falls back to LLM generation only when necessary
- Significantly reduces cost and latency

### ⚡ High-performance Retrieval
- FAISS vector search for fast template matching
- Multilingual embeddings (**Persian + English** support)
- Cosine similarity threshold routing

### 🔁 Self-healing SQL System
- Automatic retry with reflection node
- LLM-powered correction of invalid SQL queries

### 📊 Interactive BI Dashboard
- Built with **Streamlit**
- Rich visualizations (bar, line, histogram, etc.)
- Downloadable results (CSV)

---

## 📦 Architecture
![Screenshot](https://github.com/saharkhalafi/hybrid-rag-bi-agent/blob/main/Architecture.png) 

## 🧪 Evaluation Results

Tested on a custom dataset of **400 real-world queries**:

| Metric                | Result    |
|-----------------------|-----------|
| ✅ Correct answers    | **98**    |
| ❌ Incorrect answers  | **4**     |
| 🎯 Accuracy           | **98%**   |

**Key insight:** Most errors came from ambiguous natural language queries or missing schema context in rare edge cases.

---

## 📊 Performance Metrics

| Metric                   | Value                          |
|--------------------------|--------------------------------|
| Avg retrieval latency    | ~5–10 ms                       |
| Avg LLM latency          | 1.5–4 sec                      |
| Cache hit speed          | < 5 ms                         |
| Cost per query           | ~$0.00006 – $0.0002            |

---

## 💡 Why Data Cleaning Matters

This system is highly dependent on **clean structured data**. Important factors:

- Consistent column naming (`snake_case`)
- No null ambiguity in key fields
- Proper categorical normalization (city, category, etc.)
- Clean date formats (critical for aggregation queries)

> Poor data quality directly reduces retrieval accuracy, SQL correctness, and LLM reasoning quality.

---

## ⚡ Scalability & Concurrency

- 👥 **30–60** concurrent users (single server)
- 🔁 **100–300** requests/min (depending on LLM usage)
- ⚡ Near real-time response for cached/template hits

**Main bottlenecks:** LLM API latency and database query execution time.

---

## 🧠 Tech Stack

- **Python** 🐍
- **Streamlit** 🎨
- **FAISS** (Vector Search)
- **SentenceTransformers** (E5 / MiniLM)
- **PostgreSQL** 🗄️
- **Google Gemini** LLM 🤖
- **Pandas + Plotly** 📊

---

## 📁 Project Structure

```bash
├── app.py                  # Streamlit UI
├── agent.py                # LangGraph / SQL pipeline
├── retriever.py            # FAISS template retriever
├── embedding_model.py      # Cached embedding model
├── sql_templates.pkl       # SQL templates dataset
├── sql_index.faiss         # Vector index
├── logs/                   # Telemetry & analytics
└── requirements.txt
'''
---
## 🔥 Key Innovations

- **Hybrid RAG + LLM SQL routing system** — Uses semantic templates first, falls back to LLM only when needed
- **Multilingual semantic matching** — Strong support for both English and Persian
- **Template-first execution** — Delivers strong cost optimization and low latency
- **Reflection-based SQL correction loop** — Self-healing system that automatically fixes invalid queries
- **Full telemetry tracking** — Monitors latency, token usage, cost, and cache hit rate in real-time

---

## 📈 Future Improvements

- Add reranker model (cross-encoder) for higher retrieval precision
- Improve Persian embedding alignment and model performance
- Implement query intent classifier (aggregation vs filter vs ranking)
- Enable multi-table and complex schema support
- Add distributed caching (Redis) for better scalability

---

## Dashboard
![Screenshot](https://github.com/saharkhalafi/hybrid-rag-bi-agent/blob/main/Dashboard1.png) 





