# Mutual Fund FAQ Assistant (Groww Facts-Only RAG)

> **Compliance Disclaimer**: *Facts-only. No investment advice.*

A production-ready, compliance-first Retrieval-Augmented Generation (RAG) assistant strictly scoped to answer objective, factual questions for 5 selected mutual fund schemes on Groww.

---

## 1. Corpus Whitelist (Strict Scope)

The corpus is strictly limited to the following 5 Groww mutual fund scheme pages. No external AMC PDFs, AMFI pages, SEBI pages, or aggregator sites are ingested or cited. Every fact returned originates from one of these 5 URLs, and every citation links verbatim to one of these 5 URLs:

1. **Mid Cap Equity**: [HDFC Mid-Cap Opportunities Fund (Direct Growth)](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth)
2. **Flexi Cap Equity**: [HDFC Flexi Cap Fund (Direct Growth)](https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth)
3. **Focused Equity**: [HDFC Focused 30 Fund (Direct Growth)](https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth)
4. **ELSS (Tax Saver)**: [HDFC ELSS Tax Saver Fund (Direct Plan Growth)](https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth)
5. **Large Cap Equity**: [HDFC Top 100 Fund (Direct Growth)](https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth)

---

## 2. Project Directory Structure

```
mutual-fund-rag/
├── .github/
│   └── workflows/
│       └── daily_data_refresh.yml     # Automated daily ingestion & verification scheduler
├── Dockerfile                         # Production container definition (Python 3.10-slim, non-root)
├── .dockerignore                      # Container build context exclusions
├── problem-statement.md               # Base problem statement & compliance constraints
├── phase-wise-architecture.md         # Full phase-wise architectural specification
├── edgecase.md                        # Comprehensive edge case test specification
├── README.md                          # Production release documentation & operations guide
├── requirements.txt                   # Project dependencies
├── data/
│   ├── corpus_registry.json           # Catalog of the 5 whitelisted Groww URLs & metadata
│   ├── raw_html/                      # Cached HTML snapshots of scheme pages
│   ├── processed_chunks/              # Extracted structured chunks (45 thematic units)
│   └── chroma_db/                     # Persistent vector database & local fallback index
├── src/
│   ├── __init__.py
│   ├── config.py                      # Allowed whitelist constants, paths & validation rules
│   ├── frontend/                      # Phase 6 responsive UI (Groww dark mode, sidebar, chat bubbles)
│   │   ├── index.html                 # Semantic HTML structure & accessible layouts
│   │   ├── style.css                  # Custom CSS design system with Groww emerald theme
│   │   └── app.js                     # Frontend state management, history & API client
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── registry.py                # Phase 1 registry loader & whitelist invariant validator
│   │   ├── scraper.py                 # Phase 2 HTML fetcher & snapshot cache
│   │   ├── extractor.py               # Phase 2 fact parser & structured chunker
│   │   └── indexer.py                 # Phase 3 ChromaDB embeddings indexer
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── pii_filter.py              # Phase 4 PII detection (PAN, Aadhaar, Phone, Folio)
│   │   └── intent_guard.py            # Phase 4 Advisory refusal & out-of-scope classifier
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── retriever.py               # Phase 3 Scheme retriever & citation selector
│   │   ├── generator.py               # Phase 5 Constrained LLM response generator
│   │   └── validator.py               # Phase 5 Output validator (<= 3 sentences, 1 URL, footer)
│   └── app.py                         # Phase 6 Multi-threaded HTTP server with REST endpoints
└── tests/
    ├── __init__.py
    ├── test_phase1_registry.py        # Phase 1: Scheme registry & whitelist invariance tests
    ├── test_phase2_scraper.py         # Phase 2.1: Live snapshot fetching & caching tests
    ├── test_phase2_extractor.py       # Phase 2.2: Chunk extraction & metadata schema tests
    ├── test_phase3_retrieval.py       # Phase 3: ChromaDB dense search & routing tests
    ├── test_phase4_guardrails.py      # Phase 4: PII blocking & intent refusal tests
    ├── test_phase5_generation.py      # Phase 5: Constrained output & validator tests
    ├── test_phase6_ui.py              # Phase 6: REST endpoints & UI integration tests
    ├── test_citation_whitelist.py     # Phase 7: Strict citation whitelist invariance & domain isolation
    ├── test_guardrails.py             # Phase 7: Advisory refusal & PII sanitization invariance
    └── test_factual_accuracy.py       # Phase 7: 25-query factual grounding benchmark against Groww snapshots
```

---

## 3. Phase 1: Scheme Registry & Whitelist Governance

Phase 1 establishes the foundational data contracts and invariants:
- **`data/corpus_registry.json`**: Authoritative registry for the 5 HDFC schemes on Groww, tracking scheme IDs, display names, categories, plan types, and aliases for natural language query resolution.
- **`src/config.py`**: Immutable constants including `ALLOWED_URLS` (`frozenset`), paths, and URL validation helper `is_allowed_url()`.
- **`src/ingestion/registry.py`**: Validates that exactly 5 schemes are registered, verifies that all URLs strictly match the whitelist, prevents duplicate entries, and provides alias resolution.
- **`tests/test_phase1_registry.py`**: 9 unit tests verifying scheme counts, category diversity, alias resolution, domain security, and unapproved URL rejection.

---

## 4. Phase 2: Ingestion & Extraction Engine

### Phase 2.1: HTML Fetching & Local Caching
- **`src/ingestion/scraper.py`**: Fetches live scheme pages with browser headers and caches snapshots in `data/raw_html/<scheme_id>.html`.
- **`tests/test_phase2_scraper.py`**: Asserts HTML size, structure, and payload validity.

### Phase 2.2: Fact Extraction & Structured Chunking
- **`src/ingestion/extractor.py`**: Parses scheme attributes from cached snapshots and builds 9 atomic, thematic chunks per scheme (45 chunks total) with strict attribution to the 5 Groww URLs:
  - `expense_ratio` (TER % and GST terms)
  - `exit_load` (penalties and holding period thresholds, or Nil for ELSS)
  - `min_investment` (minimum SIP and lumpsum)
  - `lock_in_period` (3-year statutory lock-in for ELSS under Sec 80C vs. Nil)
  - `riskometer` (official Riskometer classification)
  - `benchmark` (benchmark index comparison)
  - `fund_managers` (names and background)
  - `scheme_overview` (AUM, NAV, and launch metadata)
  - `taxation` (equity mutual fund capital gains & 80C deduction rules)
- **`data/processed_chunks/`**:
  - `data/processed_chunks/<scheme_id>.json` (individual scheme chunks)
  - `data/processed_chunks/all_chunks.json` (consolidated catalog)
- **`tests/test_phase2_extractor.py`**: Unit tests verifying chunk counts, topic completeness, non-empty fields, and 100% whitelist citation compliance.

---

## 5. Phase 3: Vector Storage & Context Retrieval

### Phase 3.1: Vector Storage Architecture
- **`src/ingestion/indexer.py`**:
  - Initializes **ChromaDB** with `PersistentClient` in `data/chroma_db/`.
  - Embeds all 45 scheme chunks into 384-dimensional dense vectors using `all-MiniLM-L6-v2`.
  - Maintains a zero-dependency, self-contained fallback vector store (`LocalVectorStore` in `data/chroma_db/local_index.json`) for seamless offline operation.
  - Enforces that 100% of indexed chunks contain verified canonical URLs in `ALLOWED_URLS`.

### Phase 3.2: Context Retrieval & Attribution Contract
- **`src/rag/retriever.py`**:
  - **Scheme-Aware Routing**: Resolves colloquial or ambiguous user scheme references (e.g. *"tax saver"*, *"top 100"*, *"flexi cap"*) using `CorpusRegistry.resolve_scheme_from_text()`.
  - **Metadata-Filtered Search**: Filters retrieval candidates by `scheme_id` to eliminate cross-fund hallucination.
  - **Dense Similarity Ranking**: Computes cosine similarity across chunks, retrieving the top $K=3$ candidate passages.
  - **Attribution Binding**: The top-scoring chunk's `source_url` is deterministically bound as the response's single canonical citation URL.
- **`tests/test_phase3_retrieval.py`**: 4 unit tests verifying ChromaDB persistence, topic precision, scheme routing, and 100% citation compliance.

---

## 6. Phase 4: Guardrails, Privacy & Refusal Engine

Phase 4 enforces strict boundary defense before queries reach retrieval or generation:
- **`src/guardrails/pii_filter.py`**:
  - Intercepts and blocks **PAN** (standard & spaced/obfuscated e.g. `A B C D E 1 2 3 4 F`), **Aadhaar** (12-digit numeric sequences), **Phone Numbers** (+91, 0, raw), and **Folio / Account Numbers**.
  - Immediate redaction alert: zero storage or logging of personal financial identifiers.
- **`src/guardrails/intent_guard.py`**:
  - Rejects **Advisory & Recommendation queries** (*"Should I invest?", "Where to put money?"*).
  - Rejects **Scheme Comparisons & Rankings** (*"Which is better: HDFC Top 100 or Flexi Cap?"*).
  - Rejects **Performance Speculations** (*"Will it give 20% next year?"*).
  - Enforces **Domain Boundary** (*"What is the exit load for SBI Small Cap?"*).
  - Withstands **Prompt Injections & Jailbreaks** (*"Ignore previous instructions"*).
  - **Zero External Citation Invariant**: Refusals contain zero unauthorized links.
- **`tests/test_phase4_guardrails.py`**: 12 unit tests for PII and intent guardrails.

---

## 7. Phase 5: Constrained Generation & Output Validator

Phase 5 enforces the deterministic attribution contract and facts-only response synthesis:
- **`src/rag/validator.py`**:
  - **Sentence Count Enforcer**: Tokenizes text while preserving abbreviations (`"Rs."`, `"Mr."`, `"p.a."`, `"0.85%"`) to assert length is $\ge 1$ and $\le 3$ sentences.
  - **Single Citation Whitelist Validator**: Regex extracts markdown links and asserts count == 1 and `cited_url in ALLOWED_URLS`.
  - **Mandatory Footer Enforcer**: Asserts presence of `Last updated from sources: <date>`.
  - **Deterministic Auto-Repair**: Programmatic repair function ensuring compliant output if model drafts vary.
- **`src/rag/generator.py`**:
  - Compliance system prompt strictly forbidding investment advice, opinions, and hallucinations.
  - Multi-provider support: Google Gemini (`gemini-1.5-flash`), OpenAI (`gpt-4o-mini`), and local deterministic grounded synthesis.
  - **Zero CTA on Missing Information**: When factual information is not available or query is ungrounded, returns `"I do not have this factual information in the official scheme documentation."` with `citation_url: ""` and 0 citation links.
  - **Standardized Attribution**: For grounded queries, uses `"You can review the scheme details directly using the below link"`.
- **`tests/test_phase5_generation.py`**: 9 unit tests verifying validator constraints and end-to-end generator output.

---

## 8. Phase 6: Responsive Web Application & REST API

Phase 6 provides a custom web application tailored to Groww's design aesthetics:
- **Frontend Architecture (`src/frontend/`)**:
  - **Left Sidebar**: Displays the 5 supported mutual funds (with clickable badge triggers) and live session chat history. Includes a "New Chat" action to reset conversations.
  - **Quick Prompt Bubbles**: Floating suggestion pills situated directly above the chat input box (e.g. *"Expense ratio of HDFC Mid Cap"*, *"Lock-in period of ELSS"*, *"Min SIP for Flexi Cap"*).
  - **Groww Aesthetic Design System**: Deep dark mode palette (`#0E1118`, `#121622`, `#1E2538`) with Groww emerald accent (`#00D09C`), glassmorphism message bubbles, and smooth micro-animations.
  - **Clean Compliance UI**: No intrusive top banner; includes a subtle bottom disclaimer: *"Facts-only assistant. Strictly limited to 5 HDFC schemes. Not financial advice."*
  - **Conditional Citation Card**: Emits a prominent, clickable citation button linking to the official Groww scheme page when factual data is provided. When factual information is missing, the CTA button is completely suppressed.
- **Backend Architecture (`src/app.py`)**:
  - Built using Python's standard `http.server.ThreadingHTTPServer` (zero extra heavyweight dependencies like Streamlit or Flask required).
  - `GET /api/funds`: Returns the catalog of 5 supported schemes.
  - `POST /api/query`: Ingests user query JSON, passes it through the full 5-stage RAG compliance pipeline, and returns validated JSON output.
  - Configurable port via CLI `--port` or environment variable `PORT` (defaults to `8501`).
- **`tests/test_phase6_ui.py`**: 8 integration unit tests validating static asset serving, REST endpoints, and query processing.

---

## 9. Phase 7: Evaluation, Compliance & Verification Suite

Phase 7 contains exhaustive automated compliance tests:
- **`tests/test_citation_whitelist.py`**:
  - **100% Whitelist Invariance**: Asserts that every single grounded query produces citations exclusively from `ALLOWED_URLS`.
  - **Domain Isolation**: Asserts zero occurrences of external domains (`amfiindia.com`, `sebi.gov.in`, `hdfcfund.com`, or unapproved PDFs).
  - **Ungrounded Query Invariance**: Asserts 0 citation links and empty `citation_url` when information is missing.
- **`tests/test_guardrails.py`**:
  - **Advisory & Comparison Refusal**: Validates 10 advisory and fund comparison prompts to guarantee 100% polite refusal without investment guidance.
  - **PII Sanitization**: Verifies that PAN, Aadhaar, and phone numbers are intercepted immediately with zero retention.
- **`tests/test_factual_accuracy.py`**:
  - **25-Query Factual Benchmark**: Tests 5 core factual attributes across all 5 schemes (expense ratio, exit load, minimum SIP, lock-in period, riskometer).
  - Verifies exact ground-truth values extracted from the official Groww scheme snapshots.

---

## 10. Daily Ingestion Scheduler

To keep scheme facts, NAV, and metrics fresh without manual intervention, a automated daily workflow is configured:
- **File**: `.github/workflows/daily_data_refresh.yml`
- **Schedule**: Everyday at `03:30 UTC` (`09:00 AM IST`).
- **Manual Trigger**: `workflow_dispatch` supported for on-demand execution.
- **Pipeline Stages**:
  1. **Scrape**: Fetches updated HTML snapshots from the 5 Groww URLs (`python3 -m src.ingestion.scraper --force`).
  2. **Extract**: Parses and updates atomic chunks (`python3 -m src.ingestion.extractor`).
  3. **Index**: Refreshes ChromaDB vectors (`python3 -m src.ingestion.indexer`).
  4. **Verify**: Runs the complete 80-test compliance suite (`python3 -m unittest discover -s tests -p "test_*.py"`).
  5. **Auto-Commit**: Automatically commits and pushes updated snapshots and chunk files back to the repository if changes are detected.

---

## 11. Deployment & Quickstart Guide

### 11.1 Local Python Execution

1. **Clone and setup virtual environment**:
   ```bash
   git clone <repository-url>
   cd mutual-fund-rag
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Environment Configuration (Optional)**:
   Create a `.env` file in the root directory if using external LLM providers:
   ```env
   # Optional: Google Gemini or OpenAI API Key
   GEMINI_API_KEY=your_gemini_api_key
   OPENAI_API_KEY=your_openai_api_key
   PORT=8501
   ```
   *(Note: The system includes a deterministic local factual generator that operates completely offline without external API keys).*

3. **Launch the Web Application**:
   ```bash
   python3 src/app.py --port 8501
   ```
   Open your browser to: `http://localhost:8501`

---

### 11.2 Docker Containerization

The repository includes a production-grade multi-layer `Dockerfile` configured with a non-root application user, pre-baked vector database artifacts, and a built-in health check.

1. **Build the Container Image**:
   ```bash
   docker build -t mutual-fund-rag:latest .
   ```

2. **Run the Container**:
   ```bash
   docker run -d \
     --name groww-mf-assistant \
     -p 8501:8501 \
     -e PORT=8501 \
     mutual-fund-rag:latest
   ```

3. **Verify Container Health**:
   ```bash
   docker inspect --format='{{json .State.Health.Status}}' groww-mf-assistant
   # Or query the health endpoint directly:
   curl -s http://localhost:8501/api/funds
   ```

---

## 12. Running Automated Tests

Run the full compliance and verification test suite (80 tests across 10 test modules):

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

### Test Suite Breakdown

| Test Module | Coverage Area | Tests | Status |
| :--- | :--- | :---: | :---: |
| `tests/test_phase1_registry.py` | 5 Whitelisted URLs, scheme metadata, alias resolution | 9 | Passed |
| `tests/test_phase2_scraper.py` | HTML caching, live fetch, snapshot sizes | 2 | Passed |
| `tests/test_phase2_extractor.py` | 45 structured chunks, schema validation, topic coverage | 6 | Passed |
| `tests/test_phase3_retrieval.py` | ChromaDB persistence, dense similarity, scheme routing | 4 | Passed |
| `tests/test_phase4_guardrails.py` | PII regex detection (PAN, Aadhaar, Phone), intent refusals | 12 | Passed |
| `tests/test_phase5_generation.py` | Sentence limit ($\le 3$), single citation, mandatory footer | 9 | Passed |
| `tests/test_phase6_ui.py` | REST endpoints (`/api/funds`, `/api/query`), static files | 8 | Passed |
| `tests/test_citation_whitelist.py` | Citation whitelist invariance, domain isolation, 0 CTA on missing info | 3 | Passed |
| `tests/test_guardrails.py` | Advisory/comparison refusals, comprehensive PII sanitization | 2 | Passed |
| `tests/test_factual_accuracy.py` | 25-query factual grounding benchmark across all 5 schemes | 25 | Passed |
| **Total** | **End-to-End Compliance & Functionality** | **80** | **100% Green** |
