import streamlit as st
import pandas as pd
from utils import configure_ai, extract_text_from_file, analyze_batch_candidate, generate_recruitment_email, send_real_email
# 引入新写的存储管理器
from preset_manager import load_presets, save_preset, delete_preset

# --- 页面配置 ---
st.set_page_config(page_title="医学人才智能招聘系统", page_icon="🏥", layout="wide")

# --- Session State 初始化 ---
if "batch_data" not in st.session_state: st.session_state["batch_data"] = [] 
if "jd_text" not in st.session_state: st.session_state["jd_text"] = ""
if "must_haves" not in st.session_state: st.session_state["must_haves"] = ""
if "role_type" not in st.session_state: st.session_state["role_type"] = "🧪 PI / 博士后 (Postdoc)"

# --- CSS 样式 ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans SC', sans-serif; background-color: #F8FAFC; }
    
    .stContainer { background-color: white; padding: 24px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #E2E8F0; margin-bottom: 20px; }
    .metric-card { background: #F1F5F9; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #CBD5E1; }
    .metric-val { font-size: 1.5rem; font-weight: 700; color: #0F172A; }
    .metric-lbl { font-size: 0.85rem; color: #64748B; }
    .skill-tag { background: #ECFDF5; color: #059669; padding: 4px 10px; border-radius: 6px; font-size: 0.9em; border: 1px solid #A7F3D0; margin-right: 5px;}
</style>
""", unsafe_allow_html=True)

# --- 侧边栏 ---
with st.sidebar:
    st.markdown("### 🏥 浙大医学中心招聘系统", unsafe_allow_html=True)
    page = st.radio("功能导航", ["📊 人才评估仪表盘", "📧 智能邀约助手"], index=0)
    
    st.divider()
    
    # --- 🌟 新增功能：岗位记忆库 ---
    st.markdown("#### 📁 岗位记忆库")
    presets = load_presets()
    preset_names = ["-- 新建/未选择 --"] + list(presets.keys())
    
    selected_preset = st.selectbox("选择已保存的岗位模板", preset_names)
    
    # 如果选择了某个模板，自动填充数据
    if selected_preset != "-- 新建/未选择 --":
        data = presets[selected_preset]
        # 将数据载入 Session State
        st.session_state["jd_text"] = data["jd"]
        st.session_state["must_haves"] = data["must_haves"]
        st.session_state["role_type"] = data["role_type"]
        # st.success(f"已加载: {selected_preset}") 
        
        if st.button("🗑️ 删除此模板"):
            delete_preset(selected_preset)
            st.rerun()
            
    st.divider()
    
    api_key = st.text_input("Google API Key", type="password")
    if api_key: configure_ai(api_key)
    st.success(f"当前候选人: {len(st.session_state['batch_data'])}")

# =========================================================
# 视图 1: 评估仪表盘
# =========================================================
if page == "📊 人才评估仪表盘":
    st.title("人才评估仪表盘 (AI Multi-Agent)")
    
    # --- 1. 配置卡片 ---
    with st.container():
        st.subheader("⚙️ 招聘岗位配置")
        
        # 赛道选择
        st.session_state["role_type"] = st.radio(
            "选择招聘赛道:", 
            ["🧪 PI / 博士后 (Postdoc)", "🧬 科研助理 (RA)", "💼 行政管理 (Admin)"], 
            horizontal=True,
            index=["🧪 PI / 博士后 (Postdoc)", "🧬 科研助理 (RA)", "💼 行政管理 (Admin)"].index(st.session_state["role_type"]) if st.session_state["role_type"] in ["🧪 PI / 博士后 (Postdoc)", "🧬 科研助理 (RA)", "💼 行政管理 (Admin)"] else 0
        )

        c1, c2 = st.columns([1, 1])
        with c1:
            # 这里的 value 绑定了 session_state，所以切换模板会自动变
            st.session_state["jd_text"] = st.text_area("职位描述 (JD)", value=st.session_state["jd_text"], height=150, placeholder="粘贴JD...")
            st.session_state["must_haves"] = st.text_input("核心硬性要求 (Must Haves)", value=st.session_state.get("must_haves", ""), placeholder="例如：海外博士, Nature一作")
            
            # --- 保存模板区域 ---
            with st.expander("💾 将当前要求保存为新模板"):
                new_preset_name = st.text_input("模板名称 (例如: 2025行政岗)")
                if st.button("保存模板"):
                    if new_preset_name and st.session_state["jd_text"]:
                        save_preset(new_preset_name, st.session_state["jd_text"], st.session_state["must_haves"], st.session_state["role_type"])
                        st.success(f"模板【{new_preset_name}】已保存！")
                        st.rerun()
                    else:
                        st.error("请输入名称和JD内容")

        with c2:
            st.write("批量上传简历")
            files = st.file_uploader("支持 PDF / Word", accept_multiple_files=True, label_visibility="collapsed")
            if st.button("开始 AI 智能分析 🚀", use_container_width=True):
                if api_key and files:
                    st.session_state["batch_data"] = []
                    bar = st.progress(0)
                    for i, f in enumerate(files):
                        with st.spinner(f"正在分析 {f.name}..."):
                            # 注意：这里传入的是 st.session_state 里的值
                            res = analyze_batch_candidate(extract_text_from_file(f), st.session_state["jd_text"], st.session_state["must_haves"], st.session_state["role_type"])
                            res['file_name'] = f.name
                            res['role_type'] = st.session_state["role_type"]
                            st.session_state["batch_data"].append(res)
                        bar.progress((i+1)/len(files))
                    st.rerun()

    if st.session_state["batch_data"]:
        # --- 2. 候选人排行榜 ---
        with st.container():
            current_role = st.session_state["role_type"]
            st.subheader(f"候选人排行榜: {current_role}")
            
            table_data = []
            for c in st.session_state["batch_data"]:
                row = {
                    "姓名": c.get('name'),
                    "AI 匹配度": c.get('fit_score'),
                }
                
                # 根据角色显示不同列
                if "PI" in current_role or "Postdoc" in current_role:
                    bib = c.get('bibliometrics', {})
                    row["H指数"] = bib.get('h_index', 'N/A')
                    row["引用数"] = bib.get('total_citations', 'N/A')
                    row["研究方向"] = c.get('research_focus_area', 'N/A')
                    
                elif "科研助理" in current_role: # RA
                    row["实验室经验(年)"] = c.get('lab_experience_years', 'N/A')
                    skills = c.get('technical_skills', [])
                    row["核心技能"] = ", ".join(skills[:3]) if skills else "N/A"
                    
                else: # Admin
                    row["工作年限"] = c.get('years_experience', 'N/A')
                    row["核心能力"] = c.get('core_competencies', [""])[0]

                table_data.append(row)
            
            df = pd.DataFrame(table_data).sort_values(by="AI 匹配度", ascending=False)
            
            st.dataframe(
                df, 
                use_container_width=True, 
                hide_index=True, 
                column_config={
                    "AI 匹配度": st.column_config.ProgressColumn("匹配度", format="%d", min_value=0, max_value=100),
                }
            )
        
        # --- 3. 深度画像卡片 ---
        st.subheader("🔍 候选人深度画像")
        sel = st.selectbox("选择候选人查看详情", df['姓名'].tolist())
        cand = next(c for c in st.session_state["batch_data"] if c.get('name') == sel)
        
        # A. 头部信息
        with st.container():
            c1, c2 = st.columns([3, 1])
            with c1:
                lang_tag = "🇨🇳 中文" if cand.get('language_preference') == 'Chinese' else "🇬🇧 English"
                st.markdown(f"## {cand.get('name')} <span style='font-size:0.5em; background:#eee; padding:5px; border-radius:5px'>{lang_tag}</span>", unsafe_allow_html=True)
                st.caption(f"邮箱: {cand.get('email')} | 赛道: {current_role}")
            with c2:
                st.metric("最终匹配得分", cand.get('fit_score'))

        # B. 角色专属指标
        if "PI" in current_role or "Postdoc" in current_role:
            with st.container():
                st.markdown("#### 📚 学术指标 (Bibliometrics)")
                bib = cand.get('bibliometrics', {})
                m1, m2, m3, m4 = st.columns(4)
                with m1: st.markdown(f"<div class='metric-card'><div class='metric-val'>{bib.get('h_index', 'N/A')}</div><div class='metric-lbl'>H-Index</div></div>", unsafe_allow_html=True)
                with m2: st.markdown(f"<div class='metric-card'><div class='metric-val'>{bib.get('total_citations', 'N/A')}</div><div class='metric-lbl'>引用数</div></div>", unsafe_allow_html=True)
                with m3: st.markdown(f"<div class='metric-card'><div class='metric-val'>{bib.get('total_paper_count', 'N/A')}</div><div class='metric-lbl'>论文总数</div></div>", unsafe_allow_html=True)
                with m4: st.markdown(f"<div class='metric-card'><div class='metric-val'>{len(cand.get('grants_found', []))}</div><div class='metric-lbl'>基金项目</div></div>", unsafe_allow_html=True)
                
                st.write("")
                st.info(f"**研究方向:** {cand.get('research_focus_area', '未识别')}")
                st.markdown("##### ⭐ 代表作")
                for p in cand.get('representative_papers', []):
                    st.markdown(f"- **{p.get('title')}** ({p.get('journal')}) - *{p.get('significance')}*")

        elif "科研助理" in current_role:
             with st.container():
                st.markdown("#### 🧬 技术栈与经验")
                m1, m2 = st.columns(2)
                with m1: st.markdown(f"<div class='metric-card'><div class='metric-val'>{cand.get('lab_experience_years', 'N/A')}</div><div class='metric-lbl'>实验室经验 (年)</div></div>", unsafe_allow_html=True)
                with m2: st.markdown(f"<div class='metric-card'><div class='metric-val'>{len(cand.get('project_participation', []))}</div><div class='metric-lbl'>参与项目数</div></div>", unsafe_allow_html=True)
                
                st.write("")
                st.markdown("##### 🛠️ 技能标签")
                skills_html = ""
                for skill in cand.get('technical_skills', []):
                    skills_html += f"<span class='skill-tag'>{skill}</span>"
                st.markdown(skills_html, unsafe_allow_html=True)

        # C. 总结与风控
        with st.container():
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("#### 📝 AI 综合评价")
                st.write(cand.get('summary'))
                st.markdown("**✅ 核心优势**")
                for s in cand.get('strengths', []): st.info(s, icon="✅")
            with c2:
                st.markdown("#### ⚠️ 风险预警 (Agent 2)")
                critique = cand.get('critique_notes', '无明显风险')
                if "未发现" in critique or "No major" in critique:
                    st.success("简历通过风控筛查")
                else:
                    st.error(critique)

# =========================================================
# 视图 2: 智能邀约
# =========================================================
elif page == "📧 智能邀约助手":
    st.title("智能邮件邀约助手")
    
    with st.container():
        st.subheader("👤 发信人配置")
        c1, c2, c3 = st.columns(3)
        with c1: sender_name = st.text_input("姓名", value="Hongli Ding")
        with c2: sender_title = st.text_input("头衔", value="Talent Acquisition Specialist")
        with c3: sender_org = st.text_input("单位", value="Zhejiang University Medical Center")
        
        with st.expander("🔐 邮箱 SMTP 设置 (发送真实邮件需配置)"):
            sender_email = st.text_input("邮箱地址")
            sender_password = st.text_input("应用专用密码 (App Password)", type="password")

    if st.session_state["batch_data"]:
        with st.container():
            st.subheader("✉️ 生成邮件草稿")
            names = [c.get('name') for c in st.session_state["batch_data"]]
            sel = st.selectbox("选择候选人", names)
            cand = next(c for c in st.session_state["batch_data"] if c.get('name') == sel)
            
            # 显示检测到的语言
            lang = cand.get('language_preference', 'English')
            st.caption(f"检测到候选人语言偏好: {lang} -> 将生成对应语言邮件")
            
            if st.button("✨ 智能生成草稿"):
                with st.spinner("AI 正在根据简历细节撰写邮件..."):
                    sender_info = {"name": sender_name, "title": sender_title, "org": sender_org}
                    st.session_state['draft'] = generate_recruitment_email(cand, sender_info, cand.get('role_type', 'Role'))
            
            if 'draft' in st.session_state:
                subj = st.text_input("邮件主题", value=f"Job Opportunity at {sender_org}")
                recip = st.text_input("收件人邮箱", value=cand.get('email', ''))
                body = st.text_area("邮件正文", st.session_state['draft'], height=350)
                
                if st.button("发送邮件 🚀", type="primary"):
                    if not sender_email or not sender_password:
                        st.error("请先在上方配置 SMTP 邮箱密码")
                    else:
                        ok, msg = send_real_email(sender_email, sender_password, recip, subj, body)
                        if ok: st.success(f"邮件已发送给 {cand.get('name')}!")
                        else: st.error(msg)

