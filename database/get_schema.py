"""
Dynamic Schema Inspection & Discovery
Provides schema metadata for ANY table in the PostgreSQL database
"""

import os
import pandas as pd
import logging
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv
from typing import Dict, List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Database Connection ---
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")
db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def get_all_tables() -> List[str]:
    """
    Get list of all table names in the database.
    
    Returns: Sorted list of table names
    """
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return sorted(tables)
    except Exception as e:
        logger.error(f"Failed to fetch tables: {e}")
        return []


def get_table_schema(table_name: str) -> Dict:
    """
    Get complete schema information for a specific table.
    
    Returns: {
        'table_name': str,
        'columns': [{'name': str, 'type': str, 'nullable': bool}, ...],
        'row_count': int,
        'sample_data': [(row1), (row2), (row3)],
        'success': bool,
        'error': str (if failed)
    }
    """
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        # Get columns
        columns = inspector.get_columns(table_name)
        column_info = [
            {
                'name': col['name'],
                'type': str(col['type']).split('(')[0],  # Remove size info (e.g., VARCHAR(100) -> VARCHAR)
                'nullable': col['nullable']
            }
            for col in columns
        ]
        
        # Get row count
        with engine.connect() as conn:
            result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            row_count = result.scalar()
        
        # Get sample data (first 3 rows)
        sample_df = pd.read_sql_query(f'SELECT * FROM "{table_name}" LIMIT 3', engine)
        sample_data = [tuple(row) for row in sample_df.itertuples(index=False)]
        
        return {
            'table_name': table_name,
            'columns': column_info,
            'row_count': row_count,
            'sample_data': sample_data,
            'column_count': len(column_info),
            'success': True,
            'error': None
        }
    
    except Exception as e:
        logger.error(f"Failed to fetch schema for '{table_name}': {e}")
        return {
            'table_name': table_name,
            'columns': [],
            'row_count': 0,
            'sample_data': [],
            'column_count': 0,
            'success': False,
            'error': str(e)
        }


def format_column_type(col_type: str) -> str:
    """
    Format column type for display with color coding hints.
    
    Returns: Formatted type string with visual category
    """
    col_type_lower = col_type.lower()
    
    if any(t in col_type_lower for t in ['int', 'bigint', 'smallint', 'numeric', 'float', 'double', 'decimal']):
        return f"{col_type} (🔢 Numeric)"
    elif any(t in col_type_lower for t in ['varchar', 'text', 'char', 'string']):
        return f"{col_type} (📝 Text)"
    elif any(t in col_type_lower for t in ['date', 'time', 'timestamp']):
        return f"{col_type} (📅 Date)"
    elif any(t in col_type_lower for t in ['bool']):
        return f"{col_type} (✓ Boolean)"
    else:
        return f"{col_type} (❓ Other)"


def get_column_statistics(table_name: str, column_name: str) -> Dict:
    """
    Get basic statistics for a column (null count, unique values, etc.)
    
    Returns: {
        'null_count': int,
        'unique_count': int,
        'null_percentage': float
    }
    """
    try:
        engine = create_engine(db_url)
        query = f"""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN "{column_name}" IS NULL THEN 1 END) as null_count,
            COUNT(DISTINCT "{column_name}") as unique_count
        FROM "{table_name}"
        """
        result = pd.read_sql_query(query, engine).iloc[0]
        
        null_pct = (result['null_count'] / result['total'] * 100) if result['total'] > 0 else 0
        
        return {
            'null_count': int(result['null_count']),
            'unique_count': int(result['unique_count']),
            'null_percentage': round(null_pct, 1)
        }
    except Exception as e:
        logger.error(f"Failed to get statistics for '{table_name}'.'{column_name}': {e}")
        return {'null_count': 0, 'unique_count': 0, 'null_percentage': 0}


# --- Example Usage (for testing) ---
if __name__ == "__main__":
    print("🔍 Available Tables:")
    tables = get_all_tables()
    for table in tables:
        print(f"  - {table}")
    
    if tables:
        print(f"\n📋 Schema for '{tables[0]}':")
        schema = get_table_schema(tables[0])
        print(f"  Rows: {schema['row_count']:,}")
        print(f"  Columns: {schema['column_count']}")
        print(f"  Columns:")
        for col in schema['columns'][:5]:
            print(f"    - {col['name']}: {col['type']} (nullable: {col['nullable']})")
