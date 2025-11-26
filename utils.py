import os
import google.generativeai as genai
import PyPDF2
import docx
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def configure_ai(api_key: str):
    if api_key: genai.configure(api_key=api_key)

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

# --- IMPROVED MULTI-AGENT WORKFLOW ---
def analyze_batch_candidate(resume_text: str, jd_text: str, must_haves: str, role_type: str) -> dict:
    
    model = genai.GenerativeModel('gemini-2.0-flash')

    # --- AGENT 1: THE TRANSLATOR & EXTRACTOR ---
    # Fixes the "Cornell vs 康乃尔" issue by forcing English normalization
    prompt_agent_1 = f"""
    ROLE: Data Extraction & Normalization Specialist.
    
    TASK: Extract data from the CV.
    CRITICAL RULE: **CROSS-LANGUAGE NORMALIZATION**.
    - If the CV is in Chinese, extract the original text BUT also provide the English translation in brackets.
    - Example: "毕业于康乃尔大学" -> "University: Kangnaier (Cornell University)"
    - Example: "擅长生物建模" -> "Skills: Biological Modeling"
    
    CV TEXT: {resume_text[:15000]}
    
    EXTRACT JSON:
    1. Name (English & Chinese if avail)
    2. Email
    3. Education (University Name + Degree). *Remember to normalize to English*
    4. Total Years of Experience (Number)
    5. List of Hard Skills (Translated to English)
    6. Top 3 Papers (If applicable)
    
    OUTPUT: JSON only.
    """
    try:
        raw_data_response = model.generate_content(prompt_agent_1, generation_config={"response_mime_type": "application/json"})
        extracted_facts = json.loads(raw_data_response.text)
    except:
        extracted_facts = {}

    # --- AGENT 2: THE CRITIC (Context Aware) ---
    prompt_agent_2 = f"""
    ROLE: Senior Risk Analyst.
    TASK: Review Candidate against JD.
    
    JD: {jd_text}
    MUST HAVES: {must_haves}
    CANDIDATE FACTS (Normalized): {json.dumps(extracted_facts)}
    
    INSTRUCTIONS:
    - Compare the English Normalized terms. (e.g. If JD asks for "Cornell", and Facts say "Kangnaier (Cornell)", that is a MATCH. Do not flag it).
    - Be strict on years of experience and specific technical skills.
    
    OUTPUT: List of 3 brief bullet points explaining risks. If no major risks, write "No major red flags detected."
    """
    try:
        critique_response = model.generate_content(prompt_agent_2)
        critique_text = critique_response.text
    except:
        critique_text = "Analysis failed."

    # --- AGENT 3: THE DECISION MAKER ---
    # (JSON Structure setup)
    if "PI" in role_type or "Postdoc" in role_type:
        json_struct = '"bibliometrics": {"h_index": "Val", "total_citations": "Val"}, "representative_papers": [{"title":"", "journal":"", "significance":""}],'
    elif "Research Assistant" in role_type:
        json_struct = '"technical_skills": ["Skill 1"], "lab_experience_years": "Val", "project_participation": ["Proj 1"],'
    else: 
        json_struct = '"core_competencies": ["Comp 1"], "software_tools": ["Tool 1"],'

    prompt_agent_3 = f"""
    ROLE: Final Hiring Decision Maker.
    INPUTS:
    1. JD: {jd_text}
    2. FACTS: {json.dumps(extracted_facts)}
    3. RISKS: {critique_text}
    
    TASK: Final Evaluation JSON.
    - If the Risk Analyst flagged a language confusion (e.g. Cornell vs 康乃尔), ignore the risk if the facts prove it's the same school.
    - Score heavily on the match of specific research areas.
    
    OUTPUT SCHEMA (JSON):
    {{
        "name": "{extracted_facts.get('name', 'Candidate')}",
        "email": "{extracted_facts.get('email', '')}",
        "fit_score": 0-100,
        "summary": "Executive summary.",
        "critique_notes": "{critique_text.replace(chr(10), ' ')}", 
        {json_struct}
        "strengths": ["Strength 1"],
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

# --- EMAIL AGENT ---
def generate_recruitment_email(candidate_data: dict, sender_info: dict, role_type: str) -> str:
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    # Draft
    draft_prompt = f"""
    Writer: {sender_info['name']} ({sender_info['org']}).
    Target: {candidate_data.get('name')}. Role: {role_type}.
    Focus: {candidate_data.get('research_focus_area', 'Background')}.
    Tone: Professional.
    Write a recruitment email asking for a 15-min call.
    """
    draft = model.generate_content(draft_prompt).text

    # Refine
    refiner_prompt = f"""
    Review this email draft.
    DRAFT: {draft}
    RULES: 
    1. Remove any brackets [].
    2. Remove internal scores.
    3. Output: Clean email text only.
    """
    return model.generate_content(refiner_prompt).text

def send_real_email(sender_email, sender_password, recipient_email, subject, body):
    try:
        # SMTP Standard
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

