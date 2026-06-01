"""
Universal CSV Ingestion with Data Validation
Enforces a "Data Contract" for reliable Text-to-SQL operations
"""

import os
import pandas as pd
import logging
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv
from typing import Tuple, List, Dict

# Configure logging
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


def validate_csv(df: pd.DataFrame, filename: str) -> Tuple[bool, List[str], Dict[str, str]]:
    """
    Validate CSV against Data Contract (5 mandatory criteria).
    
    Returns: (is_valid: bool, errors: list[str], warnings: dict[str, str])
    - is_valid: True if all critical checks pass
    - errors: List of blocking issues (prevents ingestion)
    - warnings: Dict of non-blocking issues (allow with user confirmation)
    """
    errors = []
    warnings = {}
    
    # ===== CHECK 1: File Format =====
    valid_extensions = ['.csv', '.xlsx', '.xls']
    has_valid_ext = any(filename.lower().endswith(ext) for ext in valid_extensions)
    if not has_valid_ext:
        errors.append(f"Unsupported file format: {filename}. Use .csv or .xlsx")
    
    # ===== CHECK 2: Empty File =====
    if df.empty or len(df) < 1:
        errors.append("File is empty or has no data rows.")
    if len(df.columns) < 1:
        errors.append("File has no headers/columns.")
    
    # Stop here if critical errors
    if errors:
        return False, errors, warnings
    
    # ===== CHECK 3: Header Quality =====
    bad_headers = []
    for col in df.columns:
        # Check for unnamed columns
        if "Unnamed" in str(col):
            bad_headers.append(f"Unnamed column detected: {col}")
        
        # Check for generic names (single char or vague)
        generic_names = ['data', 'col', 'value', 'x', 'y', 'a', 'b', 'col1', 'col2', 'column']
        if col.lower() in generic_names:
            bad_headers.append(f"Generic header name: '{col}' (use descriptive names like 'customer_id', 'sales_amount')")
        
        # Check header length
        if len(str(col)) > 50:
            bad_headers.append(f"Header too long: '{col}' (keep under 50 characters)")
    
    if bad_headers:
        errors.extend(bad_headers)
    
    # ===== CHECK 4: Data Type Consistency =====
    type_issues = []
    for col in df.columns:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue  # Skip all-null columns
        
        # Check for mixed types
        types = non_null.apply(type).value_counts()
        if len(types) > 1:
            type_ratios = types / len(non_null)
            # If no single type dominates (>70%), flag it
            if type_ratios.iloc[0] < 0.7:
                type_list = [str(t.__name__) for t in types.index]
                type_issues.append(f"Column '{col}' has mixed data types: {', '.join(type_list)}")
        
        # Check for common numeric column contamination
        numeric_keywords = ['price', 'amount', 'total', 'count', 'qty', 'quantity', 'sales', 'revenue']
        if any(kw in col.lower() for kw in numeric_keywords):
            try:
                pd.to_numeric(non_null, errors='coerce')
                # Check if conversion lost >20% of values
                converted = pd.to_numeric(non_null, errors='coerce')
                lost_ratio = converted.isna().sum() / len(non_null)
                if lost_ratio > 0.2:
                    type_issues.append(f"Column '{col}' looks numeric but {lost_ratio*100:.0f}% values are non-numeric")
            except Exception:
                type_issues.append(f"Column '{col}' appears numeric but contains non-numeric values")
    
    if type_issues:
        warnings['data_types'] = "; ".join(type_issues)
    
    # ===== CHECK 5: Date Format Consistency =====
    date_keywords = ['date', 'time', 'datetime', 'created_at', 'updated_at', 'date_of_compedition', 
                     'timestamp', 'day', 'month', 'year']
    date_columns = [col for col in df.columns if any(kw in col.lower() for kw in date_keywords)]
    
    date_issues = []
    for col in date_columns:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue
        
        try:
            parsed = pd.to_datetime(non_null, errors='coerce')
            # Check if parsing was successful (not too many NaT)
            nat_ratio = parsed.isna().sum() / len(non_null)
            if nat_ratio > 0.3:
                date_issues.append(f"Column '{col}': {nat_ratio*100:.0f}% dates couldn't be parsed")
            else:
                # Check if mostly ISO format (YYYY-MM-DD)
                iso_count = sum(1 for v in non_null if pd.notna(v) and str(v).count('-') >= 2)
                iso_ratio = iso_count / len(non_null)
                if iso_ratio < 0.7:
                    date_issues.append(f"Column '{col}' may not be in ISO 8601 format (YYYY-MM-DD)")
        except Exception:
            date_issues.append(f"Column '{col}' has unparseable dates")
    
    if date_issues:
        warnings['dates'] = "; ".join(date_issues)
    
    # ===== CHECK 6: Minimum Row Count =====
    MIN_ROWS = 5  # Lower threshold for flexibility
    if len(df) < MIN_ROWS:
        warnings['rows'] = f"Only {len(df)} rows found. Recommend ≥{MIN_ROWS} for meaningful analysis."
    
    # ===== CHECK 7: Column Count =====
    if len(df.columns) > 100:
        warnings['columns'] = f"{len(df.columns)} columns found. Consider narrowing schema for better LLM focus."
    elif len(df.columns) < 2:
        errors.append("CSV must have at least 2 columns.")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names:
    - Convert to lowercase
    - Replace spaces with underscores
    - Remove special characters
    """
    df.columns = (
        df.columns
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('[^a-z0-9_]', '', regex=True)
    )
    return df


def ingest_csv_to_postgres(
    df: pd.DataFrame, 
    table_name: str, 
    if_exists: str = 'append',
    original_filename: str = None,
    sheet_name: str = 'Main'
) -> Tuple[bool, str, int]:
    """
    Ingest validated DataFrame into PostgreSQL with registry tracking.
    
    Args:
        df: DataFrame to ingest
        table_name: Target table name (will be created if not exists)
        if_exists: 'replace', 'append', or 'fail'
        original_filename: Original filename for registry (e.g., 'Sales.xlsx')
        sheet_name: Sheet name for registry (default 'Main')
    
    Returns: (success: bool, message: str, rows_ingested: int)
    """
    try:
        # Normalize columns
        df = normalize_columns(df)
        
        # Connect to database
        logger.info("Connecting to PostgreSQL...")
        engine = create_engine(db_url)
        
        # Test connection
        with engine.connect() as conn:
            logger.info("✓ Database connection successful")
        
        # Ingest data
        logger.info(f"Ingesting {len(df)} rows into table '{table_name}'...")
        df.to_sql(
            table_name,
            engine,
            if_exists=if_exists,
            index=False,
            method='multi',
            chunksize=5000
        )
        
        logger.info(f"✅ Successfully ingested {len(df)} rows into '{table_name}'")
        
        # Register this ingestion in the file_registry (if metadata provided)
        if original_filename:
            try:
                from database.get_schema import init_file_registry
                init_file_registry(engine)
                
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO file_registry (original_filename, sheet_name, db_table_name)
                        VALUES (:filename, :sheet, :table)
                        ON CONFLICT (db_table_name) DO UPDATE
                        SET original_filename = :filename, sheet_name = :sheet
                    """), {
                        'filename': original_filename,
                        'sheet': sheet_name,
                        'table': table_name
                    })
                logger.info(f"✓ Registry updated: {original_filename} - {sheet_name} → {table_name}")
            except Exception as e:
                logger.warning(f"Registry update failed (non-critical): {e}")
        
        return True, f"✅ Ingested {len(df):,} rows into table '{table_name}'", len(df)
    
    except Exception as e:
        error_msg = f"Ingestion failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, 0


def register_file_ingestion(original_filename: str, sheet_name: str, db_table_name: str) -> bool:
    """
    Standalone function to register a file ingestion in the registry.
    Useful for post-ingestion registration or batch operations.
    """
    try:
        from database.get_schema import init_file_registry
        engine = create_engine(db_url)
        init_file_registry(engine)
        
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO file_registry (original_filename, sheet_name, db_table_name)
                VALUES (:filename, :sheet, :table)
                ON CONFLICT (db_table_name) DO UPDATE
                SET original_filename = :filename, sheet_name = :sheet
            """), {
                'filename': original_filename,
                'sheet': sheet_name,
                'table': db_table_name
            })
        logger.info(f"✓ Registered: {original_filename} - {sheet_name} → {db_table_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to register file: {e}")
        return False


def get_existing_tables() -> List[str]:
    """Get list of all tables in the database."""
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return sorted(tables)
    except Exception as e:
        logger.error(f"Failed to fetch tables: {e}")
        return []


def table_exists(table_name: str) -> bool:
    """Check if table exists in database."""
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception as e:
        logger.error(f"Failed to check table: {e}")
        return False


# --- Example Usage (for testing) ---
if __name__ == "__main__":
    # Test validation with a sample CSV
    sample_df = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Age': [25, 30, 28],
        'Email': ['alice@example.com', 'bob@example.com', 'charlie@example.com']
    })
    
    is_valid, errors, warnings = validate_csv(sample_df, "test.csv")
    print(f"Valid: {is_valid}")
    print(f"Errors: {errors}")
    print(f"Warnings: {warnings}")
    
    if is_valid:
        success, msg, rows = ingest_csv_to_postgres(sample_df, "test_table", if_exists='replace')
        print(f"Success: {success}, Message: {msg}, Rows: {rows}")
