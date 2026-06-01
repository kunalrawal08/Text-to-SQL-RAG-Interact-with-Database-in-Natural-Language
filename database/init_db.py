"""
Database Initialization Script
Auto-loads PowerLift data on Docker container startup.
This ensures the database is pre-populated before API/UI services start.
"""

import os
import sys
import time
import pandas as pd
import logging
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database connection from environment
db_url = os.getenv(
    "DB_URL",
    "postgresql://POWERLIFTER_KUNAL:Kunal123@localhost:2003/powerlifting_db"
)

# Path to raw data CSV - Environment-aware (Docker vs Local)
# Docker containers use /app/ path, local development uses relative/absolute Windows paths
DOCKER_CSV_PATH = "/app/data/raw/openpowerlifting-2026-01-03-daa0ab53.csv"
LOCAL_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "raw", "openpowerlifting-2026-01-03-daa0ab53.csv"
)

# Determine which path to use
if os.path.exists(LOCAL_CSV_PATH):
    CSV_PATH = LOCAL_CSV_PATH
elif os.path.exists(DOCKER_CSV_PATH):
    CSV_PATH = DOCKER_CSV_PATH
else:
    # Fallback to environment variable if set
    CSV_PATH = os.getenv("CSV_PATH", LOCAL_CSV_PATH)

logger.info(f"CSV Path Resolution:")
logger.info(f"  Docker Path: {DOCKER_CSV_PATH} (exists: {os.path.exists(DOCKER_CSV_PATH)})")
logger.info(f"  Local Path: {LOCAL_CSV_PATH} (exists: {os.path.exists(LOCAL_CSV_PATH)})")
logger.info(f"  Using: {CSV_PATH}")

# Table name for the data
TABLE_NAME = "powerlifting_meets"


def wait_for_database(max_retries=30, retry_delay=2):
    """Wait for PostgreSQL to become available before attempting to load data."""
    logger.info("⏳ Waiting for PostgreSQL database to be ready...")
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("✅ Database is ready!")
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️  Database not ready (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logger.error(f"❌ Database failed to become ready after {max_retries} attempts")
                return False
    
    return False


def check_if_data_exists():
    """Check if data is already loaded in the database."""
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        if TABLE_NAME in inspector.get_table_names():
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME}"))
                count = result.scalar()
                if count > 0:
                    logger.info(f"✅ Data already exists: {count} rows in '{TABLE_NAME}' table")
                    return True
    except Exception as e:
        logger.warning(f"Could not check existing data: {e}")
    
    return False


def load_csv_data():
    """Load the PowerLift CSV file into the database."""
    if not os.path.exists(CSV_PATH):
        logger.error(f"❌ CSV file not found: {CSV_PATH}")
        return False
    
    logger.info(f"📥 Loading CSV: {CSV_PATH}")
    
    try:
        # Read the CSV
        df = pd.read_csv(CSV_PATH)
        logger.info(f"✓ CSV loaded: {len(df)} rows, {len(df.columns)} columns")
        
        # Normalize column names (lowercase, replace spaces with underscores)
        df.columns = [col.lower().replace(' ', '_').replace('-', '_') for col in df.columns]
        
        # Connect and load data
        logger.info(f"📝 Ingesting data into '{TABLE_NAME}' table...")
        engine = create_engine(db_url)
        
        df.to_sql(
            TABLE_NAME,
            engine,
            if_exists='replace',  # Replace if exists (fresh load)
            index=False,
            method='multi',
            chunksize=5000
        )
        
        logger.info(f"✅ Successfully loaded {len(df)} rows into '{TABLE_NAME}'")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to load CSV data: {e}")
        return False


def initialize_file_registry():
    """Initialize the file_registry table (required by get_schema.py)."""
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        if 'file_registry' not in inspector.get_table_names():
            logger.info("📝 Creating file_registry table...")
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS file_registry (
                        id SERIAL PRIMARY KEY,
                        original_filename VARCHAR(255) NOT NULL,
                        sheet_name VARCHAR(255) NOT NULL DEFAULT 'Main',
                        db_table_name VARCHAR(255) NOT NULL,
                        row_count INT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Register the PowerLift data
                conn.execute(text(f"""
                    INSERT INTO file_registry (original_filename, sheet_name, db_table_name, row_count)
                    SELECT 
                        'openpowerlifting-2026-01-03-daa0ab53.csv',
                        'Main',
                        '{TABLE_NAME}',
                        COUNT(*)
                    FROM {TABLE_NAME}
                    ON CONFLICT DO NOTHING
                """))
                conn.commit()
                logger.info("✅ File registry initialized")
        else:
            logger.info("✓ File registry already exists")
    
    except Exception as e:
        logger.warning(f"⚠️  Could not initialize file_registry: {e}")


def main():
    """Main initialization workflow."""
    logger.info("=" * 70)
    logger.info("🚀 DATABASE INITIALIZATION SCRIPT")
    logger.info("=" * 70)
    
    # Step 1: Wait for database
    if not wait_for_database():
        logger.error("Failed to connect to database. Exiting.")
        sys.exit(1)
    
    # Step 2: Check if data already exists
    if check_if_data_exists():
        logger.info("Database already populated. Skipping data load.")
        initialize_file_registry()
        logger.info("✅ Initialization complete (using existing data)")
        return True
    
    # Step 3: Load CSV data
    if not load_csv_data():
        logger.error("Failed to load CSV data. Exiting.")
        sys.exit(1)
    
    # Step 4: Initialize file registry
    initialize_file_registry()
    
    logger.info("=" * 70)
    logger.info("✅ DATABASE INITIALIZATION COMPLETE")
    logger.info("=" * 70)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
