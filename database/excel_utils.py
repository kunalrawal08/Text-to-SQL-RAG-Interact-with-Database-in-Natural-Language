"""
Multi-Sheet Excel Detection & Parsing
Detects all sheets in Excel files without loading data into memory.
"""

import pandas as pd
from typing import Dict, List

def detect_excel_sheets(uploaded_file) -> Dict:
    """
    Detect all sheets in an Excel file with metadata.
    
    Returns:
    {
        'filename': 'sales_data.xlsx',
        'sheet_count': 3,
        'sheets': [
            {
                'name': 'Sheet1',
                'columns': ['sale_id', 'customer_id', 'amount'],
                'row_count': 150,
                'data_types': {'sale_id': 'INTEGER', 'customer_id': 'INTEGER', 'amount': 'DECIMAL'}
            },
            ...
        ]
    }
    """
    try:
        # Read all sheet names
        xl_file = pd.ExcelFile(uploaded_file)
        sheet_names = xl_file.sheet_names
        
        sheets_info = []
        
        for sheet_name in sheet_names:
            try:
                # Read only first row to get columns and infer types
                df_sample = pd.read_excel(uploaded_file, sheet_name=sheet_name, nrows=100)
                
                if df_sample.empty:
                    continue
                
                # Get column info
                columns = list(df_sample.columns)
                
                # Infer data types
                data_types = {}
                for col in columns:
                    dtype = str(df_sample[col].dtype)
                    if 'int' in dtype:
                        data_types[col] = 'INTEGER'
                    elif 'float' in dtype:
                        data_types[col] = 'DECIMAL'
                    elif 'object' in dtype:
                        data_types[col] = 'VARCHAR'
                    elif 'datetime' in dtype:
                        data_types[col] = 'DATE'
                    else:
                        data_types[col] = 'VARCHAR'
                
                sheets_info.append({
                    'name': sheet_name,
                    'columns': columns,
                    'row_count': len(df_sample),
                    'data_types': data_types
                })
            except Exception as e:
                sheets_info.append({
                    'name': sheet_name,
                    'columns': [],
                    'row_count': 0,
                    'error': str(e)
                })
        
        return {
            'filename': uploaded_file.name,
            'sheet_count': len(sheet_names),
            'sheets': sheets_info,
            'success': True
        }
    
    except Exception as e:
        return {
            'filename': uploaded_file.name if hasattr(uploaded_file, 'name') else 'unknown',
            'sheet_count': 0,
            'sheets': [],
            'success': False,
            'error': str(e)
        }


def is_multi_sheet_excel(uploaded_file) -> bool:
    """Check if uploaded file is Excel with multiple sheets."""
    if not uploaded_file.name.endswith('.xlsx'):
        return False
    
    try:
        xl_file = pd.ExcelFile(uploaded_file)
        return len(xl_file.sheet_names) > 1
    except:
        return False
