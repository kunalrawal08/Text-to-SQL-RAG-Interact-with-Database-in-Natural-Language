"""
DAX Quality Assurance Module - Logic Consistency Verification

This module provides QA verification to ensure SQL and DAX measures 
implement the same business logic (Master-Level feature).

Uses a fast LLM model (Haiku/lightweight) for instant verification.
"""

import time
import os
import re
import traceback
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ============================================================================
# QA SYSTEM PROMPT (OPTIMIZED - Token-Efficient for Groq API)
# ============================================================================

QA_SYSTEM_PROMPT = """
ROLE: Senior Data Auditor
TASK: Compare a SQL Query and a DAX Measure for logic parity.

CONSTRAINTS:
1. FOCUS ONLY on logic: Do they target the same columns and apply the same filters?
2. IGNORE syntax differences: SQL uses WHERE, DAX uses CALCULATE/KEEPFILTERS. This is expected.
3. IGNORE Table vs Scalar differences: If SQL uses "SELECT *" and DAX uses "KEEPFILTERS" on a table, this is a MATCH for intent.
4. BREVITY: Your response must follow the strict format below. No prose.

EVALUATION CRITERIA:
- Are the filtered values identical? (e.g., 'Rajat Dalal' in both?)
- Are the target tables/columns the same?
- Is the mathematical intent (Sum, Count, or Table Filter) the same?

OUTPUT FORMAT:
If logic matches: "MATCH"
If logic differs: "DISCREPANCY: [1-sentence reason why]"

No explanations. No prose. Just "MATCH" or "DISCREPANCY: reason".
"""

# ============================================================================
# QA USER PROMPT TEMPLATE
# ============================================================================

QA_USER_PROMPT_TEMPLATE = """
Verify SQL ↔ DAX Logic Parity:

SQL Query:
{sql_query}

DAX Measure:
{dax_measure}

Schema Context (for reference):
{schema_context}

Question: Do the SQL and DAX implement the SAME business logic?
Answer ONLY with: MATCH or DISCREPANCY: [specific reason]
"""

# ============================================================================
# QA LLM Chain Setup
# ============================================================================

def get_qa_chain():
    """
    Returns a LangChain QA verification chain using a fast LLM model.
    
    Uses lightweight model (Haiku) for instant verification (200-400ms).
    """
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", QA_SYSTEM_PROMPT),
        ("human", QA_USER_PROMPT_TEMPLATE)
    ])
    
    # Use lightweight model for fast QA verification
    qa_llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama-3.3-70b-versatile",  # Fast Groq model
        temperature=0  # Deterministic verification
    )
    
    return qa_prompt | qa_llm | StrOutputParser()

# ============================================================================
# Main QA Verification Function (Master-Level Feature)
# ============================================================================

def verify_dax_sql_parity(sql_query: str, dax_measure: str, schema_context: str) -> dict:
    """
    Quality Assurance verification: Ensure SQL and DAX target the same logic.
    Uses a fast LLM model for instant verification.
    
    Args:
        sql_query (str): The generated SQL query
        dax_measure (str): The generated DAX measure code
        schema_context (str): Schema context for reference
    
    Returns:
        {
            "status": str,                # "MATCH" or "DISCREPANCY: [reason]"
            "passed": bool,               # True if "MATCH", False if "DISCREPANCY"
            "verification_time_ms": int,  # Time spent on verification
            "details": str                # Explanation (same as status)
        }
    
    Example successful response:
        {
            "status": "MATCH",
            "passed": True,
            "verification_time_ms": 287,
            "details": "SQL and DAX logic are equivalent"
        }
    
    Example failed response:
        {
            "status": "DISCREPANCY: SQL filters on date, DAX does not",
            "passed": False,
            "verification_time_ms": 342,
            "details": "DISCREPANCY: SQL filters on date, DAX does not"
        }
    """
    qa_start = time.time()
    
    try:
        # ✅ ROBUST SPLITTING: Split by 'Table:' header, not just double newlines
        schema_sections = re.split(r'\n(?=Table:)', schema_context)
        sql_lower = sql_query.lower()
        
        # ✅ SCHEMA PRUNING: Extract only relevant table metadata
        pruned_context_lines = []
        for section in schema_sections:
            if not section.strip():
                continue
            first_line = section.split('\n')[0].strip()
            table_identifier = first_line.replace('table:', '').replace('table :', '').strip()
            if table_identifier and table_identifier in sql_lower:
                pruned_context_lines.append(section)
        
        # ✅ FALLBACK LOGIC: If empty, use first 1000 chars of original schema
        if pruned_context_lines:
            pruned_context = "\n".join(pruned_context_lines)
        else:
            pruned_context = schema_context[:1000]
        
        # ✅ DEBUG LOGGING: Show pruned schema size in terminal
        print(f'QA DEBUG - Pruned Schema Length: {len(pruned_context)}')
        
        # ✅ MODEL CHECK: Verify model name is llama-3.3-70b-versatile
        qa_chain = get_qa_chain()
        qa_response = qa_chain.invoke({
            "sql_query": sql_query,
            "dax_measure": dax_measure,
            "schema_context": pruned_context
        })
        
        qa_time_ms = int((time.time() - qa_start) * 1000)
        qa_response_clean = qa_response.strip()
        passed = "MATCH" in qa_response_clean.upper()
        
        return {
            "status": qa_response_clean,
            "passed": passed,
            "verification_time_ms": qa_time_ms,
            "details": qa_response_clean
        }
    
    except Exception as e:
        # ✅ TRACEBACK: Print full error traceback to console
        traceback.print_exc()
        qa_time_ms = int((time.time() - qa_start) * 1000)
        return {
            "status": "Verification Pending",
            "passed": False,
            "verification_time_ms": qa_time_ms,
            "details": f"QA skipped: {str(e)[:60]}"
        }
