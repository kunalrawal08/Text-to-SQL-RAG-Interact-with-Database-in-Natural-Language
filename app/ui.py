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
import google.generativeai as genai
from sqlalchemy import create_engine, inspect
from langchain_community.utilities import SQLDatabase

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PowerLift AI",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Load CSS ───────────────────────────────────────────────────────────────────
css_path = os.path.join(os.path.dirname(__file__), "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as css_file:
        st.markdown(f"<style>{css_file.read()}</style>", unsafe_allow_html=True)

# ── PHASE 1: Environment Validation ────────────────────────────────────────────
def validate_environment():
    """Validate all required environment variables at startup."""
    if 'env_validated' not in st.session_state:
        required_vars = {
            'GOOGLE_API_KEY': 'Google Gemini API Key',
            'DB_USER': 'Database User',
            'DB_PASSWORD': 'Database Password',
            'DB_HOST': 'Database Host',
            'DB_PORT': 'Database Port',
            'DB_NAME': 'Database Name',
        }
        
        missing_vars = []
        for var, desc in required_vars.items():
            if not os.getenv(var):
                missing_vars.append(f"  • {var} ({desc})")
        
        if missing_vars:
            st.session_state.env_error = "\n".join(missing_vars)
            st.session_state.env_validated = False
            return False
        
        # Configure Gemini API only once per session
        try:
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            st.session_state.env_validated = True
            st.session_state.env_error = None
            return True
        except Exception as e:
            st.session_state.env_error = f"Failed to configure Gemini API: {str(e)}"
            st.session_state.env_validated = False
            return False
    
    return st.session_state.env_validated

# ── Setup ──────────────────────────────────────────────────────────────────────
env_valid = validate_environment()

def get_natural_response(question, query_results):
    """Convert raw SQL results into natural language using Gemini."""
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    You are a helpful AI data assistant specializing in powerlifting data.
    The user asked: "{question}"
    The SQL database returned these results: {query_results}
    
    Formulate a polite, conversational, natural language sentence answering the user's question.
    Do NOT mention SQL, databases, tuples, or technical details. Be direct and human-friendly.
    """
    response = model.generate_content(prompt)
    return response.text

# ── PHASE 2: Database Caching & Enhanced Error Handling ────────────────────────
@st.cache_resource
def get_dynamic_schema():
    """Fetch the actual database schema from PostgreSQL. Cached for session lifetime."""
    try:
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT")
        db_name = os.getenv("DB_NAME")
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        engine = create_engine(db_url)
        db_inspector = inspect(engine)
        columns = db_inspector.get_columns('powerlifting_meets')
        return columns, None  # Return columns + no error
    except ConnectionRefusedError:
        return None, "🔴 **Database Connection Failed**: PostgreSQL server is not responding. Please check if the database is running at " + os.getenv("DB_HOST") + ":" + str(os.getenv("DB_PORT", 5432))
    except Exception as e:
        error_str = str(e)
        if "authentication failed" in error_str.lower() or "password" in error_str.lower():
            return None, "🔴 **Authentication Error**: Database connection failed. Check DB_USER and DB_PASSWORD in .env"
        elif "does not exist" in error_str.lower():
            return None, "🔴 **Table Not Found**: The 'powerlifting_meets' table doesn't exist in the database."
        else:
            return None, f"🔴 **Database Error**: {error_str}"

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Show environment error if validation failed
    if not env_valid:
        st.error("🔴 **Environment Configuration Error**")
        st.write("Missing or invalid environment variables:")
        st.write(st.session_state.get('env_error', 'Unknown error'))
        st.info("Please check your .env file and ensure all required variables are set.")
        st.stop()
    
    st.markdown("""
    <div class="sidebar-brand">
        <div style="width: 38px; height: 38px; background: #ea580c; color: white; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">🏋️</div>
        <div>
            <div class="sidebar-brand-name">PowerLift AI</div>
            <div class="sidebar-brand-tagline">RAG-Powered Analytics</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('**Database Schema**')
    st.markdown('📊 **powerlifting_meets**')

    schema_cols, schema_error = get_dynamic_schema()
    
    if schema_error:
        st.markdown(schema_error)
        if st.button("🔄 Retry Connection", use_container_width=True):
            st.cache_resource.clear()
            st.rerun()
    elif schema_cols:
        with st.expander(f"📋 View All {len(schema_cols)} Columns", expanded=True):
            for col in schema_cols:
                col_name = col['name']
                col_type = str(col['type']).split('(')[0]
                st.caption(f"`{col_name}` — {col_type}")

    st.divider()

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-container">
    <div class="hero-badge">✦ RAG-Powered · Natural Language to SQL</div>
    <h1 class="hero-title">Powerlifting Analytics AI</h1>
    <p class="hero-subtitle">
        Ask natural language questions about powerlifting data — PowerLift AI converts them to SQL,
        retrieves results from PostgreSQL, and delivers human-friendly insights powered by Gemini.
    </p>
    <div class="hero-stats">
        <div class="stat-pill">
            <span class="stat-number">30+</span>
            <span class="stat-label">Columns Available</span>
        </div>
        <div class="stat-pill">
            <span class="stat-number">Gemini 1.5</span>
            <span class="stat-label">AI Engine</span>
        </div>
        <div class="stat-pill">
            <span class="stat-number">PostgreSQL</span>
            <span class="stat-label">Database</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── PHASE 3: Clickable Example Queries ────────────────────────────────────────
st.divider()
st.markdown("### 💡 Try These Queries")

example_cols = st.columns(4, gap="medium")
examples = [
    ("📊 Avg Total", "What is the average total for female lifters in the 63kg class?"),
    ("💪 Max Deadlift", "Who has the highest raw deadlift?"),
    ("🏆 Top Lifters", "Top 5 male lifters by total"),
    ("⚙️ Equipment", "Average squat by equipment type"),
]

for idx, (icon_label, example) in enumerate(examples):
    with example_cols[idx]:
        if st.button(f"{icon_label}", key=f"example_{idx}", use_container_width=True, help=example):
            st.session_state.selected_example = example
            st.rerun()

# ── PHASE 3 & 6: Search Bar with Input Validation & UI Polish ────────────────
st.divider()
st.markdown("### 🔍 Ask Your Question")

# Pre-fill from example if clicked
initial_question = st.session_state.get('selected_example', '')

col_input, col_btn = st.columns([5, 1], gap="small")
with col_input:
    question = st.text_input(
        label="query_input",
        placeholder="E.g., What's the average deadlift for males over 100kg?",
        value=initial_question,
        max_chars=500,
        label_visibility="collapsed",
    )
    # Show character count
    char_count = len(question)
    if char_count > 400:
        st.caption(f"⚠️ {char_count}/500 characters (getting close to limit)")
    elif char_count > 0:
        st.caption(f"📝 {char_count}/500 characters")

with col_btn:
    submit = st.button("⚡ Run", use_container_width=True, type="primary", help="Execute your natural language query")

# Clear example selection after use
if question and initial_question and question == initial_question:
    st.session_state.selected_example = ''

# ── PHASE 4: Multi-Step Progress & Metrics Display ────────────────────────────
if submit and question:
    st.divider()
    
    import time
    query_start_time = time.time()

    try:
        with st.status("🔄 Processing your query...", expanded=True) as status:
            # Step 1: SQL Generation
            st.write("📝 Step 1: Converting your question to SQL...")
            from rag_pipeline.chain import get_sql_chain
            chain = get_sql_chain()
            
            # Step 2: Query Execution
            st.write("🗄️ Step 2: Executing query on database...")
            result = chain.invoke({"question": question})
            
            # Step 3: AI Response Generation
            st.write("🤖 Step 3: Generating AI insight...")
            
            query_duration = time.time() - query_start_time
            status.update(label="✅ Query completed!", state="complete")
        
        # Display metrics in a beautiful 4-column grid
        col_metrics1, col_metrics2, col_metrics3, col_metrics4 = st.columns(4, gap="medium")
        with col_metrics1:
            st.metric("⏱️ Speed", f"{query_duration:.2f}s")
        with col_metrics2:
            try:
                row_count = len(result) if isinstance(result, (list, tuple)) else 1
                st.metric("📊 Rows", row_count)
            except:
                st.metric("📊 Rows", "N/A")
        with col_metrics3:
            st.metric("🤖 Model", "Gemini 1.5")
        with col_metrics4:
            st.metric("✅ Status", "Success")
        
        st.divider()
        
        # PHASE 6: Improved Tab Naming
        tab1, tab2, tab3 = st.tabs(["💬  AI Insight", "🗃️  Raw Data", "💻  SQL Query"])

        with tab1:
            try:
                natural_answer = get_natural_response(question, str(result))
                st.markdown(f"""
                <div class="insight-card">
                    <div class="insight-label">● AI-Generated Insight</div>
                    {natural_answer}
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.write("Result:", result)

        with tab2:
            st.write(result)
            
            # Try to convert to DataFrame if it's a list of tuples
            try:
                if isinstance(result, list) and result and isinstance(result[0], tuple):
                    df = pd.DataFrame(result)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Data as CSV",
                        data=csv,
                        file_name='powerlifting_results.csv',
                        mime='text/csv',
                    )
            except Exception:
                pass

        with tab3:
            st.write("**Question asked:**", question)
            st.write("**Raw result:**", result)

    except Exception as e:
        # PHASE 5: Enhanced Exception Handling with Specific Error Types
        error_msg = str(e)
        
        # Rate limit detection
        if "429" in error_msg or "Quota" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            st.error("🔴 **API Rate Limit Exceeded**: Google Gemini API quota has been reached.")
            st.info("**Action**: Wait 60 seconds and try again, or simplify your question to use fewer API calls.")
            if st.button("🔄 Retry", use_container_width=True):
                st.rerun()
        # Connection errors
        elif "connection" in error_msg.lower() or "could not connect" in error_msg.lower():
            st.error("🔴 **Database Connection Failed**: Could not connect to PostgreSQL.")
            st.info("**Action**: Check if the database is running and your connection settings (DB_HOST, DB_PORT) are correct.")
        # Authentication errors
        elif "authentication" in error_msg.lower() or "permission denied" in error_msg.lower():
            st.error("🔴 **Authentication Failed**: Database credentials are incorrect.")
            st.info("**Action**: Verify your DB_USER and DB_PASSWORD in the .env file.")
        # Timeout errors
        elif "timeout" in error_msg.lower():
            st.error("🔴 **Query Timeout**: The database took longer than expected.")
            st.info("**Action**: Try simplifying your question or breaking it into smaller queries.")
        # Generic fallback
        else:
            st.error("🔴 **Query Error**: An unexpected error occurred.")
            st.info(f"**Technical Details**: {error_msg[:200]}...") if len(error_msg) > 200 else st.info(f"**Technical Details**: {error_msg}")
            with st.expander("📋 View Full Error Details"):
                st.code(error_msg, language="text")

elif submit and not question:
    st.error("🔴 **Empty Question**: Please enter a question before clicking Run Query.")
    st.info("👇 Try one of the example queries above, or ask your own question about the powerlifting data.")

# ── Footer ─────────────────────────────────────────────────────────────────────
if not submit or not question:
    st.divider()
    st.markdown("""
    <div class="app-footer" style="text-align: center; padding: 20px; color: #64748b; font-size: 0.85rem;">
        <span>PowerLift AI · RAG-Powered Analytics · Built with Streamlit & LangChain · Powered by Gemini · © 2026</span>
    </div>
    """, unsafe_allow_html=True)
