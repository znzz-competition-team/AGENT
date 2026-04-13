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
        ("LLM灵活评分（灵活性高，可能有波动）", "llm")
    ],
    format_func=lambda x: x[0],
    help="确定性评分确保相同输入产生相同输出；灵活评分更灵活但结果可能有差异"
)

method_value = evaluation_method[1]

if method_value == "rule_engine":
    st.info("💡 LLM确定性评分特点：\n- 相同论文多次评分结果完全一致\n- 基于大模型深度理解论文内容\n- 适合标准化、可复现的评价")
else:
    st.warning("⚠️ 大模型灵活评分特点：\n- 评分更灵活，能理解语义\n- 相同论文多次评分可能有差异\n- 适合需要深度理解的评价")

st.markdown("---")

st.subheader("📄 选择毕业设计论文")
st.markdown("从已上传的毕业设计提交中选择论文进行评估")

submission_content = ""
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
                                                        
                                                        st.markdown("##### 3️⃣ 技术术语识别 (权重10%)")
                                                        if tech_terms:
                                                            for type_key, terms in tech_terms.items():
                                                                if terms:
                                                                    st.markdown(f"**{type_labels.get(type_key, type_key)}**:")
                                                                    st.write(", ".join(terms[:5]))
                                                        
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
                                                    - **关键词特征**：分析论文中出现的技术关键词，如"深度学习"、"仿真"、"硬件"等
                                                    - **章节结构**：识别论文章节标题，如"算法设计"、"仿真分析"、"硬件制作"等
                                                    - **技术术语**：识别具体的技术名词，如CNN、ANSYS、STM32等
                                                    - **综合评分**：关键词60% + 章节结构30% + 技术术语10%
                                                    """)
                                                
                                                st.session_state['detected_project_type'] = project_type
                                                st.session_state['detected_project_type_name'] = project_type_name
                                                
                                                with st.expander("📖 查看论文内容片段（确认提取正确）"):
                                                    st.text_area("内容预览", submission_content[:3000] + "..." if len(submission_content) > 3000 else submission_content, height=300, disabled=True)
                                            else:
                                                st.warning("⚠️ 未能从论文中提取到摘要")
                                                with st.expander("📖 查看论文内容片段"):
                                                    st.text_area("内容预览", submission_content[:3000] + "..." if len(submission_content) > 3000 else submission_content, height=300, disabled=True)
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
        
        st.divider()
        st.subheader("📈 自动计算权重")
        
        weight_display_cols = st.columns(len(dimensions))
        for i, dim in enumerate(dimensions):
            dim_id = dim.get('dimension_id', '')
            dim_name = dim.get('name', dim_id)
            weight = dimension_weights.get(dim_id, 25)
            
            with weight_display_cols[i]:
                st.metric(dim_name, f"{weight}%")
        
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
        
        st.subheader("🔢 融合系数说明")
        st.markdown("""
        融合系数根据各维度评分等级自动确定，用于调节最终评分：
        
        | 等级 | 融合系数 | 效果 |
        |------|---------|------|
        | 优秀 (90-100分) | 1.10 - 1.20 | 分数增加10%-20% |
        | 良好 (80-89分) | 1.00 - 1.10 | 分数增加0%-10% |
        | 中等 (70-79分) | 0.95 - 1.00 | 分数减少0%-5% |
        | 及格 (60-69分) | 0.85 - 0.95 | 分数减少5%-15% |
        | 不及格 (<60分) | 0.70 - 0.85 | 分数减少15%-30% |
        
        **计算公式**：最终分数 = 原始指标分数 × 综合调节系数
        """)

st.markdown("---")

if st.button("🚀 开始毕业设计评估", use_container_width=True, type="primary"):
    if not submission_content:
        st.error("❌ 请选择毕业设计论文")
    elif method_value == "rule_engine" and not extracted_guidance:
        st.error("❌ 规则引擎评分需要先选择评价指标")
    else:
        if method_value == "rule_engine":
            with st.spinner("正在进行LLM确定性评分（这可能需要1-2分钟）..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/evaluate_with_rule_engine",
                        json={
                            "submission_content": submission_content,
                            "indicators": extracted_guidance,
                            "student_info": student_info,
                            "use_cache": use_cache
                        },
                        timeout=180
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        st.success("✅ 评估完成！（确定性评分，结果可复现）")
                        
                        overall_score = result.get('overall_score', 0)
                        grade_level = result.get('grade_level', '')
                        evaluation_method = result.get('evaluation_method', 'llm_deterministic')
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("综合评分", f"{overall_score}分")
                        with col2:
                            st.metric("等级", grade_level)
                        with col3:
                            st.metric("评分方式", "LLM确定性评分")
                        
                        overall_comment = result.get('overall_comment', '')
                        if overall_comment:
                            st.subheader("📝 总体评价")
                            st.markdown(overall_comment)
                        
                        dimension_scores = result.get('dimension_scores', [])
                        if dimension_scores:
                            st.subheader("📈 各指标评分")
                            
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
                        
                        if strengths:
                            st.subheader("💪 优势")
                            for s in strengths:
                                st.markdown(f"✅ {s}")
                        
                        if weaknesses:
                            st.subheader("📌 待改进")
                            for w in weaknesses:
                                st.markdown(f"⚠️ {w}")
                        
                        institutional_eval = result.get('institutional_evaluation', {})
                        if institutional_eval and institutional_eval.get('institutional_scores'):
                            st.divider()
                            st.subheader("🏛️ 校方固有评价体系评分")
                            st.info("📋 校方固有评价体系包含四个核心维度：创新度、研究分析深度、文章结构、研究方法与实验")
                            
                            inst_scores = institutional_eval.get('institutional_scores', [])
                            overall_inst_score = institutional_eval.get('overall_institutional_score', 0)
                            overall_inst_grade = institutional_eval.get('overall_institutional_grade', '')
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("固有体系总分", f"{overall_inst_score}分")
                            with col2:
                                st.metric("总体等级", overall_inst_grade)
                            
                            for inst_score in inst_scores:
                                dim_name = inst_score.get('dimension_name', '未知维度')
                                dim_score = inst_score.get('score', 0)
                                dim_grade = inst_score.get('grade_level', '')
                                dim_reason = inst_score.get('score_reason', '')
                                dim_evidence = inst_score.get('evidence', '')
                                
                                with st.expander(f"**{dim_name}** - {dim_score}分 ({dim_grade})"):
                                    if dim_reason:
                                        st.markdown(f"**评分理由:** {dim_reason}")
                                    if dim_evidence:
                                        st.markdown(f"**论文证据:**")
                                        st.markdown(f"> {dim_evidence}")
                            
                            fusion_details = result.get('fusion_details', {})
                            if fusion_details:
                                st.subheader("⚖️ 权重融合详情")
                                original_score = result.get('original_score', overall_score)
                                fusion_coefficient = result.get('fusion_coefficient', 1.0)
                                adjustment = fusion_details.get('adjustment', 0)
                                
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("原始评分", f"{original_score}分")
                                with col2:
                                    st.metric("融合系数", f"{fusion_coefficient:.4f}")
                                with col3:
                                    if adjustment >= 0:
                                        st.metric("分数调整", f"+{adjustment}分")
                                    else:
                                        st.metric("分数调整", f"{adjustment}分")
                                
                                dim_coefs = fusion_details.get('dimension_coefficients', {})
                                if dim_coefs:
                                    st.markdown("**各维度调节系数:**")
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
                                        st.markdown(f"- **{display_name}**: 系数 {coef:.4f} (评分: {score}分, 等级: {grade})")
                    else:
                        st.error(f"❌ 评估失败: {response.json().get('detail', '未知错误')}")
                except Exception as e:
                    st.error(f"❌ 评估失败: {str(e)}")
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
