# Enterprise Knowledge Assistant: Architecture & Project Structure

**Last Updated:** June 1, 2026  
**Version:** 2.0 (Production-Grade Docker Orchestration)

---

## 📋 Table of Contents
1. [Project Directory Tree](#project-directory-tree)
2. [System Architecture Diagram](#system-architecture-diagram)
3. [Data Flow Pipeline](#data-flow-pipeline)
4. [Container Orchestration](#container-orchestration)
5. [Critical File Reference](#critical-file-reference)

---

## 📁 Project Directory Tree

```
RAG sql to text/
│
├── 📄 README.md                          ⭐ START HERE - Full documentation
├── 📄 ARCHITECTURE.md                    📍 This file - Technical deep dive
├── 📄 requirements.txt                   ✓ Verified: 17 core packages + openpyxl + xlrd
├── 📄 docker-compose.yml                 ✓ Fixed: Corrected healthcheck with -d powerlifting_db
├── 📄 Dockerfile.ui                      ✓ Streamlit 1.35.0 container
├── 📄 Dockerfile.api                     ✓ FastAPI 0.104.1 container
├── 📄 Dockerfile.init                    ✓ Database initialization container
├── 📄 .env                               ⚠️  Git-ignored: GROQ_API_KEY
├── 📄 .gitignore                         ✓ Excludes .env, __pycache__, .conda
├── 📄 .dockerignore                      ✓ Reduces image size
├── 📂 .streamlit/
│   └── config.toml                       ✓ Streamlit theme & UI configuration
│
├── 🎨 app/                               [FRONTEND COMPONENTS]
│   ├── __init__.py                       ✓ Package initialization
│   ├── ui.py                             ✓ Streamlit helper functions (tabs, widgets)
│   └── style.css                         ✓ Custom CSS for professional branding
│
├── 🚀 api.py                             ⭐ ENTRY POINT: FastAPI microservice
│   │
│   ├── Endpoints:
│   │   ├── POST /api/dax                 ✓ Generate DAX measures with QA
│   │   └── POST /api/tableau             ✓ Generate Tableau calculated fields
│   │
│   ├── Middleware:
│   │   └── TimeoutMiddleware(120s)       ✓ Global request timeout protection
│   │
│   └── Features:
│       ├── CORS enabled                  ✓ Allows UI to call API
│       ├── Pydantic request validation   ✓ Type-safe payloads
│       └── Error handling & logging      ✓ Production-grade observability
│
├── 💬 app.py                             ⭐ ENTRY POINT: Streamlit UI
│   │
│   ├── Tabs:
│   │   ├── Tab 1: AI Insight             ✓ Natural language chat interface
│   │   ├── Tab 2: Raw Data               ✓ Browse tables & schema
│   │   ├── Tab 3: SQL Query              ✓ Write/execute raw SQL
│   │   └── Tab 4: Power BI               ✓ Generate DAX & Tableau code
│   │
│   ├── Key Functions:
│   │   ├── get_dynamic_schema()          ✓ Fixed: Uses unified DB_URL env var
│   │   ├── execute_query()               ✓ Calls PostgreSQL with error handling
│   │   └── call_api()                    ✓ POST requests to FastAPI backend
│   │
│   └── Session State:
│       ├── generated_sql                 ✓ Cached SQL generation results
│       ├── query_result                  ✓ Cached query execution results
│       └── current_schema_context        ✓ Active database schema metadata
│
├── 🗄️  database/                         [DATA LAYER & UTILITIES]
│   │
│   ├── 📍 init_db.py                     ⭐ CRITICAL: Smart CSV loader
│   │   │
│   │   ├── Features:
│   │   │   ├── ✓ Docker path detection  /app/data/raw/openpowerlifting-*.csv
│   │   │   ├── ✓ Local path detection   D:\RAG sql to text\data\raw\*.csv
│   │   │   ├── ✓ Environment fallback    Reads $env:CSV_PATH if available
│   │   │   ├── ✓ Idempotent loading      Skips re-ingestion if data exists
│   │   │   ├── ✓ Database healthcheck    Waits for PostgreSQL readiness
│   │   │   ├── ✓ Chunked ingestion       5000 rows per batch for memory efficiency
│   │   │   ├── ✓ File registry tracking  Logs metadata about loaded datasets
│   │   │   └── ✓ Comprehensive logging   DEBUG/INFO/ERROR with timestamps
│   │   │
│   │   ├── Tables Created:
│   │   │   ├── powerlifting_meets        3.7M+ rows (main dataset)
│   │   │   └── file_registry             Metadata about ingested files
│   │   │
│   │   ├── Return Values:
│   │   │   ├── 0 = Success              Database ready with data loaded
│   │   │   ├── 1 = CSV not found        CSV_PATH resolution failed
│   │   │   ├── 2 = DB connection error  PostgreSQL unavailable
│   │   │   └── 3 = Data load failed     Ingestion error (FK, types, etc.)
│   │   │
│   │   └── Usage:
│   │       └── python database/init_db.py
│   │
│   ├── get_schema.py                     ✓ Dynamic schema introspection
│   │   ├── get_all_schemas()             ✓ Lists all tables in database
│   │   ├── get_table_schema()            ✓ Extracts columns & data types
│   │   ├── get_categorical_examples()   ✓ Sample values for enum fields
│   │   └── get_unique_values()           ✓ Distinct values for constraints
│   │
│   ├── ingest_csv.py                     ✓ CSV validation & ingestion
│   │   ├── validate_csv()                ✓ Type checking & constraint validation
│   │   ├── normalize_columns()           ✓ Converts to lowercase_with_underscores
│   │   ├── detect_types()                ✓ Infers PostgreSQL data types
│   │   └── ingest_to_database()          ✓ Executes INSERT via SQLAlchemy
│   │
│   ├── ingest_data.py                    ✓ Legacy pandas data loader
│   │   ├── Reads cleaned Excel files
│   │   └── Falls back for .xlsx support (now with openpyxl + xlrd)
│   │
│   ├── load_any_csv.py                   ✓ Generic CLI CSV loader
│   │   └── Usage: python load_any_csv.py --csv <path> --table <name>
│   │
│   ├── excel_utils.py                    ⭐ FIXED: Multi-sheet Excel support
│   │   ├── detect_excel_sheets()         ✓ Identifies all sheets in .xlsx
│   │   ├── is_multi_sheet_excel()        ✓ Boolean check for complex workbooks
│   │   ├── pd.read_excel() support       ✓ Now works with openpyxl backend
│   │   └── xlrd support                  ✓ Legacy .xls file handling
│   │
│   ├── relationship_detector.py          ✓ Foreign key analysis
│   │   └── detect_relationships()        ✓ Infers table joins automatically
│   │
│   ├── sanitizer.py                      ✓ Data cleaning utilities
│   │   ├── clean_column_names()          ✓ Removes special characters
│   │   ├── standardize_types()           ✓ Enforces PostgreSQL types
│   │   └── create_sheet_to_table_mapping() ✓ Multi-sheet schema normalization
│   │
│   ├── table_resolver.py                 ✓ Dynamic table mapping
│   │   └── resolve_table()               ✓ Maps human-friendly names to DB tables
│   │
│   ├── reset_vector_store.py             ✓ ChromaDB reset & rebuild
│   │   ├── Scans all PostgreSQL tables
│   │   ├── Extracts schema metadata
│   │   └── Embeds into ChromaDB for LLM routing
│   │
│   └── docker-compose.yml                ✓ Local PostgreSQL (legacy)
│       └── Note: Now superseded by root docker-compose.yml
│
├── 🤖 rag_pipeline/                      [LANGCHAIN ORCHESTRATION]
│   │
│   ├── 📍 chain.py                       ⭐ CORE: SQL Generation Chain (LCEL)
│   │   │
│   │   ├── Main Functions:
│   │   │   └── generate_dax_measure()    ✓ Fixed: Returns "bi_code" + "metric_name"
│   │   │       ├── Accepts parameters: question, sql_query, schema_context, 
│   │   │       │                        sql_result_snapshot, insight
│   │   │       ├── Chains: Schema retrieval → LLM → DAX QA → Return
│   │   │       └── Timeout: 45 seconds with max_retries=1
│   │   │
│   │   ├── LLM Configuration:
│   │   │   ├── Model: Groq Llama 3.3 70B
│   │   │   ├── Temperature: 0.0 (deterministic)
│   │   │   ├── Max retries: 1 (self-healing)
│   │   │   └── Timeout: 45 seconds
│   │   │
│   │   ├── LCEL Pipeline:
│   │   │   ├── 1. get_schema() → Dynamic context retrieval
│   │   │   ├── 2. get_dax_prompt_template() → System prompt
│   │   │   ├── 3. llm.invoke() → LLM generation
│   │   │   ├── 4. verify_dax_sql_parity() → QA check
│   │   │   └── 5. Return formatted response
│   │   │
│   │   └── Error Handling:
│   │       ├── Catches Groq timeouts
│   │       ├── Falls back to generic DAX
│   │       └── Logs errors to CloudWatch
│   │
│   ├── dax_chain.py                      ✓ DAX-specific chain wrapper
│   │   └── invoke_dax_chain()            ✓ Calls chain.py with DAX context
│   │
│   ├── dax_prompts.py                    ✓ Fixed: Uses langchain_core imports
│   │   ├── get_dax_prompt_template()     ✓ System prompt for DAX measures
│   │   ├── Variables: {question}, {sql_query}, {schema_context},
│   │   │                {sql_result_snapshot}, {insight}
│   │   └── Format: Expert DAX consultant persona
│   │
│   ├── dax_qa.py                         ✓ Fixed: Uses langchain_core imports
│   │   ├── verify_dax_sql_parity()       ✓ Validates DAX correctness
│   │   ├── Checks: Syntax, column references, aggregations
│   │   └── Returns: Boolean pass/fail + feedback
│   │
│   ├── tableau_chain.py                  ✓ Tableau field generation
│   │   └── invoke_tableau_chain()        ✓ Calls tableau-specific logic
│   │
│   ├── tableau_prompts.py                ✓ Fixed: Uses langchain_core imports
│   │   └── get_tableau_prompt_template() ✓ System prompt for Tableau fields
│   │
│   ├── prompts.py                        ✓ Core SQL generation prompts
│   │   ├── get_sql_prompt_template()     ✓ System prompt for SQL generation
│   │   ├── Few-shot examples               ✓ 5-10 example queries for routing
│   │   └── Schema context injection       ✓ Dynamic table/column metadata
│   │
│   ├── dynamic_prompts.py                ✓ Template-based prompt building
│   │   ├── build_prompt()                ✓ Constructs prompts from variables
│   │   └── insert_context()              ✓ Injects schema at runtime
│   │
│   ├── multi_table_prompt.py             ✓ Multi-table join prompts
│   │   └── generate_join_prompt()        ✓ Handles complex relationships
│   │
│   ├── universal_prompts.py              ✓ Dataset-agnostic utilities
│   │   ├── error_recovery_prompt()       ✓ Self-healing for SQL errors
│   │   └── constraint_prompt()           ✓ Enforces data integrity
│   │
│   ├── sequential_executor.py            ✓ Query execution orchestrator
│   │   ├── execute_query()               ✓ Runs SQL with error handling
│   │   ├── Retries failed queries         ✓ Up to 3 attempts with backoff
│   │   └── Formats results                ✓ JSON + Pandas DataFrame
│   │
│   └── vector_store.py                   ✓ ChromaDB initialization
│       ├── initialize_vector_store()     ✓ Creates collection in ChromaDB
│       ├── embed_schema()                ✓ Generates embeddings for schema
│       └── retrieve_similar()            ✓ Semantic schema example retrieval
│
├── 📊 data/                              [DATASET FILES]
│   │
│   ├── raw/
│   │   └── openpowerlifting-2026-01-03-daa0ab53.csv  ⭐ MAIN DATASET
│   │       ├── Size: ~1.2 GB (compressed: ~150 MB)
│   │       ├── Rows: 3,745,206 powerlifting meet records
│   │       ├── Columns: 54 (Name, Squat, Bench, Deadlift, Date, ...)
│   │       └── Format: UTF-8, comma-delimited with headers
│   │
│   └── clean/
│       └── cleaned_meets.xlsx            ✓ Processed data (optional)
│           ├── Multi-sheet structure
│           ├── Data-cleaning applied
│           └── Ready for analysis
│
├── 📦 db/                                [VECTOR STORE & PERSISTENCE]
│   │
│   └── chroma_db/
│       ├── chroma.sqlite3                ✓ ChromaDB backend database
│       └── <uuid>/                       ✓ Collection storage directories
│           ├── metadata.json             ✓ Collection metadata
│           └── data/                     ✓ Embedded vectors
│
├── 📓 etl/                               [JUPYTER NOTEBOOKS]
│   │
│   ├── Data_Cleaning_to_excel.ipynb      ✓ ETL pipeline notebook
│   │   ├── Reads raw CSV
│   │   ├── Applies data transformations
│   │   └── Exports cleaned Excel file
│   │
│   └── Exploratory Data Analysis.ipynb   ✓ EDA & insights notebook
│       ├── Statistical summaries
│       ├── Distribution analysis
│       └── Visualization & charting
│
└── 🐳 [DOCKER CONFIGURATION FILES]
    │
    ├── docker-compose.yml                ⭐ Main orchestration file
    │   ├── Service: db (PostgreSQL 16)
    │   │   ├── Container: powerlifting_postgres_db
    │   │   ├── Port: 2003:5432 (external:internal)
    │   │   ├── Env: POSTGRES_USER=POWERLIFTER_KUNAL
    │   │   ├── Env: POSTGRES_PASSWORD=Kunal123
    │   │   ├── Env: POSTGRES_DB=powerlifting_db
    │   │   ├── Healthcheck: pg_isready -U POWERLIFTER_KUNAL -d powerlifting_db
    │   │   │                (interval: 5s, timeout: 5s, retries: 10)
    │   │   ├── Volume: postgres_data (persistent storage)
    │   │   └── Restart: always
    │   │
    │   ├── Service: init (Database initialization)
    │   │   ├── Dockerfile: Dockerfile.init
    │   │   ├── Container: powerlift_init
    │   │   ├── Env: DB_URL=postgresql://...@db:5432/powerlifting_db
    │   │   ├── Depends on: db (service_healthy condition)
    │   │   ├── Volume: ./data/raw:/app/data/raw (CSV mount)
    │   │   ├── Entrypoint: python database/init_db.py
    │   │   └── Exit behavior: Runs once, then exits
    │   │
    │   ├── Service: api (FastAPI backend)
    │   │   ├── Dockerfile: Dockerfile.api
    │   │   ├── Container: powerlift_api
    │   │   ├── Port: 8080:8080 (external:internal)
    │   │   ├── Env: DB_URL=postgresql://...@db:5432/powerlifting_db
    │   │   ├── Env: GROQ_API_KEY=${GROQ_API_KEY} (from .env)
    │   │   ├── Depends on: init (waits for init to complete)
    │   │   ├── Entrypoint: uvicorn api:app --host 0.0.0.0 --port 8080
    │   │   ├── Restart: always
    │   │   └── Health: Endpoint-based (from FastAPI)
    │   │
    │   ├── Service: ui (Streamlit frontend)
    │   │   ├── Dockerfile: Dockerfile.ui
    │   │   ├── Container: powerlift_ui
    │   │   ├── Port: 8501:8501 (external:internal)
    │   │   ├── Env: API_BASE_URL=http://api:8080/api
    │   │   ├── Env: DB_URL=postgresql://...@db:5432/powerlifting_db
    │   │   ├── Depends on: init (waits for init to complete)
    │   │   ├── Entrypoint: streamlit run app.py
    │   │   ├── Restart: always
    │   │   └── Config: .streamlit/config.toml
    │   │
    │   ├── Network: ragsqltotext_default (bridge)
    │   │   ├── Type: Docker bridge network
    │   │   ├── Services communicate via hostnames:
    │   │   │   ├── api:8080 (from ui container)
    │   │   │   ├── db:5432 (from api & ui containers)
    │   │   │   └── localhost (from host machine)
    │   │   └── DNS resolution: Automatic via Docker
    │   │
    │   └── Volumes:
    │       └── postgres_data (named volume for DB persistence)
    │
    ├── Dockerfile.init                   ⭐ Init container build spec
    │   ├── Base: python:3.11-slim
    │   ├── Working directory: /app
    │   ├── Dependencies: pandas, sqlalchemy, psycopg2-binary, python-dotenv
    │   ├── Copy files: requirements.txt, database/, data/, rag_pipeline/
    │   ├── Entrypoint: python database/init_db.py
    │   └── Purpose: One-shot CSV ingestion at startup
    │
    ├── Dockerfile.api                    ✓ FastAPI container build spec
    │   ├── Base: python:3.11
    │   ├── Working directory: /app
    │   ├── Installs: All requirements.txt packages
    │   ├── Copy files: *, requirements.txt, app/, rag_pipeline/, database/
    │   ├── Expose: 8080
    │   ├── Entrypoint: uvicorn api:app --host 0.0.0.0 --port 8080
    │   └── Purpose: Microservice for SQL/BI code generation
    │
    └── Dockerfile.ui                     ✓ Streamlit container build spec
        ├── Base: python:3.11
        ├── Working directory: /app
        ├── Installs: All requirements.txt packages
        ├── Copy files: *, app/, .streamlit/
        ├── Expose: 8501
        ├── Entrypoint: streamlit run app.py
        └── Purpose: Interactive web frontend

```

---

## 🔄 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     LOCAL DEVELOPMENT MACHINE                   │
│                         (Windows/macOS/Linux)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                    docker-compose up -d --build
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
    ┌────────────┐       ┌────────────┐       ┌────────────┐
    │   Port     │       │   Port     │       │   Port     │
    │   8501     │       │   8080     │       │   2003     │
    └────────────┘       └────────────┘       └────────────┘
        ▲                     ▲                     ▲
        │                     │                     │
        │ HTTP/REST          │ HTTP/REST          │ PostgreSQL
        │ Requests           │ Requests           │ Connection
        │                     │                     │
    ┌──┴────────────┐    ┌───┴─────────────┐  ┌───┴──────────────┐
    │  Streamlit UI │    │  FastAPI        │  │  PostgreSQL 16   │
    │   (8501)      │────│  Backend        │──│  (5432 internal) │
    │               │    │  (8080)         │  │  (2003 external) │
    │ ┌─────────┐   │    │ ┌───────────┐   │  │                  │
    │ │ Tab 1   │   │    │ │POST /api/ │   │  │ ┌──────────────┐ │
    │ │ AI      │   │    │ │dax        │   │  │ │powerlifting_ │ │
    │ │ Insight │   │◄───┼─│           │───┼─┤ │meets (3.7M   │ │
    │ │         │   │    │ │POST /api/ │   │  │ │rows)         │ │
    │ │ Tab 2   │   │    │ │tableau    │   │  │ │              │ │
    │ │ Raw Data│   │    │ │           │   │  │ │file_registry │ │
    │ │         │   │    │ │           │   │  │ │              │ │
    │ │ Tab 3   │   │    │ └───────────┘   │  │ └──────────────┘ │
    │ │ SQL     │   │    │                 │  │                  │
    │ │ Query   │   │    │ ┌───────────┐   │  │ ┌──────────────┐ │
    │ │         │   │    │ │LangChain  │   │  │ │ChromaDB      │ │
    │ │ Tab 4   │   │    │ │LCEL       │   │  │ │Vector Store  │ │
    │ │ Power   │   │    │ │Chains     │   │  │ │(Mounted: /db)│ │
    │ │ BI      │   │    │ │           │   │  │ │              │ │
    │ │         │   │    │ │Groq LLM   │   │  │ └──────────────┘ │
    │ │         │   │    │ │(45s)      │   │  │                  │
    │ └─────────┘   │    │ └───────────┘   │  │                  │
    │               │    │                 │  │                  │
    │ session_state │    │ environment:    │  │ environment:     │
    │ ├─ generated_ │    │ ├─ DB_URL       │  │ ├─ POSTGRES_USER │
    │ │ sql         │    │ ├─ GROQ_API_KEY │  │ ├─ POSTGRES_PASS │
    │ ├─ query_     │    │ │                 │  │ ├─ POSTGRES_DB  │
    │ │ result      │    │ │                 │  │ └─ healthcheck  │
    │ └─ current_   │    │ │                 │  │    [FIXED]      │
    │   schema_     │    │ │                 │  │                  │
    │   context     │    │ │                 │  │ Restart: always │
    │               │    │ │                 │  │                  │
    │ Network:      │    │ │ Network:       │  │ Network:         │
    │ host:8501     │    │ │ host:8080      │  │ host:2003        │
    │ ◄─────────────────│ │ ◄────────────────│  │                  │
    │  docker       │    │  docker         │  │  docker          │
    │  internal     │    │  internal       │  │  internal        │
    │  api:8080     │    │  db:5432        │  │  (5432)          │
    │               │    │  (init waits)   │  │                  │
    └───────────────┘    └─────────────────┘  └──────────────────┘

    ▲
    │
    ├─ init:powerlift_init
    │  ├─ Dockerfile.init
    │  ├─ CSV Path Detection:
    │  │  ├─ Docker path: /app/data/raw/*.csv ✓
    │  │  ├─ Local path: D:\RAG sql to text\data\raw\*.csv ✓
    │  │  └─ Env fallback: $env:CSV_PATH
    │  ├─ Database initialization
    │  ├─ depends_on: db (service_healthy)
    │  └─ Volume: ./data/raw:/app/data/raw
    │
    └─ ragsqltotext_default (bridge network)
       ├─ Internal DNS: api:8080, db:5432
       ├─ External: localhost:8501, localhost:8080, localhost:2003
       └─ Persistent Volume: postgres_data
```

---

## 📊 Data Flow Pipeline

```
USER QUERY (Natural Language)
        │
        ▼
┌─────────────────────────────────────┐
│  Streamlit UI (Tab 1: AI Insight)  │
│  User types: "Top 10 lifters"      │
└─────────────────────┬───────────────┘
                      │
        POST http://api:8080/api/dax
                      │
        ┌─────────────▼──────────────┐
        │ FastAPI Backend (api.py)   │
        │ ├─ Receive DAXRequest      │
        │ ├─ Extract parameters      │
        │ └─ Apply request validation│
        └──────────┬──────────────────┘
                   │
    ┌──────────────▼──────────────────┐
    │ LangChain LCEL Chain            │
    │ (rag_pipeline/chain.py)         │
    │                                 │
    │ 1. get_dynamic_schema()         │
    │    └─ Query PostgreSQL for      │
    │       table/column metadata     │
    │                                 │
    │ 2. get_dax_prompt_template()    │
    │    └─ Construct system prompt   │
    │       with schema context       │
    │                                 │
    │ 3. llm.invoke()                 │
    │    └─ Call Groq Llama 3.3 70B   │
    │       (45s timeout, max 1 retry)│
    │       Returns: "MEASURE Lifts..." │
    │                                 │
    │ 4. verify_dax_sql_parity()      │
    │    └─ QA check: Is DAX valid?   │
    │       Returns: true/false       │
    │                                 │
    │ 5. Return formatted response    │
    │    ├─ bi_code                   │
    │    ├─ metric_name               │
    │    ├─ qa_passed                 │
    │    ├─ tokens_prompt             │
    │    └─ tokens_response           │
    └──────────┬──────────────────────┘
               │
        ┌──────▼────────────────────┐
        │ FastAPI Response          │
        │ (DAXResponse JSON model)   │
        └──────┬────────────────────┘
               │
        HTTP 200 OK + JSON
               │
        ┌──────▼──────────────┐
        │ Streamlit UI        │
        │ ├─ Display bi_code  │
        │ ├─ Show metric_name │
        │ ├─ Indicate qa_pass │
        │ └─ Show token count │
        └─────────────────────┘
```

---

## 🐳 Container Orchestration Timeline

```
COMMAND: docker-compose up -d --build

Timeline:
─────────

T+0s    Build Phase
        ├─ docker build -f Dockerfile.ui -t ragsqltotext_ui .
        ├─ docker build -f Dockerfile.api -t ragsqltotext_api .
        ├─ docker build -f Dockerfile.init -t ragsqltotext_init .
        └─ Create ragsqltotext_default network

T+5s    Database Phase
        ├─ Start container: powerlifting_postgres_db
        ├─ Run initialization scripts
        └─ Healthcheck begins (pg_isready every 5s)

T+6s    Healthcheck T+1
        ├─ pg_isready -U POWERLIFTER_KUNAL -d powerlifting_db
        └─ Expected: "accepting connections"

T+11s   Healthcheck T+2-10 (5s interval)
        └─ ✓ db service is now HEALTHY

T+12s   Init Service Phase
        ├─ Start container: powerlift_init
        ├─ Detected CSV path (LOCAL or DOCKER)
        ├─ Wait for PostgreSQL readiness
        ├─ Load openpowerlifting CSV (3.7M rows)
        ├─ Insert records in 5000-row chunks
        │   ├─ Chunk 1: rows 0-4999 (commit)
        │   ├─ Chunk 2: rows 5000-9999 (commit)
        │   ├─ ... (repeat 750 times)
        │   └─ Final chunk: last rows (commit)
        ├─ Create file_registry table
        ├─ Register loaded dataset
        └─ Exit with status 0

T+90s   Init Complete (typical timing for 3.7M rows)
        └─ Database now contains populated powerlifting_meets table

T+91s   API Service Phase
        ├─ Start container: powerlift_api
        ├─ Import app (api.py)
        │   ├─ Load LangChain LCEL chains
        │   ├─ Initialize ChromaDB vector store
        │   └─ Setup Groq LLM client
        ├─ Start uvicorn server (port 8080)
        └─ Ready for requests

T+93s   UI Service Phase
        ├─ Start container: powerlift_ui
        ├─ Import app (app.py)
        │   ├─ Initialize Streamlit state
        │   ├─ Cache database schema
        │   └─ Start session tracking
        ├─ Start Streamlit server (port 8501)
        └─ Ready for browser access

T+95s   All Services Running ✓
        ├─ ui:8501 → http://localhost:8501
        ├─ api:8080 → http://localhost:8080/docs
        └─ db:2003 → postgresql://...@localhost:2003

        docker-compose ps output:
        ─────────────────────────
        NAME                    STATUS
        powerlift_ui            Running
        powerlift_api           Running
        powerlift_init          Exited (0)
        powerlifting_postgres_db  Healthy
        ragsqltotext_default     (network)
```

---

## 🔑 Critical File Reference

| File | Purpose | Criticality | Recent Fix |
|------|---------|-------------|-----------|
| `docker-compose.yml` | Service orchestration | ⭐⭐⭐ | Healthcheck: `-d powerlifting_db` added |
| `database/init_db.py` | CSV loading & initialization | ⭐⭐⭐ | Path detection: Docker + Local + Env |
| `app.py` | Streamlit frontend | ⭐⭐⭐ | DB_URL unified (removed 5 broken env vars) |
| `api.py` | FastAPI microservice | ⭐⭐⭐ | Timeout protection (120s middleware) |
| `requirements.txt` | Dependencies | ⭐⭐⭐ | Nuclear option: 17 packages (no constraints) |
| `rag_pipeline/chain.py` | SQL generation | ⭐⭐ | Return keys: "bi_code" + "metric_name" |
| `database/excel_utils.py` | Multi-sheet Excel | ⭐⭐ | openpyxl + xlrd backends |
| `.env` | Secrets management | ⭐⭐⭐ | GROQ_API_KEY required |
| `Dockerfile.*` | Container specifications | ⭐⭐ | Multi-stage, optimized layers |

---

**End of Architecture Document**  
*For deployment instructions, see [README.md](README.md)*
