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
    # Cloud Deployment: No Proxy needed
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

# --- ANALYSIS LOGIC ---
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

    # 2. Research Assistant Prompt
    elif "Research Assistant" in role_type:
        task_prompt = """
        TASK: Technical Skill & Execution Profiling.
        1. Lab Skills: Extract specific wet/dry lab techniques (e.g. PCR, Cell Culture, Python).
        2. Experience: Look for project participation and reliability.
        3. Publications: Count papers (participation is good, but first author not required).
        """
        json_structure = """
        "technical_skills": ["Skill 1", "Skill 2"],
        "lab_experience_years": "Value",
        "project_participation": ["Project 1", "Project 2"],
        """

    # 3. Admin / Support Prompt
    else: 
        task_prompt = """
        TASK: Administrative & Soft Skill Profiling.
        1. Skills: Project Management, Communication, Office/SAP software, Event Planning.
        2. Experience: Years of relevant work, previous hospital/uni experience.
        3. Tone: Professionalism and organizational ability.
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
        "fit_score": 0-100 (Relevance to this specific role type),
        "summary": "Executive summary",
        {json_structure}
        "strengths": ["Strength 1", "Strength 2"],
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

# --- SMART EMAIL GENERATOR (Fixed: No Placeholders) ---
def generate_recruitment_email(candidate_data: dict, sender_info: dict, role_type: str) -> str:
    """
    Generates a highly personalized email.
    """
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    # --- 1. Prepare Hook Data ---
    hook_text = ""
    
    # Hook for PI/Researchers (Papers)
    papers = candidate_data.get('representative_papers', [])
    if papers and len(papers) > 0:
        top_paper = papers[0].get('title', 'recent publication')
        hook_text = f"I was particularly impressed by your work on '{top_paper}'."
        
    # Hook for RA/Admin (Skills)
    elif candidate_data.get('technical_skills'):
        skills = ", ".join(candidate_data.get('technical_skills')[:2])
        hook_text = f"Your technical proficiency in {skills} caught our eye and aligns well with our lab's needs."
    
    # Fallback Focus Area
    focus_area = candidate_data.get('research_focus_area', 'your professional background')

    # --- 2. Stricter Prompt ---
    prompt = f"""
    You are {sender_info['name']}, the {sender_info['title']} at {sender_info['org']}.
    
    Write a professional recruiting email to:
    Name: {candidate_data.get('name')}
    Role: {role_type}
    
    CONTEXT:
    - Candidate Strength: {hook_text} (Mention this early!)
    - Their Focus: {focus_area}
    - Internal Fit Score: {candidate_data.get('fit_score')} (High = >80, Med = 50-80, Low = <50)
    
    CRITICAL RULES:
    1. **NO PLACEHOLDERS**: NEVER leave brackets like [Insert Project] or [Date].
    2. **NO INTERNAL DATA**: Do NOT mention the "Score" (e.g. "Score of 70") to the candidate. That is rude.
    3. **BE GENERAL IF NEEDED**: If you don't know the specific lab name, use "our research team" or "our department".
    4. **CALL TO ACTION**: Ask "Are you available for a brief 15-minute introductory call next week?"
    
    TONE GUIDE:
    - If Score > 80: Enthusiastic. "Your background is exactly what we are looking for."
    - If Score < 80: Polite but interested. "We see potential in your profile."
    
    OUTPUT: Email Body Only. No Subject Line.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Error generating smart email."

# --- REAL EMAIL SENDER ---
def send_real_email(sender_email, sender_password, recipient_email, subject, body):
    try:
        # Standard SMTP for Cloud Deployment
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
