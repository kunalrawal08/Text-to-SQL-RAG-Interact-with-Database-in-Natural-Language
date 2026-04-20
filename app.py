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

def get_dynamic_schema():
    """Fetch the actual database schema from PostgreSQL."""
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    engine = create_engine(db_url)
    db_inspector = inspect(engine)
    columns = db_inspector.get_columns('powerlifting_meets')
    return columns

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
        from database.get_schema import get_all_tables, get_table_schema, format_column_type
        
        # Initialize session state for active table
        if 'active_table' not in st.session_state:
            tables = get_all_tables()
            if 'powerlifting_meets' in tables:
                st.session_state.active_table = 'powerlifting_meets'
            elif tables:
                st.session_state.active_table = tables[0]
            else:
                st.session_state.active_table = None
        
        st.markdown('<div class="section-card-blue"><div class="section-label">📊 Active Database</div>', unsafe_allow_html=True)
        
        tables = get_all_tables()
        if tables:
            selected_table = st.selectbox(
                "Database Table",
                options=tables,
                index=tables.index(st.session_state.active_table) if st.session_state.active_table in tables else 0,
                help="Select which table to query",
                key="table_selector",
                label_visibility="collapsed"
            )
            st.session_state.active_table = selected_table
            
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
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # ── SECTION 2: Schema & Data Explorers ──
        if tables and schema_info.get('success', False):
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
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                from database.ingest_csv import validate_csv, ingest_csv_to_postgres
                
                is_valid, errors, warnings = validate_csv(df, uploaded_file.name)
                
                if errors:
                    st.error("Validation Failed")
                    for error in errors:
                        st.text(error)
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
                    
                    if st.button("🚀 Ingest", use_container_width=True, type="primary") and proceed:
                        with st.status("📤 Preparing data for ingestion...", expanded=True) as status:
                            status.write("✓ Reading CSV file...")
                            status.write("✓ Normalizing column names...")
                            status.write("⏳ Connecting to PostgreSQL...")
                            status.write("📊 Ingesting data to database (this may take 3-5 minutes)...")
                            
                            success, message, rows = ingest_csv_to_postgres(df, table_name, if_exists='replace')
                            
                            if success:
                                status.update(label="✅ Ingestion Complete!", state="complete")
                                st.success(f"✨ Successfully ingested {rows:,} rows into '{table_name}'")
                                st.balloons()
                                import time
                                time.sleep(2)
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
                                    db_user = os.getenv("DB_USER")
                                    db_password = os.getenv("DB_PASSWORD")
                                    db_host = os.getenv("DB_HOST")
                                    db_port = os.getenv("DB_PORT")
                                    db_name = os.getenv("DB_NAME")
                                    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
                                    
                                    engine = create_engine(db_url)
                                
                                with st.spinner(f"🗑️ Removing table '{st.session_state.active_table}'..."):
                                    with engine.connect() as conn:
                                        from sqlalchemy import text
                                        conn.execute(text(f'DROP TABLE IF EXISTS "{st.session_state.active_table}" CASCADE'))
                                        conn.commit()
                                
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
    st.divider()
    st.markdown("### 📊 Query Results")

    with st.status("🧠 Processing Your Question...", expanded=True) as status_container:
        try:
            # Step 1: Retrieve context from database
            status_container.update(label="🔍 Retrieving context from database...", state="running")
            retrieval_start = time.time()
            
            from rag_pipeline.chain import get_sql_chain
            
            # Pass the active_table to the chain for direct schema injection (Phase 3)
            active_table = st.session_state.get('active_table', 'powerlifting_meets')
            chain = get_sql_chain(active_table=active_table)
            
            retrieval_time = time.time() - retrieval_start
            status_container.write(f"✓ Retrieved schema context for '{active_table}' ({retrieval_time:.2f}s)")
            
            # Step 2: Generate SQL with LLM
            status_container.update(label="🤖 Generating SQL with Llama 3.3...", state="running")
            sql_start = time.time()
            
            response = chain.invoke({"question": question})
            
            sql_time = time.time() - sql_start
            status_container.write(f"✓ Generated SQL ({sql_time:.2f}s)")
            
            # Step 3: Execute query
            status_container.update(label="🗄️ Executing query on PostgreSQL...", state="running")
            exec_start = time.time()
            
            # Extract SQL query and execution result
            generated_sql = response.get("sql", "")
            query_result = response.get("result", [])
            success = response.get("success", False)
            error_msg = response.get("error", "")
            
            if not success and error_msg:
                raise Exception(error_msg)
            
            exec_time = time.time() - exec_start
            rows_returned = len(query_result) if isinstance(query_result, list) else 1
            status_container.write(f"✓ Executed query ({exec_time:.2f}s) • {rows_returned} rows returned")
            
            # Step 4: Format natural language response
            status_container.update(label="✨ Formatting natural language response...", state="running")
            nlp_start = time.time()
            
            natural_answer, nlp_metrics = get_natural_response(question, str(query_result))
            
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
        result_tab1, result_tab2, result_tab3 = st.tabs(["💬  AI Insight", "🗃️  Raw Data", "💻  SQL Query"])

        with result_tab1:
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

elif submit and not question:
    st.error("🔴 **Empty Question**: Please enter a question before clicking Run Query.")
    st.info("👇 Try one of the example queries above, or ask your own question about the powerlifting data.")
