"""
Universal CSV Loader for Any Dataset
Accepts a CSV file and table name, loads into PostgreSQL
"""

import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_any_csv(csv_path, table_name):
    """
    Load any CSV file into PostgreSQL with a specified table name.
    
    Args:
        csv_path (str): Path to the CSV file
        table_name (str): Name of the table to create/replace in PostgreSQL
    """
    load_dotenv()
    
    # Database credentials
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    try:
        logging.info(f"Reading CSV from: {csv_path}")
        df = pd.read_csv(csv_path)
        logging.info(f"✓ Successfully loaded {len(df)} rows, {len(df.columns)} columns")
        
        # Normalize column names to lowercase (PostgreSQL best practice)
        df.columns = df.columns.str.lower()
        logging.info(f"✓ Column names normalized to lowercase")
        
        logging.info(f"Connecting to PostgreSQL at {db_host}:{db_port}")
        engine = create_engine(db_url)
        
        # Load data into PostgreSQL
        logging.info(f"Loading data into table '{table_name}'...")
        df.to_sql(
            table_name,
            engine,
            if_exists='replace',
            index=False,
            method='multi',
            chunksize=5000
        )
        
        logging.info(f"✅ Successfully loaded {len(df)} rows into table '{table_name}'")
        
    except FileNotFoundError:
        logging.error(f"❌ CSV file not found: {csv_path}")
    except Exception as e:
        logging.error(f"❌ Error loading CSV: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load any CSV into PostgreSQL")
    parser.add_argument("--csv", required=True, help="Path to CSV file")
    parser.add_argument("--table", required=True, help="Name of table to create")
    
    args = parser.parse_args()
    load_any_csv(args.csv, args.table)

# Usage Examples:
# python database/load_any_csv.py --csv hr_data.csv --table employees
# python database/load_any_csv.py --csv real_estate.csv --table properties
# python database/load_any_csv.py --csv student_data.csv --table students
