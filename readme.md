# 🚀 Hybrid RAG BI Agent

### Production-Oriented Natural Language Analytics for PostgreSQL

A production-oriented **Natural Language → SQL → Analytics** system that allows business users to query PostgreSQL data using natural language.

The system combines **semantic SQL-template retrieval, LLM-based SQL generation, deterministic routing, SQL security controls, structured analytical planning, Python-based analytics, evaluation, and observability** into a single BI agent.

Instead of sending every question directly to an LLM, the system follows a **retrieval-first architecture** and only invokes the LLM when necessary.

> **Goal:** Build a reliable, secure, cost-aware BI agent that can answer both simple business questions and multi-step analytical questions without turning every request into an expensive LLM workflow.

---

## ✨ Key Features

* 🧠 **Hybrid RAG + LLM Text-to-SQL**
* 🔎 **FAISS-based semantic SQL-template retrieval**
* 🎯 **Compatibility-aware deterministic routing**
* 🤖 **Gemini fallback for unseen SQL patterns**
* 📊 **Multi-step analytical reasoning**
* 🧩 **Structured analytical planning**
* 🔐 **SQL AST firewall and read-only database access**
* 🛡️ **Prompt-injection and input protection**
* 🔄 **SQL reflection / retry for recoverable failures**
* 📈 **Automatic result visualization**
* 📋 **Interactive result tables and KPI cards**
* 💰 **LLM cost tracking**
* ⚡ **Latency and execution monitoring**
* 🧪 **Offline evaluation and benchmark suite**
* 🖥️ **Streamlit enterprise-style BI interface**

---

# 🏗️ Architecture

The system uses two execution paths depending on query complexity.

## Simple Query Path

For straightforward analytical questions:

```text
                    User Question
                          │
                          ▼
                  Input Validation
                          │
                          ▼
               FAISS Semantic Retrieval
                          │
                          ▼
              Template Compatibility
                     Validation
                          │
             ┌────────────┴────────────┐
             │                         │
       Compatible Template        No Suitable Template
             │                         │
             ▼                         ▼
       Template SQL              Gemini SQL Generation
             │                         │
             └────────────┬────────────┘
                          ▼
                    SQL Firewall
                          │
                          ▼
                  PostgreSQL Executor
                          │
                          ▼
                    Result Analysis
                          │
                          ▼
                    BI Presentation
```

### Why retrieval-first?

Instead of generating SQL with an LLM for every query:

```text
User → LLM → SQL
```

the system first attempts:

```text
User → Semantic Retrieval → Existing SQL Template
```

This reduces:

* LLM calls
* latency
* generation errors
* operational cost

while keeping the LLM available for queries that cannot be handled by existing templates.

---

# 🧠 Complex Analytical Query Path

Some questions cannot be reliably answered with a single SQL statement.

For example:

> چرا فروش شهریور نسبت به مرداد کاهش پیدا کرد و چه عواملی باعث این کاهش شدند؟

The system detects that this is a multi-step analytical problem and activates a dedicated analytical workflow.

```text
User Question
      │
      ▼
Deterministic Complexity Detection
      │
      ▼
Structured Gemini Planner
      │
      ▼
Validated Analysis Plan
      │
      ├───────────────┐
      ▼               ▼
Current Period    Previous Period
      │               │
      └───────┬───────┘
              ▼
       Deterministic SQL
              │
              ▼
        PostgreSQL
              │
              ▼
      Python Analytics
              │
      ┌───────┼────────┐
      ▼       ▼        ▼
   Change   Ratio    Ranking
              │
              ▼
        Final Insights
```

### Important design decision

The system does **not** use an LLM for every analytical step.

For complex queries:

* Gemini is used for **high-level planning**
* SQL construction is deterministic whenever possible
* arithmetic is performed in Python
* ratios and percentage changes are deterministic
* ranking is deterministic
* final synthesis does not require another LLM call

This significantly reduces latency and cost.

---

# 📊 Example Analytical Plan

A complex question can be converted into a structured plan such as:

```json
{
  "analysis_type": "causal_change",
  "steps": [
    {
      "id": "current_period_revenue",
      "metric": "revenue",
      "period": "شهریور",
      "operation": "fetch"
    },
    {
      "id": "previous_period_revenue",
      "metric": "revenue",
      "period": "مرداد",
      "operation": "fetch"
    },
    {
      "id": "revenue_percentage_change",
      "operation": "percentage_change",
      "inputs": [
        "current_period_revenue",
        "previous_period_revenue"
      ]
    },
    {
      "id": "revenue_drivers_breakdown",
      "operation": "dimension_breakdown",
      "dimensions": [
        "city",
        "brand"
      ],
      "inputs": [
        "current_period_revenue",
        "previous_period_revenue"
      ]
    }
  ]
}
```

The plan is validated before execution and does not directly execute arbitrary LLM-generated operations.

---

# 🔎 Hybrid Retrieval

The RAG layer contains reusable SQL templates representing common business questions.

Each template contains structured metadata such as:

```text
Template
├── id
├── example_questions
├── SQL
├── intent
├── dimensions
├── metrics
├── filters
├── time_filter
└── supports_top_n
```

FAISS retrieves semantically similar templates.

However, **similarity alone does not determine routing**.

A high similarity score is not sufficient if the template cannot answer the requested question.

For example:

```text
Query:
"فروش تهران در شهریور چقدر بوده؟"

Retrieved template:
"فروش ماهانه در سال جاری"

Semantic similarity:
High

But:
City filter is unsupported
```

The compatibility layer rejects the template and routes the query to the appropriate fallback.

This prevents **false-positive template routing**.

---

# 🎯 Compatibility-Aware Routing

The router checks whether a retrieved template actually supports the semantics of the query.

Validation includes:

### Filters

* city
* brand
* category
* status
* other categorical values

### Time

* month
* year
* relative dates
* calendar periods

### Dimensions

* city
* brand
* category
* gender
* etc.

### Metrics

* revenue
* order count
* quantity
* customer count
* etc.

### Ranking

* Top-N
* best/worst
* ranking-based questions

This creates a two-stage routing strategy:

```text
Semantic Similarity
        │
        ▼
Semantic Compatibility
        │
        ▼
Final Route
```

---

# 🤖 LLM Fallback

When no compatible template is found, Gemini generates SQL from the natural-language request.

The generated SQL is **never executed directly**.

It must pass through the security layer first.

```text
Natural Language
      │
      ▼
Gemini SQL Generation
      │
      ▼
SQL AST Validation
      │
      ▼
Firewall
      │
      ▼
Read-only PostgreSQL
```

---

# 🔐 Security Architecture

Security is treated as a first-class component rather than an afterthought.

## Input Guard

The input layer performs:

* input normalization
* request length limits
* Persian/English prompt-injection detection
* basic rate limiting
* invalid request rejection

---

## SQL Firewall

Generated SQL is parsed using **SQLGlot** and validated as an AST.

The firewall enforces policies such as:

* `SELECT` / CTE only
* allowed tables
* allowed columns
* blocked system catalogs
* blocked comments
* blocked dangerous functions
* maximum query limit
* no destructive statements

Example:

```sql
DROP TABLE orders;
DELETE FROM orders;
UPDATE orders SET revenue = 0;
```

These statements are rejected before execution.

---

## Database Protection

The PostgreSQL execution layer uses:

* read-only database access
* statement timeouts
* controlled query execution
* result-size limits

The application therefore follows:

```text
LLM Output
   ↓
AST Validation
   ↓
Security Policy
   ↓
Read-only Executor
   ↓
Database
```

---

# 🔄 Reflection & Recovery

SQL generation failures are handled through a controlled retry/reflection mechanism.

Example:

```text
Generated SQL
     │
     ▼
Firewall
     │
     ▼
Execution
     │
   Error?
    / \
  No   Yes
  │     │
  ▼     ▼
Result Reflection
        │
        ▼
     Retry
```

The goal is to recover from common SQL-generation issues without blindly retrying indefinitely.

---

# 📈 BI Presentation Layer

The Streamlit interface automatically selects an appropriate presentation format based on the result structure.

### Time-series data

```text
Monthly Revenue
      ↓
Line Chart
```

### Ranking

```text
Top Brands
      ↓
Bar Chart
```

### Small KPI result

```text
Revenue:     1.2B
Orders:      8,421
Customers:   5,102
```

### Detailed result

```text
Interactive Data Table
```

The UI can combine:

* KPI cards
* charts
* tables
* analytical insights
* execution metadata

depending on the query.

---

# 🖥️ Dashboard

The application provides an enterprise-style BI interface built with Streamlit.

Main components include:

```text
┌──────────────────────────────────────────────┐
│                BI ANALYTICS AGENT            │
├───────────────┬──────────────────────────────┤
│               │                              │
│ New Analysis  │     Natural Language Query   │
│               │                              │
│ Examples      │──────────────────────────────│
│               │                              │
│ Recent        │       Key Insights           │
│ Queries       │                              │
│               │       KPI Cards              │
│ System Status │                              │
│               │       Visualization          │
│               │                              │
│ Debug         │       Result Table           │
│               │                              │
└───────────────┴──────────────────────────────┘
```

For debugging and development, the interface can expose safe metadata such as:

* routing mode
* retrieved template
* similarity score
* generated SQL
* execution time
* number of returned rows
* LLM usage
* estimated cost
* firewall status
* retry status

Sensitive information such as API keys is never displayed.

---

# 🧪 Evaluation

The project includes an offline evaluation framework instead of relying only on manual testing.

Evaluation covers:

### Routing

* template retrieval
* compatibility filtering
* correct route selection
* false-positive routing

### Execution

* SQL generation success
* SQL execution success
* result correctness

### Analytical Reasoning

* complexity detection
* planner success
* analytical step completion

### Operational Metrics

* latency
* LLM calls
* token usage
* estimated cost

---

# 📊 Evaluation Results

The routing improvements were evaluated on a benchmark of **250 business questions**.

| Metric                        |   Before |        After |
| ----------------------------- | -------: | -----------: |
| Routing Accuracy              |    84.9% |    **88.4%** |
| Template Route Precision      |    85.7% |    **96.8%** |
| False-Positive Template Hits  |        5 |        **1** |
| Wrong-Template Errors         |        4 |        **1** |
| Execution Success             |     100% |    **98.8%** |
| Strict Result Accuracy        |    90.7% |    **93.0%** |
| Strict Non-Ambiguous Accuracy |    96.2% |    **97.4%** |
| Average Latency               |  3351 ms |  **3326 ms** |
| Average Cost / Query          | $0.00122 | **$0.00121** |

The main improvement came from **compatibility-aware routing**, rather than simply increasing or tuning a similarity threshold.

---

# ⚡ Complex Query Optimization

The initial analytical pipeline used multiple LLM calls for planning, SQL generation, and final synthesis.

This resulted in approximately:

```text
~7.2 LLM calls / complex query
~28.7 sec latency
~$0.0133 / query
```

The optimized architecture reduced this to:

```text
1 planner LLM call
0 SQL-generation LLM calls
0 final-synthesis LLM calls
~2.4 database queries
```

Result:

| Metric                  |   Before |        After |
| ----------------------- | -------: | -----------: |
| LLM Calls               |     ~7.2 |      **1.0** |
| DB Queries              |     ~4–6 |     **~2.4** |
| Latency                 |  ~28.7 s |   **~6.4 s** |
| Cost                    | ~$0.0133 | **~$0.0031** |
| Analytical Step Success |     100% |     **100%** |

This optimization preserves the analytical capability while moving deterministic work out of the LLM.

---

# 💬 Example Questions

### Simple aggregation

```text
فروش تهران چقدر بوده؟
```

### Filtering

```text
فروش تهران در شهریور چقدر بوده؟
```

### Ranking

```text
پرفروش‌ترین برندها کدامند؟
```

### Time series

```text
فروش ماهانه را نشان بده
```

### Detailed analysis

```text
فروش را بر اساس شهر و برند نشان بده
```

### Complex analytical question

```text
چرا فروش شهریور نسبت به مرداد کاهش پیدا کرد؟
```

The final question activates the multi-step analytical pipeline.

---


# 🧩 Design Principles

The project follows several engineering principles.

### 1. Retrieval before generation

Prefer deterministic reusable SQL templates over unnecessary LLM generation.

### 2. LLM only where it adds value

Use the LLM for:

* unseen SQL patterns
* high-level analytical planning

Avoid using it for deterministic operations.

### 3. Security before execution

No generated SQL reaches PostgreSQL without validation.

### 4. Deterministic computation

Arithmetic, ratios, rankings, and other deterministic operations are performed outside the LLM.

### 5. Evaluation-driven development

Architecture decisions are validated against a benchmark rather than subjective demos.

### 6. Cost and latency awareness

LLM usage is treated as an operational resource and monitored explicitly.

### 7. Separation of concerns

```text
Retrieval
    ↓
Routing
    ↓
Planning
    ↓
Execution
    ↓
Analysis
    ↓
Presentation
    ↓
Observability
```

Each layer has a clearly defined responsibility.

---

# 🛡️ Reliability Model

The system does not assume that semantic similarity equals correctness.

Instead:

```text
Similarity
    +
Semantic Compatibility
    +
Security Validation
    +
Database Execution
    +
Result Validation
```

are combined to produce a reliable execution pipeline.

This is particularly important for enterprise BI systems where a **confidently wrong number is often worse than an explicit failure**.

---

# 🚧 Known Limitations

Current limitations include:

* Some business metrics can have multiple valid definitions.
* Historical database coverage can affect analytical conclusions.
* Natural-language ambiguity may still require clarification.
* LLM latency can dominate complex-query latency.
* The current schema allow-list is intentionally restrictive.
* The benchmark currently focuses on a controlled business schema.

These limitations are treated as part of the evaluation and system-design process rather than hidden from the user.

---

# 🔮 Future Improvements

Potential future extensions include:

* semantic metric catalog
* business glossary / metric definitions
* automatic clarification questions
* query-result caching
* parallel execution of independent analytical steps
* richer anomaly detection
* trend and seasonality analysis
* row-level security
* user-level permissions
* multi-database support
* query cost estimation
* human feedback loop

---

# 🧠 Technical Stack

| Component       | Technology                 |
| --------------- | -------------------------- |
| Language        | Python                     |
| LLM             | Google Gemini              |
| Database        | PostgreSQL                 |
| Vector Search   | FAISS                      |
| SQL Parsing     | SQLGlot                    |
| UI              | Streamlit                  |
| Data Processing | Pandas                     |
| Visualization   | Plotly / Streamlit         |
| Evaluation      | Custom benchmark framework |

---

# 🎯 What This Project Demonstrates

This project is designed to demonstrate practical experience with:

* **LLM application architecture**
* **RAG systems**
* **Text-to-SQL**
* **Semantic retrieval**
* **Hybrid routing**
* **Structured LLM outputs**
* **Agentic workflows**
* **Analytical reasoning**
* **SQL security**
* **Prompt-injection defense**
* **PostgreSQL**
* **Vector search**
* **LLM cost optimization**
* **Latency optimization**
* **Observability**
* **Offline evaluation**
* **Production-oriented system design**

The central design principle is simple:

> **Use the LLM where reasoning is required, and deterministic software everywhere else.**

---

# 📌 Project Status

**Status:** Active / Production-oriented prototype

The current implementation supports:

* Simple BI queries
* Semantic SQL-template retrieval
* LLM SQL fallback
* Compatibility-aware routing
* Secure SQL execution
* Multi-step analytical queries
* Cost and latency tracking
* Automated evaluation
* Interactive BI visualization

---

## ⭐ Why this architecture?

A naive Text-to-SQL architecture looks like:

```text
User
 ↓
LLM
 ↓
SQL
 ↓
Database
```

This project intentionally goes further:

```text
                  ┌───────────────┐
                  │ User Question │
                  └───────┬───────┘
                          │
                          ▼
                  ┌───────────────┐
                  │ Input Guard   │
                  └───────┬───────┘
                          │
                          ▼
               ┌─────────────────────┐
               │ Complexity Detector │
               └──────────┬──────────┘
                          │
             ┌────────────┴────────────┐
             │                         │
          Simple                    Complex
             │                         │
             ▼                         ▼
      FAISS Retrieval            LLM Planner
             │                         │
             ▼                         ▼
      Compatibility              Validated Plan
             │                         │
       ┌─────┴─────┐                   │
       │           │                   │
   Template      Gemini                │
       │           │                   │
       └─────┬─────┘                   │
             │                         │
             └────────────┬────────────┘
                          ▼
                    SQL Firewall
                          │
                          ▼
                  PostgreSQL Executor
                          │
                          ▼
                 Deterministic Analysis
                          │
                          ▼
                    BI Presentation
                          │
                          ▼
                    Observability
```

This architecture balances **accuracy, security, cost, latency, and flexibility** instead of optimizing for LLM usage alone.
