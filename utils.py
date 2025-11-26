import os
import google.generativeai as genai
import PyPDF2
import docx
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Configuration ---
def configure_ai(api_key: str):
    # 🚨 云端部署修改：删除了本地代理设置
    # Streamlit Cloud 服务器在美国，可以直接连接 Google
    if api_key:
        genai.configure(api_key=api_key)

# --- Parsing ---
def extract_text_from_file(uploaded_file) -> str:
    try:
        if uploaded_file.name.endswith('.pdf'):
            reader = PyPDF2.PdfReader(uploaded_file)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text
        elif uploaded_file.name.endswith('.docx'):
            doc = docx.Document(uploaded_file)
            text = "\n".join(para.text for para in doc.paragraphs)
            return text
        elif uploaded_file.name.endswith('.txt'):
            return str(uploaded_file.read(), "utf-8")
        return ""
    except Exception as e:
        return f"Error reading file: {str(e)}"

# --- ADAPTIVE ANALYSIS LOGIC ---
def analyze_batch_candidate(resume_text: str, jd_text: str, must_haves: str, role_type: str) -> dict:
    
    model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
    
    # 1. PI / Postdoc Prompt
    if "PI" in role_type or "Postdoc" in role_type:
        task_prompt = """
        TASK: Deep Academic Profiling.
        1. Metrics: Extract H-Index (Est if needed) and Total Citations.
        2. Papers: Identify top 3 high-impact papers.
        3. Grants: Look for NSFC/NIH funding.
        """
        json_structure = """
        "bibliometrics": {"h_index": "Val", "total_citations": "Val", "total_paper_count": "Val"},
        "representative_papers": [{"title": "", "journal": "", "role": "", "significance": ""}],
        "grants_found": ["Grant 1"],
        """
    # 2. RA Prompt
    elif "Research Assistant" in role_type:
        task_prompt = """
        TASK: Technical Skill & Execution Profiling.
        1. Lab Skills: Extract specific wet/dry lab techniques.
        2. Experience: Look for project participation.
        3. Publications: Count papers.
        """
        json_structure = """
        "technical_skills": ["Skill 1", "Skill 2"],
        "lab_experience_years": "Value",
        "project_participation": ["Project 1", "Project 2"],
        """
    # 3. Admin Prompt
    else: 
        task_prompt = """
        TASK: Administrative & Soft Skill Profiling.
        1. Skills: Project Management, Communication, Office/SAP software.
        2. Experience: Years of relevant work.
        3. Tone: Professionalism.
        """
        json_structure = """
        "core_competencies": ["Competency 1", "Competency 2"],
        "years_experience": "Value",
        "software_tools": ["Tool 1", "Tool 2"],
        """

    prompt = f"""
    You are an Expert Hospital Recruiter evaluating candidates for a: {role_type} role.
    TARGET REQUIREMENTS: {jd_text}
    CRITERIA: {must_haves}
    CANDIDATE CV: {resume_text}
    {task_prompt}
    OUTPUT SCHEMA (JSON):
    {{
        "name": "Name",
        "email": "Email",
        "fit_score": 0-100,
        "summary": "Executive summary",
        {json_structure}
        "strengths": ["Strength 1"],
        "gaps": ["Gap 1"]
    }}
    """
    try:
        response = model.generate_content(prompt)
        data = json.loads(response.text)
        if isinstance(data, list): return data[0]
        return data
    except Exception as e:
        return {"name": "Error", "fit_score": 0, "summary": f"AI Error: {str(e)}"}

# --- SMART EMAIL GENERATOR ---
def generate_recruitment_email(candidate_data: dict, sender_info: dict, role_type: str) -> str:
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    hook_text = ""
    papers = candidate_data.get('representative_papers', [])
    if papers and len(papers) > 0:
        top_paper = papers[0].get('title', 'your recent publication')
        hook_text = f"I was particularly impressed by your work on '{top_paper}'."
    elif candidate_data.get('technical_skills'):
        hook_text = f"Your experience with {', '.join(candidate_data.get('technical_skills')[:2])} caught our eye."
    
    focus_area = candidate_data.get('research_focus_area', 'your field of expertise')
    
    prompt = f"""
    You are {sender_info['name']}, the {sender_info['title']} at {sender_info['org']}.
    Write a HIGHLY PERSONALIZED recruiting email to:
    Name: {candidate_data.get('name')}
    Role: {role_type}
    CONTEXT: Focus: {focus_area}, Hook: {hook_text}, Score: {candidate_data.get('fit_score')}
    INSTRUCTIONS: No placeholders. Ask for a 15-min call. Professional tone.
    Email Body Only.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Error generating smart email."

# --- REAL EMAIL SENDER (Standard SMTP) ---
def send_real_email(sender_email, sender_password, recipient_email, subject, body):
    try:
        # 🚨 云端部署修改：移除了 socks 代理代码
        # Streamlit Cloud 可以直接连接 Gmail SMTP
        
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))
        
        session = smtplib.SMTP('smtp.gmail.com', 587) 
        session.starttls()
        session.login(sender_email, sender_password) 
        session.sendmail(sender_email, recipient_email, message.as_string())
        session.quit()
        return True, "Email Sent Successfully"
    except Exception as e:
        return False, f"Failed: {str(e)}"