import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

def get_dynamic_schema():
    db_url = os.getenv("DB_URL")
    if not db_url:
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "postgres")
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    engine = create_engine(db_url)
    db_inspector = inspect(engine)
    table_name = 'powerlifting_meets'
    
    columns = db_inspector.get_columns(table_name)
    schema_text = f"SCHEMA DEFINITION: The database has one table named '{table_name}'. The columns and their data types are: "
    column_details = [f"{col['name']} ({col['type']})" for col in columns]
    schema_text += ", ".join(column_details) + "."
    return schema_text

def build_vector_store():
    load_dotenv()
    print("1. Extracting dynamic schema from PostgreSQL...")
    schema_doc = get_dynamic_schema()
    
    print("2. Initializing Google Gemini Embeddings...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    ai_dictionary = [
        Document(page_content=schema_doc, metadata={"type": "schema"}),
        Document(
            page_content="BUSINESS RULE: When asked for the 'heaviest' or 'highest' lift, use the MAX() function on the respective column (e.g., best_squat, best_benchpress, best_deadlift). Ignore rows where the lift value is NULL or less than 0.",
            metadata={"type": "rule"}
        ),
        Document(
            page_content="EXAMPLE 1 - Query: What is the average total for female lifters in the 63kg class? SQL: SELECT AVG(total_kg) FROM powerlifting_meets WHERE sex = 'F' AND weightclasskg = '63';",
            metadata={"type": "example"}
        ),
        Document(
            page_content="EXAMPLE 2 - Query: Who has the highest raw deadlift of all time? SQL: SELECT lifter_name, best_deadlift FROM powerlifting_meets WHERE equipment = 'Raw' ORDER BY best_deadlift DESC NULLS LAST LIMIT 1;",
            metadata={"type": "example"}
        )
    ]

    persist_directory = "./db/chroma_db"
    print(f"3. Embedding {len(ai_dictionary)} documents into ChromaDB at {persist_directory}...")
    
    vectorstore = Chroma.from_documents(
        documents=ai_dictionary,
        embedding=embeddings,
        collection_name="powerlifting_schema",
        persist_directory=persist_directory
    )
    print("Success! AI Dictionary created with Gemini Vectors.")

if __name__ == "__main__":
    build_vector_store()