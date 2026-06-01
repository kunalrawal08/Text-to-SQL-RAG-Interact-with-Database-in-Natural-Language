# Enterprise Knowledge Assistant: Powerlifting Text-to-SQL Analytics

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35.0-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-316192?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![LangChain](https://img.shields.io/badge/LangChain-Core-121212?logo=chainlink&logoColor=white)](https://python.langchain.com/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**A production-grade, containerized enterprise application that translates natural language queries into SQL and generates Business Intelligence code (DAX, Tableau) for the OpenPowerlifting dataset—3.7+ million records of athletic performance data.**

## 📋 Overview

The Enterprise Knowledge Assistant bridges the gap between natural language and complex database queries. Users ask questions in plain English, and the system automatically generates optimized SQL, executes it against a massive powerlifting dataset, and optionally generates BI code for visualization platforms.

### Why This Matters
- **Data Democratization:** Non-technical stakeholders can query sophisticated databases without SQL knowledge.
- **Enterprise Scale:** Handles 3.7M+ records with sub-second latency and intelligent caching.
- **AI-Driven Intelligence:** Leverages LangChain LCEL, Groq Llama 3.3 70B, and ChromaDB for semantic schema routing.
- **Multi-Tenant BI:** Generates DAX measures for Power BI and Tableau calculated fields for embedded analytics.

---

## 🏛️ System Architecture

The application follows a **microservices-first, containerized design** with three independently scalable services orchestrated by Docker Compose:

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI (Port 8501)                 │
│              (Charts • Tables • Chat Interface)              │
└────────────────────────┬────────────────────────────────────┘
                         │
                    HTTP/REST (Port 8080)
                         │
        ┌────────────────▼─────────────────┐
        │   FastAPI Backend (Port 8080)    │
        │  (LangChain • SQL Gen • BI Code) │
        └────────────────┬─────────────────┘
                         │
               Native PostgreSQL (Port 5432)
                         │
        ┌────────────────▼─────────────────┐
        │  PostgreSQL 16 (Port 2003 local) │
        │  (3.7M powerlifting records)     │
        └─────────────────────────────────┘
```

### Technology Stack
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | Streamlit 1.35.0 | Interactive web interface with multi-tab dashboard |
| **Backend API** | FastAPI 0.104.1 | Microservice handling SQL generation & BI code synthesis |
| **Database** | PostgreSQL 16 | Structured data storage with relational queries |
| **Orchestration** | Docker Compose 3.8 | Multi-container deployment & networking |
| **LLM Framework** | LangChain Core | LCEL chains for SQL generation & quality assurance |
| **Inference Engine** | Groq Llama 3.3 70B | 45-second timeout, max 1 retry for self-healing SQL |
| **Embeddings** | Google Gemini | Semantic schema example retrieval via ChromaDB |
| **Vector Store** | ChromaDB | Persistent semantic cache of schema examples |

### Containerized Services
1. **PostgreSQL (db)** - Relational database with healthcheck
2. **Init Service** - Intelligent CSV loader with environment-aware path detection
3. **FastAPI (api)** - Stateless microservice with timeout protection
4. **Streamlit (ui)** - Real-time interactive frontend

---

## 🛠️ Prerequisites

Before deploying, ensure you have:

- **Docker Desktop** (Windows, macOS) or **Docker Engine + Docker Compose** (Linux)
  - [Install Docker](https://docs.docker.com/get-docker/)
  - [Install Docker Compose](https://docs.docker.com/compose/install/)
- **Git** (for cloning the repository)
- **GROQ API Key** (free tier available at [console.groq.com](https://console.groq.com))
- **Available Ports:** 8501 (UI), 8080 (API), 2003 (DB), 5432 (internal)

---

## 🚀 Getting Started

### Step 1: Clone & Configure
```bash
git clone <repository-url>
cd "RAG sql to text"
```

### Step 2: Create Environment File
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_actual_groq_api_key_here
```

### Step 3: Deploy with Docker Compose
Start all services in detached mode:
```bash
docker-compose up -d --build
```

This command:
- ✅ Builds Docker images for UI, API, and init service
- ✅ Starts PostgreSQL with automatic healthcheck
- ✅ Runs init service to load OpenPowerlifting CSV (3.7M rows)
- ✅ Starts FastAPI backend (connects to DB when ready)
- ✅ Starts Streamlit UI (connects to API when ready)

**Expected Output:**
```
[+] Running 5/5
 ✔ Network ragsqltotext_default         Created    0.1s
 ✔ Container powerlifting_postgres_db   Healthy    6.6s
 ✔ Container powerlift_init             Started    6.9s
 ✔ Container powerlift_api              Started    7.2s
 ✔ Container powerlift_ui               Started    7.3s
```

### Step 4: Access the Application
- **UI:** Open browser to [http://localhost:8501](http://localhost:8501)
- **API Documentation:** [http://localhost:8080/docs](http://localhost:8080/docs)
- **Database (local access):** `postgresql://POWERLIFTER_KUNAL:Kunal123@localhost:2003/powerlifting_db`

### Step 5: Verify Data Ingestion
In the UI, navigate to the **"Raw Data"** tab. You should see:
- ✅ `powerlifting_meets` table with 3.7M+ rows
- ✅ Schema metadata (columns, data types)
- ✅ Sample records from the OpenPowerlifting dataset

---

## 💬 Usage Guide

### Querying the Database (AI Insight Tab)
1. **Ask a Question:** "Who are the top 10 strongest lifters in IPF competitions?"
2. **System Generates SQL:** Behind the scenes, the backend generates a PostgreSQL query
3. **View Results:** SQL executes and returns filtered data with row counts
4. **Generate BI Code (Optional):**
   - Select results → Click "Generate DAX Measure" for Power BI
   - Select results → Click "Generate Tableau Field" for Tableau Public

### Example Queries
```sql
-- Natural Language: "Average squat by weight class"
SELECT weight_class, AVG(best_squat_kg) FROM powerlifting_meets GROUP BY weight_class;

-- Natural Language: "Female lifters with total over 400kg"
SELECT * FROM powerlifting_meets WHERE sex = 'F' AND total_kg > 400 ORDER BY total_kg DESC;

-- Natural Language: "Training history for lifter named John"
SELECT meet_name, event, total_kg FROM powerlifting_meets WHERE name ILIKE '%John%' ORDER BY date DESC;
```

### Tabs Overview
| Tab | Purpose |
|-----|---------|
| **AI Insight** | Natural language chat interface for query generation |
| **Raw Data** | Browse tables, view schema, inspect metadata |
| **SQL Query** | Write/execute raw SQL; view execution plans |
| **Power BI** | Generate DAX measures for enterprise dashboards |

---

## 🏗️ Project Structure

```
RAG sql to text/
├── app.py                          # Streamlit frontend (4-tab interface)
├── api.py                          # FastAPI backend (microservice)
├── requirements.txt                # Python dependencies (17 core packages)
├── docker-compose.yml              # Service orchestration & networking
├── Dockerfile.ui                   # Streamlit container image
├── Dockerfile.api                  # FastAPI container image
├── Dockerfile.init                 # CSV initialization container
├── ARCHITECTURE.md                 # Deep dive into system architecture and design
│
├── app/                            # UI components
│   ├── __init__.py
│   ├── ui.py                       # Streamlit helper functions
│   └── style.css                   # Custom styling
│
├── database/                       # Data layer & utilities
│   ├── init_db.py                  # ⭐ Smart CSV loader (detects Docker/local paths)
│   ├── get_schema.py               # PostgreSQL schema introspection
│   ├── ingest_csv.py               # CSV validation & ingestion
│   ├── ingest_data.py              # Legacy data loader (pandas)
│   ├── load_any_csv.py             # Generic CSV CLI tool
│   ├── excel_utils.py              # Multi-sheet Excel detection
│   ├── relationship_detector.py    # Foreign key analysis
│   ├── sanitizer.py                # Data cleaning utilities
│   ├── table_resolver.py           # Dynamic table mapping
│   ├── reset_vector_store.py       # ChromaDB reset utility
│   └── docker-compose.yml          # Database service config
│
├── rag_pipeline/                   # LangChain orchestration
│   ├── chain.py                    # SQL generation chain (LCEL)
│   ├── dax_chain.py                # DAX measure generation
│   ├── dax_prompts.py              # DAX system prompts
│   ├── dax_qa.py                   # DAX validation & QA
│   ├── tableau_chain.py            # Tableau field generation
│   ├── tableau_prompts.py          # Tableau system prompts
│   ├── prompts.py                  # Core SQL generation prompts
│   ├── dynamic_prompts.py          # Template-based prompt building
│   ├── multi_table_prompt.py       # Multi-join SQL prompts
│   ├── universal_prompts.py        # Shared prompt utilities
│   ├── sequential_executor.py      # Query execution orchestrator
│   └── vector_store.py             # ChromaDB initialization
│
├── data/
│   ├── raw/
│   │   └── openpowerlifting-2026-01-03-daa0ab53.csv  # 3.7M rows
│   └── clean/                      # Processed datasets (optional)
│
├── db/
│   └── chroma_db/                  # Vector store persistence
│       └── chroma.sqlite3          # ChromaDB backend
│
├── etl/                            # Jupyter notebooks
│   ├── Data_Cleaning_to_excel.ipynb
│   └── Exploratory Data Analysis.ipynb
│
└── .env                            # Environment variables (git-ignored)
```

### 2. Infrastructure Initialization

Start the PostgreSQL container, load the initial data, and build the vector dictionary:

```bash
# 1. Start Database
docker-compose -f database/docker-compose.yml up -d

# 2. Load Dataset
python database/ingest_data.py

# 3. Build Semantic Dictionary
python rag_pipeline/vector_store.py
```

### 3. Launch Application

```bash
streamlit run app.py
```

Navigate to `http://localhost:8501` to access the interface.

---

## 🌐 Dataset-Agnostic Scalability

This system is engineered to handle **any structured dataset** without code changes. The RAG pipeline relies on dynamic schema ingestion rather than hardcoded tables.

### Loading Custom Datasets

To point the assistant at a new dataset (e.g., HR records, financial data):

**1. Ingest the CSV:**

```bash
python database/load_any_csv.py --csv /path/to/enterprise_data.csv --table new_dataset_name
```

**2. Rebuild the Universal Vector Store:**

```bash
python database/reset_vector_store.py
```

*This command scans all PostgreSQL tables, extracts their schemas (columns/types), and embeds them into a universal ChromaDB collection for the LLM to access.*

**3. Query Instantly:**
The LLM will automatically evaluate the new schema context in ChromaDB, route your natural language query to the correct table, and generate the appropriate SQL.

---

## 🗄️ Database Administration

The repository includes a suite of tools for database management and verification via Docker.

<details>
<summary><b>Click to expand: Common Database Operations</b></summary>

**Access the PostgreSQL Container:**

```bash
# Find container name
docker ps | grep postgres

# Connect to database
docker exec -it <container_name> psql -U POWERLIFTER_KUNAL -d powerlifting_db
```

**Helpful `psql` Commands:**

* `\dt` - List all tables
* `\d table_name` - View table schema
* `SELECT COUNT(*) FROM table_name;` - Verify row counts
* `\q` - Exit prompt

**Backup a Table:**

```bash
docker exec -it <container_name> psql -U POWERLIFTER_KUNAL -d powerlifting_db -c "\COPY table_name TO '/tmp/backup.csv' WITH CSV HEADER;"
docker cp <container_name>:/tmp/backup.csv ./backups/backup.csv
```

</details>

---

## 📁 Repository Structure

```text
├── app.py                              # Main Streamlit application entry point
├── api.py                              # FastAPI backend (microservice)
├── requirements.txt                    # Python dependencies
├── .env                                # Environment configuration (not tracked)
├── .gitignore                          # Git ignore rules
├── README.md                           # This file
├── ARCHITECTURE.md                     # Deep dive into system architecture and design
├── docker-compose.yml                  # Service orchestration & networking
├── Dockerfile.ui                       # Streamlit container image
├── Dockerfile.api                      # FastAPI container image
├── Dockerfile.init                     # CSV initialization container
├── .streamlit/
│   └── config.toml                     # Streamlit configuration
│
├── app/
│   ├── __init__.py                     # Package initialization
│   ├── ui.py                           # Frontend components and utilities
│   └── style.css                       # Custom UI styling and typography
│
├── rag_pipeline/
│   ├── __init__.py                     # Package initialization
│   ├── chain.py                        # LLM orchestration and SQL execution logic
│   ├── dax_chain.py                    # DAX measure generation
│   ├── dax_prompts.py                  # DAX system prompts
│   ├── dax_qa.py                       # DAX validation & QA
│   ├── tableau_chain.py                # Tableau field generation
│   ├── tableau_prompts.py              # Tableau system prompts
│   ├── prompts.py                      # Domain-specific routing prompts
│   ├── dynamic_prompts.py              # Dynamic prompt generation utilities
│   ├── multi_table_prompt.py           # Multi-join SQL prompts
│   ├── universal_prompts.py            # Dataset-agnostic prompt templates
│   ├── sequential_executor.py          # Query execution orchestrator
│   └── vector_store.py                 # ChromaDB embedding generators
│
├── database/
│   ├── docker-compose.yml              # Containerized PostgreSQL infrastructure config
│   ├── init_db.py                      # ⭐ Smart CSV loader (detects Docker/local paths)
│   ├── get_schema.py                   # Dynamic schema discovery utility
│   ├── ingest_csv.py                   # CSV validation and ingestion module
│   ├── ingest_data.py                  # Primary powerlifting data ingestion script
│   ├── load_any_csv.py                 # Universal ETL utility for any dataset
│   ├── excel_utils.py                  # Multi-sheet Excel detection
│   ├── relationship_detector.py        # Foreign key analysis
│   ├── sanitizer.py                    # Data cleaning utilities
│   ├── table_resolver.py               # Dynamic table mapping
│   └── reset_vector_store.py           # Schema discovery and indexing utility
│
├── db/
│   └── chroma_db/                      # Persisted ChromaDB vector store
│       ├── chroma.sqlite3              # Vector store database
│       └── <embedding-collections>/    # Embedded schema collections
│
├── data/
│   ├── raw/
│   │   └── openpowerlifting-2026-01-03.csv   # Raw powerlifting dataset
│   └── clean/
│       └── cleaned_meets.xlsx          # Processed powerlifting data
│
└── etl/
    ├── Data_Cleaning_to_excel.ipynb    # Data processing notebook
    └── Exploratory Data Analysis.ipynb # EDA and insights notebook
```

---

## � FastAPI Endpoints Reference

The FastAPI backend exposes a RESTful API for programmatic access to the SQL generation and BI code synthesis capabilities.

### SQL Query Generation
**Endpoint:** `POST /api/sql`
```json
{
  "question": "Top 10 lifters by total in 2024",
  "schema_context": "Available tables: powerlifting_meets(id, name, total_kg, ...)"
}
```

**Response:**
```json
{
  "sql_query": "SELECT name, total_kg FROM powerlifting_meets ORDER BY total_kg DESC LIMIT 10;",
  "success": true,
  "execution_time_ms": 234
}
```

### DAX Measure Generation
**Endpoint:** `POST /api/dax`
```json
{
  "question": "Total lifts by competition",
  "sql_query": "SELECT meet_name, COUNT(*) FROM powerlifting_meets GROUP BY meet_name;",
  "schema_context": "Tables: powerlifting_meets",
  "sql_result_snapshot": "meet_name | count | IPF Masters Cup | 1250 | ...",
  "insight": "Competition participation metrics"
}
```

**Response:**
```json
{
  "bi_code": "MEASURE Meets[Total Lifts] = COUNTROWS(powerlifting_meets)",
  "metric_name": "Total Lifts",
  "success": true,
  "qa_passed": true,
  "tokens_prompt": 450,
  "tokens_response": 120
}
```

### Tableau Calculated Field Generation
**Endpoint:** `POST /api/tableau`
```json
{
  "question": "Normalized performance score",
  "sql_query": "SELECT total_kg / body_weight_kg AS score FROM powerlifting_meets;",
  "schema_context": "Tables: powerlifting_meets",
  "sql_result_snapshot": "score | 5.2 | 6.1 | 4.8 | ...",
  "insight": "Weight-normalized strength metric"
}
```

**Response:**
```json
{
  "bi_code": "SUM([total_kg]) / SUM([body_weight_kg])",
  "metric_name": "Strength Score",
  "success": true,
  "qa_passed": true
}
```

**Full API Documentation:** [http://localhost:8080/docs](http://localhost:8080/docs) (Swagger UI available after deployment)

---

## 🚀 Advanced Deployment

### Production Scaling

For enterprise deployments, consider:

1. **Load Balancing:** Deploy multiple FastAPI replicas behind nginx/HAProxy
2. **Database Replication:** Configure PostgreSQL streaming replication for HA
3. **Vector Store Clustering:** Distribute ChromaDB across multiple nodes
4. **Reverse Proxy:** Add SSL/TLS termination with Traefik or Caddy

### Environment Variables for Production

Create a `.env.production` file:
```env
GROQ_API_KEY=<production-key>
POSTGRES_PASSWORD=<strong-password>
API_TIMEOUT=120
LOG_LEVEL=INFO
CACHE_TTL=3600
REPLICA_COUNT=3
```

### Docker Compose for Production

```bash
# Deploy with resource limits and health monitoring
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale api=3
```

---

## 🔧 Troubleshooting

* **Port 2003 Collision:** If the database fails to start, check for port conflicts (`netstat -ano | findstr :2003`) and terminate the conflicting process, or adjust the port in `docker-compose.yml` and `.env`.
* **Vector Store Errors:** If the LLM fails to find tables, rebuild the ChromaDB index via `python database/reset_vector_store.py`.
* **UI State Issues:** Clear the Streamlit cache (`streamlit cache clear`) or hard refresh your browser to resolve component rendering anomalies.
* **CSV Ingestion Timeout:** For datasets > 5M rows, increase the timeout in `Dockerfile.init`:
  ```dockerfile
  ENV PYTHONUNBUFFERED=1
  ENV INIT_TIMEOUT=600  # 10 minutes
  ```
* **API Timeout (45s default):** Adjust in `api.py` for complex multi-table joins:
  ```python
  TimeoutMiddleware(app, timeout=120)  # Increase to 120 seconds
  ```
* **Nuclear Reset:** To completely wipe the database and vector stores:
  ```bash
  docker-compose down -v
  Remove-Item -Path db\chroma_db -Recurse -Force
  streamlit cache clear
  ```

---

## 🔐 Security Considerations

- **API Keys:** Never commit `.env` files. Use Docker secrets for production.
- **Database Credentials:** Rotate `POSTGRES_PASSWORD` quarterly in production.
- **SQL Injection Prevention:** All queries are generated via LangChain with parameterization. Never concatenate user input directly.
- **Network Isolation:** By default, services communicate via Docker's internal network. Only expose ports 8501 (UI) and 8080 (API) to the internet; keep PostgreSQL internal (port 2003 is for local dev only).

---

## 📚 References & Learning Resources

| Resource | Description |
|----------|-------------|
| [Streamlit Docs](https://docs.streamlit.io) | Frontend framework documentation |
| [FastAPI Tutorial](https://fastapi.tiangolo.com) | Backend API framework |
| [LangChain Documentation](https://python.langchain.com) | LLM orchestration & LCEL |
| [PostgreSQL 16](https://www.postgresql.org/docs/16/) | Database documentation |
| [Groq Console](https://console.groq.com) | LLM API key management |
| [Docker Compose](https://docs.docker.com/compose/) | Container orchestration |

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to your branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup
```bash
git clone <repository-url>
cd "RAG sql to text"
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Optional: for linting & testing
```

---

## ❓ FAQ

**Q: Can I use this with my own dataset?**  
A: Yes! The system is dataset-agnostic. Simply use `python database/load_any_csv.py` to ingest your data, then rebuild the vector store with `python database/reset_vector_store.py`.

**Q: What's the maximum dataset size supported?**  
A: The system has been tested with 3.7M+ rows. For datasets > 100M rows, consider implementing data partitioning strategies.

**Q: How do I update the Groq API key?**  
A: Update the `GROQ_API_KEY` in your `.env` file and restart the containers: `docker-compose restart api ui`.

**Q: Can I use other LLMs besides Groq?**  
A: Yes. Modify `rag_pipeline/chain.py` to instantiate any LangChain-supported LLM (OpenAI, Anthropic, Cohere, etc.).

**Q: How do I export query results?**  
A: Use the "Download as CSV" button in the **"SQL Query"** tab to export any result set.

---

*Developed by Kunal Rawal.*
