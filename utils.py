import streamlit as st
import pandas as pd
from utils import configure_ai, extract_text_from_file, analyze_batch_candidate, generate_recruitment_email, send_real_email

# --- PAGE CONFIG ---
st.set_page_config(page_title="Med-Recruit AI", page_icon="🏥", layout="wide")

if "batch_data" not in st.session_state: st.session_state["batch_data"] = [] 
if "jd_text" not in st.session_state: st.session_state["jd_text"] = ""
if "role_type" not in st.session_state: st.session_state["role_type"] = "🧪 PI / Postdoc"

# --- BUSINESS CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }
    
    /* Card Styling */
    .stContainer {
        background-color: white;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #E2E8F0;
        margin-bottom: 20px;
    }
    
    /* Metrics */
    .metric-card {
        background: #F1F5F9;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #CBD5E1;
    }
    .metric-val { font-size: 1.5rem; font-weight: 700; color: #0F172A; }
    .metric-lbl { font-size: 0.85rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; }

    /* Tags */
    .paper-tag { background: #EEF2FF; color: #4F46E5; padding: 4px 10px; border-radius: 6px; font-size: 0.9em; border: 1px solid #C7D2FE;}
    .skill-tag { background: #ECFDF5; color: #059669; padding: 4px 10px; border-radius: 6px; font-size: 0.9em; border: 1px solid #A7F3D0; margin-right: 5px;}
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🏥 Med-Recruit <span style='font-size:0.8em; color:gray'>Pro</span>", unsafe_allow_html=True)
    page = st.radio("Navigation", ["📊 Talent Evaluation", "📧 Outreach"], index=0)
    st.divider()
    api_key = st.text_input("Google API Key", type="password")
    if api_key: configure_ai(api_key)
    st.success(f"Candidates Loaded: {len(st.session_state['batch_data'])}")

# =========================================================
# VIEW 1: EVALUATION (Dynamic Dashboard)
# =========================================================
if page == "📊 Talent Evaluation":
    st.title("Talent Evaluation Dashboard")
    
    # --- 1. CONFIG CARD ---
    with st.container():
        st.subheader("⚙️ Hiring Configuration")
        # Store previous role to detect change
        prev_role = st.session_state.get("role_type")
        st.session_state["role_type"] = st.radio("Track:", ["🧪 PI / Postdoc", "🧬 Research Assistant (RA)", "💼 Administrative"], horizontal=True)
        
        # Clear data if role changes to avoid mixing tables
        if prev_role != st.session_state["role_type"] and len(st.session_state["batch_data"]) > 0:
            st.warning("⚠️ Switching tracks will clear current results.")
            if st.button("Confirm Switch & Clear Data"):
                st.session_state["batch_data"] = []
                st.rerun()

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
                        with st.spinner(f"Analyzing {f.name}..."):
                            res = analyze_batch_candidate(extract_text_from_file(f), st.session_state["jd_text"], must_haves, st.session_state["role_type"])
                            res['file_name'] = f.name
                            res['role_type'] = st.session_state["role_type"]
                            st.session_state["batch_data"].append(res)
                        bar.progress((i+1)/len(files))
                    st.rerun()

    if st.session_state["batch_data"]:
        # --- 2. DYNAMIC LEADERBOARD (Role Specific Columns) ---
        with st.container():
            current_role = st.session_state["role_type"]
            st.subheader(f"Leaderboard: {current_role}")
            
            table_data = []
            for c in st.session_state["batch_data"]:
                row = {
                    "Name": c.get('name'),
                    "Fit Score": c.get('fit_score'),
                }
                
                # ROLE SPECIFIC COLUMNS
                if "PI" in current_role or "Postdoc" in current_role:
                    bib = c.get('bibliometrics', {})
                    row["H-Index"] = bib.get('h_index', 'N/A')
                    row["Total Citations"] = bib.get('total_citations', 'N/A')
                    row["Research Area"] = c.get('research_focus_area', 'N/A')
                    
                elif "Research Assistant" in current_role:
                    row["Lab Exp (Yrs)"] = c.get('lab_experience_years', 'N/A')
                    skills = c.get('technical_skills', [])
                    row["Top Skills"] = ", ".join(skills[:3]) if skills else "N/A"
                    
                else: # Admin
                    row["Exp (Yrs)"] = c.get('years_experience', 'N/A')
                    row["Key Competency"] = c.get('core_competencies', [""])[0]

                table_data.append(row)
            
            df = pd.DataFrame(table_data).sort_values(by="Fit Score", ascending=False)
            
            # Configure visual columns
            st.dataframe(
                df, 
                use_container_width=True, 
                hide_index=True, 
                column_config={
                    "Fit Score": st.column_config.ProgressColumn("Fit", format="%d", min_value=0, max_value=100),
                }
            )
        
        # --- 3. DEEP DIVE (Visual Cards) ---
        st.subheader("🔍 Deep Profile Analysis")
        sel = st.selectbox("Select Candidate", df['Name'].tolist())
        cand = next(c for c in st.session_state["batch_data"] if c.get('name') == sel)
        
        # A. PROFILE HEADER
        with st.container():
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"## {cand.get('name')}")
                st.caption(f"📧 {cand.get('email')} | Track: {current_role}")
            with c2:
                st.metric("Final Fit Score", cand.get('fit_score'))

        # B. ROLE SPECIFIC METRICS (The "Helpful" Blocks)
        if "PI" in current_role or "Postdoc" in current_role:
            with st.container():
                st.markdown("#### 📚 Bibliometrics & Research Focus")
                
                # Metric Row
                bib = cand.get('bibliometrics', {})
                m1, m2, m3, m4 = st.columns(4)
                with m1: 
                    st.markdown(f"<div class='metric-card'><div class='metric-val'>{bib.get('h_index', 'N/A')}</div><div class='metric-lbl'>H-Index</div></div>", unsafe_allow_html=True)
                with m2: 
                    st.markdown(f"<div class='metric-card'><div class='metric-val'>{bib.get('total_citations', 'N/A')}</div><div class='metric-lbl'>Citations</div></div>", unsafe_allow_html=True)
                with m3:
                    st.markdown(f"<div class='metric-card'><div class='metric-val'>{bib.get('total_paper_count', 'N/A')}</div><div class='metric-lbl'>Papers</div></div>", unsafe_allow_html=True)
                with m4:
                    grant_count = len(cand.get('grants_found', []))
                    st.markdown(f"<div class='metric-card'><div class='metric-val'>{grant_count}</div><div class='metric-lbl'>Grants</div></div>", unsafe_allow_html=True)
                
                st.write("")
                st.info(f"**Research Focus:** {cand.get('research_focus_area', 'Not identified')}")

                # Papers Section
                st.markdown("##### ⭐ Representative Papers")
                for p in cand.get('representative_papers', []):
                    st.markdown(f"""
                    <div style="padding:10px; border-left:3px solid #4F46E5; background:#EEF2FF; margin-bottom:10px;">
                        <strong>{p.get('title')}</strong><br>
                        <span style="font-size:0.9em; color:#4338ca">{p.get('journal')}</span> | 
                        <span style="font-size:0.9em; color:#6B7280">{p.get('role')}</span><br>
                        <em style="font-size:0.9em">{p.get('significance')}</em>
                    </div>
                    """, unsafe_allow_html=True)

        elif "Research Assistant" in current_role:
             with st.container():
                st.markdown("#### 🧬 Technical Skills & Experience")
                m1, m2 = st.columns(2)
                with m1:
                    st.markdown(f"<div class='metric-card'><div class='metric-val'>{cand.get('lab_experience_years', 'N/A')}</div><div class='metric-lbl'>Years Lab Exp</div></div>", unsafe_allow_html=True)
                with m2:
                    proj_count = len(cand.get('project_participation', []))
                    st.markdown(f"<div class='metric-card'><div class='metric-val'>{proj_count}</div><div class='metric-lbl'>Key Projects</div></div>", unsafe_allow_html=True)
                
                st.write("")
                st.markdown("##### 🛠️ Skill Stack")
                # Badges for skills
                skills_html = ""
                for skill in cand.get('technical_skills', []):
                    skills_html += f"<span class='skill-tag'>{skill}</span>"
                st.markdown(skills_html, unsafe_allow_html=True)

        # C. COMMON SECTIONS (Summary & Risk)
        with st.container():
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("#### 📝 Executive Summary")
                st.write(cand.get('summary'))
            with c2:
                st.markdown("#### ⚠️ Risk Analysis")
                critique = cand.get('critique_notes', 'No risks.')
                if "No major red flags" in critique:
                    st.success("Clear Profile")
                else:
                    st.error(critique)

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
            
            if st.button("✨ Generate Draft"):
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


