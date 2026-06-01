"""
Database Table Name Sanitization
Ensures valid PostgreSQL identifiers from user uploads.
"""

import re
import hashlib

def sanitize_table_name(workbook_name: str, sheet_name: str) -> str:
    """
    Convert sheet name to a valid PostgreSQL table name.
    PERMANENT FIX: Only uses sheet_name, completely ignores workbook_name.
    
    Examples:
    - "Cleaned Sales Data" → "cleaned_sales_data"
    - "Customer (2024)" → "customer_2024"
    - "Report - Q1" → "report_q1"
    """
    
    def normalize(s: str) -> str:
        """Normalize string to valid PostgreSQL identifier."""
        # Lowercase
        s = s.lower()
        # Replace spaces with underscores
        s = s.replace(' ', '_')
        # Remove special characters, keep only alphanumeric and underscore
        s = re.sub(r'[^a-z0-9_]', '', s)
        # Remove leading/trailing underscores
        s = s.strip('_')
        # Remove multiple consecutive underscores
        s = re.sub(r'_+', '_', s)
        return s
    
    # PERMANENT FIX: Only normalize sheet_name, ignore workbook_name completely
    table_name = normalize(sheet_name)
    
    # Handle edge case: empty string after normalization
    if not table_name:
        table_name = "imported_data"
    
    # PostgreSQL table name limit is 63 characters
    if len(table_name) > 63:
        # Keep first 55 chars + hash of full name for uniqueness
        hash_suffix = hashlib.md5(table_name.encode()).hexdigest()[:7]
        table_name = table_name[:55] + "_" + hash_suffix
    
    return table_name


def create_sheet_to_table_mapping(workbook_name: str, sheet_names: list) -> dict:
    """
    Create mapping from original sheet names to sanitized table names.
    
    Returns: {
        "Sheet1": "q1_metrics_sheet1",
        "Sales Data": "q1_metrics_sales_data",
        ...
    }
    """
    mapping = {}
    for sheet_name in sheet_names:
        table_name = sanitize_table_name(workbook_name, sheet_name)
        mapping[sheet_name] = table_name
    
    return mapping
