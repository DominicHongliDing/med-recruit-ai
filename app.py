import streamlit as st
import pandas as pd
from utils import configure_ai, extract_text_from_file, analyze_batch_candidate, generate_recruitment_email, send_real_email

# --- PAGE CONFIG ---
st.set_page_config(page_title="Med-Recruit AI", page_icon="🏥", layout="wide")

if "batch_data" not in st.session_state: st.session_state["batch_data"] = [] 
if "jd_text" not in st.session_state: st.session_state["jd_text"] = ""
if "role_type" not in st.session_state: st.session_state["role_type"] = "🧪 PI / Postdoc"

# --- CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; background-color: #F0F2F6; }
    .stButton>button { background-color: #00796B; color: white; border: none; }
    .critic-box { background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 15px; border-radius: 4px; }
    .role-tag { background: #E8F5E9; color: #2E7D32; padding: 4px 10px; border-radius: 12px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🏥 Med-Recruit")
    st.caption("Multi-Agent Edition")
    page = st.radio("Navigation", ["📊 Talent Evaluation", "📧 Outreach"], index=0)
    st.divider()
    api_key = st.text_input("Google API Key", type="password")
    if api_key: configure_ai(api_key)
    st.info(f"Candidates: {len(st.session_state['batch_data'])}")

# =========================================================
# VIEW 1: EVALUATION (Multi-Agent)
# =========================================================
if page == "📊 Talent Evaluation":
    st.title("Talent Evaluation Dashboard (Multi-Agent)")
    
    with st.expander("⚙️ Hiring Configuration", expanded=True):
        st.session_state["role_type"] = st.radio("Track:", ["🧪 PI / Postdoc", "🧬 Research Assistant (RA)", "💼 Administrative"], horizontal=True)
        c1, c2 = st.columns(2)
        with c1:
            st.session_state["jd_text"] = st.text_area("Job Requirements", value=st.session_state["jd_text"], height=100)
            must_haves = st.text_input("Key Filters")
        with c2:
            files = st.file_uploader("Upload CVs", accept_multiple_files=True)
            if st.button("Start 3-Agent Analysis 🚀", use_container_width=True):
                if api_key and files:
                    st.session_state["batch_data"] = []
                    bar = st.progress(0)
                    for i, f in enumerate(files):
                        with st.spinner(f"Agent 1 extracting... Agent 2 critiquing... Agent 3 scoring {f.name}..."):
                            res = analyze_batch_candidate(extract_text_from_file(f), st.session_state["jd_text"], must_haves, st.session_state["role_type"])
                            res['file_name'] = f.name
                            res['role_type'] = st.session_state["role_type"]
                            st.session_state["batch_data"].append(res)
                        bar.progress((i+1)/len(files))
                    st.rerun()

    if st.session_state["batch_data"]:
        # Table Logic (Simplified for brevity, same as before)
        df_data = []
        for c in st.session_state["batch_data"]:
            df_data.append({"Name": c.get('name'), "Score": c.get('fit_score'), "Email": c.get('email')})
        df = pd.DataFrame(df_data).sort_values(by="Score", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True, column_config={"Score": st.column_config.ProgressColumn("Fit", format="%d", min_value=0, max_value=100)})
        
        # DEEP DIVE
        st.divider()
        st.subheader("🔍 Deep Profile Analysis")
        sel = st.selectbox("Select Candidate", df['Name'].tolist())
        cand = next(c for c in st.session_state["batch_data"] if c.get('name') == sel)
        
        # Header
        c1, c2 = st.columns([3,1])
        with c1: st.markdown(f"### {cand.get('name')}")
        with c2: st.metric("Final Score", cand.get('fit_score'))
        
        # --- THE NEW "CRITIC" SECTION ---
        st.markdown("#### 🕵️ Agent 2: Risk Analysis Report")
        # Display the critique neatly
        critique_raw = cand.get('critique_notes', 'No risks flagged.')
        # Clean up the format slightly if it's messy
        critique_clean = critique_raw.replace(" | ", "\n\n")
        
        st.markdown(f"""
        <div class="critic-box">
            <strong>⚠️ The "Devil's Advocate" Agent flagged these potential risks:</strong><br><br>
            {critique_clean}
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        
        # Rest of the profile (Summary, Skills, etc.)
        st.markdown("#### 📝 Final Summary (Agent 3)")
        st.write(cand.get('summary'))
        
        # Conditional Blocks (PI/RA/Admin) - same as previous version
        if "PI" in st.session_state["role_type"]:
            st.markdown("#### 📚 Academic Metrics")
            bib = cand.get('bibliometrics', {})
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("H-Index", bib.get('h_index', 'N/A'))
            with m2: st.metric("Citations", bib.get('total_citations', 'N/A'))
            with m3: st.metric("Papers", bib.get('total_paper_count', 'N/A'))

# =========================================================
# VIEW 2: OUTREACH
# =========================================================
elif page == "📧 Outreach":
    st.title("Smart Outreach")
    with st.expander("👤 Sender Profile", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1: sender_name = st.text_input("Name", value="Hongli Ding")
        with c2: sender_title = st.text_input("Title", value="TA Specialist")
        with c3: sender_org = st.text_input("Org", value="Zhejiang Univ. Medical Center")
        with st.popover("🔐 SMTP"):
            sender_email = st.text_input("Email")
            sender_password = st.text_input("App Password", type="password")

    if st.session_state["batch_data"]:
        names = [c.get('name') for c in st.session_state["batch_data"]]
        sel = st.selectbox("Select Candidate", names)
        cand = next(c for c in st.session_state["batch_data"] if c.get('name') == sel)
        
        if st.button("✨ Draft Email (Double-Check Agent)"):
            with st.spinner("Drafting & Refining..."):
                sender_info = {"name": sender_name, "title": sender_title, "org": sender_org}
                st.session_state['draft'] = generate_recruitment_email(cand, sender_info, cand.get('role_type', 'Role'))
        
        if 'draft' in st.session_state:
            subj = st.text_input("Subject", value=f"Opportunity at {sender_org}")
            recip = st.text_input("Recipient", value=cand.get('email', ''))
            body = st.text_area("Body", st.session_state['draft'], height=300)
            if st.button("Send 🚀"):
                ok, msg = send_real_email(sender_email, sender_password, recip, subj, body)
                if ok: st.success("Sent!")
                else: st.error(msg)
