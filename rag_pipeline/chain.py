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

# Import prompt templates with routing logic
from rag_pipeline.prompts import SQL_PROMPT as POWERLIFTING_PROMPT
from rag_pipeline.dynamic_prompts import DYNAMIC_SQL_PROMPT as GENERIC_PROMPT

def get_prompt_for_table(table_name):
    """
    Route to the appropriate prompt template based on the table name.
    
    Args:
        table_name (str or None): The name of the table being queried
    
    Returns:
        ChatPromptTemplate: The appropriate prompt template for this table
    """
    # Powerlifting-specific prompt for optimized performance on powerlifting_meets
    if table_name and table_name.lower() == 'powerlifting_meets':
        return POWERLIFTING_PROMPT
    # Generic prompt for any other table (uploaded CSVs, new tables, etc.)
    # Also used as fallback for legacy ChromaDB retrieval (no active_table)
    else:
        return GENERIC_PROMPT

def build_schema_context(table_name):
    """
    Fetch the exact schema from PostgreSQL and format it as context for the LLM.
    
    Returns:
        str: Formatted schema context with table name, columns, sample data, and rules.
    """
    try:
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT")
        db_name = os.getenv("DB_NAME")
        
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        # Get columns
        columns = inspector.get_columns(table_name)
        column_descriptions = []
        for col in columns:
            col_type = str(col['type'])
            nullable = "✓" if col['nullable'] else "✗"
            column_descriptions.append(f"  - {col['name']} ({col_type}) [Nullable: {nullable}]")
        
        # Build context string
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
        return context.strip()
    
    except Exception as e:
        return f"Error loading schema for {table_name}: {str(e)}"


def get_sql_chain(active_table=None):
    """
    Constructs the main LangChain Expression Language (LCEL) chain for the Text-to-SQL RAG pipeline.
    
    Args:
        active_table (str, optional): The table name to query. If provided, uses direct schema injection.
                                     If not provided, falls back to ChromaDB retrieval (legacy behavior).
    
    Returns:
        The LCEL chain for generating and executing SQL queries.
    """
    load_dotenv()

    # --- 1. Initialize Connections ---
    # Connect to the PostgreSQL database
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    db = SQLDatabase.from_uri(db_url)

    # Initialize the Groq LLM (Using Llama 3.3 70B for high-accuracy SQL)
    llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )

    # --- 2. Define the RAG Chain Logic ---
    
    # Phase 4: Route to appropriate prompt template based on table
    selected_prompt = get_prompt_for_table(active_table)
    
    # Phase 3 Logic: If active_table is provided, use direct schema injection
    if active_table:
        # Build context directly from the actual table schema
        schema_context = build_schema_context(active_table)
        
        # Create a function that injects the schema context directly
        def inject_schema_context(inputs):
            """Inject the schema context directly without ChromaDB retrieval."""
            return {
                **inputs,
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
        """Remove markdown code blocks from SQL text generated by LLM."""
        sql_text = re.sub(r"```sql\s*", "", sql_text)
        sql_text = re.sub(r"```\s*", "", sql_text)
        return sql_text.strip()
    
    # This function executes the generated SQL query and returns both SQL and result
    def execute_query_with_sql(sql):
        """Execute SQL query and return both the generated SQL and execution result."""
        cleaned_sql = clean_sql(sql)
        try:
            result = db.run(cleaned_sql)
            return {
                "sql": cleaned_sql,
                "result": result,
                "success": True
            }
        except Exception as e:
            return {
                "sql": cleaned_sql,
                "result": None,
                "error": str(e),
                "success": False
            }

    # The complete chain: retrieve context, generate SQL, execute SQL, and return both SQL and result
    full_chain = (
        sql_generation_chain
        | RunnableLambda(execute_query_with_sql)
    )

    return full_chain

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

