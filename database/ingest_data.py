import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import logging

# --- Configuration & Setup ---
# Configure logging to provide clear output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# --- Database Connection Details ---
DATABASE_URL = os.getenv("DB_URL")
if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "postgres")
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# --- Data File Configuration ---
# Path to the cleaned data file
DATA_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'clean', 'cleaned_meets.xlsx')
TABLE_NAME = "powerlifting_meets"

def ingest_data():
    """
    Reads data from an Excel file and ingests it into a PostgreSQL database table.
    """
    logging.info("Starting data ingestion process...")

    try:
        # --- Step 1: Connect to the Database ---
        logging.info(f"Connecting to database '{DB_NAME}' on {DB_HOST}:{DB_PORT}...")
        engine = create_engine(DATABASE_URL)
        
        # Test the connection
        with engine.connect() as connection:
            logging.info("Database connection successful.")

        # --- Step 2: Read the Excel Data ---
        logging.info(f"Reading data from '{DATA_FILE_PATH}'...")
        if not os.path.exists(DATA_FILE_PATH):
            logging.error(f"Data file not found at: {DATA_FILE_PATH}")
            return
            
        df = pd.read_excel(DATA_FILE_PATH)
        logging.info(f"Successfully loaded {len(df)} rows from the Excel file.")

        # --- Step 3: Normalize Column Names to Lowercase ---
        # PostgreSQL converts unquoted mixed-case column names to lowercase by default.
        # Converting here ensures consistency between our ingestion and database schema.
        df.columns = df.columns.str.lower()
        logging.info("Column names normalized to lowercase.")

        # --- Step 4: Ingest Data into PostgreSQL ---
        logging.info(f"Ingesting data into table '{TABLE_NAME}'...")
        # Use 'if_exists='replace'' to ensure we start with a fresh table each time.
        # For production, you might use 'append' or handle conflicts differently.
        df.to_sql(
            TABLE_NAME,
            engine,
            if_exists='replace',
            index=False,
            method='multi',
            chunksize=10000  # Process data in chunks for memory efficiency
        )
        logging.info(f"Successfully ingested {len(df)} rows into '{TABLE_NAME}'.")

    except FileNotFoundError:
        logging.error(f"ERROR: The data file was not found at {DATA_FILE_PATH}. Please ensure the file exists.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    ingest_data()
