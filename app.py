import streamlit as st
import pandas as pd
from utils import configure_ai, extract_text_from_file, analyze_batch_candidate, generate_recruitment_email, send_real_email

# --- PAGE CONFIG ---
st.set_page_config(page_title="Med-Recruit AI", page_icon="🏥", layout="wide")

# --- SESSION STATE INITIALIZATION ---
if "batch_data" not in st.session_state: st.session_state["batch_data"] = [] 
if "jd_text" not in st.session_state: st.session_state["jd_text"] = ""
if "role_type" not in st.session_state: st.session_state["role_type"] = "🧪 PI / Postdoc"

# --- CSS STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; background-color: #F0F2F6; }
    .stButton>button { background-color: #00796B; color: white; border: none; }
    .stButton>button:hover { background-color: #004D40; }
    .metric-box { background: #fff; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }
    .role-tag { background: #E8F5E9; color: #2E7D32; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 0.9em; }
    h1, h2, h3 { color: #004D40; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🏥 Med-Recruit")
    st.caption("Zhejiang Univ. Medical Center Edition")
    
    # Navigation Switcher
    page = st.radio("Navigation", ["📊 Talent Evaluation", "📧 Outreach"], index=0)
    
    st.divider()
    
    # API Key Input
    api_key = st.text_input("Google API Key", type="password")
    if api_key: configure_ai(api_key)
    
    st.info(f"Candidates Loaded: {len(st.session_state['batch_data'])}")

# =========================================================
# VIEW 1: EVALUATION DASHBOARD
# =========================================================
if page == "📊 Talent Evaluation":
    st.title("Talent Evaluation Dashboard")
    
    # 1. CONFIGURATION & UPLOAD
    with st.expander("⚙️ Hiring Configuration", expanded=True):
        # Hiring Track Selector
        st.session_state["role_type"] = st.radio(
            "Select Hiring Track:", 
            ["🧪 PI / Postdoc", "🧬 Research Assistant (RA)", "💼 Administrative / Support"],
            horizontal=True
        )
        
        c1, c2 = st.columns(2)
        with c1:
            st.session_state["jd_text"] = st.text_area("Job Requirements", value=st.session_state["jd_text"], height=100, placeholder=f"Requirements for {st.session_state['role_type']}...")
            must_haves = st.text_input("Key Filters", placeholder="e.g. PhD, Python, or Project Management Cert")
        with c2:
            st.write(f"Upload Candidates for **{st.session_state['role_type']}**")
            files = st.file_uploader("Upload CVs (PDF/Docx)", accept_multiple_files=True)
            
            if st.button("Analyze Candidates 🚀", use_container_width=True):
                if api_key and files:
                    st.session_state["batch_data"] = []
                    bar = st.progress(0)
                    for i, f in enumerate(files):
                        # Pass Role Type to Utils
                        res = analyze_batch_candidate(extract_text_from_file(f), st.session_state["jd_text"], must_haves, st.session_state["role_type"])
                        res['file_name'] = f.name
                        res['role_type'] = st.session_state["role_type"] 
                        st.session_state["batch_data"].append(res)
                        bar.progress((i+1)/len(files))
                    st.rerun()

    # 2. RESULTS & RANKINGS
    if st.session_state["batch_data"]:
        df_data = []
        current_role = st.session_state["role_type"]
        
        for c in st.session_state["batch_data"]:
            base_info = {
                "Name": c.get('name'),
                "Score": c.get('fit_score'),
                "Email": c.get('email'),
                "ID": c.get('file_name')
            }
            
            # Dynamic Columns based on Role
            if current_role == "🧪 PI / Postdoc":
                base_info["H-Index"] = c.get('bibliometrics', {}).get('h_index', 'N/A')
                base_info["Key Grants"] = len(c.get('grants_found', []))
            elif current_role == "🧬 Research Assistant (RA)":
                base_info["Lab Exp (Yrs)"] = c.get('lab_experience_years', 'N/A')
                base_info["Top Skills"] = ", ".join(c.get('technical_skills', [])[:3])
            else: # Admin
                base_info["Exp (Yrs)"] = c.get('years_experience', 'N/A')
                base_info["Competencies"] = ", ".join(c.get('core_competencies', [])[:2])
            
            df_data.append(base_info)
        
        df = pd.DataFrame(df_data).sort_values(by="Score", ascending=False)
        
        st.subheader(f"Rankings: {current_role}")
        st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True,
            column_config={"Score": st.column_config.ProgressColumn("Fit Score", format="%d", min_value=0, max_value=100)}
        )
        
        # 3. DEEP DIVE PROFILE
        st.divider()
        st.subheader("🔍 Deep Profile Analysis")
        
        sel_name = st.selectbox("Select Candidate to Review", df['Name'].tolist())
        cand = next(c for c in st.session_state["batch_data"] if c.get('name') == sel_name)
        
        # Profile Header
        col_t1, col_t2 = st.columns([3,1])
        with col_t1: st.markdown(f"### {cand.get('name')} <span class='role-tag'>{current_role}</span>", unsafe_allow_html=True)
        with col_t2: st.metric("Fit Score", cand.get('fit_score'))
        
        # Conditional Display Logic
        if current_role == "🧪 PI / Postdoc":
            st.markdown("#### 📚 Publication Impact")
            bib = cand.get('bibliometrics', {})
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("H-Index", bib.get('h_index', 'N/A'))
            with m2: st.metric("Citations", bib.get('total_citations', 'N/A'))
            with m3: st.metric("Papers", bib.get('total_paper_count', 'N/A'))
            
            for p in cand.get('representative_papers', []):
                with st.expander(f"📄 {p.get('title')}", expanded=True):
                    st.info(f"**Journal:** {p.get('journal')} | **Role:** {p.get('role')}\n\n💡 {p.get('significance')}")

        elif current_role == "🧬 Research Assistant (RA)":
            st.markdown("#### 🛠️ Technical Proficiency")
            tech_cols = st.columns(3)
            for i, skill in enumerate(cand.get('technical_skills', [])):
                tech_cols[i%3].success(f"🔹 {skill}")
            st.caption(f"Total Lab Experience: {cand.get('lab_experience_years')} Years")

        else: # Admin
            st.markdown("#### 💼 Professional Competencies")
            soft_cols = st.columns(2)
            with soft_cols[0]:
                st.write("**Core Competencies:**")
                for comp in cand.get('core_competencies', []):
                    st.write(f"- {comp}")
            with soft_cols[1]:
                st.write("**Software/Tools:**")
                for tool in cand.get('software_tools', []):
                    st.write(f"- {tool}")

        # Summary & Gaps
        st.markdown("#### 📝 Executive Summary")
        st.write(cand.get('summary'))
        
        c1, c2 = st.columns(2)
        with c1: 
            st.markdown("**✅ Strengths**")
            for s in cand.get('strengths', []): st.success(s)
        with c2: 
            st.markdown("**⚠️ Potential Gaps**")
            for g in cand.get('gaps', []): st.error(g)

# =========================================================
# VIEW 2: SMART OUTREACH (Fixed Email Input)
# =========================================================
elif page == "📧 Outreach":
    st.title("Smart Outreach Assistant")
    
    # 1. SENDER PROFILE
    with st.expander("👤 Sender Profile", expanded=True):
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            sender_name = st.text_input("Your Name", value="Hongli Ding")
        with col_s2:
            sender_title = st.text_input("Your Title", value="Talent Acquisition Specialist") 
        with col_s3:
            sender_org = st.text_input("Organization", value="Zhejiang University Medical Center")
            
        with st.popover("🔐 SMTP Credentials (Click to Edit)"):
            st.caption("Enter your Gmail/Outlook details to send real emails.")
            sender_email = st.text_input("Your Email Address")
            sender_password = st.text_input("App Password", type="password")

    st.divider()

    # 2. SELECT CANDIDATE
    if not st.session_state["batch_data"]:
        st.warning("⚠️ No candidates found. Please analyze CVs in the Evaluation tab first.")
    else:
        names = [c.get('name') for c in st.session_state["batch_data"]]
        sel = st.selectbox("Select Candidate to Contact", names)
        
        cand = next(c for c in st.session_state["batch_data"] if c.get('name') == sel)
        
        st.info(f"Targeting: **{cand.get('name')}** | Role: **{cand.get('role_type', 'General')}**")
        
        # 3. GENERATE
        if st.button("✨ Generate Personalized Email"):
            sender_info = {
                "name": sender_name,
                "title": sender_title,
                "org": sender_org
            }
            
            with st.spinner(f"Drafting email from {sender_name}..."):
                st.session_state['draft'] = generate_recruitment_email(
                    cand, 
                    sender_info, 
                    cand.get('role_type', 'Candidate')
                )
        
        # 4. REVIEW & SEND
        if 'draft' in st.session_state:
            # Smart Subject Line
            default_subject = f"Opportunity at {sender_org}: {cand.get('research_focus_area', 'Research Position')}"
            
            subject = st.text_input("Subject Line", value=default_subject)
            
            # 🟢 [FIX] ADDED RECIPIENT INPUT HERE
            # This allows you to delete "<TBD>" and type the real email
            recipient = st.text_input("Recipient Email", value=cand.get('email', ''))
            
            body = st.text_area("Smart Draft", st.session_state['draft'], height=400)
            
            col_send, col_test = st.columns([1, 2])
            with col_send:
                if st.button("Send to Candidate 🚀", type="primary"):
                    if not sender_email or not sender_password:
                        st.error("Please configure SMTP Credentials above.")
                    elif not recipient or "@" not in recipient:
                        st.error("Please enter a valid Recipient Email.")
                    else:
                        with st.spinner("Sending..."):
                            ok, msg = send_real_email(sender_email, sender_password, recipient, subject, body)
                            if ok: st.success(f"Email sent to {recipient}!")
                            else: st.error(msg)