import os
import re
from dotenv import load_dotenv
from operator import itemgetter
from sqlalchemy import create_engine, inspect

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_groq import ChatGroq
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.utilities import SQLDatabase
from langchain_chroma import Chroma

# ============================================================================
# CRITIC PROMPT TEMPLATE: Self-Healing Execution Loop
# ============================================================================

CRITIC_PROMPT_TEMPLATE = ChatPromptTemplate.from_template(
    """You are a Senior PostgreSQL Database Expert.
The previous AI agent wrote a SQL query that failed to execute.

Original Question: {question}

Database Schema:
{schema_context}

Failed SQL Query:
{failed_sql}

Database Error Message:
{error_message}

Analyze the error and correct the SQL query. Return ONLY the fixed valid SQL query.
Do not include markdown formatting like ```sql or ```python, just the raw SQL statement."""
)

# ============================================================================
# PERMANENT FIX #1: Prompt Version Hashing for Cache Invalidation
# ============================================================================
import hashlib

def get_prompt_version_hash():
    """
    Compute SHA256 hash of current prompt templates.
    When prompts change, hash changes, old cache keys become invalid.
    
    Returns:
        str: 8-character hex hash of concatenated prompt templates
    """
    try:
        # Import current prompt templates
        from rag_pipeline.prompts import SQL_PROMPT_TEMPLATE
        from rag_pipeline.tableau_prompts import TABLEAU_PROMPT_TEMPLATE
        from rag_pipeline.dax_prompts import DAX_PROMPT_TEMPLATE
        
        # Concatenate all prompts
        combined_prompts = (
            SQL_PROMPT_TEMPLATE + 
            TABLEAU_PROMPT_TEMPLATE + 
            DAX_PROMPT_TEMPLATE
        )
        
        # Compute SHA256 hash and return first 8 chars
        hash_obj = hashlib.sha256(combined_prompts.encode('utf-8'))
        return hash_obj.hexdigest()[:8]
    
    except Exception as e:
        # Fallback to a default hash if import fails
        # This prevents caching errors but uses a stable hash
        return "00000000"

# Import prompt templates with routing logic
from rag_pipeline.prompts import SQL_PROMPT as POWERLIFTING_PROMPT
from rag_pipeline.dynamic_prompts import DYNAMIC_SQL_PROMPT as GENERIC_PROMPT
from rag_pipeline.multi_table_prompt import MULTI_TABLE_SQL_PROMPT, format_relationships_context

def get_prompt_for_table(table_name, is_multi_table=False, relationships=None):
    """
    Route to the appropriate prompt template based on context.
    
    Args:
        table_name (str or None): The name of the table being queried
        is_multi_table (bool): Whether this is a multi-table query
        relationships (list): List of approved relationships for multi-table queries
    
    Returns:
        ChatPromptTemplate: The appropriate prompt template
    """
    # Powerlifting-specific prompt (highest priority - preserve existing)
    if table_name and table_name.lower() == 'powerlifting_meets':
        return POWERLIFTING_PROMPT
    # Multi-table prompt for cross-sheet queries
    elif is_multi_table and relationships:
        return MULTI_TABLE_SQL_PROMPT
    # Generic prompt for single-sheet or uploaded tables
    else:
        return GENERIC_PROMPT

# ============================================================================
# SEMANTIC LAYER: Pillar 2 - Distinct Value Fetching
# Prevents logical mapping errors by showing concrete examples
# ============================================================================

def get_distinct_values(engine, table_name: str, column_name: str, limit: int = 5) -> str:
    """Fetch distinct values using SQLAlchemy 2.0 compliant syntax."""
    try:
        from sqlalchemy import text  # Import needed for modern SQLAlchemy
        
        query = f'SELECT DISTINCT "{column_name}" FROM "{table_name}" WHERE "{column_name}" IS NOT NULL ORDER BY "{column_name}" LIMIT {limit}'
        
        samples = []
        # SQLAlchemy 2.0 syntax using a context manager
        with engine.connect() as conn:
            result = conn.execute(text(query))
            
            for row in result:
                if row[0] is not None:
                    val_str = str(row[0])[:50]
                    # Add quotes if it looks like a string
                    if not val_str.replace('.', '').replace('-', '').replace(':', '').isdigit():
                        samples.append(f"'{val_str}'")
                    else:
                        samples.append(val_str)
        
        if samples:
            return f"Examples: {', '.join(samples)}"
        else:
            return "(empty)"
            
    except Exception as e:
        # Actually print the error so we have terminal observability!
        print(f"Semantic Error on {column_name}: {e}")
        return "(unable to fetch)"

def build_schema_context(table_name=None, dataset_tables=None, mode='single'):
    """
    Fetch the exact schema from PostgreSQL and format it as context for the LLM.
    
    Args:
        table_name (str): Single table name (for single-table mode)
        dataset_tables (list): List of all table names in dataset (for dataset/virtual workspace mode)
        mode (str): 'single' or 'dataset'
    
    Returns:
        str: Formatted schema context with table name(s), columns, sample data, and rules.
    """
    try:
        db_url = os.getenv("DB_URL")
        if not db_url:
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASSWORD", "")
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME", "postgres")
            db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        # VIRTUAL WORKSPACE MODE: Build unified schema for all dataset tables
        if mode == 'dataset' and dataset_tables:
            all_tables_schema = []
            total_rows = 0
            
            for tbl in dataset_tables:
                try:
                    columns = inspector.get_columns(tbl)
                    
                    # PERMANENT FIX #1: Use SQLAlchemy 2.0+ compatible method
                    try:
                        from sqlalchemy import text
                        with engine.connect() as conn:
                            result = conn.execute(text(f'SELECT COUNT(*) FROM "{tbl}"'))
                            row_count = result.scalar() or 0  # Ensure int, not None
                            if row_count is None:
                                row_count = 0
                    except Exception:
                        row_count = 0  # Fallback to 0 if query fails
                    
                    total_rows += row_count
                    
                    # ENHANCED FORMAT: Include sample values for each column to prevent hallucination
                    # Shows actual data so LLM cannot invent columns that don't exist
                    col_descriptions = []
                    
                    for col in columns:
                        col_name = col['name']
                        col_type = str(col['type'])
                        
                        # Fetch sample values from this column (non-null, limit 3)
                        try:
                            # PERMANENT FIX #2: Use SQLAlchemy 2.0+ compatible method for sample data
                            from sqlalchemy import text
                            sample_query = f'SELECT DISTINCT "{col_name}" FROM "{tbl}" WHERE "{col_name}" IS NOT NULL LIMIT 3'
                            with engine.connect() as conn:
                                result = conn.execute(text(sample_query))
                                samples = [str(row[0])[:30] for row in result.fetchall()]  # Use fetchall()
                            sample_text = ", ".join(samples) if samples else "(empty)"
                        except Exception:
                            sample_text = "(unable to fetch)"
                        
                        col_descriptions.append(f"    - {col_name} ({col_type}): {sample_text}")
                    
                    table_schema_str = "\n".join(col_descriptions)
                    all_tables_schema.append(f"[{tbl}] ({row_count:,} rows)\n{table_schema_str}")
                    
                except Exception as tbl_err:
                    all_tables_schema.append(f"[{tbl}] Error: {str(tbl_err)[:50]}")
            
            context = f"""
### VIRTUAL WORKSPACE SCHEMA: Unified Dataset ({len(dataset_tables)} tables)

**Dataset Overview ({total_rows:,} total rows across tables):**

{chr(10).join(all_tables_schema)}

**CRITICAL COLUMN REFERENCE RULES (PREVENTS HALLUCINATION):**
1. The columns listed above are the ONLY columns that exist in each table
2. Use EXACT column names (case-sensitive, lowercase with underscores)
3. If your query needs a column NOT listed above, you MUST use a JOIN to another table
4. DO NOT invent or hallucinate column names - if you see the sample values above, the column exists; if not, it doesn't
5. Example: If you see "state_code (VARCHAR): CA, TX, NY" then state_code exists and you can use it
6. Example: If "state" is NOT in the column list, do NOT use s.state - use s.state_code instead
7. If a requested column is missing from the schema, return the error fallback query

**Multi-Table Query Rules:**
1. All column names are lowercase with underscores
2. Use EXACT column names and table names from schema above - do NOT hallucinate
3. For columns not in primary table, ALWAYS write INNER JOINs using the approved relationships
4. Use table aliases to avoid ambiguity: SELECT s.col1, t.col2 FROM table1 s JOIN table2 t ON ...
5. For numeric aggregations, use SUM(), AVG(), MAX(), MIN(), COUNT()
6. For filtering aggregates, use HAVING clause after GROUP BY
7. NULLS LAST is ONLY valid inside ORDER BY clause - NEVER elsewhere
8. Return ONLY raw SQL starting with SELECT - no markdown, no explanations
"""
            
            # PERMANENT FIX #3: Append multi-grain pattern guidance to schema context
            # Ensures LLM sees detection keywords and decomposition framework even if prompt injection fails
            multi_grain_guidance = """

### 🔥 CRITICAL: MULTI-GRAIN AGGREGATION PATTERNS (ALWAYS CHECK FOR THESE)

**DETECTION: Look for these keywords in the question:**
- "average of [aggregate]" → "average of total sales per store"
- "sum of [aggregate]" → "sum of monthly averages"
- "count of [aggregate]" → "count of distinct orders per category"
- Two aggregation verbs → "top 3 categories by average price"

**IF YOU DETECT MULTI-GRAIN:**
1. STOP and identify three grain levels:
   - BASE GRAIN: What is each raw row? (e.g., store × month)
   - INTERMEDIATE GRAIN: What intermediate grouping is needed? (e.g., store)
   - TARGET GRAIN: Final GROUP BY? (e.g., city)

2. IF base_grain ≠ target_grain AND question mentions two aggregates:
   - MUST use CTE with intermediate aggregation
   - Build WITH clause FIRST with intermediate grain
   - Then SELECT from CTE with final aggregation

3. TEMPLATE for multi-grain SQL:
   ```
   WITH intermediate_agg AS (
     SELECT target_dims, intermediate_dims, FIRST_AGG(metric) as intermediate_metric
     FROM table
     GROUP BY target_dims, intermediate_dims
   )
   SELECT target_dims, FINAL_AGG(intermediate_metric) as result
   FROM intermediate_agg
   GROUP BY target_dims
   ```

**REAL EXAMPLE (rebel_foods table if available):**
- Question: "For each city, average of total NET REVENUE per store?"
- Base: monthly rows (store × date)
- Intermediate: store (SUM revenues per store)
- Target: city (AVG of store totals)
- Correct SQL:
  ```
  WITH store_totals AS (
    SELECT city, store, SUM(net_revenue) as store_total
    FROM rebel_foods
    GROUP BY city, store
  )
  SELECT city, AVG(store_total) as avg_store_revenue
  FROM store_totals
  GROUP BY city
  ```

**WRONG APPROACH (single-grain, do NOT use):**
- SELECT city, AVG(net_revenue) FROM rebel_foods GROUP BY city;
- Problem: Averages individual monthly rows, not store totals (incorrect grain)
"""
            
            return (context + multi_grain_guidance).strip()
        
        # SINGLE-TABLE MODE: With Semantic Layer (Pillar 2)
        else:
            if not table_name:
                return "Error: table_name required for single-table mode"
            
            columns = inspector.get_columns(table_name)
            column_descriptions = []
            
            # Categorical columns that need distinct value examples (Semantic Layer)
            # These prevent the LLM from making logical mapping errors
            semantic_columns = {
                'city', 'store', 'month', 'status', 'revenue_cohort', 'ebitda_category',
                'region', 'zone', 'category', 'product', 'brand', 'state', 'country',
                'season', 'quarter', 'segment', 'channel', 'location', 'type'
            }
            
            for col in columns:
                col_name = col['name']
                col_type = str(col['type'])
                nullable = "✓" if col['nullable'] else "✗"
                
                # For semantic columns, append distinct value examples to prevent LLM hallucination
                if col_name.lower() in semantic_columns:
                    distinct_values = get_distinct_values(engine, table_name, col_name, limit=5)
                    column_descriptions.append(f"  - {col_name} ({col_type}) [Nullable: {nullable}] — {distinct_values}")
                else:
                    column_descriptions.append(f"  - {col_name} ({col_type}) [Nullable: {nullable}]")
            
            context = f"""
### TABLE SCHEMA: {table_name}

**Columns ({len(columns)} total):**
{chr(10).join(column_descriptions)}

**Query Rules for {table_name}:**
1. All column names are lowercase with underscores (e.g., lifter_name, best_deadlift)
2. Use EXACT column names from the schema above - do NOT hallucinate columns
3. For numeric aggregations, use SUM(), AVG(), MAX(), MIN(), COUNT()
4. For filtering aggregates (e.g., "total > 500"), use HAVING clause after GROUP BY
5. CRITICAL: NULLS LAST is ONLY valid inside ORDER BY clause (e.g., ORDER BY column DESC NULLS LAST). NEVER place NULLS LAST after GROUP BY or anywhere else. If no ORDER BY clause exists, omit NULLS LAST entirely.
6. For date filtering, use EXTRACT(YEAR FROM date_column::DATE) for year extraction
7. Return ONLY raw SQL starting with SELECT - no markdown, no explanations
"""
            
            # PERMANENT FIX #3: Append multi-grain pattern guidance to schema context
            # Ensures LLM sees detection keywords and decomposition framework even if prompt injection fails
            multi_grain_guidance = """

### 🔥 CRITICAL: MULTI-GRAIN AGGREGATION PATTERNS (ALWAYS CHECK FOR THESE)

**DETECTION: Look for these keywords in the question:**
- "average of [aggregate]" → "average of total sales per store"
- "sum of [aggregate]" → "sum of monthly averages"
- "count of [aggregate]" → "count of distinct orders per category"
- Two aggregation verbs → "top 3 categories by average price"

**IF YOU DETECT MULTI-GRAIN:**
1. STOP and identify three grain levels:
   - BASE GRAIN: What is each raw row?
   - INTERMEDIATE GRAIN: What intermediate grouping is needed?
   - TARGET GRAIN: Final GROUP BY?

2. IF base_grain ≠ target_grain AND question mentions two aggregates:
   - MUST use CTE with intermediate aggregation
   - Build WITH clause FIRST with intermediate grain
   - Then SELECT from CTE with final aggregation

3. TEMPLATE for multi-grain SQL:
   ```
   WITH intermediate_agg AS (
     SELECT target_dims, intermediate_dims, FIRST_AGG(metric) as intermediate_metric
     FROM table
     GROUP BY target_dims, intermediate_dims
   )
   SELECT target_dims, FINAL_AGG(intermediate_metric) as result
   FROM intermediate_agg
   GROUP BY target_dims
   ```
"""
            
            return (context + multi_grain_guidance).strip()
    
    except Exception as e:
        return f"Error loading schema: {str(e)}"


def get_sql_chain(active_table=None, is_multi_table=False, relationships=None, dataset_tables=None):
    """
    Constructs the main LangChain Expression Language (LCEL) chain for the Text-to-SQL RAG pipeline.
    
    Args:
        active_table (str, optional): The table name to query (must be sanitized name as it exists in PostgreSQL).
                                     If provided, uses direct schema injection.
                                     If not provided, falls back to ChromaDB retrieval (legacy behavior).
        is_multi_table (bool): Whether this is a multi-table query requiring relationship context
        relationships (list): List of approved relationships [{from_sheet, from_column, to_sheet, to_column, ...}]
                             for multi-table queries. Injected into prompt to prevent LLM hallucination.
        dataset_tables (list, optional): NEW - List of all table names in a Virtual Workspace dataset.
                                        When provided, builds unified schema for entire dataset.
    
    Returns:
        The LCEL chain for generating and executing SQL queries.
    """
    load_dotenv()

    # --- 1. Initialize Connections ---
    # Connect to the PostgreSQL database
    db_url = os.getenv("DB_URL")
    if not db_url:
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "postgres")
        db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    db = SQLDatabase.from_uri(db_url)

    # Initialize the Groq LLM (Using Llama 3.3 70B for high-accuracy SQL)
    # PERMANENT FIX #1: Add timeout to prevent infinite hangs on LLM API calls
    llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama-3.3-70b-versatile",
        temperature=0,
        timeout=45,  # Maximum 45 seconds per LLM call
        max_retries=1  # Only retry once to avoid cascading delays
    )

    # --- 2. Define the RAG Chain Logic ---
    
    # Initialize schema_context variable (will be set in each mode branch)
    schema_context = ""
    
    # VIRTUAL WORKSPACE MODE: Build unified schema for entire dataset
    if dataset_tables and is_multi_table:
        selected_prompt = get_prompt_for_table(table_name=None, is_multi_table=True, relationships=relationships)
        schema_context = build_schema_context(dataset_tables=dataset_tables, mode='dataset')
        
        def inject_schema_context(inputs):
            """Inject unified dataset schema + relationships for Virtual Workspace.
            
            Dynamically injects variables matching what the selected prompt template expects.
            PERMANENT FIX: Always return both 'schema_context' and 'context' for consistency.
            """
            # Check what variables this specific prompt template requires
            prompt_vars = getattr(selected_prompt, 'input_variables', [])
            relationships_context = format_relationships_context(relationships)
            
            # ALWAYS return all potential variables for consistency
            # This ensures both schema_context and context are available
            # regardless of which prompt template is selected
            return {
                **inputs,
                "schema_context": schema_context,
                "relationships_context": relationships_context,
                "context": schema_context
            }
        
        sql_generation_chain = (
            RunnableLambda(inject_schema_context)
            | selected_prompt
            | llm
            | StrOutputParser()
        )
    
    # SINGLE-TABLE MODE: Original behavior
    elif active_table:
        # Phase 4: Route to appropriate prompt template based on table
        selected_prompt = get_prompt_for_table(table_name=active_table, is_multi_table=is_multi_table, relationships=relationships)
        
        # Build context directly from the actual table schema
        schema_context = build_schema_context(table_name=active_table, mode='single')
        
        # Create a function that injects the schema context directly
        def inject_schema_context(inputs):
            """Inject the schema context with variables matching the selected prompt.
            
            PERMANENT FIX: Always returns both 'schema_context' and 'context' keys
            for consistency, regardless of which prompt template is selected.
            This ensures backward compatibility and allows debug/inspection code
            to access schema_context reliably.
            """
            relationships_context = format_relationships_context(relationships) if relationships else ""
            
            # ALWAYS return all potential variables for consistency
            # This ensures both schema_context and context are available
            # regardless of which prompt template is selected
            return {
                **inputs,
                "schema_context": schema_context,
                "relationships_context": relationships_context,
                "context": schema_context
            }
        
        sql_generation_chain = (
            RunnableLambda(inject_schema_context)
            | selected_prompt
            | llm
            | StrOutputParser()
        )
    
    else:
        # Legacy: Use ChromaDB retrieval if no active_table provided
        schema_context = ""  # Initialize for legacy mode
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        
        vector_store = Chroma(
            collection_name="powerlifting_schema",
            persist_directory="./db/chroma_db",
            embedding_function=embeddings,
        )
        retriever = vector_store.as_retriever(search_kwargs={"k": 5})
        
        # Format retrieved documents
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)
        
        sql_generation_chain = (
            RunnablePassthrough.assign(context=(itemgetter("question") | retriever | format_docs))
            | selected_prompt
            | llm
            | StrOutputParser()
        )

    # --- 3. Define the Full RAG and Execution Chain ---
    
    # This function cleans SQL by removing markdown code blocks
    def clean_sql(sql_text):
        """Extract just the SQL query from LLM output, removing conversational text."""
        # 1. If it has markdown sql blocks, extract the last one.
        code_blocks = re.findall(r"```(?:sql)?\s*([\s\S]*?)\s*```", sql_text, re.IGNORECASE)
        if code_blocks:
            return code_blocks[-1].strip()
            
        # 2. Otherwise, look for the last SQL statement (starting with SELECT or WITH)
        statements = list(re.finditer(r"(?i)\b(?:SELECT|WITH)\b[\s\S]*?(?:;|$)", sql_text))
        
        if statements:
            # We return the last valid SQL block found
            return statements[-1].group(0).strip()
            
        # 3. Fallback to just stripping markdown if regex didn't find anything
        sql_text = re.sub(r"```sql\s*", "", sql_text)
        sql_text = re.sub(r"```\s*", "", sql_text)
        return sql_text.strip()
    
    # This function executes the generated SQL query and returns both SQL and result
    def execute_query_with_sql(sql):
        """Execute SQL query and return SQL, result, AND schema_context for DAX generation."""
        import threading
        cleaned_sql = clean_sql(sql)
        result_holder = [None]
        exception_holder = [None]
        
        def run_query():
            try:
                result_holder[0] = db.run(cleaned_sql)
            except Exception as e:
                exception_holder[0] = e
        
        # PERMANENT FIX #2: Add 30-second timeout for database queries using threading
        query_thread = threading.Thread(target=run_query, daemon=True)
        query_thread.start()
        query_thread.join(timeout=30)  # Wait max 30 seconds
        
        try:
            if query_thread.is_alive():
                # Query timed out
                return {
                    "sql": cleaned_sql,
                    "result": None,
                    "error": "Database query exceeded 30 second timeout",
                    "success": False,
                    "schema_context": schema_context
                }
            elif exception_holder[0]:
                # Query failed with exception
                return {
                    "sql": cleaned_sql,
                    "result": None,
                    "error": str(exception_holder[0]),
                    "success": False,
                    "schema_context": schema_context
                }
            else:
                # Query succeeded
                return {
                    "sql": cleaned_sql,
                    "result": result_holder[0],
                    "success": True,
                    "schema_context": schema_context  # ✅ INJECT SCHEMA CONTEXT
                }
        except Exception as e:
            return {
                "sql": cleaned_sql,
                "result": None,
                "error": str(e),
                "success": False,
                "schema_context": schema_context  # ✅ INJECT SCHEMA CONTEXT
            }
    
    # --- 3b. Self-Healing Execution Loop ---
    # Agentic retry mechanism: generates SQL, tries to execute, and if it fails,
    # sends the error to a Critic agent which corrects the SQL and retries.
    def self_healing_execution(inputs: dict) -> dict:
        """
        Agentic self-healing execution loop with Critic agent.
        
        Flow:
        1. Generate initial SQL from user question
        2. Execute the SQL
        3. If successful, return result immediately
        4. If failed, invoke Critic agent to analyze error and correct SQL
        5. Retry execution (up to 3 attempts total)
        6. Return final result (success or failure after max retries)
        
        Args:
            inputs (dict): Must contain 'question' key with user's natural language query
        
        Returns:
            dict: Result dict with keys: sql, result, success, error, schema_context, retry_count
        """
        # Build the Critic chain locally
        critic_chain = CRITIC_PROMPT_TEMPLATE | llm | StrOutputParser()
        
        max_retries = 3
        retry_count = 0
        current_sql = None
        
        while retry_count < max_retries:
            # First attempt: generate SQL from the user question
            # Subsequent attempts: use the Critic's corrected SQL
            if current_sql is None:
                print("\n--- WHAT THE AI SEES (SEMANTIC LAYER) ---")
                # We invoke just the schema injection part to peek at it
                schema_peek = inject_schema_context(inputs)
                print(schema_peek["schema_context"])
                print("-----------------------------------------\n")
                current_sql = sql_generation_chain.invoke(inputs)
            
            # Execute the current SQL
            result_dict = execute_query_with_sql(current_sql)
            
            # Success: return immediately with retry count
            if result_dict["success"]:
                result_dict["retry_count"] = retry_count
                return result_dict
            
            # Failure: check if we have retries remaining
            if retry_count < max_retries - 1:
                # Print debug message to console
                error_preview = result_dict["error"][:80] if result_dict["error"] else "Unknown error"
                print(f"[Self-Healing] Retry {retry_count + 1}/{max_retries} — SQL failed: {error_preview}")
                
                # Invoke Critic agent to correct the SQL
                # PERMANENT FIX #3: Add timeout to critic agent to prevent cascading hangs
                try:
                    import threading
                    critic_output_holder = [None]
                    critic_exception_holder = [None]
                    
                    def run_critic():
                        try:
                            critic_output_holder[0] = critic_chain.invoke({
                                "question": inputs["question"],
                                "schema_context": result_dict["schema_context"],
                                "failed_sql": result_dict["sql"],
                                "error_message": result_dict["error"]
                            })
                        except Exception as e:
                            critic_exception_holder[0] = e
                    
                    # Run critic with 45-second timeout
                    critic_thread = threading.Thread(target=run_critic, daemon=True)
                    critic_thread.start()
                    critic_thread.join(timeout=45)  # Wait max 45 seconds
                    
                    if critic_thread.is_alive():
                        print(f"[Self-Healing] Critic agent exceeded 45 second timeout")
                        result_dict["retry_count"] = retry_count
                        return result_dict
                    elif critic_exception_holder[0]:
                        raise critic_exception_holder[0]
                    else:
                        critic_output = critic_output_holder[0]
                        # Clean markdown backticks from Critic's output
                        current_sql = critic_output.replace('```sql', '').replace('```python', '').replace('```', '').strip()
                        retry_count += 1
                except Exception as critic_error:
                    # If Critic itself fails, return the original error
                    print(f"[Self-Healing] Critic agent failed: {str(critic_error)[:80]}")
                    result_dict["retry_count"] = retry_count
                    return result_dict
            else:
                # All retries exhausted, return final error state
                result_dict["retry_count"] = max_retries
                return result_dict
        
        # Fallback (should not reach here due to loop logic)
        result_dict["retry_count"] = max_retries
        return result_dict

    # The complete chain with self-healing: invoke self_healing_execution which handles
    # the entire retry loop internally. This keeps the frontend clean and decoupled.
    full_chain = RunnableLambda(self_healing_execution)

    return full_chain

# ============================================================================
# DAX MEASURE GENERATION FUNCTIONS (Phase 1.5 & 2: Elite Features)
# ============================================================================

def extract_sql_parameters(sql_query: str) -> str:
    """
    Extract hardcoded values from SQL to convert into DAX variables.
    
    Finds:
    - Numeric thresholds (WHERE > 10000, WHERE < 100)
    - Limits (LIMIT 5, TOP 10)
    - Dates (BETWEEN '2025-01-01', DATE > '2024-06-01')
    - String literals in IN clauses
    
    Args:
        sql_query (str): The SQL query to extract parameters from
    
    Returns:
        str: Formatted string of extracted parameters, e.g.:
            "- Threshold: 10000 (from WHERE weight > 10000)
             - Limit: 5 (from LIMIT 5)
             - Date: 2025-01-01 (from BETWEEN)"
    """
    try:
        parameters = []
        
        # Improved resilient pattern: handles spacing variations (>, >=, <, <=) and multiple data types
        # Matches: column > 10000, column>=10000, column > '2025-01-01', zone='Zone A'
        comparison_pattern = r"(?:WHERE|AND|OR)\s+(\w+)\s*([>=<]{1,2})\s*([\d\.]+|\d{4}-\d{2}-\d{2}|'[^']+')" 
        for match in re.finditer(comparison_pattern, sql_query, re.IGNORECASE):
            col_name, op, value = match.groups()
            # Clean up value (remove quotes if present)
            clean_value = value.replace("'", "")
            parameters.append(f"- {col_name} {op} {clean_value} (from WHERE {col_name} {op} {value})")
        
        # Extract LIMIT/TOP values
        limit_pattern = r'(?:LIMIT|TOP)\s+(\d+)'
        for match in re.finditer(limit_pattern, sql_query, re.IGNORECASE):
            value = match.group(1)
            parameters.append(f"- Record Limit: {value} (from LIMIT/TOP {value})")
        
        # Extract date ranges from BETWEEN clauses
        date_pattern = r"BETWEEN\s+'(\d{4}-\d{2}-\d{2})'\s+AND\s+'(\d{4}-\d{2}-\d{2})'"
        for match in re.finditer(date_pattern, sql_query, re.IGNORECASE):
            start_date, end_date = match.groups()
            parameters.append(f"- Date Range: {start_date} to {end_date} (from BETWEEN clause)")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_params = []
        for param in parameters:
            if param not in seen:
                seen.add(param)
                unique_params.append(param)
        
        # Format as string for LLM
        if unique_params:
            return "\n".join(unique_params)
        else:
            return "No hardcoded parameters detected in SQL."
    
    except Exception as e:
        return f"Error extracting parameters: {str(e)}"


def generate_dax_measure(
    sql_query: str, 
    schema_context: str, 
    question: str = "",
    sql_result_snapshot: str = "",
    insight: str = ""
) -> dict:
    """
    Generate a PRODUCTION-READY Power BI DAX measure equivalent to the SQL query.
    
    Enforces 9 Architectural Principles:
    1. SYNTAX RIGIDITY: Strict DAX syntax (no SQL keywords, correct aggregations)
    2. NAKED MEASURE RULE: [MeasureName] for measures, 'Table'[Column] for columns
    3. RETURN SHAPE PARITY: Output shape matches SQL (table vs scalar) + post-aggregation enforcement
    4. CALCULATE & CONTEXT ENGINE: CALCULATE() with KEEPFILTERS() for performance
    5. TIME INTELLIGENCE: Assume Date table with 1:Many relationship
    6. DYNAMIC PARAMETERIZATION: Extract hardcoded values to VAR statements
    7. FORMATTING & DOCUMENTATION: Production-grade output with usage notes
    8. GOLD STANDARD TABLE PATTERN: ADDCOLUMNS + SUMMARIZE for calculation reliability
    9. ITERATOR ENFORCEMENT: AVERAGEX/SUMX/MINX/MAXX for mathematical expressions
    
    Additional Features:
    - Dynamic Variable Injection: Parameterized VAR statements for flexibility
    - Star Schema Optimization: Uses CALCULATE() + KEEPFILTERS() for VertiPaq performance
    - Usage Note Generation: Best practice guidance for analyst review
    - Logic Verification: QA check to ensure SQL ↔ DAX parity (Master-Level)
    
    Args:
        sql_query (str): The generated SQL query
        schema_context (str): Schema context (table names, columns, types, relationships)
        question (str, optional): Original user question for context
    
    Returns:
        dict: {
            "dax": str,                    # Generated DAX measure code (production-ready)
            "measure_name": str,           # Extracted measure name
            "success": bool,               # True if generation succeeded
            "error": str,                  # Error message if failed
            "usage_note": str,             # Best practice note for analyst
            "generation_ms": int,          # DAX generation time
            "tokens_prompt": int,          # Input tokens
            "tokens_response": int,        # Output tokens
            "qa_status": str,              # "MATCH" or "DISCREPANCY: reason"
            "qa_passed": bool,             # True if logic verified (MATCH)
            "qa_time_ms": int              # QA verification time
        }
    """
    import time
    from rag_pipeline.dax_prompts import get_dax_prompt_template
    from rag_pipeline.dax_qa import verify_dax_sql_parity
    
    start_time = time.time()
    
    try:
        # Step 1: Extract hardcoded parameters from SQL
        extracted_params = extract_sql_parameters(sql_query)
        
        # Step 2: Build DAX prompt with all placeholders
        dax_prompt = get_dax_prompt_template()
        
        # Step 3: Create LLM chain
        llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama-3.3-70b-versatile",
            temperature=0
        )
        
        dax_chain = dax_prompt | llm | StrOutputParser()
        
        # Step 4: Invoke DAX generation
        dax_response = dax_chain.invoke({
            "sql_query": sql_query,
            "schema_context": schema_context,
            "extracted_parameters": extracted_params,
            "question": question,
            "sql_result_snapshot": sql_result_snapshot,
            "insight": insight
        })
        
        # Step 5: Parse DAX response to extract components
        # Split on [USAGE_NOTE] marker
        if "[USAGE_NOTE]" in dax_response:
            dax_code_part, usage_note_part = dax_response.split("[USAGE_NOTE]", 1)
            dax_code = dax_code_part.strip()
            # Extract text between [USAGE_NOTE] and [/USAGE_NOTE]
            if "[/USAGE_NOTE]" in usage_note_part:
                usage_note = usage_note_part.split("[/USAGE_NOTE]")[0].strip()
            else:
                usage_note = usage_note_part.strip()
        else:
            dax_code = dax_response.strip()
            usage_note = ""
        
        # Step 6: Extract measure name (first word before "=")
        measure_name = "Generated Measure"
        name_match = re.search(r'(\w+)\s*=', dax_code)
        if name_match:
            measure_name = name_match.group(1)
        
        # Step 7: Calculate generation time and token counts
        generation_ms = int((time.time() - start_time) * 1000)
        
        # Get token counts from LLM response metadata (if available)
        tokens_prompt = 0
        tokens_response = 0
        if hasattr(llm, 'last_prompt_tokens'):
            tokens_prompt = llm.last_prompt_tokens
        if hasattr(llm, 'last_completion_tokens'):
            tokens_response = llm.last_completion_tokens
        
        # Step 8: Run QA Verification (Master-Level Feature) 🏆
        qa_result = verify_dax_sql_parity(sql_query, dax_code, schema_context)
        
        # Return complete response with all metrics
        return {
            "bi_code": dax_code,
            "metric_name": measure_name,
            "success": True,
            "error": "",
            "usage_note": usage_note,
            "generation_ms": generation_ms,
            "tokens_prompt": tokens_prompt,
            "tokens_response": tokens_response,
            "qa_status": qa_result["status"],
            "qa_passed": qa_result["passed"],
            "qa_time_ms": qa_result["verification_time_ms"]
        }
    
    except Exception as e:
        # Return error state
        return {
            "bi_code": "",
            "metric_name": "",
            "success": False,
            "error": str(e),
            "usage_note": "",
            "generation_ms": int((time.time() - start_time) * 1000),
            "tokens_prompt": 0,
            "tokens_response": 0,
            "qa_status": "Generation Failed",
            "qa_passed": False,
            "qa_time_ms": 0
        }

# Example of how to run the chain (for testing purposes)
if __name__ == '__main__':
    print("=" * 80)
    print("PHASE 3 & 4 TEST: Context-Aware RAG with Prompt Routing")
    print("=" * 80)
    
    # Test 1: Query with active_table="powerlifting_meets" (uses POWERLIFTING_PROMPT)
    print("\n[TEST 1] Powerlifting Meets Query (POWERLIFTING_PROMPT)")
    print("-" * 80)
    chain_pw = get_sql_chain(active_table='powerlifting_meets')
    question_pw = "What is the average total for female lifters in the 63kg class?"
    print(f"Question: {question_pw}")
    response_pw = chain_pw.invoke({"question": question_pw})
    print(f"Generated SQL:\n{response_pw['sql']}")
    print(f"Result: {response_pw['result']}")
    
    print("\n" + "=" * 80)

