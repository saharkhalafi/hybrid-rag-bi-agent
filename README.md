# Enterprise BI Agent

AI-powered analytics assistant using:
- Hybrid RAG routing
- SQL template retrieval
- LLM fallback generation
- PostgreSQL
- FAISS semantic search
- LangGraph orchestration

---

## Features

- Natural language → SQL
- Hybrid deterministic + generative architecture
- Similarity-based SQL template routing
- Persian + English query support
- Query caching
- Cost + latency logging
- SQL validation/firewall
- Auto chart generation
- AI-generated business insights

---

## Architecture

[add architecture image]

---

## Tech Stack

- Python
- Streamlit
- PostgreSQL
- FAISS
- Sentence Transformers
- Gemini 2.5 Flash
- LangGraph
- Plotly

---

## Evaluation

- Tested on 100 business questions
- Accuracy: 98%
- Supports multilingual analytics queries

---

## Key Engineering Challenges

- Reducing unnecessary LLM calls
- Similarity threshold tuning
- Multilingual retrieval
- SQL safety validation
- Observability and telemetry
- Latency optimization

---

## Running Locally

```bash
git clone ...
cd ...
pip install -r requirements.txt
streamlit run app.py


---

# 5. Add Architecture Diagram

VERY important.

Add:
- User
- Retriever
- FAISS
- Threshold router
- LLM fallback
- SQL firewall
- PostgreSQL
- Visualization

You already made a LinkedIn image.  
Create one cleaner architecture image too.

You can even use:
- [Excalidraw](https://excalidraw.com?utm_source=chatgpt.com)
- [Figma](https://www.figma.com?utm_source=chatgpt.com)

---

# 6. Add Screenshots

Recruiters LOVE screenshots.

Add:
- Streamlit UI
- Generated chart
- SQL debug panel
- Example question
- Latency/cost logs

Example in README:

```md
## Demo

![Dashboard](dashboard.png)
