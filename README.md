# AlphaLens — AI-Powered Stock Analysis System

**AlphaLens** is an investment analysis platform that combines a multi-agent AI workflow, vector search over SEC filings, and financial data aggregation to produce comprehensive stock insights based on fundamentals, filings, news, and sentiment.

---

## 🎯 Overview

AlphaLens automates investment research by:

- **Ingesting SEC filings** (10-K, 10-Q, 8-K) and creating searchable vector embeddings
- **Fetching financial data** from Yahoo Finance and Financial Modeling Prep
- **Scoring companies** across financial health, growth, valuation, moat, and predictability
- **Detecting red flags** from accounting metrics and filing language
- **Analyzing sentiment** from recent news articles
- **Orchestrating agents** via LangGraph into a single analysis workflow exposed over a FastAPI backend

---

## 🏗️ Architecture

### High-Level System

```
┌──────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                        │
│   /analyze/{ticker} | /financials/{ticker} | /scorecard/{ticker}  │
│             /ask/{ticker} | /ask | /health                        │
└────────────────────────────────┬─────────────────────────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │   LangGraph Orchestrator │
                     │    (StateGraph / DAG)    │
                     └────────────┬─────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                        │
     ┌────▼─────┐         ┌───────▼────────┐       ┌──────▼──────┐
     │Financial │         │     Scorer     │       │  Red Flag   │
     │  Agent   │         │     Agent      │       │    Agent    │
     └────┬─────┘         └───────┬────────┘       └──────┬──────┘
          │                       │                       │
     ┌────▼─────┐         ┌───────▼────────┐       ┌──────▼──────┐
     │   News   │         │      RAG       │       │  Database   │
     │  Agent   │         │     Agent      │       │ (Postgres)  │
     └──────────┘         └────────────────┘       └─────────────┘
```

### Data Flow

```
┌──────────────┬─────────────────┬──────────────┬─────────────────┐
│ SEC EDGAR    │ Yahoo Finance   │ FMP API      │ News Sources    │
│ (10-K/Q/8-K) │ (free)          │ (/stable)    │ (yfinance/RSS)  │
└──────┬───────┴────────┬────────┴──────┬───────┴────────┬────────┘
       │                │               │                │
       ▼                ▼               ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐
│   Scraper   │  │   YFinance  │  │ FMP Client  │  │  News    │
│  (SEC API)  │  │   Fetcher   │  │  (httpx)    │  │ Scraper  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬────┘
       │                └───────┬────────┘               │
       ▼                        ▼                         ▼
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│  Chunker →  │         │  Normalizer  │         │  Sentiment   │
│  Embedder   │         │  → Financials│         │   Analyzer   │
│  (Gemini)   │         │    Table     │         │  (Gemini)    │
└──────┬──────┘         └──────┬───────┘         └──────┬───────┘
       │                       │                        │
       ▼                       ▼                        ▼
┌──────────────────────────────────────────────────────────────┐
│              PostgreSQL Database (pgvector)                    │
├────────────────┬────────────────┬─────────────────────────────┤
│  sec_filings   │  sec_chunks    │  financials                 │
│  scorecard     │  red_flags     │  data_fetch_log             │
└────────────────┴────────────────┴─────────────────────────────┘
```

### Agents

| Agent | Responsibility | Key Modules |
|-------|----------------|-------------|
| **RAG Agent** | SEC filing ingestion, embedding, retrieval | `scraper`, `chunker`, `embedder`, `cache_manager`, `retriever`, `grader` |
| **Financial Agent** | Fundamentals aggregation & normalization | `yahoo_finance`, `fmp_client`, `data_normalizer` |
| **Scorer Agent** | 5-dimensional investment scoring | `financial_health`, `growth_scorer`, `valuation_scorer`, `moat_scorer`, `predictability_scorer`, `scorecard_builder` |
| **Red Flag Agent** | Risk detection from financials & filings | `financial_flags`, `filing_flags`, `flag_aggregator` |
| **News Agent** | News scraping & sentiment | `news_scraper`, `sentiment_analyzer` |

---

## 📊 Database Schema

PostgreSQL with the `pgvector` extension. Six tables:

#### `sec_filings`
Metadata for SEC filings (10-K, 10-Q, 8-K).
```sql
id UUID PK | ticker | filing_type | filing_date | accession_number (unique)
url | period_of_report | is_processed | created_at | updated_at
```

#### `sec_chunks`
Section-aware text chunks with embeddings.
```sql
id UUID PK | filing_id FK | ticker | section_type | chunk_index
chunk_text | embedding VECTOR(3072)  -- gemini-embedding-001 | created_at
```

#### `financials`
Financial statements and ratios — income statement, balance sheet, cash flow,
and valuation metrics (revenue, margins, EPS, debt ratios, FCF, PE/PB/PS, EV/EBITDA,
market cap), plus `raw_data JSONB`, `source` (YAHOO / FMP / YAHOO_FMP), and timestamps.

#### `scorecard`
Per-company investment scores (0–100): `financial_health_score`, `growth_score`,
`valuation_score`, `moat_score`, `predictability_score`, `overall_score`,
`score_details JSONB`, plus timestamps.

#### `red_flags`
Warning indicators: `category` (FINANCIAL / FILING / GOVERNANCE),
`severity` (LOW / MEDIUM / HIGH), `flag_type`, `description`, timestamps.

#### `data_fetch_log`
Audit trail for every fetch: `source`, `data_type`, `status` (SUCCESS / FAILED / PARTIAL),
`records_fetched`, `error_message`, `fetched_at`.

---

## 🔧 Technology Stack

- **Language:** Python 3.12
- **API:** FastAPI + Uvicorn
- **ORM / DB driver:** SQLAlchemy 2.x (async) + asyncpg
- **Database:** PostgreSQL with `pgvector`
- **Orchestration:** LangGraph (`langgraph` 1.0.x), with optional LangSmith tracing
- **AI / Embeddings:** Google Gemini via `google-genai` — `gemini-embedding-001` (3072-dim) for embeddings, Gemini chat models for sentiment & Q&A
- **Data sources:** SEC EDGAR (free, 10 req/s), Yahoo Finance (`yfinance`), Financial Modeling Prep (`/stable`), news via yfinance + Yahoo RSS + optional NewsAPI
- **Infra:** Docker Compose (Postgres + pgvector), Conda for environment management

See [requirements.txt](requirements.txt) for pinned versions.

---

## 🚀 Setup

### 1. Prerequisites
- Python 3.12+ (Conda recommended)
- Docker Desktop

### 2. Environment
```bash
cd AlphaLens
conda create -n StablePythonEnv python=3.12
conda activate StablePythonEnv
pip install -r requirements.txt
```

### 3. Configure environment variables
Create a `.env` file in the project root. The database URL is assembled from the
individual `POSTGRES_*` variables in [src/dbo/database.py](src/dbo/database.py):

```bash
# Database (Docker maps host port 5433 -> container 5432)
POSTGRES_USER=alphalens_user
POSTGRES_PASSWORD=alphalens_pass
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=alphalens

# Google Gemini API (required for embeddings, sentiment, Q&A)
GEMINI_API_KEY=your_gemini_api_key_here
EMBEDDING_MODEL=gemini-embedding-001

# Financial Modeling Prep (optional — free tier: 250 req/day)
FMP_API_KEY=your_fmp_api_key_here

# Optional integrations
NEWSAPI_KEY=your_newsapi_key_here

# Optional: LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=AlphaLens
```

When the LangSmith variables are set, orchestration runs are automatically traced
(run name, ticker metadata, request parameters, and `alphalens` / `orchestration`
tags) via [src/orchestration/langsmith_config.py](src/orchestration/langsmith_config.py).

### 4. Start the database & initialize the schema
```bash
docker-compose up -d
conda run -n StablePythonEnv python -m src.dbo.init_db
```
`init_db` enables the `pgvector` extension, creates all tables, and builds the
IVFFlat index on `sec_chunks.embedding`.

### 5. Run the API
```bash
./start_api.sh
# or
conda run -n StablePythonEnv uvicorn main:app --reload
```
- API root: http://localhost:8000/
- Swagger UI: http://localhost:8000/docs

---

## 🔌 API Endpoints

All endpoints are served under the `/api/v1` prefix. Access is currently open
(no authentication); API keys are planned for a future release.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/analyze/{ticker}` | Full orchestrated analysis (financial + scoring + red flags + news; `?include_sec_analysis=true` adds SEC filing analysis, `?async_mode=true` runs in the background) |
| `GET`  | `/analysis-status/{analysis_id}` | Poll the status of a background (async) analysis |
| `GET`  | `/analysis-result/{analysis_id}` | Fetch a completed background analysis result |
| `GET`  | `/financials/{ticker}` | **Read** the latest stored financial data (no external fetch) |
| `GET`  | `/scorecard/{ticker}` | **Read** the latest stored investment scores (no recompute) |
| `POST` | `/ask/{ticker}` | Ask an AI question about a stock — Gemini-generated, grounded in scores, red flags, news, and (when filings are ingested) cited SEC filing excerpts |
| `POST` | `/ask` | Ask a general investment question (Gemini-generated) |
| `GET`  | `/health` | Overall system health |
| `GET`  | `/health/quick` | Fast liveness check |
| `GET`  | `/health/database` | Database connectivity |
| `GET`  | `/health/apis` | External API status (Yahoo, FMP, Gemini) |

> `/financials` and `/scorecard` are read-only and return stored data — run
> `POST /analyze/{ticker}` first to populate or refresh it. Q&A endpoints fall back
> to deterministic templated answers when no Gemini key is configured.

**Example:**
```bash
# Full analysis (with SEC filing analysis, if filings are ingested)
curl -X POST "http://localhost:8000/api/v1/analyze/AAPL?include_sec_analysis=true"

# Background analysis, then poll + fetch
curl -X POST "http://localhost:8000/api/v1/analyze/AAPL?async_mode=true"
curl "http://localhost:8000/api/v1/analysis-status/<analysis_id>"
curl "http://localhost:8000/api/v1/analysis-result/<analysis_id>"

# Ask a question about a stock
curl -X POST "http://localhost:8000/api/v1/ask/AAPL" \
  -H "Content-Type: application/json" \
  -d '{"question": "Is AAPL a good long-term investment?"}'
```

---

## 🔀 LangGraph Orchestration

AlphaLens coordinates agents through a LangGraph `StateGraph`. The Financial Agent
runs first (it is a data dependency); the Scorer, Red Flag, and News agents then run
in parallel; finally a report node aggregates results into a recommendation. When
`include_sec_analysis=true`, a SEC filing-analysis node joins the parallel branch
(it reads already-ingested filings; it does not scrape/embed).

```
START → Financial Agent ─┬─→ Scorer Agent ───┐
                         ├─→ Red Flag Agent ──┤
                         ├─→ News Agent ───────┼─→ Final Report → END
                         └─→ SEC Agent* ──────┘
                            (*only if include_sec_analysis=true)
```

### Shared state
```python
class AnalysisState(TypedDict):
    ticker: str
    financial_data: Dict[str, Any]
    scores: Dict[str, float]
    red_flags: Dict[str, Any]
    news_sentiment: Dict[str, Any]
    errors: Annotated[List[str], operator.add]  # concurrent aggregation
    started_at: datetime
    completed_at: datetime
    workflow_status: str
    recommendation: str   # STRONG BUY | BUY | HOLD | SELL | STRONG SELL
    confidence: float     # 0.0–1.0
    summary: str
```

- `Annotated[List[str], operator.add]` lets the parallel nodes aggregate errors safely.
- Scorer and Red Flag nodes skip gracefully if the Financial Agent fails.

### Recommendation logic
```python
if   score >= 80: "STRONG BUY"
elif score >= 70: "BUY"
elif score >= 50: "HOLD"
elif score >= 40: "SELL"
else:             "STRONG SELL"

# Confidence starts at 0.7 and is adjusted by news availability
# and the presence of medium/high red flags.
```

### Programmatic usage
```python
from src.orchestration import run_analysis

result = await run_analysis("AAPL")
print(result["recommendation"], result["confidence"])
print(result["summary"])
```

---

## 🧮 Scoring Methodology

Each dimension is scored 0–100 (higher is better; for valuation, lower ratios score
higher). The default weights are:

| Dimension | Weight | Signals |
|-----------|--------|---------|
| Financial Health | 25% | Liquidity, solvency, cash-flow quality |
| Growth | 20% | Revenue / EPS trends, margin expansion |
| Valuation | 20% | PE, PS, PB, EV/EBITDA |
| Moat | 20% | ROE, profit margins, capital efficiency |
| Predictability | 15% | Earnings consistency / volatility |

The weighted overall score maps to the recommendation tiers above.

### Red flag severity thresholds
- **HIGH:** current ratio < 1.0, D/E > 200%, margin decline > 5pp, negative FCF
- **MEDIUM:** current ratio < 1.2, D/E > 150%, margin decline > 3pp, goodwill > 30%
- **LOW:** other notable concerns

### Sentiment classification
Scores range from −1.0 to +1.0: positive (> 0.3), neutral (−0.3 to 0.3),
negative (< −0.3), with a keyword-based fallback when Gemini is unavailable.

---

## 🔒 Rate Limits & Quotas

| Source | Limit | Notes |
|--------|-------|-------|
| SEC EDGAR | 10 req/sec | Free; requires a `User-Agent` header |
| Gemini (free tier) | 100 req/min, 1000 req/day | Quota resets daily (UTC); sliding-window limiter implemented |
| Yahoo Finance | none official | Avoid aggressive scraping |
| FMP (free tier) | 250 req/day | `/stable` endpoints only |

---

## 📁 Project Structure

```
AlphaLens/
├── README.md
├── docker-compose.yml          # PostgreSQL + pgvector
├── requirements.txt
├── pytest.ini                  # Test discovery & markers
├── main.py                     # FastAPI entry point (uvicorn main:app)
├── run_api.py                  # Programmatic server launcher
├── start_api.sh                # Conda-based server launcher
├── run_tests.py                # CLI test runner / benchmark eval
├── .env                        # Environment variables (git-ignored)
│
├── src/
│   ├── agents/
│   │   ├── rag_agent/          # scraper, chunker, embedder, cache_manager,
│   │   │                       #   retriever, grader
│   │   ├── financial_agent/    # yahoo_finance, fmp_client, data_normalizer
│   │   ├── scorer_agent/       # 5 scorers + scorecard_builder
│   │   ├── red_flag_agent/     # financial_flags, filing_flags, flag_aggregator
│   │   └── news_agent/         # news_scraper, sentiment_analyzer
│   │
│   ├── dbo/
│   │   ├── database.py         # Async session management & health check
│   │   ├── init_db.py          # Schema + pgvector + index initialization
│   │   ├── models/             # SQLAlchemy models
│   │   └── repositories/       # Data-access layer (one repo per table)
│   │
│   ├── orchestration/
│   │   ├── state.py            # AnalysisState TypedDict
│   │   ├── nodes.py            # Agent wrapper functions
│   │   ├── graph.py            # StateGraph builder + run_analysis
│   │   └── langsmith_config.py # Optional tracing config
│   │
│   └── api/
│       ├── main.py             # Application factory
│       ├── routes/             # analysis.py, health.py
│       └── schemas/            # analysis.py (Pydantic request/response models)
│
└── tests/
    ├── conftest.py             # Shared fixtures
    ├── fixtures/               # alphalens_eval_benchmark.json
    ├── agents/                 # Unit tests + *_manual.py exploratory scripts
    ├── orchestration/          # Workflow tests + manual script
    └── integration/            # test_api.py (API endpoint tests)
```

---

## ✅ Component Status

| Component | Status | Notes |
|-----------|--------|-------|
| Database layer | ✅ Complete | Async models, repositories, audit trail |
| Financial Agent | ✅ Complete | Yahoo + FMP (`/stable`), normalization, upsert |
| Scorer Agent | ✅ Complete | 5-dimensional scoring + weighted scorecard |
| Red Flag Agent | ✅ Complete | Financial + filing flags, severity classification |
| News Agent | ✅ Complete | Multi-source scraping + Gemini sentiment + fallback |
| LangGraph orchestration | ✅ Complete | Sequential → parallel → report |
| FastAPI backend | ✅ Complete | Analysis, scorecard, Q&A, and health endpoints |
| RAG ingestion (scrape/chunk/embed) | ✅ Complete | Section-aware chunking, rate-limited Gemini embeddings |
| RAG retrieval / grading | ✅ Wired in | Agentic retrieve → grade → answer. Used by `/ask/{ticker}` (cited excerpts) and by the optional SEC node in the `/analyze` workflow. Analyzes already-ingested filings; ingestion (`ingest_company`) remains an offline step. |
| Q&A generation | ✅ LLM-backed | `/ask` and `/ask/{ticker}` use Gemini grounded in gathered context, with a deterministic templated fallback when no key is set. |
| Async analysis | ✅ Functional | `?async_mode=true` + `/analysis-status` / `/analysis-result`. State is in-memory (single-process) — see Known Issues. |
| Authentication | ⏳ Planned | Endpoints are currently open access |
| Web dashboard / deployment | ⏳ Planned | — |

---

## 🧪 Testing

Tests use **pytest** with `pytest-asyncio` (async mode) and `pytest-cov`. The suite
contains ~100 automated tests across the agents, orchestration, and API, plus
`*_manual.py` exploratory scripts that hit live data sources.

```
tests/
├── agents/
│   ├── test_financial_agent.py      (3)
│   ├── test_news_agent.py           (18)
│   ├── test_rag_agent.py            (22)
│   ├── test_red_flag_agent.py       (17)
│   └── test_scorer_agent.py         (20)
├── orchestration/
│   └── test_orchestration.py        (21)
└── integration/
    └── test_api.py                  (1)
```

### Running tests

```bash
# All tests
conda run -n StablePythonEnv pytest tests/ -v

# A specific module
pytest tests/agents/test_news_agent.py -v

# By marker (markers: unit, integration, slow, rag, financial,
#            scorer, red_flag, news, orchestration)
pytest -m "not slow" -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### CLI test runner ([run_tests.py](run_tests.py))

```bash
python run_tests.py                  # all tests
python run_tests.py --agent news     # one agent: financial|scorer|red_flag|news|rag|orchestration
python run_tests.py --coverage       # coverage report
python run_tests.py --unit-only      # fast unit tests only
python run_tests.py -k sentiment     # filter by name pattern
python run_tests.py -x               # fail-fast
python run_tests.py --eval           # benchmark eval over tests/fixtures/alphalens_eval_benchmark.json
```

### Manual / live-data scripts
```bash
conda run -n StablePythonEnv python tests/agents/test_financial_agent_manual.py
conda run -n StablePythonEnv python tests/orchestration/test_orchestration_manual.py
```

---

## 🗺️ Roadmap

- [x] Wire the RAG retriever + grader into the `/ask` flow with citations
- [x] Add a SEC/RAG node to the LangGraph workflow (`include_sec_analysis`)
- [ ] Move background-analysis state to Redis/DB for multi-worker production
- [ ] API key authentication and per-key rate limiting
- [ ] Peer comparison and historical trend analysis
- [ ] Web dashboard (React/Next.js)
- [ ] Cloud deployment, monitoring, and CI/CD

---

## 🐛 Known Issues

1. **Gemini daily quota (free tier):** 1000 embedding requests/day limits how many
   large filings can be ingested per day. Workaround: wait for the daily reset or
   upgrade to a paid tier. A sliding-window limiter with exponential backoff is
   implemented to stay within the per-minute cap.
2. **FMP v3 endpoints deprecated** for new users — resolved by migrating to `/stable`.
3. **`google.generativeai` deprecated** — resolved by migrating to the `google-genai` client.
4. **Background analysis state is in-memory** (a per-process dict), so `async_mode`
   results are lost on restart and not shared across workers. Fine for single-process
   dev; production needs Redis or a DB-backed store.
5. **SEC analysis requires pre-ingested filings.** `include_sec_analysis` (and the
   filing grounding in `/ask`) analyze filings already in pgvector; they do not trigger
   ingestion. Run `ingest_company` offline first (it is slow and Gemini-quota bound).

---

## 🤝 Contributing

```bash
git clone https://github.com/your-username/AlphaLens.git
cd AlphaLens
conda create -n StablePythonEnv python=3.12
conda activate StablePythonEnv
pip install -r requirements.txt
```

**Code style:** PEP 8 with type hints, Google-style docstrings, async for all I/O,
and explicit error logging (never fail silently).

---

## 📚 Resources

- [SEC EDGAR API](https://www.sec.gov/edgar/sec-api-documentation)
- [Financial Modeling Prep Docs](https://site.financialmodelingprep.com/developer/docs)
- [Gemini Embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
- [LangGraph](https://langchain-ai.github.io/langgraph/)

---

## 📧 Contact

**Project Lead:** Ananth Nityandal
**Email:** ananthnityandal2000@gmail.com

*License: proprietary and confidential.*
