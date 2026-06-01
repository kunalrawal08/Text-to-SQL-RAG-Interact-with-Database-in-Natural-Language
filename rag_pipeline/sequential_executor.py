"""
Sequential Executor - Orchestrates SQL → DAX generation in strict Phase 1 → Phase 2 order
Purpose: Eliminate token bloat and API rate-limit errors by separating concerns
"""

import time
import streamlit as st
from rag_pipeline.dax_chain import invoke_dax_chain, extract_data_insight
from rag_pipeline.tableau_chain import invoke_tableau_chain


class SequentialExecutor:
    """
    Orchestrates sequential SQL generation (Phase 1) followed by DAX generation (Phase 2).
    Passes schema_context from Phase 1 to Phase 2 to eliminate re-fetching (~40% token savings).
    """
    
    @staticmethod
    def execute(
        chain,
        question: str,
        **chain_input_kwargs
    ) -> dict:
        """
        Execute SQL → DAX sequentially.
        
        Args:
            chain: SQL chain from rag_pipeline.chain.get_sql_chain()
            question: User's natural language question
            **chain_input_kwargs: Additional params for chain (context, schema_context, etc)
        
        Returns:
            {
                "phase1_result": SQLChainOutput,
                "phase2_result": DAXChainOutput,
                "total_time_ms": int,
                "phase1_time_ms": int,
                "phase2_time_ms": int,
                "execution_flow": "SQL_ONLY" | "SQL_THEN_DAX"
            }
        """
        orchestrator_start = time.time()
        
        # ============================================================================
        # PHASE 1: SQL Generation & Execution
        # ============================================================================
        phase1_start = time.time()
        
        try:
            phase1_result = chain.invoke({"question": question, **chain_input_kwargs})
            phase1_time_ms = int((time.time() - phase1_start) * 1000)
            
            # Ensure schema_context is in the result for Phase 2
            if "schema_context" not in phase1_result:
                phase1_result["schema_context"] = ""
            
            phase1_success = phase1_result.get("success", False)
        
        except Exception as e:
            phase1_time_ms = int((time.time() - phase1_start) * 1000)
            phase1_result = {
                "sql": "",
                "result": [],
                "success": False,
                "error": str(e),
                "schema_context": "",
                "execution_time_ms": phase1_time_ms,
                "tokens_prompt": 0,
                "tokens_response": 0
            }
            phase1_success = False
        
        # ============================================================================
        # PHASE 2: DAX Generation (Only if Phase 1 succeeded)
        # ============================================================================
        phase2_result = None
        phase2_time_ms = 0
        execution_flow = "SQL_ONLY"
        
        if phase1_success:
            phase2_start = time.time()
            
            try:
                # Extract needed inputs from Phase 1 output
                sql_query = phase1_result.get("sql", "")
                schema_context = phase1_result.get("schema_context", "")
                sql_result = phase1_result.get("result", [])
                
                # INSIGHT-FIRST BRIDGE: Extract business insight BEFORE naming
                data_insight = extract_data_insight(sql_result, sql_query)
                
                # Extract parameters for dynamic schema reflection
                active_table = chain_input_kwargs.get("active_table", "")
                db = chain_input_kwargs.get("db", None)
                
                # ✅ ARCHITECTURAL TWEAK #2: Get BI tool selection
                # Branching logic for Phase 2: Route to DAX or Tableau chain
                selected_bi_tool = st.session_state.get("selected_bi_tool")
                
                if selected_bi_tool == "Power BI (DAX)":
                    # DAX generation path
                    phase2_result = invoke_dax_chain(
                        question=question,
                        sql_query=sql_query,
                        schema_context=schema_context,
                        sql_result=sql_result,
                        insight=data_insight,
                        relationships_context=chain_input_kwargs.get("relationships_context", ""),
                        db=db,
                        active_table=active_table
                    )
                elif selected_bi_tool == "Tableau (Calculated Fields)":
                    # Tableau generation path
                    phase2_result = invoke_tableau_chain(
                        question=question,
                        sql_query=sql_query,
                        schema_context=schema_context,
                        sql_result=sql_result,
                        insight=data_insight,
                        relationships_context=chain_input_kwargs.get("relationships_context", ""),
                        db=db,
                        active_table=active_table
                    )
                else:
                    # ✅ ABSTRACT KEYS: Fallback uses abstract key contract
                    phase2_result = {
                        "bi_code": "",
                        "metric_name": "",
                        "usage_note": "",
                        "success": False,
                        "error": "No BI tool selected (This should not happen if execution gate works)",
                        "generation_ms": 0,
                        "tokens_prompt": 0,
                        "tokens_response": 0,
                        "qa_status": "Verification Pending",
                        "qa_passed": False,
                        "qa_time_ms": 0
                    }
                
                phase2_time_ms = int((time.time() - phase2_start) * 1000)
                execution_flow = "SQL_THEN_BI_TOOL"
            
            except Exception as e:
                phase2_time_ms = int((time.time() - phase2_start) * 1000)
                # ✅ ABSTRACT KEYS: Error response also uses abstract key contract
                phase2_result = {
                    "bi_code": "",
                    "metric_name": "",
                    "usage_note": "",
                    "success": False,
                    "error": str(e),
                    "generation_ms": phase2_time_ms,
                    "tokens_prompt": 0,
                    "tokens_response": 0,
                    "qa_status": "Verification Pending",
                    "qa_passed": False,
                    "qa_time_ms": 0
                }
        
        total_time_ms = int((time.time() - orchestrator_start) * 1000)
        
        return {
            "phase1_result": phase1_result,
            "phase2_result": phase2_result,
            "total_time_ms": total_time_ms,
            "phase1_time_ms": phase1_time_ms,
            "phase2_time_ms": phase2_time_ms,
            "execution_flow": execution_flow
        }
