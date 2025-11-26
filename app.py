import streamlit as st
import pandas as pd
from utils import configure_ai, extract_text_from_file, analyze_batch_candidate, generate_recruitment_email, send_real_email

# --- PAGE CONFIG ---
st.set_page_config(page_title="Med-Recruit AI", page_icon="🏥", layout="wide")

if "batch_data" not in st.session_state: st.session_state["batch_data"] = [] 
if "jd_text" not in st.session_state: st.session_state["jd_text"] = ""
if "role_type" not in st.session_state: st.session_state["role_type"] = "🧪 PI / Postdoc"

# --- BUSINESS CSS (Professional UI) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F1F5F9; }
    
    /* Card Styling */
    .stContainer {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border: 1px solid #E2E8F0;
        margin-bottom: 20px;
    }
    
    /* Header Styling */
    h1, h2, h3 { color: #0F172A; font-weight: 700; }
    .stMetricLabel { font-size: 0.9rem; color: #64748B; }
    .stMetricValue { font-size: 1.8rem; color: #0F172A; }
    
    /* Buttons */
    .stButton>button { 
        background-color: #0F766E; 
        color: white; 
        border-radius: 8px; 
        border: none; 
        height: 45px;
        font-weight: 600;
    }
    .stButton>button:hover { background-color: #0D9488; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🏥 Med-Recruit <span style='font-size:0.8em; color:gray'>Ent</span>", unsafe_allow_html=True)
    page = st.radio("Navigation", ["📊 Talent Evaluation", "📧 Outreach"], index=0)
    st.divider()
    api_key = st.text_input("Google API Key", type="password")
    if api_key: configure_ai(api_key)
    st.success(f"loaded {len(st.session_state['batch_data'])} candidates")

# =========================================================
# VIEW 1: EVALUATION (Multi-Agent)
# =========================================================
if page == "📊 Talent Evaluation":
    st.title("Talent Evaluation Dashboard")
    
    # --- INPUT CARD ---
    with st.container():
        st.subheader("⚙️ Hiring Configuration")
        st.session_state["role_type"] = st.radio("Track:", ["🧪 PI / Postdoc", "🧬 Research Assistant (RA)", "💼 Administrative"], horizontal=True)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.session_state["jd_text"] = st.text_area("Job Requirements", value=st.session_state["jd_text"], height=100, placeholder="Paste JD here...")
            must_haves = st.text_input("Key Filters (Must Haves)")
        with c2:
            st.write("Upload Candidates")
            files = st.file_uploader("Upload CVs", accept_multiple_files=True, label_visibility="collapsed")
            if st.button("Start 3-Agent Analysis 🚀", use_container_width=True):
                if api_key and files:
                    st.session_state["batch_data"] = []
                    bar = st.progress(0)
                    for i, f in enumerate(files):
                        with st.spinner(f"Agents analyzing {f.name}..."):
                            res = analyze_batch_candidate(extract_text_from_file(f), st.session_state["jd_text"], must_haves, st.session_state["role_type"])
                            res['file_name'] = f.name
                            res['role_type'] = st.session_state["role_type"]
                            st.session_state["batch_data"].append(res)
                        bar.progress((i+1)/len(files))
                    st.rerun()

    if st.session_state["batch_data"]:
        # --- RANKING CARD ---
        with st.container():
            df_data = [{"Name": c.get('name'), "Score": c.get('fit_score'), "Email": c.get('email')} for c in st.session_state["batch_data"]]
            df = pd.DataFrame(df_data).sort_values(by="Score", ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True, column_config={"Score": st.column_config.ProgressColumn("Fit", format="%d", min_value=0, max_value=100)})
        
        # --- DEEP DIVE CARD ---
        st.subheader("🔍 Deep Profile Analysis")
        
        sel = st.selectbox("Select Candidate", df['Name'].tolist())
        cand = next(c for c in st.session_state["batch_data"] if c.get('name') == sel)
        
        # Profile Header Card
        with st.container():
            c1, c2 = st.columns([3,1])
            with c1: 
                st.markdown(f"## {cand.get('name')}")
                st.caption(f"Role: {cand.get('role_type')} | Email: {cand.get('email')}")
            with c2: 
                st.metric("Final Score", cand.get('fit_score'))

        # Risk Analysis (The Critic)
        with st.container():
            st.markdown("#### 🕵️ Agent 2: Risk Analysis Report")
            critique = cand.get('critique_notes', 'No risks flagged.')
            if "No major red flags" in critique:
                st.success(critique)
            else:
                # Use st.error for the red box effect (Clean UI)
                st.error(critique)

        # Summary & Details
        with st.container():
            st.markdown("#### 📝 Executive Summary")
            st.write(cand.get('summary'))
            
            c1, c2 = st.columns(2)
            with c1: 
                st.markdown("**✅ Strengths**")
                for s in cand.get('strengths', []): st.info(s, icon="✅")
            with c2: 
                st.markdown("**⚠️ Gaps**")
                for g in cand.get('gaps', []): st.warning(g, icon="⚠️")

# =========================================================
# VIEW 2: OUTREACH
# =========================================================
elif page == "📧 Outreach":
    st.title("Smart Outreach")
    
    with st.container():
        st.subheader("👤 Sender Profile")
        c1, c2, c3 = st.columns(3)
        with c1: sender_name = st.text_input("Name", value="Hongli Ding")
        with c2: sender_title = st.text_input("Title", value="TA Specialist")
        with c3: sender_org = st.text_input("Org", value="Zhejiang Univ. Medical Center")
        
        with st.expander("🔐 SMTP Credentials"):
            sender_email = st.text_input("Email")
            sender_password = st.text_input("App Password", type="password")

    if st.session_state["batch_data"]:
        with st.container():
            st.subheader("✉️ Draft Email")
            names = [c.get('name') for c in st.session_state["batch_data"]]
            sel = st.selectbox("Select Candidate", names)
            cand = next(c for c in st.session_state["batch_data"] if c.get('name') == sel)
            
            if st.button("✨ Generate Draft (Double-Check Agent)"):
                with st.spinner("Drafting..."):
                    sender_info = {"name": sender_name, "title": sender_title, "org": sender_org}
                    st.session_state['draft'] = generate_recruitment_email(cand, sender_info, cand.get('role_type', 'Role'))
            
            if 'draft' in st.session_state:
                subj = st.text_input("Subject", value=f"Opportunity at {sender_org}")
                recip = st.text_input("Recipient Email", value=cand.get('email', ''))
                body = st.text_area("Body", st.session_state['draft'], height=300)
                
                if st.button("Send 🚀", type="primary"):
                    if not sender_email or not sender_password:
                        st.error("Missing SMTP credentials.")
                    else:
                        ok, msg = send_real_email(sender_email, sender_password, recip, subj, body)
                        if ok: st.success("Sent!")
                        else: st.error(msg)

