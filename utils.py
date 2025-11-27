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

# --- 分析逻辑 (保持不变) ---
def analyze_batch_candidate(resume_text: str, jd_text: str, must_haves: str, role_type: str) -> dict:
    
    model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
    
    # 1. AGENT 1: 提取
    prompt_agent_1 = f"""
    ROLE: Data Extraction Specialist.
    TASK: Extract data from the CV.
    CRITICAL STEP - LANGUAGE DETECTION: Determine `language_preference` ("Chinese" or "English").
    CV TEXT: {resume_text[:15000]}
    
    EXTRACT JSON:
    1. Name
    2. Email
    3. language_preference
    4. Education
    5. Total Years of Experience
    6. List of Hard Skills / Core Competencies
    7. Top 3 Papers (Title + Journal) or Key Projects
    
    OUTPUT: JSON only.
    """
    try:
        raw_data_response = model.generate_content(prompt_agent_1, generation_config={"response_mime_type": "application/json"})
        extracted_facts = json.loads(raw_data_response.text)
    except:
        extracted_facts = {"language_preference": "English"}

    # 2. AGENT 2: 风控 (中文)
    prompt_agent_2 = f"""
    角色: 招聘风控专家。用中文回答。
    JD: {jd_text} | 必须: {must_haves} | 事实: {json.dumps(extracted_facts)}
    输出: 3个风险点 (Bullet points)。如无风险，回"无明显风险"。
    """
    try:
        critique_text = model.generate_content(prompt_agent_2).text
    except:
        critique_text = "分析失败"

    # 3. AGENT 3: 决策 (中文)
    if "PI" in role_type or "Postdoc" in role_type:
        json_struct = '"bibliometrics": {"h_index": "Val", "total_citations": "Val", "total_paper_count": "Val"}, "representative_papers": [{"title":"", "journal":"", "significance":""}],'
    elif "Research Assistant" in role_type:
        json_struct = '"technical_skills": ["Skill 1"], "lab_experience_years": "Val", "project_participation": ["Proj 1"],'
    else: 
        json_struct = '"core_competencies": ["Comp 1"], "software_tools": ["Tool 1"],'

    prompt_agent_3 = f"""
    角色: 招聘决策官。
    输入: JD: {jd_text} | 事实: {json.dumps(extracted_facts)} | 风险: {critique_text}
    任务: 生成评估 JSON (中文内容)。
    
    OUTPUT SCHEMA (JSON):
    {{
        "name": "{extracted_facts.get('name', 'Candidate')}",
        "email": "{extracted_facts.get('email', '')}",
        "language_preference": "{extracted_facts.get('language_preference', 'English')}",
        "fit_score": 0-100,
        "summary": "中文画像总结",
        "critique_notes": "{critique_text.replace(chr(10), ' ')}", 
        {json_struct}
        "strengths": ["优势1"],
        "gaps": ["劣势1"]
    }}
    """
    try:
        data = json.loads(model.generate_content(prompt_agent_3, generation_config={"response_mime_type": "application/json"}).text)
        if isinstance(data, list): return data[0]
        return data
    except Exception as e:
        return {"name": "Error", "fit_score": 0, "summary": f"AI Error: {str(e)}"}

# --- 【核心修复】智能邮件生成器 (防占位符版) ---
def generate_recruitment_email(candidate_data: dict, sender_info: dict, role_type: str) -> str:
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    lang = candidate_data.get('language_preference', 'Chinese')
    
    # 1. Python 预处理：强制生成“钩子”文本，防止 AI 偷懒留空
    # 我们在这里直接拼好字符串，而不是让 AI 去找
    hook_str = ""
    
    # 情况 A: 学术岗 (找论文)
    papers = candidate_data.get('representative_papers', [])
    if ("PI" in role_type or "Postdoc" in role_type) and papers:
        top_paper = papers[0].get('title', '您的近期研究成果')
        if lang == "Chinese":
            hook_str = f"特别是您发表的关于《{top_paper}》的研究工作给我留下了深刻印象。"
        else:
            hook_str = f"I was particularly impressed by your work on '{top_paper}'."
            
    # 情况 B: 技术/行政岗 (找技能或能力)
    elif candidate_data.get('technical_skills') or candidate_data.get('core_competencies'):
        # 优先取技能，没有则取能力
        skills_list = candidate_data.get('technical_skills', []) + candidate_data.get('core_competencies', [])
        top_skill = skills_list[0] if skills_list else "专业技能"
        
        if lang == "Chinese":
            hook_str = f"尤其是您在【{top_skill}】方面的丰富经验，与我们要寻找的人才高度契合。"
        else:
            hook_str = f"Especially your experience in {top_skill}, which aligns perfectly with our needs."
            
    # 情况 C: 兜底 (什么都没提取到，使用通用安全话术)
    else:
        if lang == "Chinese":
            hook_str = "我们详细评估了您的过往经历，认为您的专业背景非常扎实。"
        else:
            hook_str = "We have reviewed your background and are impressed by your professional experience."

    # 2. 生成 Prompt
    if lang == "Chinese":
        draft_prompt = f"""
        写信人: {sender_info['name']} ({sender_info['org']} {sender_info['title']})。
        收信人: {candidate_data.get('name')}。
        职位: {role_type}。
        
        【强制使用的赞美句】: "{hook_str}"
        
        任务: 写一封中文招聘邮件。
        要求:
        1. 直接使用上面的【强制使用的赞美句】，不要改动，不要加括号，不要加[请填入...]。
        2. 语气专业、热情。
        3. 邀请下周进行 15 分钟电话沟通。
        4. **严禁**出现任何 [xxx] 格式的占位符。
        5. **严禁**提到具体的匹配分数值 (如 70分)。
        
        输出: 仅邮件正文。
        """
    else:
        draft_prompt = f"""
        Sender: {sender_info['name']} from {sender_info['org']}.
        Candidate: {candidate_data.get('name')}. Role: {role_type}.
        
        MANDATORY HOOK SENTENCE: "{hook_str}"
        
        Task: Write a recruitment email in English.
        Rules:
        1. Use the MANDATORY HOOK SENTENCE verbatim. Do not use placeholders like [Insert here].
        2. Professional tone.
        3. Ask for a 15-min call next week.
        4. NEVER mention the internal score numbers.
        
        Output: Body text only.
        """

    # 3. 生成初稿
    draft = model.generate_content(draft_prompt).text
    
    # 4. 二次清洗 (Regenerate if placeholders exist)
    # 如果发现 AI 还是不听话留了括号，强制清洗
    if "[" in draft or "]" in draft:
        fix_prompt = f"""
        Fix this email immediately. Remove ANY text inside brackets [] and the brackets themselves.
        Make the text flow smoothly without them.
        
        Original:
        {draft}
        """
        draft = model.generate_content(fix_prompt).text

    return draft

def send_real_email(sender_email, sender_password, recipient_email, subject, body):
    try:
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
        return True, "发送成功"
    except Exception as e:
        return False, f"发送失败: {str(e)}"

