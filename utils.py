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

# --- MULTI-AGENT WORKFLOW ---
def analyze_batch_candidate(resume_text: str, jd_text: str, must_haves: str, role_type: str) -> dict:
    
    # We use Flash because it is fast enough to run 3 times in a row quickly
    model = genai.GenerativeModel('gemini-2.0-flash')

    # --- AGENT 1: THE FACT EXTRACTOR (No Judgment, Just Data) ---
    # Purpose: Prevent hallucination by forcing raw data extraction first.
    prompt_agent_1 = f"""
    ROLE: Data Extraction Specialist.
    TASK: Extract hard data from the CV. Do not evaluate quality yet.
    CV TEXT: {resume_text[:15000]}
    
    EXTRACT:
    1. Name & Email
    2. Total Years of Experience (Number)
    3. H-Index / Citations (If research role)
    4. Top 3 Papers (Title + Journal)
    5. List of Hard Skills
    
    OUTPUT: JSON only.
    """
    try:
        raw_data_response = model.generate_content(prompt_agent_1, generation_config={"response_mime_type": "application/json"})
        extracted_facts = json.loads(raw_data_response.text)
    except:
        extracted_facts = {}

    # --- AGENT 2: THE CRITIC (The "Bad Cop") ---
    # Purpose: AI is usually too nice. This agent is forced to find flaws.
    prompt_agent_2 = f"""
    ROLE: Senior Risk Analyst / "Devil's Advocate".
    TASK: Review the Candidate Data against the JD and find 3 specific RISKS or GAPS.
    
    JD: {jd_text}
    MUST HAVES: {must_haves}
    CANDIDATE FACTS: {json.dumps(extracted_facts)}
    
    INSTRUCTIONS:
    - Be strict.
    - Look for: Short tenures, low journal impact, missing specific tech stack, generic descriptions.
    - If they miss a "Must Have", flag it immediately.
    
    OUTPUT: List of 3 brief bullet points explaining the risks.
    """
    try:
        critique_response = model.generate_content(prompt_agent_2)
        critique_text = critique_response.text
    except:
        critique_text = "Analysis failed."

    # --- AGENT 3: THE HIRING MANAGER (Final Decision) ---
    # Purpose: Synthesize Facts + Critique + JD into a final Score.
    
    # Dynamic JSON structure based on role (Same as before, but smarter now)
    if "PI" in role_type or "Postdoc" in role_type:
        json_structure = """
        "bibliometrics": {"h_index": "Val", "total_citations": "Val", "total_paper_count": "Val"},
        "representative_papers": [{"title": "", "journal": "", "role": "", "significance": ""}],
        "grants_found": ["Grant 1"],
        """
    elif "Research Assistant" in role_type:
        json_structure = """
        "technical_skills": ["Skill 1", "Skill 2"],
        "lab_experience_years": "Value",
        "project_participation": ["Project 1", "Project 2"],
        """
    else: 
        json_structure = """
        "core_competencies": ["Competency 1", "Competency 2"],
        "years_experience": "Value",
        "software_tools": ["Tool 1", "Tool 2"],
        """

    prompt_agent_3 = f"""
    ROLE: Final Hiring Decision Maker.
    
    INPUTS:
    1. JD: {jd_text}
    2. CANDIDATE FACTS: {json.dumps(extracted_facts)}
    3. RISK REPORT (From Risk Analyst): {critique_text}
    
    TASK: Generate the Final Evaluation JSON.
    - Use the Risk Report to lower the score if necessary.
    - Be objective.
    
    OUTPUT SCHEMA (JSON):
    {{
        "name": "{extracted_facts.get('name', 'Candidate')}",
        "email": "{extracted_facts.get('email', '')}",
        "fit_score": 0-100,
        "summary": "Executive summary incorporating strengths and the risks identified.",
        "critique_notes": "{critique_text.replace(chr(10), ' | ')}", 
        {json_structure}
        "strengths": ["Strength 1", "Strength 2"],
        "gaps": ["Gap 1"]
    }}
    """
    
    try:
        final_response = model.generate_content(prompt_agent_3, generation_config={"response_mime_type": "application/json"})
        data = json.loads(final_response.text)
        if isinstance(data, list): return data[0]
        return data
    except Exception as e:
        return {"name": "Error", "fit_score": 0, "summary": f"AI Error: {str(e)}"}

# --- EMAIL AGENT (Refiner Loop) ---
def generate_recruitment_email(candidate_data: dict, sender_info: dict, role_type: str) -> str:
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    # 1. Draft
    draft_prompt = f"""
    Writer: {sender_info['name']} ({sender_info['org']}).
    Target: {candidate_data.get('name')}. Role: {role_type}.
    Focus: {candidate_data.get('research_focus_area', 'Background')}.
    Tone: Professional.
    Write a recruitment email asking for a 15-min call.
    """
    draft = model.generate_content(draft_prompt).text

    # 2. Refine (Self-Correction Agent)
    refiner_prompt = f"""
    Review this email draft.
    DRAFT: {draft}
    RULES: 
    1. Remove any brackets [].
    2. Remove internal scores (e.g. "Score: 80").
    3. Ensure sender is {sender_info['name']}.
    Output: Clean email text only.
    """
    return model.generate_content(refiner_prompt).text

# --- REAL EMAIL SENDER ---
def send_real_email(sender_email, sender_password, recipient_email, subject, body):
    try:
        # Standard SMTP
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

