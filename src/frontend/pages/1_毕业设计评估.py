import streamlit as st
import requests
import json
import os
import re

API_BASE_URL = "http://localhost:8000"

def clean_pdf_text(text):
    """
    智能清理PDF提取的文本，保留可读性和段落结构
    
    改进点：
    1. 保留合理的空格（区分中英文）
    2. 保留段落结构（双换行）
    3. 智能处理行内多余空白
    4. 清理中文文本中的多余空格
    """
    if not text:
        return ""
    
    text = ''.join(c if c.isprintable() or c in '\n\t\r' else '' for c in text)
    
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        line = re.sub(r'[ \t]+', ' ', line)
        cleaned_lines.append(line)
    
    text = '\n'.join(cleaned_lines)
    
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    text = clean_chinese_spaces(text)
    
    return text

def clean_chinese_spaces(text):
    """
    清理中文文本中的多余空格
    
    规则：
    1. 移除中文字符之间的空格
    2. 移除中文标点前后的空格
    3. 保留英文单词之间的空格
    4. 保留数字与英文之间的空格
    """
    if not text:
        return ""
    
    chinese_punctuation = '，。！？、；：""''（）【】《》—…·'
    
    for _ in range(5):
        old_text = text
        text = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', text)
        if text == old_text:
            break
    
    for _ in range(5):
        old_text = text
        text = re.sub(r'([\u4e00-\u9fff])\s+([' + re.escape(chinese_punctuation) + r'])', r'\1\2', text)
        text = re.sub(r'([' + re.escape(chinese_punctuation) + r'])\s+([\u4e00-\u9fff])', r'\1\2', text)
        if text == old_text:
            break
    
    for _ in range(5):
        old_text = text
        text = re.sub(r'\s+([' + re.escape(chinese_punctuation) + r'])', r'\1', text)
        text = re.sub(r'([' + re.escape(chinese_punctuation) + r'])\s+', r'\1', text)
        if text == old_text:
            break
    
    text = re.sub(r'([\u4e00-\u9fff])\s+([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z])\s+([\u4e00-\u9fff])', r'\1 \2', text)
    
    text = re.sub(r'([\u4e00-\u9fff])\s+(\d)', r'\1\2', text)
    text = re.sub(r'(\d)\s+([\u4e00-\u9fff])', r'\1\2', text)
    
    text = re.sub(r' +', ' ', text)
    
    return text

def extract_pdf_with_pymupdf(file_path):
    """使用PyMuPDF提取PDF内容（对中文支持最好）"""
    try:
        import fitz
        doc = fitz.open(file_path)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)
    except ImportError:
        return ""
    except Exception as e:
        return ""

def extract_pdf_with_pdfplumber(file_path):
    """使用pdfplumber提取PDF内容"""
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        return ""

def extract_pdf_content(file_path):
    """
    提取PDF内容（改进版）
    
    使用多库组合策略：
    1. 优先使用PyMuPDF（对中文支持最好）
    2. 备用pdfplumber
    3. 最后使用pypdf/PyPDF2
    """
    content = extract_pdf_with_pymupdf(file_path)
    if content.strip():
        return clean_pdf_text(content)
    
    content = extract_pdf_with_pdfplumber(file_path)
    if content.strip():
        return clean_pdf_text(content)
    
    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += clean_pdf_text(page_text) + "\n"
        return text
    except:
        pass
    
    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += clean_pdf_text(page_text) + "\n"
            return text
    except:
        pass
    
    return ""

st.set_page_config(
    page_title="毕业设计评估",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 毕业设计评估")

st.markdown("""
**功能说明：**
- 自动检测项目类型（算法类、仿真类、实物类、传统机械类、混合类）
- 使用确定性评价标准，确保评价结果一致
- 不同项目类型有不同的评价指标和权重
- 支持校方固有评价体系融合评分
""")

detected_type_display = st.empty()

try:
    types_response = requests.get(f"{API_BASE_URL}/project_types")
    if types_response.status_code == 200:
        project_types = types_response.json().get('project_types', [])
        
        type_options = {"自动检测（基于摘要分析）": None}
        for pt in project_types:
            type_options[f"{pt['name']} ({pt['indicators_count']}个指标)"] = pt['value']
        
        detected_type = st.session_state.get('detected_project_type', None)
        detected_type_name = st.session_state.get('detected_project_type_name', None)
        
        if detected_type and detected_type_name:
            detected_type_display.success(f"🎯 已检测到论文类型：**{detected_type_name}**")
        
        selected_type = st.selectbox(
            "选择项目类型（可选，不选则使用自动检测结果）",
            options=list(type_options.keys())
        )
        project_type_value = type_options[selected_type]
        
        if not project_type_value and detected_type:
            project_type_value = detected_type
        
        if project_type_value:
            with st.expander(f"📋 查看评价标准"):
                standards_response = requests.get(f"{API_BASE_URL}/evaluation_standards/{project_type_value}")
                if standards_response.status_code == 200:
                    standards_data = standards_response.json()
                    standards = standards_data.get('standards', {})
                    
                    st.markdown(f"**描述：** {standards.get('description', '')}")
                    
                    indicators = standards.get('indicators', [])
                    if indicators:
                        st.markdown("### 评价指标")
                        for ind in indicators:
                            st.markdown(f"**{ind['name']}** (权重: {ind['weight']}%)")
                            st.markdown(f"- 描述: {ind['description']}")
                            with st.expander("查看评分等级"):
                                grades = ind.get('grade_levels', {})
                                for level, desc in grades.items():
                                    level_name = {"excellent": "优秀", "good": "良好", "medium": "中等", "pass": "及格", "fail": "不及格"}.get(level, level)
                                    st.markdown(f"- **{level_name}**: {desc}")
                            st.markdown("---")
                    
                    excluded = standards.get('excluded_indicators', [])
                    if excluded:
                        st.warning(f"⚠️ 本类型不评价以下内容: {', '.join(excluded)}")
    else:
        st.warning("无法获取项目类型列表")
        project_type_value = None
except Exception as e:
    st.error(f"获取项目类型失败: {str(e)}")
    project_type_value = None

st.markdown("---")

st.subheader("📋 评价指导指标")
st.markdown("选择已在大纲管理页面提炼或衍生的评价指标")

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

extracted_dir = os.path.join(project_root, "extracted_indicators")
derived_dir = os.path.join(project_root, "derived_standards")

indicator_files = []

if os.path.exists(extracted_dir):
    for f in os.listdir(extracted_dir):
        if f.endswith('.json'):
            indicator_files.append(("提炼指标", os.path.join(extracted_dir, f), f))

if os.path.exists(derived_dir):
    for f in os.listdir(derived_dir):
        if f.endswith('.json'):
            indicator_files.append(("衍生指标", os.path.join(derived_dir, f), f))

if not indicator_files:
    st.warning("⚠️ 没有找到已提炼的评价指标，请先在大纲管理页面提炼或生成评价指标")
    extracted_guidance = None
else:
    type_labels = [f"[{t}] {n}" for t, p, n in indicator_files]
    selected_indicator_idx = st.selectbox(
        "选择评价指标",
        options=range(len(indicator_files)),
        format_func=lambda x: type_labels[x],
        help="选择已提炼或衍生的评价指标"
    )
    
    selected_type, selected_path, selected_name = indicator_files[selected_indicator_idx]
    st.info(f"📄 已选择: {selected_name} ({selected_type})")
    
    try:
        with open(selected_path, 'r', encoding='utf-8') as f:
            extracted_guidance = json.load(f)
        
        st.session_state["extracted_guidance"] = extracted_guidance
        
        with st.expander("📝 查看指标详情"):
            if extracted_guidance.get('indicators'):
                st.markdown("### 📋 评价指标")
                for ind in extracted_guidance.get('indicators', []):
                    st.markdown(f"**{ind.get('name', '')}** (权重: {ind.get('weight', '未知')})")
                    if ind.get('description'):
                        st.markdown(f"- 描述: {ind.get('description')}")
                    st.markdown("")
            
            if extracted_guidance.get('grading_levels'):
                st.markdown("### 📊 评分等级")
                grading = extracted_guidance.get('grading_levels', {})
                for level, desc in grading.items():
                    level_names = {
                        "excellent": "优秀",
                        "good": "良好",
                        "medium": "中等",
                        "pass": "及格",
                        "fail": "不及格"
                    }
                    st.markdown(f"**{level_names.get(level, level)}**: {desc}")
            
            if extracted_guidance.get('key_requirements'):
                st.markdown("### 📌 关键要求")
                for req in extracted_guidance.get('key_requirements', []):
                    st.markdown(f"- {req}")
            
            if extracted_guidance.get('summary'):
                st.markdown("### 📝 总结")
                st.write(extracted_guidance.get('summary', ''))
            
            if extracted_guidance.get('grade_levels'):
                st.markdown("### 📊 评分等级详情")
                for ind in extracted_guidance.get('indicators', []):
                    if ind.get('grade_levels'):
                        st.markdown(f"**{ind.get('name', '')}**")
                        for level, desc in ind.get('grade_levels', {}).items():
                            level_names = {
                                "excellent": "优秀",
                                "good": "良好",
                                "medium": "中等",
                                "pass": "及格",
                                "fail": "不及格"
                            }
                            st.markdown(f"- **{level_names.get(level, level)}**: {desc}")
                        st.markdown("")
    except Exception as e:
        st.error(f"❌ 读取评价指标失败: {str(e)}")
        extracted_guidance = None

st.markdown("---")

st.subheader("⚙️ 评分方式")
evaluation_method = st.radio(
    "选择评分方式",
    options=[
        ("LLM确定性评分（结果一致，可复现）", "rule_engine"),
        ("分段评估（智能分段，适合长篇论文）", "sectioned"),
        ("LLM灵活评分（灵活性高，可能有波动）", "llm")
    ],
    format_func=lambda x: x[0],
    help="确定性评分确保相同输入产生相同输出；分段评估适合长篇论文，解决内容丢失问题"
)

method_value = evaluation_method[1]

if method_value == "rule_engine":
    st.info("💡 LLM确定性评分特点：\n- 相同论文多次评分结果完全一致\n- 基于大模型深度理解论文内容\n- 适合标准化、可复现的评价")
elif method_value == "sectioned":
    st.info("💡 分段评估特点：\n- 智能识别论文结构，按章节分段评估\n- 检测章节之间的逻辑衔接\n- 检测承诺-兑现一致性\n- 适合长篇论文，解决内容丢失问题")
else:
    st.warning("⚠️ 大模型灵活评分特点：\n- 评分更灵活，能理解语义\n- 相同论文多次评分可能有差异\n- 适合需要深度理解的评价")

st.markdown("---")

st.subheader("📄 选择毕业设计论文")
st.markdown("从已上传的毕业设计提交中选择论文进行评估")

submission_content = st.session_state.get('submission_content', "")
student_info = {}
selected_submission_data = None

try:
    submissions_response = requests.get(f"{API_BASE_URL}/submissions", params={"limit": 100})
    if submissions_response.status_code == 200:
        all_submissions = submissions_response.json()
        graduation_submissions = [s for s in all_submissions if s.get('submission_purpose', 'normal') == 'graduation']
        
        if graduation_submissions:
            submission_options = {}
            for sub in graduation_submissions:
                sub_id = sub.get('submission_id', '')
                title = sub.get('title', '无标题')
                student_id = sub.get('student_id', '未知学号')
                created_at = sub.get('created_at', '')[:10] if sub.get('created_at') else ''
                label = f"{title} - {student_id} ({created_at})"
                submission_options[label] = sub_id
            
            selected_label = st.selectbox(
                "选择毕业设计提交",
                options=list(submission_options.keys()),
                help="选择已上传的毕业设计论文"
            )
            
            selected_submission_id = submission_options[selected_label]
            
            if selected_submission_id:
                detail_response = requests.get(f"{API_BASE_URL}/submissions/{selected_submission_id}")
                if detail_response.status_code == 200:
                    selected_submission_data = detail_response.json()
                    
                    files_response = requests.get(f"{API_BASE_URL}/submissions/{selected_submission_id}/files")
                    if files_response.status_code == 200:
                        files = files_response.json()
                        
                        if files:
                            st.markdown(f"**📎 关联文件 ({len(files)} 个):**")
                            for f in files:
                                st.markdown(f"- {f.get('file_name', '未知文件')} ({f.get('media_type', '未知类型')})")
                            
                            with st.spinner("正在读取文件内容..."):
                                all_content = []
                                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                                
                                for f in files:
                                    file_path = f.get('file_path', '')
                                    file_name = f.get('file_name', '未知文件')
                                    
                                    if file_path and not os.path.isabs(file_path):
                                        file_path = os.path.join(project_root, file_path)
                                    
                                    try:
                                        file_ext = os.path.splitext(file_path)[1].lower() if file_path else ''
                                        
                                        if file_path and os.path.exists(file_path):
                                            if file_ext == '.pdf':
                                                content = extract_pdf_content(file_path)
                                                if content.strip():
                                                    all_content.append(f"【{file_name}】\n{content}")
                                                else:
                                                    st.warning(f"⚠️ PDF文件 {file_name} 内容为空")
                                            elif file_ext in ['.docx', '.doc']:
                                                from docx import Document
                                                doc = Document(file_path)
                                                content = "\n".join([para.text for para in doc.paragraphs])
                                                all_content.append(f"【{file_name}】\n{content}")
                                            elif file_ext in ['.txt', '.md']:
                                                with open(file_path, 'r', encoding='utf-8') as file:
                                                    content = file.read()
                                                all_content.append(f"【{file_name}】\n{content}")
                                        else:
                                            st.warning(f"⚠️ 文件路径不存在: {file_path}")
                                    except Exception as e:
                                        st.warning(f"读取文件 {file_name} 失败: {str(e)}")
                            
                            if all_content:
                                submission_content = "\n\n".join(all_content)
                                st.session_state['submission_content'] = submission_content
                                st.success(f"✅ 已读取论文内容 ({len(submission_content)} 字符)")
                                
                                with st.spinner("正在分析论文摘要和类型..."):
                                    try:
                                        analyze_response = requests.post(
                                            f"{API_BASE_URL}/analyze_thesis_abstract",
                                            json={
                                                "content": submission_content,
                                                "title": selected_submission_data.get('title', '')
                                            },
                                            timeout=60
                                        )
                                        
                                        if analyze_response.status_code == 200:
                                            analyze_result = analyze_response.json()
                                            
                                            st.markdown("---")
                                            st.markdown("### 📄 论文摘要")
                                            
                                            if analyze_result.get('has_abstract'):
                                                abstract = analyze_result.get('abstract', '')
                                                st.info(f"**摘要内容：**\n\n{abstract}")
                                                
                                                st.markdown("### 🏷️ 自动检测论文类型")
                                                project_type = analyze_result.get('project_type', 'mixed')
                                                project_type_name = analyze_result.get('project_type_name', '混合类')
                                                confidence = analyze_result.get('confidence', 0)
                                                reason = analyze_result.get('reason', '')
                                                features = analyze_result.get('features', {})
                                                
                                                col_type1, col_type2 = st.columns(2)
                                                with col_type1:
                                                    st.metric("检测类型", project_type_name)
                                                with col_type2:
                                                    st.metric("置信度", f"{confidence*100:.0f}%")
                                                
                                                if reason:
                                                    st.markdown(f"**判断理由：** {reason}")
                                                
                                                with st.expander("📊 查看详细判断依据"):
                                                    st.markdown("#### 检测维度分析")
                                                    
                                                    if features:
                                                        keyword_scores = features.get('keyword_scores', {})
                                                        chapter_features = features.get('chapter_features', {})
                                                        tech_terms = features.get('tech_terms', {})
                                                        final_scores = features.get('final_scores', {})
                                                        matched_keywords = features.get('matched_keywords', {})
                                                        matched_chapters = features.get('matched_chapters', {})
                                                        
                                                        type_labels = {
                                                            'algorithm': '算法类',
                                                            'simulation': '仿真类',
                                                            'physical': '实物类',
                                                            'traditional_mechanical': '传统机械类',
                                                            'mixed': '混合类'
                                                        }
                                                        
                                                        st.markdown("##### 1️⃣ 关键词特征分析 (权重60%)")
                                                        if keyword_scores:
                                                            kw_data = []
                                                            for type_key, score in keyword_scores.items():
                                                                kw_data.append({
                                                                    "类型": type_labels.get(type_key, type_key),
                                                                    "得分": f"{score:.3f}",
                                                                    "得分条": "█" * int(score * 20)
                                                                })
                                                            st.table(kw_data)
                                                            
                                                            if matched_keywords:
                                                                st.markdown("**匹配到的关键词详情：**")
                                                                for type_key, keywords in matched_keywords.items():
                                                                    if keywords:
                                                                        kw_detail = "、".join([f"「{k[0]}」(权重{k[1]}, 出现{k[2]}次)" for k in keywords[:5]])
                                                                        st.markdown(f"- **{type_labels.get(type_key, type_key)}**: {kw_detail}")
                                                        
                                                        st.markdown("##### 2️⃣ 章节结构分析 (权重30%)")
                                                        if chapter_features:
                                                            ch_data = []
                                                            for type_key, score in chapter_features.items():
                                                                ch_data.append({
                                                                    "类型": type_labels.get(type_key, type_key),
                                                                    "得分": f"{score:.3f}",
                                                                    "得分条": "█" * int(score * 20)
                                                                })
                                                            st.table(ch_data)
                                                            
                                                            if matched_chapters:
                                                                st.markdown("**匹配到的章节标题：**")
                                                                for type_key, chapters in matched_chapters.items():
                                                                    if chapters:
                                                                        st.markdown(f"- **{type_labels.get(type_key, type_key)}**: {', '.join(chapters)}")
                                                        
                                                        st.markdown("##### 3️⃣ 技术术语识别 (权重10%)")
                                                        if tech_terms:
                                                            for type_key, terms in tech_terms.items():
                                                                if terms:
                                                                    st.markdown(f"**{type_labels.get(type_key, type_key)}**: {', '.join(terms[:5])}")
                                                        
                                                        st.markdown("##### 4️⃣ 综合评分")
                                                        if final_scores:
                                                            st.markdown("| 类型 | 综合得分 | 得分可视化 |")
                                                            st.markdown("|:---:|:---:|:---|")
                                                            sorted_scores = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
                                                            for type_key, score in sorted_scores:
                                                                is_winner = type_key == project_type
                                                                marker = "🏆 " if is_winner else ""
                                                                bar_len = int(score * 50)
                                                                bar = "█" * bar_len + "░" * (50 - bar_len)
                                                                st.markdown(f"| {marker}{type_labels.get(type_key, type_key)} | {score:.3f} | {bar} |")
                                                    
                                                    st.markdown("---")
                                                    st.markdown("##### 📝 检测说明")
                                                    st.markdown("""
                                                    - **关键词特征**：分析论文中出现的技术关键词，根据权重和出现次数计算得分
                                                    - **章节结构**：识别论文章节标题，匹配典型章节模式
                                                    - **技术术语**：识别具体的技术名词，如CNN、ANSYS、STM32等
                                                    - **综合评分**：关键词60% + 章节结构30% + 技术术语10%
                                                    - **判断依据**：得分最高的类型即为检测结果
                                                    """)
                                                
                                                st.session_state['detected_project_type'] = project_type
                                                st.session_state['detected_project_type_name'] = project_type_name
                                                
                                                with st.expander("📖 查看论文内容片段（确认提取正确）"):
                                                    chapter_options = ["全文预览", "摘要", "引言", "绪论", "结论", "总结", "参考文献", "致谢"]
                                                    
                                                    if 'selected_chapter' not in st.session_state:
                                                        st.session_state['selected_chapter'] = "全文预览"
                                                    
                                                    selected_chapter = st.selectbox("选择要查看的章节", chapter_options, key="chapter_selector_main")
                                                    
                                                    current_content = st.session_state.get('submission_content', submission_content)
                                                    
                                                    if selected_chapter == "全文预览":
                                                        st.text_area("内容预览", current_content[:3000] + "..." if len(current_content) > 3000 else current_content, height=300, disabled=True, key="full_content_preview")
                                                    else:
                                                        try:
                                                            chapter_response = requests.post(
                                                                f"{API_BASE_URL}/extract_chapter",
                                                                json={"content": current_content, "chapter_name": selected_chapter},
                                                                timeout=30
                                                            )
                                                            if chapter_response.status_code == 200:
                                                                chapter_data = chapter_response.json()
                                                                if chapter_data.get("has_content"):
                                                                    st.text_area(f"{selected_chapter}内容", chapter_data.get("content", ""), height=300, disabled=True, key=f"chapter_content_{selected_chapter}")
                                                                else:
                                                                    st.info(f"未能提取到「{selected_chapter}」内容")
                                                            else:
                                                                st.warning(f"提取章节失败: {chapter_response.status_code}")
                                                        except Exception as e:
                                                            st.warning(f"提取章节出错: {str(e)}")
                                                            st.text_area("内容预览", current_content[:3000] + "..." if len(current_content) > 3000 else current_content, height=300, disabled=True, key="fallback_preview")
                                            else:
                                                st.warning("⚠️ 未能从论文中提取到摘要")
                                                with st.expander("📖 查看论文内容片段"):
                                                    chapter_options = ["全文预览", "摘要", "引言", "绪论", "结论", "总结", "参考文献", "致谢"]
                                                    selected_chapter = st.selectbox("选择要查看的章节", chapter_options, key="chapter_selector_no_abstract")
                                                    
                                                    current_content = st.session_state.get('submission_content', submission_content)
                                                    
                                                    if selected_chapter == "全文预览":
                                                        st.text_area("内容预览", current_content[:3000] + "..." if len(current_content) > 3000 else current_content, height=300, disabled=True, key="full_content_preview_no_abstract")
                                                    else:
                                                        try:
                                                            chapter_response = requests.post(
                                                                f"{API_BASE_URL}/extract_chapter",
                                                                json={"content": current_content, "chapter_name": selected_chapter},
                                                                timeout=30
                                                            )
                                                            if chapter_response.status_code == 200:
                                                                chapter_data = chapter_response.json()
                                                                if chapter_data.get("has_content"):
                                                                    st.text_area(f"{selected_chapter}内容", chapter_data.get("content", ""), height=300, disabled=True, key=f"chapter_content_{selected_chapter}_no_abstract")
                                                                else:
                                                                    st.info(f"未能提取到「{selected_chapter}」内容")
                                                            else:
                                                                st.warning(f"提取章节失败: {chapter_response.status_code}")
                                                        except Exception as e:
                                                            st.warning(f"提取章节出错: {str(e)}")
                                                            st.text_area("内容预览", current_content[:3000] + "..." if len(current_content) > 3000 else current_content, height=300, disabled=True, key="fallback_preview_no_abstract")
                                                st.session_state['detected_project_type'] = None
                                        else:
                                            st.warning("⚠️ 论文分析失败")
                                    except Exception as e:
                                        st.warning(f"⚠️ 论文分析出错: {str(e)}")
                            else:
                                st.warning("⚠️ 未能读取到文件内容")
                        else:
                            st.warning("⚠️ 该提交没有关联文件")
                    
                    student_info = {
                        "name": selected_submission_data.get('student_id', ''),
                        "student_id": selected_submission_data.get('student_id', ''),
                        "title": selected_submission_data.get('title', ''),
                        "submission_id": selected_submission_id
                    }
        else:
            st.warning("⚠️ 没有找到毕业设计提交，请先在\"文件上传\"页面上传毕业设计论文")
            st.info("💡 提示：上传时请选择\"毕业设计\"作为提交目的")
    else:
        st.error("❌ 获取提交列表失败")
except Exception as e:
    st.error(f"❌ 获取毕业设计提交失败: {str(e)}")

st.markdown("---")
st.markdown("### ⚙️ 评估选项")

col_opt1, col_opt2 = st.columns(2)
with col_opt1:
    use_cache = st.checkbox(
        "使用缓存结果", 
        value=True, 
        help="启用后，相同论文内容将返回缓存的评估结果，确保100%一致性；禁用后每次重新评估，分数可能有1-3分波动"
    )
with col_opt2:
    if use_cache:
        st.info("🔒 缓存模式：相同内容100%返回相同结果")
    else:
        st.warning("🔄 实时模式：每次重新评估，分数可能有1-3分波动")

st.markdown("---")

with st.expander("⚖️ 融合评价设置", expanded=False):
    st.markdown("""
    配置校方固有评价体系的权重和融合系数。这些设置将影响毕业设计论文的最终评分。
    
    💡 **说明：**
    - **维度权重**：各维度在融合计算中的权重比例，总和应为100%
    - **融合系数**：根据各维度评分等级确定的调节系数范围
    - 最终分数 = 原始指标分数 × 综合调节系数
    """)
    
    institutional_config_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'institutional_criteria.json')
    
    if 'institutional_config' not in st.session_state:
        try:
            with open(institutional_config_path, 'r', encoding='utf-8') as f:
                st.session_state.institutional_config = json.load(f)
        except Exception as e:
            st.error(f"❌ 加载配置文件失败: {str(e)}")
            st.session_state.institutional_config = None
    
    dimension_weights = {}
    
    if st.session_state.institutional_config:
        config = st.session_state.institutional_config
        dimensions = config.get('dimensions', [])
        
        st.subheader("📊 维度重要程度设置")
        st.markdown("设置各评价维度的重要程度（0-10），系统将自动计算权重比例")
        
        for dim in dimensions:
            dim_id = dim.get('dimension_id', '')
            importance_key = f"thesis_importance_{dim_id}"
            if importance_key not in st.session_state:
                default_weight = dim.get('weight', 0.25)
                default_importance = int(default_weight * 10)
                st.session_state[importance_key] = min(10, max(1, default_importance))
        
        importance_values = {}
        importance_cols = st.columns(len(dimensions))
        
        for i, dim in enumerate(dimensions):
            dim_id = dim.get('dimension_id', '')
            dim_name = dim.get('name', dim_id)
            
            with importance_cols[i]:
                importance = st.slider(
                    f"{dim_name}",
                    min_value=0,
                    max_value=10,
                    value=st.session_state[f"thesis_importance_{dim_id}"],
                    step=1,
                    key=f"thesis_importance_{dim_id}",
                    help=f"设置{dim_name}的重要程度"
                )
                importance_values[dim_id] = importance
        
        total_importance = sum(importance_values.values())
        
        dimension_weights = {}
        if total_importance > 0:
            for dim in dimensions:
                dim_id = dim.get('dimension_id', '')
                weight = round(importance_values.get(dim_id, 1) * 100 / total_importance)
                dimension_weights[dim_id] = weight
        else:
            for dim in dimensions:
                dimension_weights[dim.get('dimension_id', '')] = 25
        
        st.session_state['dimension_weights'] = dimension_weights
        
        st.divider()
        st.subheader("📈 自动计算权重")
        
        weight_display_cols = st.columns(len(dimensions))
        for i, dim in enumerate(dimensions):
            dim_id = dim.get('dimension_id', '')
            dim_name = dim.get('name', dim_id)
            weight = dimension_weights.get(dim_id, 25)
            
            with weight_display_cols[i]:
                st.metric(dim_name, f"{weight}%")
        
        st.divider()
        st.subheader("🔧 融合系数设置")
        st.markdown("""
        设置各评分等级对应的融合系数。融合系数用于调整最终分数。
        
        💡 **说明：**
        - **融合系数 > 1**：分数提升（表现好的维度）
        - **融合系数 = 1**：分数不变
        - **融合系数 < 1**：分数降低（表现差的维度）
        - 最终分数 = 原始分数 × 平均融合系数
        """)
        
        use_custom_coefficients = st.checkbox("使用自定义融合系数", value=False, key="use_custom_coefficients_checkbox")
        
        if use_custom_coefficients:
            st.markdown("**各等级融合系数设置：**")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.markdown("**优秀**")
                st.markdown("(90-100分)")
                excellent_coef = st.number_input("系数", min_value=0.50, max_value=2.00, value=1.15, step=0.01, key="coef_excellent")
            
            with col2:
                st.markdown("**良好**")
                st.markdown("(80-89分)")
                good_coef = st.number_input("系数", min_value=0.50, max_value=2.00, value=1.05, step=0.01, key="coef_good")
            
            with col3:
                st.markdown("**中等**")
                st.markdown("(70-79分)")
                medium_coef = st.number_input("系数", min_value=0.50, max_value=2.00, value=0.98, step=0.01, key="coef_medium")
            
            with col4:
                st.markdown("**及格**")
                st.markdown("(60-69分)")
                pass_coef = st.number_input("系数", min_value=0.50, max_value=2.00, value=0.90, step=0.01, key="coef_pass")
            
            with col5:
                st.markdown("**不及格**")
                st.markdown("(<60分)")
                fail_coef = st.number_input("系数", min_value=0.50, max_value=2.00, value=0.78, step=0.01, key="coef_fail")
            
            coefficient_config = {
                "excellent": excellent_coef,
                "good": good_coef,
                "medium": medium_coef,
                "pass": pass_coef,
                "fail": fail_coef
            }
            st.info(f"📊 自定义融合系数：优秀{excellent_coef:.2f}, 良好{good_coef:.2f}, 中等{medium_coef:.2f}, 及格{pass_coef:.2f}, 不及格{fail_coef:.2f}")
        else:
            coefficient_config = {
                "excellent": 1.15,
                "good": 1.05,
                "medium": 0.98,
                "pass": 0.90,
                "fail": 0.78
            }
            st.info("📊 使用默认融合系数：优秀1.15, 良好1.05, 中等0.98, 及格0.90, 不及格0.78")
        
        st.session_state['coefficient_config'] = coefficient_config
        
        col_save, col_reset = st.columns(2)
        with col_save:
            if st.button("💾 保存权重设置", use_container_width=True, type="primary"):
                for dim in dimensions:
                    dim_id = dim.get('dimension_id', '')
                    dim['weight'] = dimension_weights.get(dim_id, 25) / 100.0
                
                try:
                    with open(institutional_config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
                    st.session_state.institutional_config = config
                    st.success("✅ 权重已保存！")
                except Exception as e:
                    st.error(f"❌ 保存失败: {str(e)}")
        
        with col_reset:
            if st.button("🔄 重置默认", use_container_width=True):
                for dim in dimensions:
                    dim['weight'] = 0.25
                    dim_id = dim.get('dimension_id', '')
                    key = f"thesis_importance_{dim_id}"
                    if key in st.session_state:
                        del st.session_state[key]
                
                try:
                    with open(institutional_config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
                    st.session_state.institutional_config = config
                    st.success("✅ 已重置为默认值！")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 重置失败: {str(e)}")
        
        st.divider()

st.markdown("---")

if st.button("🚀 开始毕业设计评估", use_container_width=True, type="primary"):
    if not submission_content:
        st.error("❌ 请选择毕业设计论文")
    elif method_value == "rule_engine" and not extracted_guidance:
        st.error("❌ 规则引擎评分需要先选择评价指标")
    elif method_value == "sectioned" and not extracted_guidance:
        st.error("❌ 分段评估需要先选择评价指标")
    else:
        current_dimension_weights = st.session_state.get('dimension_weights', {})
        current_coefficient_config = st.session_state.get('coefficient_config', {})
        current_use_custom_coefficients = st.session_state.get('use_custom_coefficients_checkbox', False)
        
        if method_value == "rule_engine":
            with st.spinner("正在进行LLM确定性评分（这可能需要1-2分钟）..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/evaluate_with_rule_engine",
                        json={
                            "submission_content": submission_content,
                            "indicators": extracted_guidance,
                            "student_info": student_info,
                            "use_cache": use_cache,
                            "dimension_weights": current_dimension_weights,
                            "coefficient_config": current_coefficient_config,
                            "use_custom_coefficients": current_use_custom_coefficients
                        },
                        timeout=180
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        st.success("✅ 评估完成！（确定性评分，结果可复现）")
                        
                        st.markdown("---")
                        st.header("📊 评估结果总览")
                        
                        original_score = result.get('original_score', 0)
                        fusion_score = result.get('overall_score', 0)
                        grade_level = result.get('grade_level', '')
                        fusion_coefficient = result.get('fusion_coefficient', 1.0)
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("原始评分", f"{original_score}分")
                        with col2:
                            st.metric("融合系数", f"{fusion_coefficient:.4f}")
                        with col3:
                            st.metric("最终评分", f"{fusion_score}分")
                        with col4:
                            st.metric("等级", grade_level)
                        
                        st.markdown("---")
                        
                        with st.expander("📋 第一部分：原始大模型评分结果", expanded=True):
                            st.subheader("🤖 规则引擎评分详情")
                            st.info("以下是基于评价指标的原始大模型评分结果，包含各指标的评分理由和论文证据。")
                            
                            overall_comment = result.get('overall_comment', '')
                            if overall_comment:
                                st.markdown("**总体评价:**")
                                st.markdown(overall_comment)
                                st.markdown("")
                            
                            dimension_scores = result.get('dimension_scores', [])
                            if dimension_scores:
                                st.markdown("**各指标评分详情:**")
                                
                                for ds in dimension_scores:
                                    indicator_id = ds.get('indicator_id', '未知指标')
                                    indicator_name = ds.get('indicator_name', indicator_id)
                                    score = ds.get('score', 0)
                                    grade = ds.get('grade_level', '')
                                    score_reason = ds.get('score_reason', '')
                                    evidence = ds.get('evidence', '')
                                    suggestions = ds.get('improvement_suggestions', [])
                                    
                                    with st.expander(f"**{indicator_name}** ({indicator_id}) - {score}分 ({grade})", expanded=False):
                                        if score_reason:
                                            st.markdown(f"**评分理由:**")
                                            st.markdown(score_reason)
                                            st.markdown("")
                                        
                                        if evidence:
                                            st.markdown(f"**论文证据:**")
                                            st.markdown(f"> {evidence}")
                                            st.markdown("")
                                        
                                        if suggestions:
                                            st.markdown(f"**改进建议:**")
                                            for s in suggestions:
                                                st.markdown(f"- {s}")
                            
                            strengths = result.get('strengths', [])
                            weaknesses = result.get('weaknesses', [])
                            
                            st.markdown("---")
                            col_s, col_w = st.columns(2)
                            with col_s:
                                if strengths:
                                    st.markdown("**💪 优势:**")
                                    for s in strengths:
                                        st.markdown(f"✅ {s}")
                            with col_w:
                                if weaknesses:
                                    st.markdown("**📌 待改进:**")
                                    for w in weaknesses:
                                        st.markdown(f"⚠️ {w}")
                        
                        institutional_eval = result.get('institutional_evaluation', {})
                        if institutional_eval and institutional_eval.get('institutional_scores'):
                            with st.expander("🏛️ 第二部分：校方固有评价体系评分", expanded=True):
                                st.subheader("🎓 四维度综合评价")
                                st.info("📋 校方固有评价体系包含四个核心维度，根据用户设置的权重进行评分。")
                                
                                dimension_weights = st.session_state.get('dimension_weights', {})
                                if dimension_weights:
                                    st.markdown("**用户设置的维度权重:**")
                                    weight_cols = st.columns(4)
                                    dim_name_map = {
                                        "innovation": "创新度",
                                        "research_depth": "研究分析深度",
                                        "structure": "文章结构",
                                        "method_experiment": "研究方法与实验"
                                    }
                                    for i, (dim_id, weight) in enumerate(dimension_weights.items()):
                                        with weight_cols[i]:
                                            dim_name = dim_name_map.get(dim_id, dim_id)
                                            st.metric(dim_name, f"{weight}%")
                                    st.markdown("")
                                
                                inst_scores = institutional_eval.get('institutional_scores', [])
                                overall_inst_score = institutional_eval.get('overall_institutional_score', 0)
                                overall_inst_grade = institutional_eval.get('overall_institutional_grade', '')
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric("固有体系加权总分", f"{overall_inst_score}分")
                                with col2:
                                    st.metric("总体等级", overall_inst_grade)
                                
                                st.markdown("---")
                                st.markdown("**各维度评分详情:**")
                                
                                for inst_score in inst_scores:
                                    dim_id = inst_score.get('dimension_id', '')
                                    dim_name = inst_score.get('dimension_name', '未知维度')
                                    dim_score = inst_score.get('score', 0)
                                    dim_grade = inst_score.get('grade_level', '')
                                    dim_reason = inst_score.get('score_reason', '')
                                    dim_evidence = inst_score.get('evidence', '')
                                    user_weight = dimension_weights.get(dim_id, 25)
                                    
                                    with st.expander(f"**{dim_name}** - {dim_score}分 ({dim_grade}) | 权重: {user_weight}%", expanded=False):
                                        st.markdown(f"**评分等级:** {dim_grade} (分数区间对应)")
                                        st.markdown(f"**评分理由:**")
                                        st.markdown(dim_reason if dim_reason else "无")
                                        if dim_evidence:
                                            st.markdown(f"**论文证据:**")
                                            st.markdown(f"> {dim_evidence}")
                            
                            fusion_details = result.get('fusion_details', {})
                            if fusion_details:
                                with st.expander("⚖️ 第三部分：融合计算详情", expanded=True):
                                    st.subheader("🔢 融合系数计算过程")
                                    st.info("根据各维度评分等级，使用用户设置的融合系数计算最终分数。")
                                    
                                    coefficient_config_used = fusion_details.get('coefficient_config_used', {})
                                    if coefficient_config_used:
                                        st.markdown("**使用的融合系数配置:**")
                                        grade_names = {
                                            "excellent": "优秀 (90-100分)",
                                            "good": "良好 (80-89分)",
                                            "medium": "中等 (70-79分)",
                                            "pass": "及格 (60-69分)",
                                            "fail": "不及格 (<60分)"
                                        }
                                        coef_cols = st.columns(5)
                                        for i, (grade_key, coef_value) in enumerate(coefficient_config_used.items()):
                                            with coef_cols[i]:
                                                grade_name = grade_names.get(grade_key, grade_key)
                                                if isinstance(coef_value, dict):
                                                    min_coef = coef_value.get('min', 1.0)
                                                    max_coef = coef_value.get('max', 1.0)
                                                    st.metric(grade_name, f"{min_coef:.2f}-{max_coef:.2f}")
                                                else:
                                                    st.metric(grade_name, f"{coef_value:.2f}")
                                        st.markdown("")
                                    
                                    dim_coefs = fusion_details.get('dimension_coefficients', {})
                                    if dim_coefs:
                                        st.markdown("**各维度融合系数计算:**")
                                        
                                        coef_data = []
                                        for dim_id, coef_info in dim_coefs.items():
                                            dim_name_map = {
                                                "innovation": "创新度",
                                                "research_depth": "研究分析深度",
                                                "structure": "文章结构",
                                                "method_experiment": "研究方法与实验"
                                            }
                                            display_name = dim_name_map.get(dim_id, dim_id)
                                            coef = coef_info.get('coefficient', 1.0)
                                            score = coef_info.get('score', 0)
                                            grade = coef_info.get('grade_level', '')
                                            coef_data.append({
                                                "维度": display_name,
                                                "评分": f"{score}分",
                                                "等级": grade,
                                                "融合系数": f"{coef:.4f}"
                                            })
                                        
                                        st.table(coef_data)
                                        
                                        st.markdown("**计算公式:**")
                                        st.markdown(f"```\n平均融合系数 = ({' + '.join([str(c['融合系数']) for c in coef_data])}) / {len(coef_data)} = {fusion_coefficient:.4f}\n```")
                                        st.markdown(f"```\n最终分数 = 原始分数 × 平均融合系数 = {original_score} × {fusion_coefficient:.4f} = {fusion_score:.1f}分\n```")
                                    
                                    adjustment = fusion_details.get('adjustment', 0)
                                    st.markdown("---")
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("原始评分", f"{original_score}分")
                                    with col2:
                                        st.metric("分数调整", f"{'+' if adjustment >= 0 else ''}{adjustment}分")
                                    with col3:
                                        st.metric("最终评分", f"{fusion_score}分")
                        
                        if not (institutional_eval and institutional_eval.get('institutional_scores')):
                            st.info("💡 未进行校方固有评价体系评分，仅显示原始大模型评分结果。")
                    else:
                        st.error(f"❌ 评估失败: {response.json().get('detail', '未知错误')}")
                except Exception as e:
                    st.error(f"❌ 评估失败: {str(e)}")
        elif method_value == "sectioned":
            with st.spinner("正在进行分段评估（这可能需要3-5分钟，请耐心等待）..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/evaluate_sectioned",
                        json={
                            "submission_content": submission_content,
                            "indicators": extracted_guidance,
                            "student_info": student_info,
                            "dimension_weights": current_dimension_weights,
                            "coefficient_config": current_coefficient_config,
                            "use_custom_coefficients": current_use_custom_coefficients
                        },
                        timeout=600
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        st.success("✅ 分段评估完成！")
                        
                        st.markdown("---")
                        st.header("📊 分段评估结果总览")
                        
                        original_score = result.get('original_score', result.get('overall_score', 0))
                        fusion_score = result.get('overall_score', 0)
                        grade_level = result.get('grade_level', '')
                        fusion_coefficient = result.get('fusion_coefficient', 1.0)
                        avg_section_score = result.get('avg_section_score', 0)
                        avg_coherence_score = result.get('avg_coherence_score', 0)
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("原始评分", f"{original_score}分")
                        with col2:
                            st.metric("融合系数", f"{fusion_coefficient:.4f}")
                        with col3:
                            st.metric("最终评分", f"{fusion_score}分")
                        with col4:
                            st.metric("等级", grade_level)
                        
                        st.markdown("---")
                        
                        thesis_structure = result.get('thesis_structure', {})
                        if thesis_structure:
                            with st.expander("📖 论文结构识别结果", expanded=False):
                                st.markdown(f"**论文类型:** {thesis_structure.get('thesis_type', '未知')}")
                                st.markdown(f"**章节总数:** {thesis_structure.get('total_sections', 0)}")
                                
                                main_works = thesis_structure.get('main_works', [])
                                if main_works:
                                    st.markdown("**主要工作:**")
                                    for work in main_works:
                                        st.markdown(f"- {work}")
                                
                                sections = thesis_structure.get('sections', [])
                                if sections:
                                    st.markdown("**章节结构:**")
                                    for sec in sections:
                                        st.markdown(f"- {sec.get('title', '')} ({sec.get('section_type_name', '')})")
                        
                        section_evaluations = result.get('section_evaluations', [])
                        if section_evaluations:
                            with st.expander("📑 各章节评估详情", expanded=True):
                                st.info(f"章节平均分: {avg_section_score}分 | 衔接平均分: {avg_coherence_score}分")
                                
                                for sec_eval in section_evaluations:
                                    section_title = sec_eval.get('section_title', '未知章节')
                                    section_score = sec_eval.get('section_score', 0)
                                    section_grade = sec_eval.get('grade_level', '')
                                    key_points = sec_eval.get('key_points', [])
                                    improvement_suggestions = sec_eval.get('improvement_suggestions', [])
                                    
                                    with st.expander(f"**{section_title}** - {section_score}分 ({section_grade})", expanded=False):
                                        if key_points:
                                            st.markdown("**关键点:**")
                                            for kp in key_points[:5]:
                                                st.markdown(f"- {kp}")
                                        
                                        content_quality = sec_eval.get('content_quality', {})
                                        if content_quality:
                                            st.markdown(f"**内容质量:** {content_quality.get('score', 0)}分 - {content_quality.get('comment', '')}")
                                        
                                        logic_coherence = sec_eval.get('logic_coherence', {})
                                        if logic_coherence:
                                            st.markdown(f"**逻辑连贯性:** {logic_coherence.get('score', 0)}分")
                                            issues = logic_coherence.get('issues', [])
                                            if issues:
                                                st.markdown("**问题:**")
                                                for issue in issues:
                                                    st.markdown(f"⚠️ {issue}")
                                        
                                        if improvement_suggestions:
                                            st.markdown("**改进建议:**")
                                            for s in improvement_suggestions:
                                                st.markdown(f"- {s}")
                        
                        coherence_checks = result.get('coherence_checks', [])
                        if coherence_checks:
                            with st.expander("🔗 章节衔接检测结果（逻辑衔接）", expanded=False):
                                st.info("此检测只关注章节之间的逻辑衔接，不包含承诺-兑现检测。承诺-兑现检测在下方单独展示。")
                                for coherence in coherence_checks:
                                    prev_section = coherence.get('prev_section', '')
                                    next_section = coherence.get('next_section', '')
                                    coherence_score = coherence.get('coherence_score', 0)
                                    
                                    with st.expander(f"**{prev_section}** → **{next_section}** ({coherence_score}分)", expanded=False):
                                        logic_flow = coherence.get('logic_flow', {})
                                        if logic_flow:
                                            st.markdown(f"**逻辑连贯性:** {logic_flow.get('score', 0)}分")
                                            comment = logic_flow.get('comment', '')
                                            if comment:
                                                st.markdown(f"- {comment}")
                                            issues = logic_flow.get('issues', [])
                                            if issues:
                                                st.markdown("**⚠️ 逻辑问题:**")
                                                for issue in issues:
                                                    st.markdown(f"- {issue}")
                                        
                                        content_consistency = coherence.get('content_consistency', {})
                                        if content_consistency:
                                            st.markdown(f"**内容一致性:** {content_consistency.get('score', 0)}分")
                                            comment = content_consistency.get('comment', '')
                                            if comment:
                                                st.markdown(f"- {comment}")
                                            inconsistencies = content_consistency.get('inconsistencies', [])
                                            if inconsistencies:
                                                st.markdown("**不一致之处:**")
                                                for inc in inconsistencies:
                                                    st.markdown(f"- {inc}")
                                        
                                        transition_quality = coherence.get('transition_quality', {})
                                        if transition_quality:
                                            st.markdown(f"**过渡质量:** {transition_quality.get('score', 0)}分")
                                            comment = transition_quality.get('comment', '')
                                            if comment:
                                                st.markdown(f"- {comment}")
                                        
                                        argument_continuity = coherence.get('argument_continuity', {})
                                        if argument_continuity:
                                            st.markdown(f"**论证连续性:** {argument_continuity.get('score', 0)}分")
                                            comment = argument_continuity.get('comment', '')
                                            if comment:
                                                st.markdown(f"- {comment}")
                                            issues = argument_continuity.get('issues', [])
                                            if issues:
                                                st.markdown("**论证不连续之处:**")
                                                for issue in issues:
                                                    st.markdown(f"- {issue}")
                                        
                                        overall_comment = coherence.get('overall_comment', '')
                                        if overall_comment:
                                            st.markdown(f"**整体评价:** {overall_comment}")
                        
                        promise_tracking = result.get('promise_tracking', {})
                        if promise_tracking and promise_tracking.get('fulfillment_status'):
                            with st.expander("📋 承诺-兑现追踪表", expanded=True):
                                fulfillment_rate = promise_tracking.get('overall_fulfillment_rate', 1.0)
                                st.metric("承诺兑现率", f"{fulfillment_rate:.1%}")
                                
                                fulfillment_status = promise_tracking.get('fulfillment_status', [])
                                if fulfillment_status:
                                    st.markdown("---")
                                    st.markdown("**详细追踪表:**")
                                    
                                    for status in fulfillment_status:
                                        promise = status.get('promise', '')
                                        source_section = status.get('source_section', '')
                                        is_fulfilled = status.get('is_fulfilled', False)
                                        fulfillment_degree = status.get('fulfillment_degree', '未兑现')
                                        fulfillment_section = status.get('fulfillment_section', '')
                                        fulfillment_evidence = status.get('fulfillment_evidence', '')
                                        comment = status.get('comment', '')
                                        
                                        if fulfillment_degree == "完全兑现":
                                            status_emoji = "✅"
                                        elif fulfillment_degree == "部分兑现":
                                            status_emoji = "🟡"
                                        else:
                                            status_emoji = "❌"
                                        
                                        with st.expander(f"{status_emoji} **{promise[:50]}{'...' if len(promise) > 50 else ''}** ({fulfillment_degree})", expanded=False):
                                            st.markdown(f"**来源章节:** {source_section}")
                                            st.markdown(f"**兑现程度:** {fulfillment_degree}")
                                            
                                            if fulfillment_section:
                                                st.markdown(f"**兑现章节:** {fulfillment_section}")
                                            
                                            if fulfillment_evidence:
                                                st.markdown(f"**兑现证据:**")
                                                st.markdown(f"> {fulfillment_evidence}")
                                            
                                            if comment:
                                                st.markdown(f"**评价:** {comment}")
                                
                                unfulfilled = promise_tracking.get('unfulfilled_promises', [])
                                partially_fulfilled = promise_tracking.get('partially_fulfilled_promises', [])
                                
                                if unfulfilled or partially_fulfilled:
                                    st.markdown("---")
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if unfulfilled:
                                            st.markdown("**❌ 未兑现的承诺:**")
                                            for uf in unfulfilled:
                                                st.markdown(f"- {uf}")
                                    with col2:
                                        if partially_fulfilled:
                                            st.markdown("**🟡 部分兑现的承诺:**")
                                            for pf in partially_fulfilled:
                                                st.markdown(f"- {pf}")
                                
                                summary = promise_tracking.get('summary', '')
                                if summary:
                                    st.markdown("---")
                                    st.markdown(f"**总结:** {summary}")
                        
                        overall_comment = result.get('overall_comment', '')
                        if overall_comment:
                            with st.expander("📝 总体评价", expanded=True):
                                st.markdown(overall_comment)
                        
                        strengths = result.get('strengths', [])
                        weaknesses = result.get('weaknesses', [])
                        
                        if strengths or weaknesses:
                            col_s, col_w = st.columns(2)
                            with col_s:
                                if strengths:
                                    st.markdown("**💪 优势:**")
                                    for s in strengths:
                                        st.markdown(f"✅ {s}")
                            with col_w:
                                if weaknesses:
                                    st.markdown("**📌 待改进:**")
                                    for w in weaknesses:
                                        st.markdown(f"⚠️ {w}")
                        
                        improvement_suggestions = result.get('improvement_suggestions', [])
                        if improvement_suggestions:
                            with st.expander("💡 改进建议", expanded=False):
                                for suggestion in improvement_suggestions:
                                    aspect = suggestion.get('aspect', '')
                                    current_issue = suggestion.get('current_issue', '')
                                    suggestion_text = suggestion.get('suggestion', '')
                                    priority = suggestion.get('priority', '中')
                                    
                                    priority_emoji = {"高": "🔴", "中": "🟡", "低": "🟢"}.get(priority, "🟡")
                                    
                                    st.markdown(f"**{priority_emoji} {aspect}** (优先级: {priority})")
                                    st.markdown(f"- 当前问题: {current_issue}")
                                    st.markdown(f"- 改进建议: {suggestion_text}")
                                    st.markdown("")
                    else:
                        st.error(f"❌ 评估失败: {response.json().get('detail', '未知错误')}")
                except Exception as e:
                    st.error(f"❌ 分段评估失败: {str(e)}")
        else:
            guidance_content_for_eval = None
            if "extracted_guidance" in st.session_state and st.session_state["extracted_guidance"]:
                guidance_content_for_eval = json.dumps(st.session_state["extracted_guidance"], ensure_ascii=False)
            
            with st.spinner("正在进行大模型评价..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/evaluate_graduation_project",
                        json={
                            "submission_content": submission_content,
                            "project_type": project_type_value,
                            "student_info": student_info,
                            "guidance_content": guidance_content_for_eval
                        },
                        timeout=120
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        st.success("✅ 评估完成！")
                        
                        detected_type = result.get('project_type_name', '未知类型')
                        st.info(f"📊 检测到项目类型: **{detected_type}**")
                        
                        overall_score = result.get('overall_score', 0)
                        grade_level = result.get('grade_level', '')
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("综合评分", f"{overall_score}分")
                        with col2:
                            st.metric("等级", grade_level)
                        with col3:
                            st.metric("项目类型", detected_type)
                        
                        dimension_scores = result.get('dimension_scores', [])
                        if dimension_scores:
                            st.subheader("📈 各指标评分")
                            
                            for ds in dimension_scores:
                                indicator_name = ds.get('indicator_name', ds.get('dimension', '未知指标'))
                                score = ds.get('score', 0)
                                grade = ds.get('grade_level', '')
                                evidence = ds.get('evidence', [])
                                reasoning = ds.get('reasoning', '')
                                
                                with st.expander(f"**{indicator_name}**: {score}分 ({grade})"):
                                    st.markdown(f"**评分理由：** {reasoning}")
                                    if evidence:
                                        st.markdown("**证据：**")
                                        for e in evidence:
                                            st.markdown(f"- {e}")
                        
                        strengths = result.get('strengths', [])
                        if strengths:
                            st.subheader("💪 优势")
                            for s in strengths:
                                st.markdown(f"✅ {s}")
                        
                        weaknesses = result.get('weaknesses', [])
                        if weaknesses:
                            st.subheader("⚠️ 待改进")
                            for w in weaknesses:
                                st.markdown(f"🔸 {w}")
                        
                        overall_eval = result.get('overall_evaluation', '')
                        if overall_eval:
                            st.subheader("📝 总体评价")
                            st.markdown(overall_eval)
                        
                        with st.expander("查看完整JSON结果"):
                            st.json(result)
                    else:
                        try:
                            error_detail = response.json().get('detail', '未知错误')
                        except:
                            error_detail = f"HTTP {response.status_code}"
                        st.error(f"❌ 评估失败: {error_detail}")
                except Exception as e:
                    st.error(f"❌ 评估过程出错: {str(e)}")
