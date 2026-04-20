# Text-to-SQL Queries RAG : Instant Database Information Retreval using Natural Language 

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![LangChain](https://img.shields.io/badge/LangChain-121212?logo=chainlink&logoColor=white)](https://langchain.com/)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Kunal%20Rawal-0077B5?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/kunaldrawal/)

An enterprise-grade Text-to-SQL database information retreval designed for analyzing large-scale datasets. While currently configured for a comprehensive powerlifting database, the architecture features dynamic schema discovery, making it entirely dataset-agnostic and scalable.

## 🏗️ System Architecture

Built with a modern data stack focusing on high-fidelity retrieval and low-latency execution.

* **UI/UX:** Streamlit (Custom Professional Theme)
* **Orchestration:** LangChain
* **LLM Engine:** Groq Llama 3.3 70B
* **Vector Store:** ChromaDB (with Google Gemini Embeddings)
* **Database:** PostgreSQL 16

### Core Pipeline
1. **Dynamic Schema Discovery:** Reads PostgreSQL metadata and schema constraints in real-time.
2. **Semantic Routing (ChromaDB):** Retrieves semantically similar schema examples to guide the LLM.
3. **SQL Generation:** Llama 3.3 70B generates context-aware, deterministic PostgreSQL queries.
4. **Secure Execution:** Native PostgreSQL execution with automated error handling and fallback logic.
5. **NLP Formatting:** Results are translated back into human-readable, formatted text.

---

## 🚀 Quick Start

### Pre-Flight Requirements
Ensure you have Python 3.9+ and Docker Desktop installed and running. Ensure port `2003` is available.

### 1. Environment Setup
Create a `.env` file in the root directory:
```env
GOOGLE_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
DB_USER=POWERLIFTER_KUNAL
DB_PASSWORD= "Your db password"
DB_HOST=localhost
DB_PORT=2003
DB_NAME= "your db name"
```

Install dependencies:

```bash
pip install -r requirements.txt
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
├── requirements.txt                    # Python dependencies
├── .env                                # Environment configuration (not tracked)
├── .gitignore                          # Git ignore rules
├── README.md                           # This file
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
│   ├── prompts.py                      # Domain-specific routing prompts
│   ├── dynamic_prompts.py              # Dynamic prompt generation utilities
│   ├── universal_prompts.py            # Dataset-agnostic prompt templates
│   └── vector_store.py                 # ChromaDB embedding generators
│
├── database/
│   ├── docker-compose.yml              # Containerized PostgreSQL infrastructure config
│   ├── get_schema.py                   # Dynamic schema discovery utility
│   ├── ingest_data.py                  # Primary powerlifting data ingestion script
│   ├── ingest_csv.py                   # CSV validation and ingestion module
│   ├── load_any_csv.py                 # Universal ETL utility for any dataset
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

## 🔧 Troubleshooting

* **Port 2003 Collision:** If the database fails to start, check for port conflicts (`netstat -ano | findstr :2003`) and terminate the conflicting process, or adjust the port in `docker-compose.yml` and `.env`.
* **Vector Store Errors:** If the LLM fails to find tables, rebuild the ChromaDB index via `python database/reset_vector_store.py`.
* **UI State Issues:** Clear the Streamlit cache (`streamlit cache clear`) or hard refresh your browser to resolve component rendering anomalies.
* **Nuclear Reset:** To completely wipe the database and vector stores:
  ```bash
  docker-compose -f database/docker-compose.yml down -v
  rmdir /S db\chroma_db
  streamlit cache clear
  ```

---

*Developed by Kunal Rawal.*
