"""
Phase 3: FastAPI Backend
Decoupled LangChain backend for Text-to-SQL generation.
Separate from Streamlit frontend for scalability and reusability.
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
from pydantic import BaseModel
import uvicorn

# Import backend functions
from database.get_schema import get_registered_tables_map, init_file_registry
from rag_pipeline.chain import get_sql_chain, generate_dax_measure
from rag_pipeline.tableau_chain import invoke_tableau_chain

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC MODELS: Request/Response Schemas
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for SQL query generation endpoint."""
    question: str
    active_table: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is the average revenue per store by city?",
                "active_table": "rebel_foods"
            }
        }


class QueryResponse(BaseModel):
    """Response model for query results."""
    sql: str
    result: str
    success: bool
    error: Optional[str] = None
    schema_context: Optional[str] = None
    retry_count: int = 0


# ============================================================================
# PYDANTIC MODELS: DAX & Tableau Generation Endpoints
# ============================================================================

class DAXRequest(BaseModel):
    """Request model for DAX measure generation endpoint."""
    question: str
    sql_query: str
    schema_context: str
    sql_result_snapshot: str = ""
    insight: str = ""
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Average revenue per store?",
                "sql_query": "SELECT store, AVG(revenue) FROM sales GROUP BY store",
                "schema_context": "Table: sales\n- store (VARCHAR)\n- revenue (DECIMAL)",
                "sql_result_snapshot": "[(store_name='Store1', avg_revenue=1500.0), ...]",
                "insight": ""
            }
        }


class DAXResponse(BaseModel):
    """Response model for DAX measure generation."""
    bi_code: str
    metric_name: str
    usage_note: Optional[str] = None
    success: bool
    error: Optional[str] = None
    generation_ms: int = 0
    tokens_prompt: int = 0
    tokens_response: int = 0
    qa_status: Optional[str] = None
    qa_passed: bool = False
    qa_time_ms: int = 0


class TableauRequest(BaseModel):
    """Request model for Tableau calculated field generation endpoint."""
    question: str
    sql_query: str
    schema_context: str
    sql_result_snapshot: str = ""
    insight: str = ""
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Average revenue per store?",
                "sql_query": "SELECT store, AVG(revenue) FROM sales GROUP BY store",
                "schema_context": "Table: sales\n- store (VARCHAR)\n- revenue (DECIMAL)",
                "sql_result_snapshot": "[(store_name='Store1', avg_revenue=1500.0), ...]",
                "insight": ""
            }
        }


class TableauResponse(BaseModel):
    """Response model for Tableau calculated field generation."""
    bi_code: str
    metric_name: str
    usage_note: Optional[str] = None
    success: bool
    error: Optional[str] = None
    generation_ms: int = 0
    tokens_prompt: int = 0
    tokens_response: int = 0
    qa_status: Optional[str] = None
    qa_passed: bool = False
    qa_time_ms: int = 0


# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for app startup and shutdown.
    Initializes registry on startup.
    """
    # Startup
    logger.info("🚀 FastAPI backend starting...")
    try:
        init_file_registry()
        logger.info("✓ File registry initialized")
    except Exception as e:
        logger.error(f"Failed to initialize registry: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 FastAPI backend shutting down...")


app = FastAPI(
    title="PowerLift AI - Text-to-SQL Backend",
    description="FastAPI backend for LangChain-based SQL generation from natural language",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (restrict in production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PERMANENT FIX #4: Add timeout middleware to FastAPI
class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware to add request timeout protection (120 seconds default)."""
    def __init__(self, app, timeout_seconds: int = 120):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
    
    async def dispatch(self, request, call_next):
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            logger.error(f"Request {request.url.path} exceeded {self.timeout_seconds} second timeout")
            return JSONResponse(
                status_code=408,
                content={
                    "detail": f"Request exceeded {self.timeout_seconds} second timeout",
                    "error": "Request Timeout"
                }
            )

# Add the middleware
app.add_middleware(TimeoutMiddleware, timeout_seconds=120)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/api/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns: {"status": "healthy"}
    """
    return {"status": "healthy", "service": "PowerLift AI Backend"}


@app.get("/api/tables")
async def get_tables():
    """
    Get all registered tables with user-friendly display names.
    
    Returns:
        {
            "Sales.xlsx - Q1": "sales_q1",
            "Sales.xlsx - Q2": "sales_q2",
            "legacy_powerlifting": "legacy_powerlifting"
        }
    """
    try:
        table_map = get_registered_tables_map()
        if not table_map:
            logger.warning("No tables found in database")
            return {}
        
        logger.info(f"✓ Returned {len(table_map)} tables")
        return table_map
    
    except Exception as e:
        logger.error(f"Failed to fetch tables: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tables: {str(e)}"
        )


@app.post("/api/query", response_model=QueryResponse)
async def query_sql(request: QueryRequest):
    """
    Generate SQL from natural language question and execute it.
    
    Request:
        - question: Natural language query (e.g., "What is the average revenue per store?")
        - active_table: Target database table (e.g., "rebel_foods")
    
    Response:
        - sql: Generated SQL query
        - result: Query result (rows as formatted string or JSON)
        - success: Boolean indicating success/failure
        - error: Error message if failed
        - schema_context: Database schema context used by LLM
        - retry_count: Number of self-healing retries performed
    
    Example:
        POST /api/query
        {
            "question": "What is the average revenue per store by city?",
            "active_table": "rebel_foods"
        }
    """
    try:
        logger.info(f"🔄 Processing query: {request.question[:60]}... | Table: {request.active_table}")
        
        # Validate inputs
        if not request.question or not request.question.strip():
            raise ValueError("Question cannot be empty")
        
        if not request.active_table or not request.active_table.strip():
            raise ValueError("Active table must be specified")
        
        # Initialize the chain with the specified table
        logger.info(f"Initializing chain for table: {request.active_table}")
        chain = get_sql_chain(active_table=request.active_table)
        
        # Invoke the chain with self-healing execution
        logger.info("Invoking chain for SQL generation...")
        result = chain.invoke({"question": request.question})
        
        # Log result
        if result.get("success"):
            logger.info(f"✓ Query succeeded after {result.get('retry_count', 0)} retries")
        else:
            logger.warning(f"✗ Query failed: {result.get('error', 'Unknown error')}")
        
        # Convert result to response model
        return QueryResponse(
            sql=result.get("sql", ""),
            result=str(result.get("result", "")),
            success=result.get("success", False),
            error=result.get("error"),
            schema_context=result.get("schema_context"),
            retry_count=result.get("retry_count", 0)
        )
    
    except ValueError as e:
        logger.error(f"Invalid request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Query execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Query execution failed: {str(e)}"
        )


@app.post("/api/dax", response_model=DAXResponse)
async def generate_dax(request: DAXRequest):
    """
    Generate Power BI DAX measure from natural language question and SQL query.
    
    Request:
        - question: Natural language query (e.g., "What is average revenue per store?")
        - sql_query: Generated SQL from Phase 1 (e.g., "SELECT store, AVG(revenue)...")
        - schema_context: Database schema context (e.g., table descriptions with columns)
    
    Response:
        - bi_code: DAX measure code ready to paste into Power BI
        - metric_name: Suggested measure name
        - generation_ms: Time taken to generate
        - tokens_prompt/tokens_response: LLM token usage
    """
    try:
        logger.info(f"🔄 Generating DAX measure for: {request.question[:60]}...")
        
        # Validate inputs
        if not request.question or not request.question.strip():
            raise ValueError("Question cannot be empty")
        if not request.sql_query or not request.sql_query.strip():
            raise ValueError("SQL query cannot be empty")
        if not request.schema_context or not request.schema_context.strip():
            raise ValueError("Schema context cannot be empty")
        
        # PERMANENT FIX #5: Add timeout wrapper around DAX generation
        import threading
        dax_result_holder = [None]
        dax_exception_holder = [None]
        
        def run_dax_generation():
            try:
                dax_result_holder[0] = generate_dax_measure(
                    sql_query=request.sql_query,
                    schema_context=request.schema_context,
                    question=request.question,
                    sql_result_snapshot=request.sql_result_snapshot,
                    insight=request.insight
                )
            except Exception as e:
                dax_exception_holder[0] = e
        
        # Run DAX generation with 45-second timeout
        dax_thread = threading.Thread(target=run_dax_generation, daemon=True)
        dax_thread.start()
        dax_thread.join(timeout=45)
        
        if dax_thread.is_alive():
            logger.error("DAX generation exceeded 45 second timeout")
            raise Exception("DAX generation timed out after 45 seconds")
        
        if dax_exception_holder[0]:
            raise dax_exception_holder[0]
        
        result = dax_result_holder[0]
        
        if result.get("success"):
            logger.info("✓ DAX measure generated successfully")
            # PERMANENT FIX #3: Type-safe extraction with None coercion to defaults
            return DAXResponse(
                bi_code=result.get("bi_code") or "",
                metric_name=result.get("metric_name") or "Measure",
                usage_note=result.get("usage_note"),
                success=True,
                generation_ms=int(result.get("generation_ms") or 0),
                tokens_prompt=int(result.get("tokens_prompt") or 0),
                tokens_response=int(result.get("tokens_response") or 0),
                qa_status=result.get("qa_status"),
                qa_passed=bool(result.get("qa_passed", False)),
                qa_time_ms=int(result.get("qa_time_ms") or 0)
            )
        else:
            raise Exception(result.get("error", "Unknown DAX generation error"))
    
    except Exception as e:
        logger.error(f"DAX generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"DAX generation failed: {str(e)}"
        )


@app.post("/api/tableau", response_model=TableauResponse)
async def generate_tableau(request: TableauRequest):
    """
    Generate Tableau calculated field from natural language question and SQL query.
    
    Request:
        - question: Natural language query (e.g., "What is average revenue per store?")
        - sql_query: Generated SQL from Phase 1
        - schema_context: Database schema context
    
    Response:
        - bi_code: Tableau calculated field code
        - metric_name: Suggested field name
        - generation_ms: Time taken to generate
        - tokens_prompt/tokens_response: LLM token usage
    """
    try:
        logger.info(f"🔄 Generating Tableau field for: {request.question[:60]}...")
        
        # Validate inputs
        if not request.question or not request.question.strip():
            raise ValueError("Question cannot be empty")
        if not request.sql_query or not request.sql_query.strip():
            raise ValueError("SQL query cannot be empty")
        if not request.schema_context or not request.schema_context.strip():
            raise ValueError("Schema context cannot be empty")
        
        # PERMANENT FIX #5: Add timeout wrapper around Tableau generation
        import threading
        tableau_result_holder = [None]
        tableau_exception_holder = [None]
        
        def run_tableau_generation():
            try:
                tableau_result_holder[0] = invoke_tableau_chain(
                    question=request.question,
                    sql_query=request.sql_query,
                    schema_context=request.schema_context,
                    sql_result=None,
                    insight=request.insight,
                    relationships_context=""
                )
            except Exception as e:
                tableau_exception_holder[0] = e
        
        # Run Tableau generation with 45-second timeout
        tableau_thread = threading.Thread(target=run_tableau_generation, daemon=True)
        tableau_thread.start()
        tableau_thread.join(timeout=45)
        
        if tableau_thread.is_alive():
            logger.error("Tableau generation exceeded 45 second timeout")
            raise Exception("Tableau generation timed out after 45 seconds")
        
        if tableau_exception_holder[0]:
            raise tableau_exception_holder[0]
        
        result = tableau_result_holder[0]
        
        if result.get("success"):
            logger.info("✓ Tableau field generated successfully")
            # PERMANENT FIX #3: Type-safe extraction with None coercion to defaults
            return TableauResponse(
                bi_code=result.get("bi_code") or "",
                metric_name=result.get("metric_name") or "Field",
                usage_note=result.get("usage_note"),
                success=True,
                generation_ms=int(result.get("generation_ms") or 0),
                tokens_prompt=int(result.get("tokens_prompt") or 0),
                tokens_response=int(result.get("tokens_response") or 0),
                qa_status=result.get("qa_status"),
                qa_passed=bool(result.get("qa_passed", False)),
                qa_time_ms=int(result.get("qa_time_ms") or 0)
            )
        else:
            raise Exception(result.get("error", "Unknown Tableau generation error"))
    
    except Exception as e:
        logger.error(f"Tableau generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Tableau generation failed: {str(e)}"
        )


@app.get("/api/docs-custom")
async def custom_docs():
    """Custom documentation endpoint with usage examples."""
    return {
        "endpoints": {
            "health": {
                "method": "GET",
                "path": "/api/health",
                "description": "Health check"
            },
            "tables": {
                "method": "GET",
                "path": "/api/tables",
                "description": "Get all registered tables",
                "response": {
                    "Sales.xlsx - Q1": "sales_q1",
                    "legacy_table": "legacy_table"
                }
            },
            "query": {
                "method": "POST",
                "path": "/api/query",
                "description": "Generate and execute SQL from natural language",
                "request": {
                    "question": "What is the average revenue per store?",
                    "active_table": "rebel_foods"
                },
                "response": {
                    "sql": "SELECT store, AVG(revenue) FROM rebel_foods GROUP BY store",
                    "result": "[(store_1, 5000), (store_2, 6000)]",
                    "success": True,
                    "retry_count": 0
                }
            }
        }
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler for consistency."""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("Starting FastAPI Backend - PowerLift AI Text-to-SQL Server")
    logger.info("=" * 70)
    logger.info("📡 Server running at: http://localhost:8080")
    logger.info("📚 API Docs at: http://localhost:8080/docs")
    logger.info("🔄 ReDoc at: http://localhost:8080/redoc")
    logger.info("=" * 70)
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
