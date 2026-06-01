"""
Automatic Foreign Key Relationship Detection
Heuristics-based detection for common join patterns.
"""

from typing import List, Dict

COMMON_FK_PATTERNS = {
    'id': ['id'],
    'customer_id': ['customer_id', 'cust_id', 'customerid'],
    'product_id': ['product_id', 'prod_id', 'productid'],
    'order_id': ['order_id', 'orderid'],
    'user_id': ['user_id', 'userid'],
    'store_id': ['store_id', 'storeid'],
    'region_id': ['region_id', 'regionid'],
    'category_id': ['category_id', 'categoryid'],
}

def detect_relationships(sheets_info: List[Dict]) -> List[Dict]:
    """
    Auto-detect foreign key relationships between sheets.
    
    Returns: [
        {
            'from_sheet': 'sales',
            'from_column': 'customer_id',
            'to_sheet': 'customers',
            'to_column': 'id',
            'confidence': 'HIGH',
            'reason': 'Exact match: sales.customer_id → customers.id'
        },
        ...
    ]
    
    NOTE: Sheet names are stored as-is (with special characters and spaces).
    The table_resolver will sanitize them when matching to actual PostgreSQL tables.
    This preserves original sheet names for UI display while enabling accurate table lookup.
    """
    relationships = []
    sheet_columns = {sheet['name']: sheet['columns'] for sheet in sheets_info}
    sheet_names_lower = {name.lower(): name for name in sheet_columns.keys()}
    
    for sheet_name, columns in sheet_columns.items():
        for col in columns:
            col_lower = col.lower()
            
            # Check if column looks like a foreign key
            for fk_pattern, variants in COMMON_FK_PATTERNS.items():
                if col_lower in variants or col_lower.endswith(fk_pattern):
                    
                    # Extract table name from FK column
                    for variant in variants:
                        if variant in col_lower:
                            # Extract base table name
                            table_base = col_lower.replace(variant, '').rstrip('_')
                            
                            # Look for matching sheet
                            for sheet_lower, sheet_original in sheet_names_lower.items():
                                if table_base in sheet_lower or sheet_lower.startswith(table_base):  # FIXED: was sheet_base
                                    # Check if target sheet has 'id' or '{table}_id'
                                    target_columns = sheet_columns[sheet_original]
                                    target_col_lower = [c.lower() for c in target_columns]
                                    
                                    if 'id' in target_col_lower:
                                        relationships.append({
                                            'from_sheet': sheet_name,  # ← KEEP original sheet name with special chars
                                            'from_column': col,
                                            'to_sheet': sheet_original,  # ← KEEP original sheet name with special chars
                                            'to_column': 'id',
                                            'confidence': 'HIGH',
                                            'reason': f'Detected pattern: {col} → id'
                                        })
                                        break
                            break
    
    # Deduplicate
    seen = set()
    unique_relationships = []
    for rel in relationships:
        key = (rel['from_sheet'], rel['from_column'], rel['to_sheet'], rel['to_column'])
        if key not in seen:
            unique_relationships.append(rel)
            seen.add(key)
    
    return unique_relationships
