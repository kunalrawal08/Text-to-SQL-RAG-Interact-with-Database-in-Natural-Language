"""
Universal Vector Store Builder
Dynamically discovers ALL tables in PostgreSQL and embeds their schemas into ChromaDB
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_all_schemas():
    """
    Dynamically discover ALL tables in PostgreSQL and extract their schemas.
    """
    load_dotenv()
    
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    engine = create_engine(db_url)
    db_inspector = inspect(engine)
    
    all_schemas = []
    tables = db_inspector.get_table_names()
    
    logging.info(f"Found {len(tables)} table(s) in database '{db_name}'")
    
    for table_name in tables:
        columns = db_inspector.get_columns(table_name)
        schema_text = f"SCHEMA DEFINITION: Table '{table_name}' contains columns: "
        column_details = [f"{c['name']} ({c['type']})" for c in columns]
        schema_text += ", ".join(column_details) + "."
        
        all_schemas.append(Document(page_content=schema_text, metadata={"type": "schema", "table": table_name}))
        logging.info(f"✓ Extracted schema for table '{table_name}'")
    
    return all_schemas

def build_universal_vector_store():
    """
    Build a universal vector store that covers ALL tables in the database.
    """
    load_dotenv()
    
    logging.info("🔨 Building Universal Vector Store...")
    
    # Step 1: Get all schemas
    logging.info("Step 1: Discovering database schemas...")
    schema_docs = get_all_schemas()
    
    # Step 2: Add generic business rules
    logging.info("Step 2: Adding business rules...")
    generic_rules = [
        Document(
            page_content="BUSINESS RULE: Use MAX() for highest values, MIN() for lowest, AVG() for averages, and COUNT() for totals.",
            metadata={"type": "rule"}
        ),
        Document(
            page_content="INSTRUCTION: Always include WHERE clauses to filter for relevant data. Use NULLS LAST to handle NULL values.",
            metadata={"type": "rule"}
        ),
        Document(
            page_content="INSTRUCTION: When joining multiple tables, ensure foreign key relationships are respected and JOIN conditions are explicit.",
            metadata={"type": "rule"}
        ),
    ]
    
    all_docs = schema_docs + generic_rules
    
    # Step 3: Initialize embeddings
    logging.info("Step 3: Initializing Google Gemini Embeddings...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    
    # Step 4: Create ChromaDB collection
    persist_directory = "./db/chroma_db_universal"
    logging.info(f"Step 4: Embedding {len(all_docs)} documents into ChromaDB...")
    
    vectorstore = Chroma.from_documents(
        documents=all_docs,
        embedding=embeddings,
        collection_name="universal_schema",
        persist_directory=persist_directory
    )
    
    logging.info(f"✅ Universal Vector Store created at {persist_directory}")
    logging.info(f"   Total embedded documents: {len(all_docs)}")
    logging.info(f"   Tables indexed: {len(schema_docs)}")

if __name__ == "__main__":
    build_universal_vector_store()

# Usage:
# python database/reset_vector_store.py
