"""
Dynamic Table Name Resolution
Resolves sheet names to actual PostgreSQL table names independently of session_state.
This survives page refreshes and ensures LLM gets correct table names.

PERMANENT FIX for table name mismatch issue.
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def resolve_relationship_sheet_names(relationships: List[Dict]) -> List[Dict]:
    """
    Dynamically resolve sheet names in relationships to actual PostgreSQL table names.
    
    This is the PERMANENT FIX for the table name mismatch issue.
    Works even if session_state.sheet_to_table_mapping is missing/lost.
    
    Args:
        relationships: List of relationships with sheet names
        
    Returns:
        List of relationships with actual PostgreSQL table names
    """
    from database.get_schema import get_all_tables
    
    if not relationships:
        logger.debug("No relationships to resolve")
        return []
    
    # Get all actual tables in PostgreSQL
    try:
        all_tables = get_all_tables()
    except Exception as e:
        logger.error(f"Failed to fetch table list from PostgreSQL: {e}")
        return relationships
    
    if not all_tables:
        logger.warning("Could not fetch table list from PostgreSQL")
        return relationships
    
    resolved_relationships = []
    
    for rel in relationships:
        from_table = find_matching_table(rel.get('from_sheet', ''), all_tables)
        to_table = find_matching_table(rel.get('to_sheet', ''), all_tables)
        
        if from_table and to_table:
            resolved_rel = {
                'from_sheet': from_table,  # Now actual PostgreSQL table name
                'from_column': rel.get('from_column', ''),
                'to_sheet': to_table,      # Now actual PostgreSQL table name
                'to_column': rel.get('to_column', ''),
                'confidence': rel.get('confidence', 'RESOLVED'),
                'reason': 'Dynamically resolved from actual PostgreSQL schema'
            }
            resolved_relationships.append(resolved_rel)
            logger.info(f"Resolved: {rel.get('from_sheet')} → {from_table}, {rel.get('to_sheet')} → {to_table}")
        else:
            logger.warning(
                f"Could not fully resolve relationship: {rel.get('from_sheet')} ↔ {rel.get('to_sheet')} "
                f"(from_table={from_table}, to_table={to_table})"
            )
    
    logger.info(f"Resolved {len(resolved_relationships)}/{len(relationships)} relationships")
    return resolved_relationships


def find_matching_table(sheet_name_or_partial: str, available_tables: List[str]) -> Optional[str]:
    """
    Find the actual PostgreSQL table that corresponds to a sheet name.
    Handles cases where table names include workbook prefix or have been sanitized.
    
    Matching strategies (in order of priority):
    1. Exact match after normalization (case-insensitive, spaces/hyphens to underscores)
    2. Table name ends with the sheet name (common with workbook prefix)
    3. Fuzzy match - table name contains the sheet name
    4. Sheet name is a substring of table name
    
    Examples:
        - "Sales" → "q1_metrics_sales" or "import_sales"
        - "Final Sheet" → "q1_metrics_final_sheet"
        - "customers" → "import_customers"
    
    Args:
        sheet_name_or_partial: Original sheet name or partial name to match
        available_tables: List of actual PostgreSQL table names
        
    Returns:
        Matched table name, or None if no match found
    """
    import re
    
    if not sheet_name_or_partial:
        logger.debug("Empty sheet name provided to find_matching_table")
        return None
    
    if not available_tables:
        logger.warning("No available tables provided to find_matching_table")
        return None
    
    # Normalize the input sheet name for comparison (MUST MATCH sanitizer.py logic)
    normalized_sheet = (
        sheet_name_or_partial
        .lower()
        .strip()
        .replace(' ', '_')
        .replace('-', '_')
        .replace('__', '_')  # Clean up double underscores
    )
    # CRITICAL: Remove special characters (asterisks, brackets, etc) to match sanitize_table_name()
    normalized_sheet = re.sub(r'[^a-z0-9_]', '', normalized_sheet)
    # Clean up any leading underscores
    normalized_sheet = normalized_sheet.lstrip('_')
    # Final cleanup of multiple underscores
    normalized_sheet = re.sub(r'_+', '_', normalized_sheet)
    
    logger.debug(f"Matching '{sheet_name_or_partial}' (normalized: '{normalized_sheet}') against {len(available_tables)} tables")
    
    # Strategy 1: Exact match (after normalization)
    for table in available_tables:
        if table.lower() == normalized_sheet:
            logger.debug(f"Strategy 1 (exact match): Found {table}")
            return table
    
    # Strategy 2: Table ends with the sheet name (common with workbook prefix)
    # e.g., "q1_metrics_sales_data" ends with "sales_data"
    for table in available_tables:
        table_lower = table.lower()
        if '_' in table_lower:
            # Check if table ends with the normalized sheet name
            if table_lower.endswith(normalized_sheet):
                logger.debug(f"Strategy 2 (ends with): Found {table}")
                return table
            # Check if table ends with any suffix of the sheet name
            sheet_parts = normalized_sheet.split('_')
            for i in range(len(sheet_parts)):
                suffix = '_'.join(sheet_parts[i:])
                if table_lower.endswith(suffix) and len(suffix) > 2:  # Avoid single-char matches
                    logger.debug(f"Strategy 2 (ends with suffix '{suffix}'): Found {table}")
                    return table
    
    # Strategy 3: Fuzzy match - table name contains the sheet name
    for table in available_tables:
        if normalized_sheet in table.lower():
            logger.debug(f"Strategy 3 (contains): Found {table}")
            return table
    
    # Strategy 4: Sheet name is a substring of table name (reversed)
    for table in available_tables:
        if table.lower() in normalized_sheet:
            logger.debug(f"Strategy 4 (is substring of): Found {table}")
            return table
    
    logger.debug(f"No matching table found for sheet: {sheet_name_or_partial} (normalized: {normalized_sheet})")
    return None
