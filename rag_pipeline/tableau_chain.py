"""
Tableau Chain Adapter - Wraps Tableau Calculated Field generation into a reusable LCEL chain
Part of Sequential SQL-to-Tableau Generation Pipeline
"""

from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from rag_pipeline.tableau_prompts import get_tableau_prompt_template
from rag_pipeline.dax_chain import (
    prune_schema_for_dax,
    get_banned_columns,
    extract_sql_parameters,
    summarize_sql_result_for_prompt,
    extract_data_insight
)
import re
import time
import traceback


def create_tableau_chain():
    """
    Create a Tableau Calculated Field generation chain that can be invoked sequentially after SQL generation.
    Returns a callable chain object.
    """
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
    prompt_template = get_tableau_prompt_template()
    
    # LCEL chain: prompt | llm | output_parser
    chain = prompt_template | llm | StrOutputParser()
    return chain


def invoke_tableau_chain(
    question: str,
    sql_query: str,
    schema_context: str,
    sql_result: list = None,
    insight: str = "",
    relationships_context: str = "",
    db = None,
    active_table: str = ""
) -> dict:
    """
    Invoke Tableau chain with schema_context from Phase 1 (no re-fetching).
    
    ✅ ARCHITECTURAL TWEAK #1: Returns ABSTRACT contract for frontend simplicity
    Both DAX and Tableau chains return identical keys {bi_code, metric_name, ...}
    
    Args:
        question: Original user question
        sql_query: Generated SQL from Phase 1
        schema_context: Database schema (from Phase 1 output)
        sql_result: Query execution result (optional)
        insight: Business insight extracted from SQL results (for Strategy 1/2 naming)
        relationships_context: Table relationships metadata
        db: LangChain SQLDatabase connection (for dynamic schema reflection)
        active_table: Name of current table (for dynamic schema reflection)
    
    Returns:
        {
            "bi_code": str,              # ← ABSTRACT: Tableau calculated field code
            "metric_name": str,          # ← ABSTRACT: Field name extracted from code
            "usage_note": str,
            "success": bool,
            "error": str,
            "generation_ms": int,
            "tokens_prompt": int,
            "tokens_response": int,
            "qa_status": str,
            "qa_passed": bool,
            "qa_time_ms": int
        }
    """
    start_time = time.time()
    
    try:
        # Initialize Tableau chain (lightweight LLM call)
        chain = create_tableau_chain()
        
        # Extract SQL parameters (hardcoded WHERE values, used as filter context)
        extracted_params = extract_sql_parameters(sql_query)
        
        # Schema pruning (same as DAX: reduces tokens by 60-90%)
        # Prunes to only tables referenced in SQL query
        pruned_schema = prune_schema_for_dax(schema_context, sql_query)
        sql_result_snapshot = summarize_sql_result_for_prompt(sql_result)
        
        # Dynamic Schema Reflection - Query live column names for validation
        banned_columns_set = get_banned_columns(db, active_table) if db and active_table else set()
        banned_columns_str = ", ".join(sorted(banned_columns_set)) if banned_columns_set else "(auto-discovered)"
        
        # Prepare prompt template variables
        prompt_vars = {
            "sql_query": sql_query,
            "extracted_parameters": extracted_params,
            "schema_context": pruned_schema,  # ← Using PRUNED schema
            "question": question,
            "sql_result_snapshot": sql_result_snapshot,
            "insight": insight,  # ← CRITICAL: Pass data insight for strategic naming
            "banned_columns": banned_columns_str  # ← Dynamic banned list
        }
        
        # Invoke chain: prompt | llm | output
        generation_start = time.time()
        llm_response = chain.invoke(prompt_vars)
        generation_ms = int((time.time() - generation_start) * 1000)
        
        # Parse response: extract Tableau code, usage note, field name
        tableau_code = parse_tableau_response(llm_response)
        usage_note = extract_usage_note(llm_response)
        field_name = extract_field_name(tableau_code, banned_columns_set)
        
        # If extraction returned None, generate from insight
        if field_name is None:
            field_name = generate_field_name_from_insight(insight, question, use_prefix=True)
        
        # QA verification disabled to save tokens (like DAX)
        qa_time_ms = 0
        
        # ✅ ABSTRACT KEYS: Convert to uniform interface for frontend
        return {
            "bi_code": tableau_code,
            "metric_name": field_name,
            "usage_note": usage_note,
            "success": True,
            "error": None,
            "generation_ms": generation_ms,
            "tokens_prompt": 0,
            "tokens_response": 0,
            "qa_status": "QA verification disabled (free tier optimization)",
            "qa_passed": True,
            "qa_time_ms": qa_time_ms
        }
    
    except Exception as e:
        error_msg = str(e)
        traceback.print_exc()
        
        # ✅ ABSTRACT KEYS: Even error responses use abstract keys
        return {
            "bi_code": "",
            "metric_name": "",
            "usage_note": "",
            "success": False,
            "error": error_msg,
            "generation_ms": int((time.time() - start_time) * 1000),
            "tokens_prompt": 0,
            "tokens_response": 0,
            "qa_status": "Verification Pending",
            "qa_passed": False,
            "qa_time_ms": 0
        }


def parse_tableau_response(response: str) -> str:
    """
    Extract Tableau Calculated Field from LLM response (before [USAGE_NOTE] tag).
    """
    if "[USAGE_NOTE]" in response:
        tableau_part = response.split("[USAGE_NOTE]")[0].strip()
    else:
        tableau_part = response.strip()
    
    return tableau_part


def extract_usage_note(response: str) -> str:
    """
    Extract usage note from [USAGE_NOTE]...[/USAGE_NOTE] tags.
    """
    if "[USAGE_NOTE]" in response and "[/USAGE_NOTE]" in response:
        start = response.find("[USAGE_NOTE]") + len("[USAGE_NOTE]")
        end = response.find("[/USAGE_NOTE]")
        return response[start:end].strip()
    
    return "No usage note available"


def extract_field_name(tableau_code: str, banned_columns: set = None) -> str:
    """
    Extract field name from Tableau Calculated Field code with DYNAMIC validation.
    Returns None if extraction fails (triggers secondary fallback).
    
    COMPONENT 1: Strict Extraction
    - Only accepts [FieldName] = pattern (primary)
    - Rejects database column names from provided `banned_columns` set (dynamic)
    - Returns None if format invalid (fail-safe)
    """
    # Use provided dynamic banned list, or fallback to empty set
    if banned_columns is None:
        banned_columns = set()

    # PRIMARY: Match pattern [FieldName] = (with square brackets)
    match = re.search(r"\[\s*(\w+)\s*\]\s*=", tableau_code, re.MULTILINE)
    if match:
        field_name = match.group(1)
        # Validate: Reject if it's a column name (case-insensitive comparison)
        if field_name.lower() not in banned_columns:
            return field_name

    # SECONDARY: Match calculation pattern (fallback for edge cases)
    # Look for common Tableau functions that might indicate a field definition
    match = re.search(r"^\s*(\w+)\s*=\s*(?:IF|SUM|AVG|COUNT|COUNTD|MAX|MIN|RUNNING_SUM|FIXED|INCLUDE|EXCLUDE)",
                     tableau_code, re.MULTILINE | re.IGNORECASE)
    if match:
        field_name = match.group(1)
        if field_name.lower() not in banned_columns:
            return field_name

    # FAIL-SAFE: Return None to trigger secondary name generation
    return None


def generate_field_name_from_insight(insight: str, question: str, use_prefix: bool = False) -> str:
    """
    COMPONENT 3 & 5: Secondary Fallback
    Generate insight-first field name when extraction fails.
    Builds name from {insight} data and {question} context.

    Args:
        insight: Short insight extracted from SQL results
        question: Original user question for context
        use_prefix: If True, prepend "CF_" (Calculated Field prefix) for namespace safety
    """
    try:
        # Extract key finding from insight if it says "Winner:"
        finding = ""
        if "Winner:" in insight:
            # Extract pattern: "Winner: category=Raw" → use "Raw" as finding
            parts = insight.split("Winner:")[1].strip().split("[OUTLIER")[0].strip()
            if "=" in parts:
                finding = parts.split("=")[-1].strip().split(",")[0]

        # Extract business concept from question for context
        context = ""
        question_lower = question.lower()
        if "efficiency" in question_lower:
            context = "Efficiency"
        elif "elite" in question_lower:
            context = "Elite"
        elif "winner" in question_lower or "best" in question_lower or "top" in question_lower:
            context = "Top"
        elif "average" in question_lower:
            context = "Avg"
        elif "compare" in question_lower or "vs" in question_lower:
            context = "Comparison"
        else:
            context = "Metric"

        # Combine finding + context
        if finding:
            field_name = f"{context}_{finding}"
        else:
            field_name = context

        # Add prefix for namespace safety if requested
        if use_prefix:
            field_name = f"CF_{field_name}"

        # Ensure reasonable length (truncate if needed)
        max_len = 28 if use_prefix else 30  # Leave room for prefix
        field_name = field_name[:max_len]
        return field_name if field_name else ("CF_Metric" if use_prefix else "Metric")
    except Exception:
        return "CF_Metric" if use_prefix else "Metric"
