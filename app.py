"""
Phase 4: Enterprise-Grade UI Layer
Text-to-SQL RAG Application for Powerlifting Data
Powered by: Streamlit + LangChain + Gemini + PostgreSQL + ChromaDB
"""

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import os
import pandas as pd
import requests
import re
import time
import json
import google.generativeai as genai
from sqlalchemy import create_engine, inspect
from langchain_community.utilities import SQLDatabase
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PowerLift AI",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── FastAPI Backend Configuration ──────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080/api")

# ── Load CSS ───────────────────────────────────────────────────────────────────
# CSS loading DISABLED - using Streamlit-only components per user request
# css_path = os.path.join(os.path.dirname(__file__), "app", "style.css")
# if os.path.exists(css_path):
#     with open(css_path, "r", encoding="utf-8") as css_file:
#         st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)

# ── Essential Component Styling ────────────────────────────────────────────────
# Add minimal CSS for insight cards and key UI elements
st.markdown("""
<style>
.insight-card {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 16px;
    padding: 1.5rem 1.75rem;
    color: #166534;
    font-size: 1.05rem;
    line-height: 1.7;
    font-weight: 400;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    margin-top: 1rem;
}

.insight-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #15803d;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.6rem;
    display: flex;
    align-items: center;
    gap: 6px;
}

.query-label {
    font-size: 0.78rem;
    font-weight: 700;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 0.5rem;
}

.sql-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 6px;
}
</style>
""", unsafe_allow_html=True)

# ── HLS Video Background (Light Mode) ──────────────────────────────────────────
# Optional HLS video background - commented out due to module availability
# Uncomment if streamlit.components.v1 is available in your environment
# hls_html = """
# <div id="video-container">
#     <video id="video-player" autoplay muted loop playsinline>
#         <source src="https://customer-cbeadsgr09pnsezs.cloudflarestream.com/32001496dbb54c46b44201e254430eb5/manifest/video.m3u8" type="application/x-mpegURL">
#     </video>
#     <div class="overlay"></div>
# </div>
# <script src="https://cdnjs.cloudflare.com/ajax/libs/hls.js/1.4.10/hls.min.js"></script>
# <script>
#     const video = document.getElementById('video-player');
#     if (Hls.isSupported()) {
#         const hls = new Hls();
#         hls.loadSource('https://customer-cbeadsgr09pnsezs.cloudflarestream.com/32001496dbb54c46b44201e254430eb5/manifest/video.m3u8');
#         hls.attachMedia(video);
#     } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
#         video.src = 'https://customer-cbeadsgr09pnsezs.cloudflarestream.com/32001496dbb54c46b44201e254430eb5/manifest/video.m3u8';
#     }
# </script>
# <style>
#     #video-container {
#         position: fixed;
#         top: 0;
#         left: 0;
#         width: 100vw;
#         height: 100vh;
#         z-index: -1;
#         overflow: hidden;
#         background: #e0f2fe;
#     }
#     video {
#         width: 100%;
#         height: 100%;
#         object-fit: cover;
#         opacity: 0.25;
#         mix-blend-mode: multiply;
#     }
#     .overlay {
#         position: absolute;
#         inset: 0;
#         background: linear-gradient(to bottom, rgba(240, 249, 255, 0.9) 0%, transparent 40%, transparent 60%, rgba(240, 249, 255, 0.9) 100%);
#     }
# </style>
# """
# components.html(hls_html, height=0)

# ── Setup ──────────────────────────────────────────────────────────────────────
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def get_natural_response(question, query_results):
    """Convert raw SQL results into natural language using Groq + Llama 3.3. Returns response + metrics."""
    llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama-3.3-70b-versatile",
        temperature=0  # Set to 0 to prevent hallucination
    )
    
    # Format results more clearly for the LLM
    if isinstance(query_results, list):
        formatted_results = "\n".join([str(row) for row in query_results[:5]])  # Limit to first 5 rows
    else:
        formatted_results = str(query_results)
    
    system_prompt = f"""You are a helpful AI data assistant specializing in powerlifting data.
The user asked: "{question}"
The SQL database returned these EXACT results: {formatted_results}

IMPORTANT: Only use the actual data provided above. Do NOT make up or estimate values.
Formulate a polite, conversational, natural language sentence answering the user's question.
Do NOT mention SQL, databases, tuples, or technical details. Be direct and human-friendly."""
    
    start_time = time.time()
    # LangChain requires messages, so we wrap the prompt in a HumanMessage
    response = llm.invoke([HumanMessage(content=system_prompt)])
    latency = time.time() - start_time
    
    # Calculate token metrics
    metrics = {
        'latency_ms': round(latency * 1000, 2),
        'system_prompt': system_prompt,
        'tokens_prompt': len(system_prompt.split()),
        'tokens_response': len(response.content.split())
    }
    
    return response.content, metrics

def get_executive_summary(question, query_results):
    """Generate 2-sentence business summary. Lightweight, optional feature."""
    try:
        llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama-3.3-70b-versatile",
            temperature=0
        )
        
        # Format results for summary
        if isinstance(query_results, list):
            formatted_results = "\n".join([str(row) for row in query_results[:10]])
        else:
            formatted_results = str(query_results)
        
        system_prompt = f"""You are a business intelligence analyst for powerlifting data.
Question: "{question}"
Data: {formatted_results}

Write EXACTLY 2 sentences summarizing the key business insight.
Focus on trends, patterns, or key metrics. Be quantitative and avoid jargon."""
        
        start_time = time.time()
        response = llm.invoke([HumanMessage(content=system_prompt)])
        latency = time.time() - start_time
        
        return response.content, latency
    except Exception as e:
        return None, 0  # Graceful degradation

def get_dynamic_schema():
    """Fetch the actual database schema from PostgreSQL dynamically based on active table."""
    db_url = os.getenv("DB_URL", "postgresql://POWERLIFTER_KUNAL:Kunal123@localhost:2003/powerlifting_db")
    
    engine = create_engine(db_url)
    db_inspector = inspect(engine)
    
    # Dynamically grab the active table's shape
    active_table = st.session_state.get('active_table')
    
    if active_table == "MULTI_TABLE_WORKSPACE":
        if hasattr(st.session_state, 'dataset_tables') and st.session_state.dataset_tables:
            active_table = st.session_state.dataset_tables[0]
        else:
            active_table = 'powerlifting_meets'
            
    if not active_table:
        active_table = 'powerlifting_meets'
        
    try:
        columns = db_inspector.get_columns(active_table)
    except:
        columns = []
        
    return columns

# ── Virtual Workspace State Management ──────────────────────────────────────
def is_dataset_workspace_active():
    """Check if we're in a multi-table dataset workspace."""
    return (
        hasattr(st.session_state, 'multi_sheet_import') 
        or hasattr(st.session_state, 'active_relationships')
    )

def reset_for_new_upload():
    """Clear all multi-sheet workspace state before new upload."""
    keys_to_clear = [
        'multi_sheet_import',
        'active_relationships',
        'sheet_to_table_mapping',
        'dataset_tables',
        'dataset_name'
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    try:
        # ── CSS for Better Styling ──
        st.markdown("""
        <style>
            .section-card {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 12px;
            }
            .section-card-blue {
                background: linear-gradient(135deg, #f0f9ff 0%, #e0f7ff 100%);
                border: 1px solid #bae6fd;
                border-left: 3px solid #0284c7;
                border-radius: 6px;
                padding: 12px;
                margin-bottom: 12px;
            }
            .section-label {
                font-size: 0.7rem;
                font-weight: 700;
                color: #0284c7;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 8px;
            }
            .section-label-alt {
                font-size: 0.7rem;
                font-weight: 700;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 8px;
            }
        </style>
        
        <style>
            /* Custom Tab Styling - Ultra Professional & Square (Streamlit 1.35+ compatible) */
            div[data-testid="stTabs"] [role="tablist"] {
                gap: 4px !important;
                background-color: #f8fafc !important;
                border: 1px solid #e2e8f0 !important;
                border-radius: 4px !important;
                padding: 4px !important;
            }

            div[data-testid="stTabs"] button[role="tab"] {
                height: 42px !important;
                white-space: pre-wrap !important;
                background-color: transparent !important;
                border-radius: 2px !important;
                padding: 8px 24px !important;
                color: #64748b !important;
                font-weight: 700 !important;
                font-size: 13px !important;
                text-transform: uppercase !important;
                letter-spacing: 0.5px !important;
                border: none !important;
                transition: all 0.2s ease-in-out !important;
            }

            div[data-testid="stTabs"] button[role="tab"]:hover {
                color: #0f172a !important;
                background-color: #f1f5f9 !important;
            }

            div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
                background-color: #0ea5e9 !important;
                color: white !important;
                box-shadow: 0 2px 4px rgba(14, 165, 233, 0.3) !important;
            }

            /* Radio Buttons to Segmented Controls */
            div[data-testid="stRadio"] > div[role="radiogroup"] {
                gap: 0 !important;
                background-color: #f8fafc !important;
                border: 1px solid #e2e8f0 !important;
                border-radius: 4px !important;
                display: inline-flex !important;
                flex-direction: row !important;
                overflow: hidden !important;
            }

            div[data-testid="stRadio"] [data-baseweb="radio"] {
                padding: 10px 20px !important;
                margin: 0 !important;
                border-right: 1px solid #e2e8f0 !important;
                background-color: transparent !important;
                cursor: pointer !important;
                transition: all 0.2s ease-in-out !important;
                align-items: center !important;
                justify-content: center !important;
            }

            div[data-testid="stRadio"] [data-baseweb="radio"]:last-child {
                border-right: none !important;
            }

            /* Hide the circular radio indicator */
            div[data-testid="stRadio"] [data-baseweb="radio"] > div:first-child {
                display: none !important;
            }

            /* Base text style */
            div[data-testid="stRadio"] [data-baseweb="radio"] p {
                font-size: 13px !important;
                font-weight: 700 !important;
                color: #64748b !important;
                margin: 0 !important;
            }

            /* Hover state */
            div[data-testid="stRadio"] [data-baseweb="radio"]:hover {
                background-color: #f1f5f9 !important;
            }
            div[data-testid="stRadio"] [data-baseweb="radio"]:hover p {
                color: #0f172a !important;
            }

            /* Active/Selected state */
            div[data-testid="stRadio"] [data-baseweb="radio"]:has(input:checked) {
                background-color: #0ea5e9 !important;
                box-shadow: inset 0 2px 4px rgba(0,0,0,0.05) !important;
            }

            div[data-testid="stRadio"] [data-baseweb="radio"]:has(input:checked) p {
                color: white !important;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # ── HEADER ──
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 2px solid #e2e8f0;">
            <div style="font-size: 1.4rem;">🏋️</div>
            <div style="flex: 1;">
                <div style="font-size: 0.9rem; font-weight: 800; color: #0f172a; margin: 0; line-height: 1.1;">PowerLift AI</div>
                <div style="color: #0284c7; font-size: 0.65rem; font-weight: 700; margin-top: 1px; text-transform: uppercase; letter-spacing: 0.08em;">RAG Analytics</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── SECTION 1: Active Table Card ──
        from database.get_schema import (
    get_all_tables, get_table_schema, format_column_type, get_registered_tables_map, init_file_registry,
    delete_from_file_registry, cleanup_orphaned_registry_entries, identify_old_convention_tables, cleanup_old_convention_tables
)
        
        # Initialize session state for active table
        if 'active_table' not in st.session_state:
            # If already in workspace mode, don't override
            if hasattr(st.session_state, 'active_relationships') and st.session_state.active_relationships:
                st.session_state.active_table = "MULTI_TABLE_WORKSPACE"
            else:
                tables = get_all_tables()
                if 'powerlifting_meets' in tables:
                    st.session_state.active_table = 'powerlifting_meets'
                elif tables:
                    st.session_state.active_table = tables[0]
                else:
                    st.session_state.active_table = None
        
        st.markdown('<div class="section-card-blue"><div class="section-label">📊 Active Database</div>', unsafe_allow_html=True)
        
        # VIRTUAL WORKSPACE MODE: Show unified dataset view
        if hasattr(st.session_state, 'dataset_tables') and st.session_state.dataset_tables:
            dataset_name = st.session_state.get('dataset_name', 'Dataset')
            dataset_tables = st.session_state.dataset_tables
            
            # Calculate total rows across all tables
            total_rows = 0
            for tbl in dataset_tables:
                try:
                    schema_info = get_table_schema(tbl)
                    if schema_info['success']:
                        total_rows += schema_info['row_count']
                except:
                    pass
            
            # Display Virtual Workspace Header
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #dbeafe 0%, #e0f7ff 100%); border: 2px solid #0284c7; 
                        border-radius: 12px; padding: 12px; margin-bottom: 8px;">
                <div style="font-size: 0.75rem; color: #0284c7; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px;">
                    📦 Virtual Workspace
                </div>
                <div style="font-size: 1.1rem; font-weight: 800; color: #0c4a6e; margin-bottom: 6px;">
                    {dataset_name}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <div style="padding: 6px; background: #ffffff; border-radius: 6px; text-align: center; border: 1px solid #bae6fd;">
                        <div style="font-size: 0.65rem; color: #0284c7; font-weight: 700; text-transform: uppercase;">Tables</div>
                        <div style="font-size: 0.95rem; font-weight: 700; color: #0284c7; margin-top: 2px;">{len(dataset_tables)}</div>
                    </div>
                    <div style="padding: 6px; background: #ffffff; border-radius: 6px; text-align: center; border: 1px solid #bae6fd;">
                        <div style="font-size: 0.65rem; color: #0284c7; font-weight: 700; text-transform: uppercase;">Total Rows</div>
                        <div style="font-size: 0.95rem; font-weight: 700; color: #0284c7; margin-top: 2px;">{total_rows:,}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Show relationships in collapsible section (if any)
            if hasattr(st.session_state, 'active_relationships') and st.session_state.active_relationships:
                with st.expander("🔗 Dataset Relationships", expanded=False):
                    rel_text = ""
                    for i, rel in enumerate(st.session_state.active_relationships, 1):
                        from_table = st.session_state.sheet_to_table_mapping.get(rel['from_sheet'], rel['from_sheet'])
                        to_table = st.session_state.sheet_to_table_mapping.get(rel['to_sheet'], rel['to_sheet'])
                        rel_text += f"{i}. `{from_table}`.{rel['from_column']} ↔ `{to_table}`.{rel['to_column']}\n"
                    st.markdown(rel_text)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # ── WORKSPACE ILLUSION: Check if Active Virtual Workspace exists ──
        if hasattr(st.session_state, 'active_relationships') and st.session_state.active_relationships:
            # WORKSPACE MODE: Show sleek banner instead of dropdown
            dataset_name = st.session_state.get('dataset_name', 'Custom Dataset')
            dataset_tables = st.session_state.get('dataset_tables', [])
            
            st.markdown('<div class="section-card-blue"><div class="section-label">📊 Active Database</div>', unsafe_allow_html=True)
            
            st.success(f"🌌 Virtual Workspace Active: **{dataset_name}**")
            
            # Show linked tables summary
            linked_tables_text = ", ".join(dataset_tables) if dataset_tables else "No tables"
            st.caption(f"**Linked Data:** {linked_tables_text}")
            
            # Set flag for backend query logic
            st.session_state.active_table = "MULTI_TABLE_WORKSPACE"
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # SINGLE-TABLE MODE: Show table selector dropdown with registry
        else:
            # Initialize registry on app startup
            init_file_registry()
            
            # PERMANENT FIX: Auto-cleanup orphaned registry entries
            cleanup_orphaned_registry_entries()
            
            # Fetch table map from FastAPI backend
            try:
                response = requests.get(f"{API_BASE_URL}/tables")
                table_map = response.json() if response.status_code == 200 else {}
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to AI Backend. Is the FastAPI server running on port 8080?")
                table_map = {}
            
            if table_map:
                display_names = list(table_map.keys())
                
                # Find correct index for current active_table
                current_index = 0
                for i, display_name in enumerate(display_names):
                    if table_map[display_name] == st.session_state.get('active_table'):
                        current_index = i
                        break
                
                selected_display_name = st.selectbox(
                    "Database Table",
                    options=display_names,
                    index=current_index,
                    key="table_selector",
                    label_visibility="collapsed"
                )
                # Save the ACTUAL table name to session state
                st.session_state.active_table = table_map[selected_display_name]
                selected_table = st.session_state.active_table
                
                # Get schema and show compact info
                schema_info = get_table_schema(selected_table)
                if schema_info['success']:
                    # Inline metrics with icons
                    st.markdown(f"""
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 8px;">
                        <div style="padding: 6px; background: #ffffff; border-radius: 4px; text-align: center;">
                            <div style="font-size: 0.7rem; color: #64748b; font-weight: 600; margin-bottom: 2px;">Rows</div>
                            <div style="font-size: 0.95rem; font-weight: 700; color: #0284c7;">{schema_info['row_count']:,}</div>
                        </div>
                        <div style="padding: 6px; background: #ffffff; border-radius: 4px; text-align: center;">
                            <div style="font-size: 0.7rem; color: #64748b; font-weight: 600; margin-bottom: 2px;">Columns</div>
                            <div style="font-size: 0.95rem; font-weight: 700; color: #0284c7;">{schema_info['column_count']}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.text(f"⚠️ Error loading schema: {schema_info['error'][:80]}")
                
                # ── SECTION 2: Schema & Data Explorers ──
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown('<div class="section-card-blue"><div class="section-label">🔍 Database Structure</div>', unsafe_allow_html=True)
                col_a, col_b = st.columns(2, gap="small")
                
                with col_a:
                    with st.expander("Schema", expanded=False):
                        # Build all schema HTML at once for proper scrollable container
                        schema_html = '<div style="height: 320px; overflow-y: auto; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; background: #f8fafc;">'
                        for col in schema_info['columns']:
                            col_icon = "✓" if not col['nullable'] else "○"
                            formatted_type = format_column_type(col['type'])
                            schema_html += (
                                '<div style="padding: 6px 0; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; gap: 8px;">'
                                f'<span style="color: #22c55e; font-weight: 600; font-size: 14px;">{col_icon}</span>'
                                f'<span style="font-family: monospace; color: #0284c7; font-weight: 600; font-size: 13px;">{col["name"]}</span>'
                                f'<span style="color: #94a3b8; font-size: 12px; margin-left: auto;">{formatted_type}</span>'
                                '</div>'
                            )
                        schema_html += "</div>"
                        st.markdown(schema_html, unsafe_allow_html=True)
                
                with col_b:
                    if schema_info['sample_data']:
                        with st.expander("Sample Data", expanded=False):
                            sample_df = pd.DataFrame(
                                schema_info['sample_data'][:3],
                                columns=[col['name'] for col in schema_info['columns']]
                            )
                            # Explicitly set all columns as TextColumn to prevent Streamlit auto-detection
                            # This prevents email validation errors on columns with "/" or special characters
                            column_config_override = {
                                col_name: st.column_config.TextColumn(width="medium") 
                                for col_name in sample_df.columns
                            }
                            st.dataframe(sample_df, use_container_width=True, hide_index=True, column_config=column_config_override)
        
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div style="height: 8px;"></div>', unsafe_allow_html=True)
        
        # ── SECTION 3: Data Ingestion ──
        st.markdown('<div class="section-card-blue"><div class="section-label">📥 Data Ingestion</div>', unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("Choose CSV or Excel file", type=["csv", "xlsx"], label_visibility="collapsed", key="sidebar_file_uploader")
        
        # ── PERMANENT FIX #1: Strict Null-Checking with Session Cleanup ──
        # If user refreshed or cancelled upload, clean up orphaned session state
        if uploaded_file is None:
            # CLEANUP: Remove orphaned session state that causes "scattered sheets" on refresh
            orphaned_keys = [
                'multi_sheet_import',
                'active_relationships', 
                'sheet_to_table_mapping',
                'dataset_tables',
                'dataset_name'
            ]
            for key in orphaned_keys:
                if key in st.session_state:
                    del st.session_state[key]
            st.info("📁 Upload a file to begin. Previous session cleared.")
        
        elif uploaded_file is not None:
            # THE UPLOADER LOCK: Check if we've already processed this specific file
            # This prevents the infinite rerun loop on every query
            if st.session_state.get('last_uploaded_file') != uploaded_file.name:
                try:
                    # Clear old state if switching from dataset to new upload
                    if is_dataset_workspace_active():
                        reset_for_new_upload()
                    
                    # ──────────────────────────────────────────────────────────────
                    # MULTI-SHEET WIZARD: Step 2 - Relationship Configuration
                    # ──────────────────────────────────────────────────────────────
                    
                    from database.excel_utils import is_multi_sheet_excel, detect_excel_sheets
                    from database.relationship_detector import detect_relationships
                    from database.sanitizer import create_sheet_to_table_mapping
                    
                    if uploaded_file.name.endswith('.xlsx') and is_multi_sheet_excel(uploaded_file):
                        # Detect sheets
                        excel_info = detect_excel_sheets(uploaded_file)
                        
                        if excel_info['success'] and excel_info['sheet_count'] > 1:
                            sheets_info = excel_info['sheets']
                            
                            # Auto-detect relationships
                            auto_relationships = detect_relationships(sheets_info)
                            
                            # Display wizard in main body (after sidebar detection)
                            st.markdown("---")
                            st.markdown("### 📊 Step 1: Multi-Sheet File Detected")
                            
                            col1, col2 = st.columns([2, 1])
                            with col1:
                                st.info(f"📄 Found **{excel_info['sheet_count']} sheets** in {uploaded_file.name}")
                            with col2:
                                import_mode = st.radio(
                                    "Import Mode",
                                    ["Single Sheet", "All Sheets"],
                                    label_visibility="collapsed",
                                    horizontal=True
                                )
                            
                            # Sheet Selection
                            st.subheader("📋 Select Sheets to Import")
                            
                            selected_sheets = {}
                            for sheet in sheets_info:
                                sheet_name = sheet['name']
                                
                                # PERMANENT FIX: Smart defaults - exclude junk sheets
                                junk_keywords = ['pivot', 'sql', 'chart', 'summary']
                                is_junk_sheet = any(
                                    keyword in sheet_name.lower() for keyword in junk_keywords
                                )
                                default_checked = not is_junk_sheet  # False if junk, True otherwise
                                
                                col1, col2, col3 = st.columns([1, 3, 1])
                                
                                with col1:
                                    select = st.checkbox(
                                        label="",
                                        value=default_checked,  # Smart default based on sheet name
                                        key=f"sheet_select_{sheet_name}",
                                        label_visibility="collapsed"
                                    )
                                
                                with col2:
                                    st.write(f"**{sheet_name}** — {len(sheet['columns'])} columns, ~{sheet['row_count']} rows")
                                    if sheet['columns']:
                                        st.caption(", ".join(sheet['columns'][:5]) + ("..." if len(sheet['columns']) > 5 else ""))
                                
                                with col3:
                                    st.write(f"✓ {sheet['row_count']}")
                                
                                selected_sheets[sheet_name] = select
                            
                            # Get only selected sheets
                            selected_sheet_names = [name for name, selected in selected_sheets.items() if selected]
                            
                            # Relationships Configuration
                            if len(selected_sheet_names) > 1:
                                st.subheader("🔗 Configure Relationships")
                                st.write("Set up how sheets relate to each other for joining data.")
                                
                                # Initialize relationships in session state
                                if 'relationships' not in st.session_state:
                                    st.session_state.relationships = auto_relationships
                                
                                # Section A: Auto-Detected
                                if auto_relationships:
                                    st.markdown("#### ✓ Auto-Detected (Confirmed)")
                                    for rel in auto_relationships:
                                        col1, col2 = st.columns([9, 1])
                                        with col1:
                                            st.markdown(
                                                f"**{rel['from_sheet']}.{rel['from_column']}** → **{rel['to_sheet']}.{rel['to_column']}**"
                                            )
                                            st.caption(rel['reason'])
                                        with col2:
                                            toggle = st.checkbox(
                                                "✓",
                                                value=True,
                                                key=f"toggle_rel_{rel['from_sheet']}_{rel['from_column']}",
                                                label_visibility="collapsed"
                                            )
                                
                                # Section B: Add Custom
                                st.markdown("#### ➕ Add Custom Relationship")
                                
                                col1, col_arrow, col2 = st.columns([2.5, 0.5, 2.5])
                                
                                with col1:
                                    from_sheet = st.selectbox(
                                        "From Sheet",
                                        options=selected_sheet_names,
                                        key="custom_from_sheet"
                                    )
                                    from_cols = sheets_info[[s['name'] for s in sheets_info].index(from_sheet)]['columns']
                                    from_col = st.selectbox(
                                        "From Column",
                                        options=from_cols,
                                        key="custom_from_col"
                                    )
                                
                                with col_arrow:
                                    st.write("**→**")
                                
                                with col2:
                                    to_sheet = st.selectbox(
                                        "To Sheet",
                                        options=[s for s in selected_sheet_names if s != from_sheet],
                                        key="custom_to_sheet"
                                    )
                                    to_cols = sheets_info[[s['name'] for s in sheets_info].index(to_sheet)]['columns']
                                    to_col = st.selectbox(
                                        "To Column",
                                        options=to_cols,
                                        key="custom_to_col"
                                    )
                                
                                if st.button("➕ Add This Relationship", use_container_width=True):
                                    new_rel = {
                                        'from_sheet': from_sheet,
                                        'from_column': from_col,
                                        'to_sheet': to_sheet,
                                        'to_column': to_col,
                                        'confidence': 'USER_DEFINED',
                                        'reason': 'Manually configured'
                                    }
                                    if new_rel not in st.session_state.relationships:
                                        st.session_state.relationships.append(new_rel)
                                        st.success("✅ Relationship added!")
                                        st.rerun()
                                
                                # Store sheet info and relationships for later use
                                st.session_state.multi_sheet_import = {
                                    'workbook_name': uploaded_file.name,
                                    'selected_sheets': selected_sheet_names,
                                    'relationships': st.session_state.relationships,
                                    'sheets_info': sheets_info
                                }
                                
                                st.markdown("---")
                                st.markdown("**Ready to proceed?** Click 'Ingest' below to import selected sheets.")
                            
                            # Fall through to ingestion logic below
                    
                    # ── Single Sheet or CSV Logic ──
                    # PERMANENT FIX #2: Only proceed if uploaded_file is safely in memory
                    df = None
                    
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    else:
                        # For single-sheet Excel or after multi-sheet selection
                        if 'multi_sheet_import' not in st.session_state:
                            df = pd.read_excel(uploaded_file)
                        else:
                            # Skip single df read for multi-sheet
                            df = None
                    
                    # PERMANENT FIX #2: CRITICAL - Only proceed if uploaded_file is not None AND (df loaded OR multi-sheet import exists)
                    # This prevents the orphaned session state vulnerability where uploaded_file becomes None on refresh
                    if uploaded_file is not None and (df is not None or 'multi_sheet_import' in st.session_state):
                        from database.ingest_csv import validate_csv, ingest_csv_to_postgres
                        
                        # PERMANENT FIX: Initialize variables for both single and multi-sheet paths
                        proceed = True
                        table_name = None
                        
                        # Only validate and show form if SINGLE-SHEET
                        if df is not None:
                            is_valid, errors, warnings = validate_csv(df, uploaded_file.name)
                            
                            if errors:
                                st.error("Validation Failed")
                                for error in errors:
                                    st.text(error)
                                proceed = False
                            else:
                                st.success(f"{len(df):,} rows × {len(df.columns)} columns")
                                proceed = True
                                if warnings:
                                    st.warning("⚠️ Upload Warnings")
                                    for warn_type, warn_msg in warnings.items():
                                        st.text(f"• {warn_msg}")
                                    proceed = st.checkbox("Continue anyway?", key="proceed_warnings", label_visibility="collapsed")
                                
                                table_name = st.text_input(
                                    "Table name",
                                    value=uploaded_file.name.split('.')[0].lower(),
                                    label_visibility="collapsed",
                                    placeholder="Enter table name"
                                )
                        
                        # PERMANENT FIX: Button moved to correct indentation level
                        # Now appears for BOTH single-sheet AND multi-sheet imports
                        if st.button("🚀 Ingest", use_container_width=True, type="primary") and proceed:
                            with st.status("📤 Preparing data for ingestion...", expanded=True) as status:
                                
                                # Handle multi-sheet imports
                                if 'multi_sheet_import' in st.session_state:
                                    multi_sheet = st.session_state.multi_sheet_import
                                    selected_sheet_names = multi_sheet['selected_sheets']
                                    
                                    status.write(f"🔄 Ingesting {len(selected_sheet_names)} sheets...")
                                    
                                    from database.sanitizer import sanitize_table_name
                                    ingest_results = {
                                        'successful': [],
                                        'failed': []
                                    }
                                    
                                    for sheet_name in selected_sheet_names:
                                        try:
                                            status.write(f"  ⏳ Processing sheet: {sheet_name}...")
                                            
                                            # Read sheet data
                                            # PERMANENT FIX #3: Double-check uploaded_file still exists before reading
                                            if uploaded_file is None:
                                                st.error("❌ Upload session lost. Please upload the file again.")
                                                break  # Exit the loop, don't try more sheets
                                            
                                            df_sheet = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                                            
                                            # Validate - use uploaded_file.name (has .xlsx extension) not sheet_name
                                            is_valid_sheet, sheet_errors, sheet_warnings = validate_csv(df_sheet, uploaded_file.name)
                                            
                                            if sheet_errors:
                                                ingest_results['failed'].append({
                                                    'sheet': sheet_name,
                                                    'reason': sheet_errors[0]
                                                })
                                                status.write(f"  ❌ {sheet_name}: Validation failed")
                                                continue
                                            
                                            # Generate table name
                                            table_name_sheet = sanitize_table_name(uploaded_file.name, sheet_name)
                                            
                                            # Ingest
                                            success, message, rows = ingest_csv_to_postgres(
                                                df_sheet, 
                                                table_name_sheet, 
                                                if_exists='replace',
                                                original_filename=uploaded_file.name,
                                                sheet_name=sheet_name
                                            )
                                            
                                            if success:
                                                ingest_results['successful'].append({
                                                    'sheet': sheet_name,
                                                    'table': table_name_sheet,
                                                    'rows': rows
                                                })
                                                status.write(f"  ✓ {sheet_name} → {table_name_sheet} ({rows:,} rows)")
                                                st.session_state.active_table = table_name_sheet
                                            else:
                                                ingest_results['failed'].append({
                                                    'sheet': sheet_name,
                                                    'reason': message
                                                })
                                                status.write(f"  ❌ {sheet_name}: {message[:60]}...")
                                        
                                        except Exception as e:
                                            ingest_results['failed'].append({
                                                'sheet': sheet_name,
                                                'reason': str(e)[:100]
                                            })
                                            status.write(f"  ❌ {sheet_name}: {str(e)[:60]}...")
                                    
                                    # Final report
                                    if ingest_results['successful']:
                                        status.update(label=f"✅ Ingested {len(ingest_results['successful'])} sheets!", state="complete")
                                        st.success(f"✨ Successfully ingested {len(ingest_results['successful'])} sheets")
                                        
                                        for succ in ingest_results['successful']:
                                            st.info(f"📊 **{succ['table']}** — {succ['rows']:,} rows")
                                        
                                        st.balloons()
                                        
                                        # Create mapping: original sheet name → sanitized table name
                                        sheet_to_table_mapping = {}
                                        dataset_tables_list = []  # NEW: List of all ingested tables for Virtual Workspace
                                        for succ in ingest_results['successful']:
                                            sheet_to_table_mapping[succ['sheet']] = succ['table']
                                            dataset_tables_list.append(succ['table'])  # NEW
                                        
                                        # Store relationships and mapping in session
                                        st.session_state.active_relationships = multi_sheet['relationships']
                                        st.session_state.sheet_to_table_mapping = sheet_to_table_mapping
                                        st.session_state.dataset_tables = dataset_tables_list  # NEW: For Virtual Workspace
                                        st.session_state.dataset_name = uploaded_file.name.split('.')[0]  # NEW: Dataset name for UI
                                        
                                        # Set active_table to first successfully ingested table (MUST be sanitized name)
                                        if ingest_results['successful']:
                                            st.session_state.active_table = ingest_results['successful'][0]['table']
                                        
                                        # Clear multi-sheet state and set the uploader lock
                                        st.session_state.last_uploaded_file = uploaded_file.name  # ← THE UPLOADER LOCK: Mark file as processed
                                        del st.session_state.multi_sheet_import
                                        import time
                                        time.sleep(1)
                                        st.rerun()
                                    
                                    if ingest_results['failed']:
                                        st.warning(f"⚠️ {len(ingest_results['failed'])} sheets failed:")
                                        for fail in ingest_results['failed']:
                                            st.text(f"  • {fail['sheet']}: {fail['reason']}")
                                
                                else:
                                    # Single sheet handling (existing logic)
                                    status.write("✓ Reading file...")
                                    status.write("✓ Normalizing column names...")
                                    status.write("⏳ Connecting to PostgreSQL...")
                                    status.write("📊 Ingesting data to database (this may take 3-5 minutes)...")
                                    
                                    success, message, rows = ingest_csv_to_postgres(
                                        df, 
                                        table_name, 
                                        if_exists='replace',
                                        original_filename=uploaded_file.name,
                                        sheet_name='Main'
                                    )
                                    
                                    if success:
                                        status.update(label="✅ Ingestion Complete!", state="complete")
                                        st.success(f"✨ Successfully ingested {rows:,} rows into '{table_name}'")
                                        st.balloons()
                                        st.session_state.last_uploaded_file = uploaded_file.name  # ← THE UPLOADER LOCK: Mark file as processed
                                        import time
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        status.update(label="❌ Ingestion Failed", state="error")
                                        st.error(f"Error: {message}")
                
                except Exception as upload_err:
                    st.text("Error: " + str(upload_err)[:100])
        
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div style="height: 8px;"></div>', unsafe_allow_html=True)
        
        # ── SECTION 4: Table Management ──
        st.markdown('<div class="section-card-blue"><div class="section-label">⚙️ Table Management</div>', unsafe_allow_html=True)
        if st.session_state.active_table and st.session_state.active_table != 'powerlifting_meets':
            with st.expander("Manage Table", expanded=False):
                st.markdown(f"""
                <div style="background: #fef2f2; border: 1px solid #fecaca; border-left: 3px solid #ef4444; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                    <div style="font-size: 0.75rem; color: #991b1b; font-weight: 600;">⚠️ Delete '{st.session_state.active_table}'</div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("🗑️ Delete Table", type="secondary", use_container_width=True):
                    st.session_state.show_delete_confirmation = True
                
                if st.session_state.get('show_delete_confirmation', False):
                    st.error("This will permanently delete the table and all data!", icon="🔴")
                    col1, col2 = st.columns(2, gap="small")
                    with col1:
                        if st.button("✅ Confirm", use_container_width=True):
                            try:
                                with st.spinner("🗑️ Connecting to database..."):
                                    db_url = os.getenv("DB_URL", "postgresql://POWERLIFTER_KUNAL:Kunal123@localhost:2003/powerlifting_db")
                                    
                                    engine = create_engine(db_url)
                                
                                with st.spinner(f"🗑️ Removing table '{st.session_state.active_table}'..."):
                                    with engine.connect() as conn:
                                        from sqlalchemy import text
                                        conn.execute(text(f'DROP TABLE IF EXISTS "{st.session_state.active_table}" CASCADE'))
                                        conn.commit()
                                    
                                    # PERMANENT FIX: Also remove from file_registry
                                    delete_from_file_registry(st.session_state.active_table)
                                
                                st.success(f"✨ Table '{st.session_state.active_table}' deleted successfully!")
                                st.session_state.show_delete_confirmation = False
                                st.session_state.active_table = None
                                import time
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as del_err:
                                st.error(f"Error: {str(del_err)[:150]}")
                                st.session_state.show_delete_confirmation = False
                    with col2:
                        if st.button("❌ Cancel", use_container_width=True):
                            st.session_state.show_delete_confirmation = False
                            st.rerun()
        else:
            st.markdown("""
            <div class="section-card">
                <div style="font-size: 0.8rem; color: #64748b; text-align: center; padding: 8px;">
                    System table • No deletion allowed
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # ── PERMANENT FIX: Database Cleanup Utilities ──
        with st.expander("🧹 Database Cleanup (Advanced)", expanded=False):
            st.markdown("""
            **Cleanup Tools:**
            - **Orphaned Entries**: Remove file_registry entries for deleted tables
            - **Old Convention Tables**: Drop tables created before the naming fix (with __ in name)
            """)
            
            cleanup_cols = st.columns(2, gap="small")
            
            with cleanup_cols[0]:
                if st.button("🧹 Clean Orphaned Entries", use_container_width=True):
                    count, deleted = cleanup_orphaned_registry_entries()
                    if count > 0:
                        st.success(f"✓ Cleaned {count} orphaned entries:\n- " + "\n- ".join(deleted[:10]))
                        if len(deleted) > 10:
                            st.caption(f"...and {len(deleted) - 10} more")
                        st.rerun()
                    else:
                        st.info("✓ No orphaned entries found")
            
            with cleanup_cols[1]:
                if st.button("⚠️ Clean Old Tables", use_container_width=True):
                    old_tables, count = identify_old_convention_tables()
                    if count > 0:
                        st.warning(f"Found {count} old-convention tables. Dropping now...")
                        dropped_count, dropped = cleanup_old_convention_tables()
                        st.success(f"✓ Dropped {dropped_count} old tables:\n- " + "\n- ".join(dropped[:10]))
                        if len(dropped) > 10:
                            st.caption(f"...and {len(dropped) - 10} more")
                        st.rerun()
                    else:
                        st.info("✓ No old-convention tables found")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # ── PERMANENT FIX #2: Cache Management Section ──
        st.markdown('<div class="section-card-blue"><div class="section-label">🧠 Query Cache Management</div>', unsafe_allow_html=True)
        
        cache_info_cols = st.columns([1, 1])
        with cache_info_cols[0]:
            # Count cached queries
            cache_count = sum(1 for key in st.session_state.keys() if key.startswith("pipeline_cache_"))
            st.metric("Cached Queries", cache_count)
        with cache_info_cols[1]:
            # Show current prompt version
            from rag_pipeline.chain import get_prompt_version_hash
            prompt_hash = get_prompt_version_hash()
            st.caption(f"Prompt v{prompt_hash}")
        
        st.caption("💡 Cache stores query results to save tokens. Clear if prompts have been updated.")
        
        if st.button("🧹 Clear Query Cache", use_container_width=True, type="secondary"):
            # Remove all pipeline cache entries from session state
            keys_to_clear = [key for key in st.session_state.keys() if key.startswith("pipeline_cache_")]
            for key in keys_to_clear:
                del st.session_state[key]
            
            st.success(f"✅ Cleared {len(keys_to_clear)} cached queries! Fresh LLM calls will be made.")
            st.info("💡 On your next query, the LLM will use the latest prompts. This is how permanent fixes take effect.")
            import time
            time.sleep(2)
            st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
        st.divider()
    
    except Exception as sidebar_err:
        st.error(f"⚠️ Sidebar Error: {str(sidebar_err)[:150]}")
        st.info("The sidebar encountered an error, but the query interface below is still available.")

# ── Profile Links (Top Right) ──────────────────────────────────────────
col_space, col_profile = st.columns([0.85, 0.15])
with col_profile:
    st.markdown("""
    <div style="display: flex; gap: 10px; justify-content: flex-end;">
        <a href="https://github.com/kunalrawal08/Text-to-SQL-RAG-Interact-with-Database-in-Natural-Language" target="_blank" style="text-decoration: none; display: inline-flex; align-items: center; gap: 5px; padding: 6px 10px; background: #1a1a1a; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;">
            <svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='white'><path d='M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v 3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z'/></svg>
            GitHub
        </a>
        <a href="https://www.linkedin.com/in/kunaldrawal/" target="_blank" style="text-decoration: none; display: inline-flex; align-items: center; gap: 5px; padding: 6px 10px; background: #0077b5; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;">
            <svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='white'><path d='M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.469v6.766z'/></svg>
            LinkedIn
        </a>
    </div>
    """, unsafe_allow_html=True)

# ── Hero Section & Query Input ────────────────────────────────────────────
# 1. The High-End Hero (Centered, Minimalist)
st.markdown("""
<div style="text-align: center; padding: 15px 20px 10px 20px;">
    <h1 style="background: linear-gradient(135deg, #0284c7, #06b6d4); color: white; padding: 12px 24px; border-radius: 16px; font-size: 24px; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 12px 0; display: inline-block; box-shadow: 0 8px 24px rgba(2, 132, 199, 0.15);">TEXT TO QUERY: INTERACT WITH DATABASE IN NATURAL LANGUAGE</h1>
</div>
""", unsafe_allow_html=True)

# Tech Stack Grid
st.markdown("""
<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px; margin: 8px auto; max-width: 100%;">
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
        <div style="padding: 6px;">
            <span style="color: #0284c7; font-weight: 700; font-size: 11px;">🗄️ DATABASE</span>
            <div style="color: #475569; font-size: 12px; margin-top: 2px; font-weight: 600;">PostgreSQL</div>
            <div style="color: #94a3b8; font-size: 10px; margin-top: 2px; line-height: 1.3;">Stores & manages relational data</div>
        </div>
        <div style="padding: 6px;">
            <span style="color: #0284c7; font-weight: 700; font-size: 11px;">🔗 ORM</span>
            <div style="color: #475569; font-size: 12px; margin-top: 2px; font-weight: 600;">SQL Alchemy</div>
            <div style="color: #94a3b8; font-size: 10px; margin-top: 2px; line-height: 1.3;">Real-time schema detection</div>
        </div>
        <div style="padding: 6px;">
            <span style="color: #0284c7; font-weight: 700; font-size: 11px;">🤖 RAG</span>
            <div style="color: #475569; font-size: 12px; margin-top: 2px; font-weight: 600;">LangChain</div>
            <div style="color: #94a3b8; font-size: 10px; margin-top: 2px; line-height: 1.3;">Retrieval → SQL → response</div>
        </div>
        <div style="padding: 6px;">
            <span style="color: #0284c7; font-weight: 700; font-size: 11px;">🧠 AI MODEL</span>
            <div style="color: #475569; font-size: 12px; margin-top: 2px; font-weight: 600;">Llama 3.3 70B</div>
            <div style="color: #94a3b8; font-size: 10px; margin-top: 2px; line-height: 1.3;">SQL generation</div>
        </div>
        <div style="padding: 6px;">
            <span style="color: #0284c7; font-weight: 700; font-size: 11px;">✨ NLP</span>
            <div style="color: #475569; font-size: 12px; margin-top: 2px; font-weight: 600;">Gemini 2.5 Flash</div>
            <div style="color: #94a3b8; font-size: 10px; margin-top: 2px; line-height: 1.3;">Human-friendly insights</div>
        </div>
        <div style="padding: 6px;">
            <span style="color: #0284c7; font-weight: 700; font-size: 11px;">📚 VECTOR DB</span>
            <div style="color: #475569; font-size: 12px; margin-top: 2px; font-weight: 600;">ChromaDB</div>
            <div style="color: #94a3b8; font-size: 10px; margin-top: 2px; line-height: 1.3;">Semantic retrieval</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align: center; padding: 8px;">
    <p style="color: #64748b; font-size: 14px; max-width: 600px; margin: 0 auto;">
        Instant retrieval of database information with natural language queries
    </p>
</div>
""", unsafe_allow_html=True)

# 2. Dynamic Context & Input Box
if st.session_state.active_table:
    col_count = len(get_dynamic_schema())
    
    # ✅ ARCHITECTURAL TWEAK #2: BI Environment Selection (Execution Gate Setup)
    st.markdown("""
<div style="margin-bottom: 12px;">
    <span style="color: #94a3b8; font-size: 12px; font-weight: 500; letter-spacing: 0.5px;">
        Select Target BI Environment
    </span>
</div>
""", unsafe_allow_html=True)

    selected_bi_tool = st.radio(
        "Target BI Environment",
        options=["Power BI (DAX)", "Tableau (Calculated Fields)"],
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state.selected_bi_tool = selected_bi_tool

    # Add subtle hint below toggle
    st.markdown("""
<div style="text-align: center; margin-bottom: 12px; font-size: 11px; color: #cbd5e1;">
    💡 Choose your BI tool's syntax for measure/field generation
</div>
""", unsafe_allow_html=True)
    
    # Styled hint above search bar
    st.markdown(f"""
    <div style="margin-bottom: 6px;">
        <span style="color: #94a3b8; font-size: 12px; font-weight: 500; letter-spacing: 0.5px;">
            Type your query • <span style="color: #0284c7; font-weight: 700;">Press Enter or Click Run</span>
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    # Search Bar + Run Button Side-by-Side (5:1 ratio)
    col_input, col_btn = st.columns([5, 1], gap="small")
    
    with col_input:
        question = st.text_input(
            "Query Input", 
            label_visibility="collapsed",
            placeholder="Select a Table to Analyze",
            help="Describe what you want to know in plain English. The AI will convert it to SQL."
        )
    
    with col_btn:
        submit = st.button("⚡ Run", use_container_width=True, type="primary", help="Execute your query")
    
    # The dynamic scope tag placed subtly UNDER the search bar
    st.markdown(f"""
    <div style="text-align: center; margin-top: 4px;">
        <span style="color: #94a3b8; font-size: 12px;">
            <span style="color: #0284c7;">🎯 Connected:</span> <b>{st.session_state.active_table}</b> ({col_count} columns)
        </span>
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("👋 **Welcome.** Please select or upload a database table in the sidebar to begin querying.")
    question = ""
    submit = False

# ── Result Section ─────────────────────────────────────────────────────────
if submit and question:
    # ✅ ARCHITECTURAL TWEAK #2: Execution Gate (Failsafe Token Protection)
    # Validates BI tool selection BEFORE Phase 1 (SQL generation) to prevent token waste
    selected_tool = st.session_state.get("selected_bi_tool")
    if not selected_tool or selected_tool is None:
        st.warning("⚠️ Please select a Target BI Environment before submitting your query.")
        st.stop()  # Exit immediately, do NOT proceed to Phase 1
    
    # If we reach here, BI tool is valid → proceed with normal execution
    st.divider()
    st.markdown("### 📊 Query Results")

    with st.status("🧠 Processing Your Question...", expanded=True) as status_container:
        try:
            from rag_pipeline.chain import generate_dax_measure, get_prompt_version_hash
            import hashlib
            
            # ============================================================================
            # STREAMLIT CACHING: Repeated queries return instantly (ZERO tokens)
            # PERMANENT FIX: Cache key now includes prompt version hash
            # When prompts.py changes → hash changes → old cache invalidated automatically
            # ============================================================================
            active_table = st.session_state.active_table  # ✅ Retrieve from session state
            
            # PERMANENT FIX #1: Include prompt version hash in cache key
            # This ensures cache is invalidated whenever prompts are updated
            prompt_version = get_prompt_version_hash()
            cache_key = hashlib.sha256(
                (question + str(active_table) + str(selected_tool) + prompt_version).encode()
            ).hexdigest()
            cache_store_key = f"pipeline_cache_{cache_key}"
            
            # Check if result is already cached
            if cache_store_key in st.session_state and st.session_state.get(cache_store_key):
                cached_data = st.session_state[cache_store_key]
                # Restore cached state and skip to display
                st.session_state.generated_sql = cached_data.get("generated_sql", "")
                st.session_state.query_result = cached_data.get("query_result", [])
                st.session_state.current_schema_context = cached_data.get("schema_context", "")
                st.session_state.orchestration_phase2_result = cached_data.get("phase2_result", {})
                
                # Setup local variables expected by the rest of the code
                generated_sql = cached_data.get("generated_sql", "")
                query_result = cached_data.get("query_result", [])
                success = True
                
                # Display metrics from cache
                pipeline_metrics = cached_data.get("pipeline_metrics", {})
                natural_answer = cached_data.get("natural_answer", "")
                executive_summary = cached_data.get("executive_summary", "")
                nlp_metrics = cached_data.get("nlp_metrics", {})
                
                status_container.update(label=f"✅ Complete (from cache)", state="complete")
                st.success("✅ Query Executed Successfully (from cache)!")
            else:
                # Step 1: Retrieve context from database
                status_container.update(label="🔍 Retrieving context from database...", state="running")
                retrieval_start = time.time()
                
                # Pass the active_table to the chain for direct schema injection
                # Check if multi-table mode with relationships
                is_multi_table = False
                relationships_for_llm = None
                dataset_tables = None  # NEW: For Virtual Workspace
                
                # NEW: Detect if we're in Workspace mode (from UI flag)
                if active_table == "MULTI_TABLE_WORKSPACE":
                    is_multi_table = True
                    # Workspace mode automatically enables multi-table with relationships
                    if hasattr(st.session_state, 'active_relationships') and st.session_state.active_relationships:
                        from database.table_resolver import resolve_relationship_sheet_names
                        relationships_for_llm = resolve_relationship_sheet_names(st.session_state.active_relationships)
                    
                    if hasattr(st.session_state, 'dataset_tables'):
                        dataset_tables = st.session_state.dataset_tables
                
                elif hasattr(st.session_state, 'active_relationships') and st.session_state.active_relationships:
                    # Traditional multi-table detection (non-workspace mode)
                    from database.table_resolver import resolve_relationship_sheet_names
                    relationships_for_llm = resolve_relationship_sheet_names(st.session_state.active_relationships)
                    is_multi_table = len(relationships_for_llm) > 0
                
                retrieval_time = time.time() - retrieval_start
                dataset_context = f"Virtual Workspace ('{st.session_state.get('dataset_name', 'Dataset')}')" if dataset_tables else f"'{active_table}'"
                status_container.write(f"✓ Retrieved schema context for {dataset_context} ({retrieval_time:.2f}s)")
                
                # Step 2: Generate SQL with FastAPI Backend
                status_container.update(label="🤖 Generating SQL with Llama 3.3 (via FastAPI)...", state="running")
                sql_start = time.time()
                
                # ============================================================================
                # CALL FASTAPI MICROSERVICE: Bypass local chain/orchestrator
                # ============================================================================
                with st.spinner("Analyzing data via FastAPI..."):
                    try:
                        payload = {
                            "question": question,
                            "active_table": st.session_state.active_table
                        }
                        api_response = requests.post(f"{API_BASE_URL}/query", json=payload, timeout=60)
                        response = api_response.json()
                        
                        if not api_response.ok:
                            raise Exception(f"API Error {api_response.status_code}: {response.get('error', 'Unknown error')}")
                        
                        # Extract Phase 1 result (SQL generation & execution)
                        sql_time = time.time() - sql_start
                        status_container.write(f"✓ Generated SQL ({sql_time:.2f}s)")
                        
                        # For now, phase2_result is None (DAX logic skipped in API mode)
                        phase2_result = None
                        st.session_state.orchestration_phase2_result = phase2_result
                        
                        # Step 3: Extract results
                        status_container.update(label="✓ Query executed on PostgreSQL", state="complete")
                        exec_time = 0.01  # Minimal time since API handled execution
                        
                        # Extract SQL query and execution result
                        generated_sql = response.get("sql", "")
                        query_result = response.get("result", [])
                        success = response.get("success", False)
                        error_msg = response.get("error", "")
                        
                        # ✅ Store results in session state for Tab 4 access
                        if success:
                            st.session_state.generated_sql = generated_sql
                            st.session_state.query_result = query_result
                            st.session_state.current_schema_context = response.get("schema_context", "")
                        
                        if not success and error_msg:
                            raise Exception(error_msg)
                        
                    except requests.exceptions.ConnectionError:
                        st.error("❌ FastAPI backend unreachable. Please ensure it's running on port 8080.")
                        raise
                    except Exception as e:
                        st.error(f"API Error: {str(e)}")
                        raise
                rows_returned = len(query_result) if isinstance(query_result, list) else 1
                status_container.write(f"✓ Executed query ({exec_time:.2f}s) • {rows_returned} rows returned")
                
                # Step 4: Format natural language response
                status_container.update(label="✨ Formatting natural language response...", state="running")
                nlp_start = time.time()
                
                natural_answer, nlp_metrics = get_natural_response(question, str(query_result))
                
                # ============================================================================
                # EXECUTIVE SUMMARY: 2-sentence business insight (OPTIONAL FEATURE)
                # ============================================================================
                executive_summary, summary_latency = get_executive_summary(question, query_result)
                
                nlp_time = time.time() - nlp_start
                status_container.write(f"✓ Formatted response ({nlp_time:.2f}s)")
                
                # Update status to complete
                total_time = retrieval_time + sql_time + exec_time + nlp_time
                status_container.update(label=f"✅ Complete ({total_time:.2f}s total)", state="complete")
                
                # Store metrics for later display
                pipeline_metrics = {
                    'retrieval_ms': round(retrieval_time * 1000, 2),
                    'sql_generation_ms': round(sql_time * 1000, 2),
                    'query_execution_ms': round(exec_time * 1000, 2),
                    'nlp_formatting_ms': round(nlp_time * 1000, 2),
                    'total_ms': round(total_time * 1000, 2),
                    'rows_returned': rows_returned,
                    'nlp_metrics': nlp_metrics,
                    'system_prompt': nlp_metrics.get('system_prompt', '')
                }
                
                # ============================================================================
                # CACHE STORAGE: Save results for repeated queries (0 token cost on cache hit)
                # ============================================================================
                st.session_state[cache_store_key] = {
                    "generated_sql": generated_sql,
                    "query_result": query_result,
                    "schema_context": response.get("schema_context", ""),
                    "phase2_result": phase2_result,
                    "pipeline_metrics": pipeline_metrics,
                    "natural_answer": natural_answer,
                    "executive_summary": executive_summary,
                    "nlp_metrics": nlp_metrics
                }
                
                st.success("✅ Query Executed Successfully!")
            
            # Display metrics in a beautiful 4-column grid
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4, gap="small")
            with metric_col1:
                st.metric("⏱️ Speed", f"{pipeline_metrics['total_ms']:.0f}ms")
            with metric_col2:
                total_tokens = nlp_metrics.get('tokens_prompt', 0) + nlp_metrics.get('tokens_response', 0)
                st.metric("🔢 Tokens", f"{total_tokens}")
            with metric_col3:
                st.metric("📊 Rows", f"{pipeline_metrics['rows_returned']}")
            with metric_col4:
                st.metric("🤖 Model", "Llama 3.3")
            
            st.info(f"🔒 Your Question: **{question}**")

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Quota" in error_msg:
                st.markdown("""
                <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);
                            border-radius:14px;padding:1.25rem 1.5rem;margin:0.5rem 0;">
                    <strong style="color:#fbbf24;font-size:0.85rem;text-transform:uppercase;
                                   letter-spacing:0.07em;">Speed Limit Reached</strong><br>
                    <span style="color:#fcd34d;font-size:0.88rem;margin-top:4px;display:block;">
                        You've hit the Gemini API free-tier limit. Please wait about 60 seconds and try again!
                    </span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.3);
                            border-radius:14px;padding:1.25rem 1.5rem;margin:0.5rem 0;">
                    <strong style="color:#f87171;font-size:0.85rem;text-transform:uppercase;
                                   letter-spacing:0.07em;">Error Occurred</strong><br>
                    <span style="color:#fca5a5;font-size:0.88rem;margin-top:4px;display:block;">
                        {error_msg}
                    </span>
                </div>
                
                <details style="background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.2);
                               border-radius:8px;padding:1rem;margin-top:1rem;">
                    <summary style="cursor:pointer;color:#f87171;font-weight:600;">📋 Error Details</summary>
                    <div style="margin-top:0.75rem;color:#fca5a5;font-family:monospace;font-size:0.85rem;white-space:pre-wrap;word-break:break-word;">
                    """ + error_msg.replace('<', '&lt;').replace('>', '&gt;') + """
                    </div>
                </details>
                """, unsafe_allow_html=True)
            st.stop()  # Exit if error occurs
        # Display results only if query succeeded
        # ✅ ARCHITECTURAL TWEAK #1: Use abstract keys (bi_code, metric_name) for frontend simplicity
        selected_tool = st.session_state.get("selected_bi_tool", "Power BI (DAX)")
        
        # Tab names differ, but response keys are ALWAYS abstract (bi_code, metric_name)
        if selected_tool == "Power BI (DAX)":
            tab_labels = ["💬  AI Insight", "🗃️  Raw Data", "💻  SQL Query", "📊 Power BI (DAX)"]
        elif selected_tool == "Tableau (Calculated Fields)":
            tab_labels = ["💬  AI Insight", "🗃️  Raw Data", "💻  SQL Query", "🔵 Tableau (Calculated Fields)"]
        else:
            tab_labels = ["💬  AI Insight", "🗃️  Raw Data", "💻  SQL Query", "❓ BI Code"]
        
        result_tab1, result_tab2, result_tab3, result_tab4 = st.tabs(tab_labels)

        with result_tab1:
            # ============================================================================
            # EXECUTIVE SUMMARY: Top-line business insight (NEW FEATURE)
            # ============================================================================
            if executive_summary:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(129, 140, 248, 0.05) 100%);
                            border-left: 4px solid #3b82f6; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem;">
                    <div style="font-weight: 600; color: #1e40af; margin-bottom: 0.5rem;">📊 Executive Summary</div>
                    <div style="color: #374151; font-size: 0.95rem; line-height: 1.6;">
                        {executive_summary}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            try:
                # Extract and highlight key values directly from the LLM response
                highlighted_answer = natural_answer
                
                # Pattern 1: Highlight all decimal/integer numbers (123.45, 100, etc.)
                number_pattern = r'\b\d+(?:\.\d+)?\b'
                highlighted_answer = re.sub(
                    number_pattern,
                    lambda m: f'<strong style="color: #ea580c; font-weight: 700;">{m.group()}</strong>',
                    highlighted_answer
                )
                
                # Pattern 2: Highlight proper nouns/names but exclude common words
                # Match patterns like "John Doe", "Taylor Schaeffer", "PowerLift" (but not "The", "And", "Is", etc.)
                name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
                # Blacklist common words (case-insensitive) that shouldn't be highlighted
                common_words = {
                    'the', 'and', 'or', 'from', 'where', 'select', 'by', 'is', 'are', 'in', 'to', 'for', 'of', 
                    'a', 'an', 'as', 'on', 'at', 'with', 'total', 'average', 'has', 'have', 'do', 'does', 'did', 
                    'not', 'can', 'could', 'will', 'would', 'should', 'all', 'each', 'every', 'some', 'if',
                    'they', 'them', 'their', 'this', 'that', 'these', 'those', 'been', 'being', 'very', 'many',
                    'much', 'more', 'such', 'just', 'only', 'first', 'second', 'third', 'last', 'now', 'then',
                    'here', 'there', 'when', 'why', 'how', 'what', 'which', 'who', 'whom', 'whose', 'been',
                    'be', 'are', 'was', 'were', 'been', 'being', 'had', 'having', 'am', 'appear', 'appearing'
                }
                highlighted_answer = re.sub(
                    name_pattern,
                    lambda m: f'<strong style="color: #ea580c; font-weight: 700;">{m.group()}</strong>' if m.group().lower() not in common_words else m.group(),
                    highlighted_answer
                )
                
                st.markdown(f"""
                <div class="insight-card">
                    <div class="insight-label">● AI-Generated Insight</div>
                    {highlighted_answer}
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.markdown(f"""
                <div class="insight-card">
                    <div class="insight-label">● Query Result</div>
                    {str(query_result)}
                </div>
                """, unsafe_allow_html=True)

        with result_tab2:
            st.markdown('<div class="query-label" style="margin-bottom:1rem;">Query Results Table</div>', unsafe_allow_html=True)
            
            try:
                # Parse query result into a proper DataFrame
                if isinstance(query_result, str):
                    # If result is a string, try to parse it as Python literal or JSON
                    try:
                        import ast
                        query_result = ast.literal_eval(query_result)
                    except:
                        query_result = [{"Result": query_result}]
                
                if isinstance(query_result, list) and query_result:
                    # Convert to DataFrame with intelligent column naming
                    if isinstance(query_result[0], (tuple, list)):
                        # Try to get actual column names from database schema
                        try:
                            schema = get_dynamic_schema()
                            column_names = [col['name'] for col in schema]
                            result_col_count = len(query_result[0])
                            
                            # Use schema columns if count matches
                            if result_col_count == len(column_names):
                                df = pd.DataFrame(query_result, columns=column_names[:result_col_count])
                            else:
                                df = pd.DataFrame(query_result)
                        except:
                            df = pd.DataFrame(query_result)
                    
                    elif isinstance(query_result[0], dict):
                        df = pd.DataFrame(query_result)
                    else:
                        df = pd.DataFrame(query_result, columns=["Value"])
                    
                    # Display record and column metadata
                    st.markdown(f"**📊 {len(df):,} records** • **{len(df.columns)} columns**")
                    
                    # Display the table with professional formatting
                    # Explicitly set all columns as TextColumn to prevent Streamlit's auto-detection
                    # from applying email or other validators to columns with special characters
                    column_config_override = {
                        col: st.column_config.TextColumn(width="medium") 
                        for col in df.columns
                    }
                    st.dataframe(
                        df, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config=column_config_override
                    )
                    
                    # Download Button
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download as CSV",
                        data=csv,
                        file_name='powerlifting_results.csv',
                        mime='text/csv',
                    )
                    
                    # Column Information Inspector (without expander to avoid nesting issues)
                    st.markdown("**ℹ️ Column Information:**", help="Details about each column")
                    col_info_data = {
                        "Column": list(df.columns),
                        "Type": [df[col].dtype.name for col in df.columns],
                        "Non-Null": [df[col].notna().sum() for col in df.columns],
                        "Sample": [str(df[col].iloc[0])[:40] if len(df) > 0 else "N/A" for col in df.columns]
                    }
                    col_info_df = pd.DataFrame(col_info_data)
                    st.dataframe(col_info_df, use_container_width=True, hide_index=True)
                    
                    # ====== CHARTING LOGIC: Works for ANY column count ======
                    
                    # CASE 1: Single-value result (1 row, 1 column) - Metric Card
                    if len(df) == 1 and len(df.columns) == 1:
                        try:
                            val = df.iloc[0, 0]
                            label = df.columns[0]
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">{val}</div>
                                <div class="metric-label">{label}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        except Exception as e:
                            st.caption("⚠️ Could not display metric card")
                    
                    # CASE 2: Single-column multi-row results (1 column, 2+ rows)
                    elif len(df.columns) == 1:
                        st.caption("ℹ️ Single-column results displayed in table above")
                    
                    # CASE 3: Multi-column results - Try charting
                    elif len(df.columns) >= 2:
                        try:
                            df_chart = df.copy()
                            # Try to convert 2nd column to numeric
                            df_chart.iloc[:, 1] = pd.to_numeric(df_chart.iloc[:, 1], errors='coerce')
                            
                            # Check if 2nd column has numeric data
                            if df_chart.iloc[:, 1].notna().any():
                                st.markdown('<div class="query-label" style="margin-top:1.5rem;">📊 Data Visualization</div>', unsafe_allow_html=True)
                                st.bar_chart(df_chart.set_index(df_chart.columns[0]))
                            else:
                                st.caption("ℹ️ Second column contains no numeric data for charting")
                        except Exception as chart_err:
                            st.caption(f"⚠️ Chart display error: {str(chart_err)[:80]}")
                else:
                    st.info("ℹ️ No results to display.")
                
            except Exception as e:
                st.error(f"Error displaying results: {str(e)}")
                st.write("Raw output:")
                st.write(query_result)

        with result_tab3:
            st.markdown('<div class="sql-label">◈ Generated SQL Query</div>', unsafe_allow_html=True)
            st.code(generated_sql, language="sql")
            
            st.divider()
            
            # Pipeline Metrics Section
            st.markdown("### 📊 Pipeline Metrics & Timing")
            metric_cols = st.columns(4, gap="small")
            with metric_cols[0]:
                st.caption("**Retrieval**")
                st.caption(f"{pipeline_metrics['retrieval_ms']:.0f}ms")
            with metric_cols[1]:
                st.caption("**SQL Gen**")
                st.caption(f"{pipeline_metrics['sql_generation_ms']:.0f}ms")
            with metric_cols[2]:
                st.caption("**Execution**")
                st.caption(f"{pipeline_metrics['query_execution_ms']:.0f}ms")
            with metric_cols[3]:
                st.caption("**NLP**")
                st.caption(f"{pipeline_metrics['nlp_formatting_ms']:.0f}ms")
            
            st.divider()
            
            # Token Economics
            st.markdown("### 🔢 Token Economics")
            token_cols = st.columns(3, gap="small")
            with token_cols[0]:
                st.metric("Prompt", nlp_metrics.get('tokens_prompt', 'N/A'))
            with token_cols[1]:
                st.metric("Response", nlp_metrics.get('tokens_response', 'N/A'))
            with token_cols[2]:
                total_tokens = nlp_metrics.get('tokens_prompt', 0) + nlp_metrics.get('tokens_response', 0)
                st.metric("Total", total_tokens)
            
            st.divider()
            
            # System Prompt
            st.markdown("### 🤖 System Prompt Used")
            st.code(pipeline_metrics.get('system_prompt', 'N/A'), language="text")
            st.caption("This is the exact prompt sent to Llama 3.3 for response generation")
            
            st.divider()
            
            st.markdown("""
                <div style="margin-top:1.5rem;">
                    <p style="color: #64748b; font-size: 0.9rem; line-height: 1.6;">
                    <strong>RAG Pipeline Architecture:</strong>
                    </p>
                    <ul style="color: #64748b; font-size: 0.9rem;">
                        <li>📊 <strong>Dynamic Schema:</strong> Retrieved from PostgreSQL in real-time</li>
                        <li>🔍 <strong>AI Dictionary:</strong> ChromaDB retrieves semantically similar examples</li>
                        <li>🤖 <strong>SQL Generation:</strong> Llama 3.3 70B generates contextual SQL</li>
                        <li>🗄️ <strong>Query Execution:</strong> Native PostgreSQL execution with error handling</li>
                        <li>✨ <strong>NLP Formatting:</strong> Llama converts results to human-friendly text</li>
                    </ul>
                </div>
            """, unsafe_allow_html=True)
        
        # ============================================================================
        # TAB 4: BI CODE (DAX / Tableau Calculated Field)
        # ============================================================================
        with result_tab4:
            if not success:
                st.info("⏳ Awaiting valid SQL logic for translation.")
            else:
                selected_tool = st.session_state.get("selected_bi_tool", "Power BI (DAX)")
                
                # Retrieve generated SQL and schema context from Phase 1
                generated_sql = st.session_state.get("generated_sql", "")
                query_result = st.session_state.get("query_result", [])
                schema_context = st.session_state.get("current_schema_context", "")
                
                if not generated_sql or not schema_context:
                    st.warning("⚠️ Missing SQL or schema context from Phase 1. Please re-run the query.")
                else:
                    # Determine which BI tool to use
                    if "Tableau" in selected_tool:
                        # TABLEAU GENERATION
                        with st.spinner("🔄 Generating Tableau calculated field..."):
                            try:
                                payload = {
                                    "question": question,
                                    "sql_query": generated_sql,
                                    "schema_context": schema_context,
                                    "sql_result_snapshot": str(query_result) if query_result else "",
                                    "insight": ""
                                }
                                bi_response = requests.post(f"{API_BASE_URL}/tableau", json=payload, timeout=60)
                                bi_data = bi_response.json()
                                
                                if not bi_response.ok:
                                    st.error(f"❌ Tableau Generation Failed: {bi_data.get('detail', 'Unknown error')}")
                                elif bi_data.get("success"):
                                    st.markdown('<div class="sql-label">◈ Generated Tableau Field</div>', unsafe_allow_html=True)
                                    st.code(bi_data["bi_code"], language="sql")
                                    
                                    if bi_data.get("metric_name"):
                                        st.markdown("### 📋 Suggested Field Name")
                                        st.code(bi_data["metric_name"], language="text")
                                        st.caption(f"👉 Copy this name to paste into {selected_tool}")
                                    
                                    if bi_data.get("usage_note"):
                                        st.caption(f"💡 {bi_data['usage_note']}")
                                    
                                    st.divider()
                                    
                                    # QA Status
                                    st.markdown("### 🛡️ Data Integrity Report")
                                    qa_status = bi_data.get("qa_status", "Verification Pending")
                                    qa_passed = bi_data.get("qa_passed", False)
                                    
                                    if "Verification Pending" in qa_status or "disabled" in qa_status.lower():
                                        st.info(f"ℹ️ {qa_status}")
                                    elif qa_passed:
                                        st.success(f"✅ Code Generated")
                                    else:
                                        st.info(f"ℹ️ {qa_status}")
                                    
                                    st.metric("Verification Latency", f"{bi_data.get('qa_time_ms', 0)}ms")
                                    
                                    st.divider()
                                    
                                    # Metrics
                                    st.markdown("### 📊 Generation Metrics")
                                    metric_cols = st.columns(4, gap="small")
                                    with metric_cols[0]:
                                        st.caption("**Gen Time**")
                                        st.caption(f"{bi_data.get('generation_ms', 0)}ms")
                                    with metric_cols[1]:
                                        st.caption("**Prompt Tokens**")
                                        st.caption(str(bi_data.get('tokens_prompt', 0)))
                                    with metric_cols[2]:
                                        st.caption("**Response Tokens**")
                                        st.caption(str(bi_data.get('tokens_response', 0)))
                                    with metric_cols[3]:
                                        st.caption("**Status**")
                                        st.caption("✅ Complete")
                                else:
                                    st.error(f"❌ Tableau Generation Failed: {bi_data.get('error', 'Unknown error')}")
                            
                            except requests.exceptions.Timeout:
                                st.error("❌ Tableau generation timed out (exceeded 60 seconds)")
                            except Exception as e:
                                st.error(f"❌ Tableau API Error: {str(e)}")
                    
                    else:
                        # DAX GENERATION (Default)
                        with st.spinner("🔄 Generating Power BI DAX measure..."):
                            try:
                                payload = {
                                    "question": question,
                                    "sql_query": generated_sql,
                                    "schema_context": schema_context,
                                    "sql_result_snapshot": str(query_result) if query_result else "",
                                    "insight": ""
                                }
                                bi_response = requests.post(f"{API_BASE_URL}/dax", json=payload, timeout=60)
                                bi_data = bi_response.json()
                                
                                if not bi_response.ok:
                                    st.error(f"❌ DAX Generation Failed: {bi_data.get('detail', 'Unknown error')}")
                                elif bi_data.get("success"):
                                    st.markdown('<div class="sql-label">◈ Generated DAX Measure</div>', unsafe_allow_html=True)
                                    st.code(bi_data["bi_code"], language="dax")
                                    
                                    if bi_data.get("metric_name"):
                                        st.markdown("### 📋 Suggested Measure Name")
                                        st.code(bi_data["metric_name"], language="text")
                                        st.caption(f"👉 Copy this name to paste into {selected_tool}")
                                    
                                    if bi_data.get("usage_note"):
                                        st.caption(f"💡 {bi_data['usage_note']}")
                                    
                                    st.divider()
                                    
                                    # QA Status
                                    st.markdown("### 🛡️ Data Integrity Report")
                                    qa_status = bi_data.get("qa_status", "Verification Pending")
                                    qa_passed = bi_data.get("qa_passed", False)
                                    
                                    if "Verification Pending" in qa_status or "disabled" in qa_status.lower():
                                        st.info(f"ℹ️ {qa_status}")
                                    elif qa_passed:
                                        st.success(f"✅ Code Generated")
                                    else:
                                        st.info(f"ℹ️ {qa_status}")
                                    
                                    st.metric("Verification Latency", f"{bi_data.get('qa_time_ms', 0)}ms")
                                    
                                    st.divider()
                                    
                                    # Metrics
                                    st.markdown("### 📊 Generation Metrics")
                                    metric_cols = st.columns(4, gap="small")
                                    with metric_cols[0]:
                                        st.caption("**Gen Time**")
                                        st.caption(f"{bi_data.get('generation_ms', 0)}ms")
                                    with metric_cols[1]:
                                        st.caption("**Prompt Tokens**")
                                        st.caption(str(bi_data.get('tokens_prompt', 0)))
                                    with metric_cols[2]:
                                        st.caption("**Response Tokens**")
                                        st.caption(str(bi_data.get('tokens_response', 0)))
                                    with metric_cols[3]:
                                        st.caption("**Status**")
                                        st.caption("✅ Complete")
                                else:
                                    st.error(f"❌ DAX Generation Failed: {bi_data.get('error', 'Unknown error')}")
                            
                            except requests.exceptions.Timeout:
                                st.error("❌ DAX generation timed out (exceeded 60 seconds)")
                            except Exception as e:
                                st.error(f"❌ DAX API Error: {str(e)}")

elif submit and not question:
    st.error("🔴 **Empty Question**: Please enter a question before clicking Run Query.")
    st.info("👇 Try one of the example queries above, or ask your own question about the powerlifting data.")
