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
# Check for Docker DB_URL first (enterprise deployment)
# Fall back to constructing from individual env vars for local development
db_url = os.getenv(
    "DB_URL",
    f"postgresql://{os.getenv('DB_USER', 'POWERLIFTER_KUNAL')}:{os.getenv('DB_PASSWORD', 'Kunal123')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '2003')}/{os.getenv('DB_NAME', 'powerlifting_db')}"
)


# ============================================================================
# METADATA REGISTRY: Permanent file-to-table mapping (Step 1 of FastAPI migration)
# ============================================================================

def init_file_registry(engine=None):
    """
    Initialize the file_registry table if it doesn't exist.
    This persists the relationship between original files and database tables.
    """
    if engine is None:
        engine = create_engine(db_url)
    
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS file_registry (
                    id SERIAL PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    db_table_name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        logger.info("✓ File registry initialized")
    except Exception as e:
        logger.error(f"Failed to initialize file registry: {e}")


def get_registered_tables_map() -> Dict[str, str]:
    """
    Fetch registered tables and return user-friendly mapping.
    Returns: {"Sales.xlsx - Q1": "sales_q1", "legacy_table": "legacy_table"}
    """
    try:
        engine = create_engine(db_url)
        table_map = {}
        
        init_file_registry(engine)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT original_filename, sheet_name, db_table_name
                FROM file_registry
                ORDER BY created_at DESC
            """))
            
            for row in result:
                original_filename, sheet_name, db_table_name = row
                display_name = f"{original_filename} - {sheet_name}"
                table_map[display_name] = db_table_name
        
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        
        user_tables = [
            t for t in all_tables 
            if not t.startswith('_') 
            and t != 'file_registry'
            and 'chroma' not in t.lower()
        ]
        
        registered_table_names = set(table_map.values())
        for table_name in user_tables:
            if table_name not in registered_table_names:
                table_map[table_name] = table_name
        
        return table_map
    
    except Exception as e:
        logger.error(f"Failed to fetch registered tables: {e}")
        try:
            engine = create_engine(db_url)
            inspector = inspect(engine)
            all_tables = inspector.get_table_names()
            user_tables = [t for t in all_tables if not t.startswith('_') and 'chroma' not in t.lower()]
            return {t: t for t in user_tables}
        except:
            return {}


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


# ============================================================================
# PERMANENT FIX: File Registry Cleanup Functions
# ============================================================================

def delete_from_file_registry(db_table_name: str) -> bool:
    """
    PERMANENT FIX: Remove a table from file_registry when it's deleted.
    This prevents "Error loading schema" for orphaned registry entries.
    
    Args:
        db_table_name: Name of the table to remove from registry
    
    Returns: True if successful, False otherwise
    """
    try:
        engine = create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM file_registry
                WHERE db_table_name = :table_name
            """), {"table_name": db_table_name})
        logger.info(f"✓ Removed '{db_table_name}' from file_registry")
        return True
    except Exception as e:
        logger.error(f"Failed to remove '{db_table_name}' from file_registry: {e}")
        return False


def cleanup_orphaned_registry_entries() -> Tuple[int, List[str]]:
    """
    PERMANENT FIX: Remove file_registry entries for tables that no longer exist.
    Prevents "Error loading schema" errors from stale registry entries.
    
    Returns: (count_deleted, list_of_deleted_tables)
    """
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        
        # Get all entries from file_registry
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT db_table_name FROM file_registry
            """))
            registry_tables = [row[0] for row in result]
        
        # Find orphaned entries (in registry but not in database)
        orphaned = [t for t in registry_tables if t not in existing_tables]
        
        if orphaned:
            with engine.begin() as conn:
                for table_name in orphaned:
                    conn.execute(text("""
                        DELETE FROM file_registry WHERE db_table_name = :table_name
                    """), {"table_name": table_name})
            
            logger.info(f"✓ Cleaned up {len(orphaned)} orphaned registry entries: {orphaned}")
            return len(orphaned), orphaned
        
        return 0, []
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned registry entries: {e}")
        return 0, []


def identify_old_convention_tables() -> Tuple[List[str], int]:
    """
    PERMANENT FIX: Find tables with old naming convention (filename_sheetname).
    These were created before the sanitizer.py fix and should be cleaned up.
    
    Old pattern: Contains double underscores (__) or matches filename_sheet patterns
    New pattern: Only sheet name, normalized
    
    Returns: (list_of_old_tables, count)
    """
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        
        # Old convention detection: double underscores (__) indicate filename + sheet combination
        old_convention = [
            t for t in all_tables
            if '__' in t and t != 'file_registry' and not t.startswith('_') and 'chroma' not in t.lower()
        ]
        
        logger.info(f"✓ Found {len(old_convention)} tables with old naming convention")
        return old_convention, len(old_convention)
    except Exception as e:
        logger.error(f"Failed to identify old convention tables: {e}")
        return [], 0


def cleanup_old_convention_tables() -> Tuple[int, List[str]]:
    """
    PERMANENT FIX: Drop all tables with old naming convention.
    These were created before the sanitizer.py fix and use the old filename_sheetname pattern.
    
    Returns: (count_dropped, list_of_dropped_tables)
    """
    try:
        old_tables, _ = identify_old_convention_tables()
        
        if old_tables:
            engine = create_engine(db_url)
            dropped = []
            
            with engine.begin() as conn:
                for table_name in old_tables:
                    try:
                        conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
                        # Also remove from file_registry if present
                        conn.execute(text("""
                            DELETE FROM file_registry WHERE db_table_name = :table_name
                        """), {"table_name": table_name})
                        dropped.append(table_name)
                        logger.info(f"  ✓ Dropped old-convention table: {table_name}")
                    except Exception as drop_err:
                        logger.error(f"  ✗ Failed to drop {table_name}: {drop_err}")
            
            logger.info(f"✓ Cleanup complete: {len(dropped)} old-convention tables removed")
            return len(dropped), dropped
        
        logger.info("✓ No old-convention tables found")
        return 0, []
    except Exception as e:
        logger.error(f"Failed to cleanup old convention tables: {e}")
        return 0, []


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
