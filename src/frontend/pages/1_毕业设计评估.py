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

def is_scanned_pdf(file_path):
    """检测是否为扫描版PDF（每页都是图片，没有文本层）"""
    try:
        import fitz
        doc = fitz.open(file_path)
        total_pages = len(doc)
        if total_pages == 0:
            return False
        
        text_pages = 0
        image_pages = 0
        
        for page in doc:
            text = page.get_text().strip()
            images = page.get_images()
            
            if len(text) > 50:
                text_pages += 1
            elif len(images) > 0:
                image_pages += 1
        
        doc.close()
        
        return image_pages > 0 and text_pages == 0
    except:
        return False

def extract_scanned_pdf_with_ocr(file_path):
    """使用OCR提取扫描版PDF内容"""
    try:
        import easyocr
        import fitz
        from PIL import Image
        import io
        
        reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        doc = fitz.open(file_path)
        
        all_text = []
        for page_num, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            result = reader.readtext(img)
            
            page_text = []
            for bbox, text, conf in result:
                if text.strip():
                    page_text.append(text)
            
            if page_text:
                all_text.append(f"--- 第{page_num + 1}页 ---\n" + "\n".join(page_text))
        
        doc.close()
        return "\n\n".join(all_text)
    except ImportError:
        return ""
    except Exception as e:
        return ""

def extract_pdf_content(file_path, enable_ocr=True):
    """
    提取PDF内容（改进版）
    
    使用多库组合策略：
    1. 优先使用PyMuPDF（对中文支持最好）
    2. 备用pdfplumber
    3. 最后使用pypdf/PyPDF2
    4. 如果是扫描版PDF，使用OCR
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
        if text.strip():
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
            if text.strip():
                return text
    except:
        pass
    
    if enable_ocr and is_scanned_pdf(file_path):
        ocr_content = extract_scanned_pdf_with_ocr(file_path)
        if ocr_content.strip():
            return ocr_content
    
    return ""


def _generate_summary_text(result, method, student_info):
    lines = []
    si = student_info or {}
    lines.append(f"毕业设计评估摘要")
    lines.append(f"学生: {si.get('student_name', si.get('name', 'N/A'))} ({si.get('student_id', 'N/A')})")
    if si.get('title'):
        lines.append(f"论文: {si['title']}")
    lines.append(f"评估方式: {method}")
    lines.append("")

    if method == 'enhanced':
        base_eval = result.get('base_evaluation', {})
        overall = result.get('final_enhanced_score', base_eval.get('overall_score', 0))
        grade = result.get('final_enhanced_grade', base_eval.get('grade_level', ''))
        base_score = result.get('base_score', base_eval.get('overall_score', 0))
        lines.append(f"基础评分: {base_score}分")
        lines.append(f"最终评分: {overall}分 ({grade})")

        novelty = result.get('novelty_verification', {})
        if novelty:
            lines.append(f"新颖度评分: {novelty.get('novelty_score', 'N/A')}分")
    else:
        overall = result.get('overall_score', 0)
        grade = result.get('grade_level', '')
        lines.append(f"总分: {overall}分 ({grade})")

    section_evals = result.get('section_evaluations', [])
    if section_evals:
        lines.append("")
        lines.append("各章节评分:")
        for se in section_evals:
            lines.append(f"  {se.get('section_title', '未知')}: {se.get('section_score', 0)}分 ({se.get('grade_level', '')})")

    strengths = result.get('strengths', [])
    if strengths:
        lines.append("")
        lines.append("优势:")
        for s in strengths[:3]:
            lines.append(f"  + {s}")

    weaknesses = result.get('weaknesses', [])
    if weaknesses:
        lines.append("")
        lines.append("不足:")
        for w in weaknesses[:3]:
            lines.append(f"  - {w}")

    return '\n'.join(lines)


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
        ("增强评估（引用验证+多模型+提示词优化）", "enhanced")
    ],
    format_func=lambda x: x[0],
    help="确定性评分确保相同输入产生相同输出；分段评估适合长篇论文；增强评估整合引用网络验证、多模型共识和提示词自动优化"
)

method_value = evaluation_method[1]

if method_value == "rule_engine":
    st.info("💡 LLM确定性评分特点：\n- 相同论文多次评分结果完全一致\n- 基于大模型深度理解论文内容\n- 适合标准化、可复现的评价")
elif method_value == "sectioned":
    st.info("💡 分段评估特点：\n- 智能识别论文结构，按章节分段评估\n- 检测章节之间的逻辑衔接\n- 检测承诺-兑现一致性\n- 适合长篇论文，解决内容丢失问题")
elif method_value == "enhanced":
    st.info("💡 增强评估特点：\n- 📚 引用网络验证：通过Semantic Scholar/CrossRef API验证参考文献真实性和新颖度\n- 🤖 多模型共识：支持多个LLM交叉评审，降低单一模型偏差\n- 🔧 提示词优化：TextGrad自举模式自动优化评估提示词\n- 📊 偏置校正：基于统计学方法校正LLM评审偏差")

if method_value == "enhanced":
    with st.expander("🔬 增强评估配置", expanded=True):
        st.markdown("### 📚 引用网络新颖度验证")
        enable_novelty = st.checkbox(
            "启用引用网络验证",
            value=True,
            help="通过Semantic Scholar和CrossRef API验证论文引用的真实性、时效性和创新性"
        )
        s2_api_key = st.text_input(
            "Semantic Scholar API Key（可选）",
            value="",
            type="password",
            help="不填也可使用，但有速率限制；填写后可提高API调用频率"
        )
        if enable_novelty:
            st.markdown("验证内容：")
            st.markdown("- ✅ 参考文献真实性（是否真实存在）")
            st.markdown("- ✅ 引用时效性（近3年/5年引用比例）")
            st.markdown("- ✅ 自引检测（识别过度自引）")
            st.markdown("- ✅ 创新性交叉验证（创新点 vs 引用网络已有工作）")

        st.markdown("---")
        st.markdown("### 🤖 多模型共识评审")
        enable_multi_judge = st.checkbox(
            "启用多模型评审",
            value=False,
            help="使用多个LLM模型交叉评审，通过加权共识降低单一模型偏差"
        )
        if enable_multi_judge:
            st.markdown("当前使用主模型（DeepSeek）作为默认评审模型。如需添加额外评审模型，请在下方配置：")

            st.markdown("#### 🧭 CompassJudger 专用评审模型")
            enable_compassjudger = st.checkbox(
                "启用CompassJudger本地模型",
                value=False,
                help="CompassJudger是OpenCompass团队开发的专用评审模型，擅长文本质量评估。需要本地GPU和Transformers库。"
            )
            if enable_compassjudger:
                st.info("CompassJudger-2-7B-Instruct 是专门训练用于评审的模型，评审质量优于通用LLM。")
                cj_model_path = st.text_input(
                    "模型路径",
                    value="opencompass/CompassJudger-2-7B-Instruct",
                    help="HuggingFace模型路径，首次使用会自动下载"
                )
                cj_weight = st.slider(
                    "CompassJudger权重",
                    min_value=0.1, max_value=2.0, value=0.8, step=0.1,
                    help="在多模型共识中的权重，建议0.8"
                )
                cj_device = st.selectbox(
                    "运行设备",
                    options=["auto", "cuda", "cpu"],
                    index=0,
                    help="auto自动选择，cuda使用GPU，cpu使用CPU（较慢）"
                )
                st.warning("⚠️ CompassJudger需要: 1) pip install transformers torch  2) 约14GB磁盘空间下载模型  3) 推荐8GB+ GPU显存")
            else:
                cj_model_path = ""
                cj_weight = 0.8
                cj_device = "auto"

            st.markdown("#### 🌐 其他OpenAI兼容模型")
            n_extra_models = st.number_input("额外评审模型数量", min_value=0, max_value=3, value=0, step=1)
            extra_models_config = []
            for i in range(n_extra_models):
                st.markdown(f"**模型 {i+1}**")
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    m_name = st.text_input(f"模型名称", value=f"model_{i+1}", key=f"extra_model_name_{i}")
                    m_api_key = st.text_input(f"API Key", value="", type="password", key=f"extra_model_key_{i}")
                with col_m2:
                    m_base_url = st.text_input(f"Base URL", value="", key=f"extra_model_url_{i}")
                    m_model_name = st.text_input(f"模型ID", value="", key=f"extra_model_id_{i}")
                m_weight = st.slider(f"权重", min_value=0.1, max_value=2.0, value=1.0, step=0.1, key=f"extra_model_weight_{i}")
                if m_api_key and m_base_url and m_model_name:
                    extra_models_config.append({
                        "name": m_name,
                        "api_key": m_api_key,
                        "base_url": m_base_url,
                        "model_name": m_model_name,
                        "weight": m_weight,
                    })
            st.session_state["extra_models_config"] = extra_models_config
            st.session_state["compassjudger_config"] = {
                "enabled": enable_compassjudger,
                "model_path": cj_model_path,
                "weight": cj_weight,
                "device": cj_device,
            }

        st.markdown("---")
        st.markdown("### 🔧 TextGrad提示词优化")
        enable_textgrad = st.checkbox(
            "启用提示词自举优化",
            value=False,
            help="无需人工评分，通过一致性检验和区分度分析自动优化评估提示词"
        )
        if enable_textgrad:
            st.warning("⚠️ 自举优化需要至少2篇论文样本，优化过程会额外消耗API调用。建议在首次评估后开启。")
            st.markdown("优化原理：")
            st.markdown("- 🔄 一致性检验：同一论文评估两次，检测评分波动")
            st.markdown("- 📏 区分度检验：不同质量论文的评分差距是否足够")
            st.markdown("- 🎯 自动改进：根据分析结果自动优化提示词")

        st.session_state["enhanced_config"] = {
            "enable_novelty": enable_novelty,
            "enable_multi_judge": enable_multi_judge,
            "enable_textgrad": enable_textgrad,
            "s2_api_key": s2_api_key,
        }

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
                                                if is_scanned_pdf(file_path):
                                                    st.warning(f"⚠️ 检测到 {file_name} 是扫描版PDF（图片型），正在尝试OCR识别...")
                                                    st.info("💡 提示：扫描版PDF识别较慢，建议上传可编辑的PDF文件以获得更好的效果")
                                                    
                                                    try:
                                                        import easyocr
                                                        with st.spinner("OCR识别中，请耐心等待（首次使用需下载模型）..."):
                                                            content = extract_pdf_content(file_path, enable_ocr=True)
                                                    except ImportError:
                                                        st.error(f"❌ {file_name} 是扫描版PDF，需要安装EasyOCR才能识别")
                                                        st.code("pip install easyocr", language="bash")
                                                        content = ""
                                                    except Exception as ocr_error:
                                                        st.error(f"❌ OCR识别失败: {str(ocr_error)}")
                                                        st.info("💡 建议：请将扫描版PDF转换为可编辑的PDF后重新上传")
                                                        content = ""
                                                else:
                                                    content = extract_pdf_content(file_path, enable_ocr=False)
                                                
                                                if content.strip():
                                                    all_content.append(f"【{file_name}】\n{content}")
                                                else:
                                                    st.warning(f"⚠️ PDF文件 {file_name} 内容为空或无法提取")
                                            elif file_ext in ['.docx', '.doc']:
                                                try:
                                                    from src.utils.word_extractor import extract_word_content
                                                    content = extract_word_content(file_path)
                                                except ImportError:
                                                    from docx import Document
                                                    doc = Document(file_path)
                                                    content = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
                                                
                                                if content.strip():
                                                    all_content.append(f"【{file_name}】\n{content}")
                                                else:
                                                    st.warning(f"⚠️ Word文件 {file_name} 内容为空")
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

col_debug1, col_debug2 = st.columns(2)
with col_debug1:
    if st.button("🔍 调试PDF提取", use_container_width=True):
        if not submission_content:
            st.error("❌ 请选择毕业设计论文")
        else:
            with st.spinner("正在调试PDF提取..."):
                try:
                    debug_response = requests.post(
                        f"{API_BASE_URL}/debug_section_extraction",
                        json={"content": submission_content},
                        timeout=60
                    )
                    
                    if debug_response.status_code == 200:
                        debug_result = debug_response.json()
                        
                        st.success("✅ 调试完成！")
                        
                        with st.expander("📊 提取统计", expanded=True):
                            st.json(debug_result.get("structure", {}))
                            
                            empty_sections = debug_result.get("empty_sections", [])
                            if empty_sections:
                                st.error(f"⚠️ 以下章节内容为空或过短: {', '.join(empty_sections)}")
                            else:
                                st.success("✅ 所有章节内容正常")
                        
                        with st.expander("📑 章节详情", expanded=False):
                            sections_debug = debug_result.get("sections_debug", [])
                            for sec in sections_debug:
                                title = sec.get("title", "未知章节")
                                content_length = sec.get("content_length", 0)
                                content_preview = sec.get("content_preview", "")
                                
                                if content_length < 100:
                                    st.error(f"❌ **{title}** - {content_length}字符（内容过短）")
                                else:
                                    st.success(f"✅ **{title}** - {content_length}字符")
                                
                                if content_preview:
                                    st.text_area(
                                        f"{title} 内容预览",
                                        content_preview,
                                        height=100,
                                        key=f"debug_preview_{title}",
                                        disabled=True
                                    )
                                st.markdown("---")
                    else:
                        st.error(f"❌ 调试失败: {debug_response.json().get('detail', '未知错误')}")
                except Exception as e:
                    st.error(f"❌ 调试失败: {str(e)}")

with col_debug2:
    if st.button("📊 查看原始内容", use_container_width=True):
        if not submission_content:
            st.error("❌ 请选择毕业设计论文")
        else:
            with st.expander("📄 原始提取内容（前5000字符）", expanded=True):
                st.text_area(
                    "内容",
                    submission_content[:5000],
                    height=400,
                    disabled=True
                )
                
                st.info(f"总字符数: {len(submission_content)}")

if st.button("🚀 开始毕业设计评估", use_container_width=True, type="primary"):
    if not submission_content:
        st.error("❌ 请选择毕业设计论文")
    elif method_value == "rule_engine" and not extracted_guidance:
        st.error("❌ 规则引擎评分需要先选择评价指标")
    elif method_value == "sectioned" and not extracted_guidance:
        st.error("❌ 分段评估需要先选择评价指标")
    elif method_value == "enhanced" and not extracted_guidance:
        st.error("❌ 增强评估需要先选择评价指标")
    else:
        current_dimension_weights = st.session_state.get('dimension_weights', {})
        current_coefficient_config = st.session_state.get('coefficient_config', {})
        current_use_custom_coefficients = st.session_state.get('use_custom_coefficients_checkbox', False)
        
        if method_value == "enhanced":
            enhanced_config = st.session_state.get("enhanced_config", {})
            extra_models = st.session_state.get("extra_models_config", [])
            compassjudger_config = st.session_state.get("compassjudger_config", {})
            
            with st.spinner("正在进行增强评估（引用验证+分段评估+多模型评审，可能需要3-8分钟）..."):
                try:
                    request_body = {
                        "submission_content": submission_content,
                        "indicators": extracted_guidance,
                        "student_info": student_info,
                        "dimension_weights": current_dimension_weights,
                        "enable_novelty_verification": enhanced_config.get("enable_novelty", True),
                        "enable_multi_judge": enhanced_config.get("enable_multi_judge", False),
                        "enable_textgrad": enhanced_config.get("enable_textgrad", False),
                        "extra_judge_models": extra_models if enhanced_config.get("enable_multi_judge") else [],
                        "semantic_scholar_api_key": enhanced_config.get("s2_api_key", "") or None,
                        "compassjudger_config": compassjudger_config if enhanced_config.get("enable_multi_judge") else {},
                    }
                    
                    response = requests.post(
                        f"{API_BASE_URL}/evaluate_enhanced",
                        json=request_body,
                        timeout=600,
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        st.success("✅ 增强评估完成！")
                        
                        st.markdown("---")
                        st.header("📊 增强评估结果总览")
                        
                        base_eval = result.get('base_evaluation', {})
                        base_error = base_eval.get('error', '')
                        if base_error:
                            if 'Insufficient Balance' in base_error or '402' in base_error:
                                st.error("💳 **API余额不足！** 请前往 DeepSeek 开放平台充值后再试。")
                                st.markdown("充值地址: [DeepSeek 开放平台](https://platform.deepseek.com/)")
                            elif 'API' in base_error and 'key' in base_error.lower():
                                st.error("🔑 **API密钥无效！** 请检查API Key配置是否正确。")
                            elif 'rate' in base_error.lower() or '429' in base_error:
                                st.error("⏳ **API调用频率超限！** 请稍后再试。")
                            else:
                                st.error(f"⚠️ 基础评估出现问题: {base_error}")
                            with st.expander("查看基础评估原始结果"):
                                st.json(base_eval)
                        
                        final_score = result.get('final_enhanced_score', 0)
                        final_grade = result.get('final_enhanced_grade', '')
                        base_score = result.get('base_score', 0)
                        total_adjustment = result.get('total_adjustment', 0)
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("基础评分", f"{base_score}分")
                        with col2:
                            st.metric("校准调整", f"{'+' if total_adjustment >= 0 else ''}{total_adjustment}分")
                        with col3:
                            st.metric("最终增强评分", f"{final_score}分")
                        with col4:
                            st.metric("等级", final_grade)
                        
                        score_adjustments = result.get('score_adjustments', {})
                        if score_adjustments:
                            with st.expander("📊 评分校准详情", expanded=True):
                                st.markdown("### 校准项明细")
                                for adj_key, adj_info in score_adjustments.items():
                                    adj_value = adj_info.get('value', 0)
                                    adj_reason = adj_info.get('reason', '')
                                    emoji = "🔴" if adj_value < 0 else "🟢" if adj_value > 0 else "⚪"
                                    st.markdown(f"{emoji} **{adj_key}**: {'+' if adj_value >= 0 else ''}{adj_value}分")
                                    st.markdown(f"   _{adj_reason}_")
                                    st.markdown("")
                        
                        enhancement_modules = result.get('enhancement_modules', {})
                        
                        novelty_data = enhancement_modules.get('novelty_verification', {})
                        if novelty_data and novelty_data.get('novelty_score') is not None:
                            with st.expander("📚 引用网络新颖度验证结果", expanded=True):
                                novelty_score = novelty_data.get('novelty_score', 0)
                                novelty_grade = novelty_data.get('novelty_grade', '')
                                
                                col_n1, col_n2 = st.columns(2)
                                with col_n1:
                                    st.metric("新颖度评分", f"{novelty_score}分")
                                with col_n2:
                                    st.metric("新颖度等级", novelty_grade)
                                
                                breakdown = novelty_data.get('novelty_breakdown', {})
                                if breakdown:
                                    st.markdown("#### 评分构成")
                                    bd_items = {
                                        "reference_verifiability": "引用可验证性",
                                        "recency": "引用时效性",
                                        "citation_quality": "引用质量",
                                        "innovation_bonus": "创新加分",
                                        "self_citation_penalty": "自引惩罚",
                                        "fake_reference_penalty": "虚假引用惩罚",
                                        "relevance_bonus": "相关性加分",
                                    }
                                    for k, v in breakdown.items():
                                        label = bd_items.get(k, k)
                                        if v > 0 and 'penalty' not in k:
                                            st.markdown(f"- 🟢 **{label}**: +{v}")
                                        elif v < 0:
                                            st.markdown(f"- 🔴 **{label}**: {v}")
                                        else:
                                            st.markdown(f"- ⚪ **{label}**: {v}")

                                fake_analysis = novelty_data.get('fake_reference_analysis', {})
                                if fake_analysis:
                                    st.markdown("---")
                                    st.markdown("#### 🚨 虚假引用检测")
                                    risk_level = fake_analysis.get('risk_level', 'unknown')
                                    fake_prob = fake_analysis.get('fake_probability', 0)
                                    assessment = fake_analysis.get('assessment', '')
                                    
                                    risk_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢", "minimal": "✅", "unknown": "⚪"}
                                    st.markdown(f"{risk_emoji.get(risk_level, '⚪')} **风险等级**: {risk_level.upper()} | **虚假概率**: {fake_prob}%")
                                    st.markdown(f"_{assessment}_")
                                    
                                    risk_factors = fake_analysis.get('risk_factors', [])
                                    if risk_factors:
                                        st.markdown("**风险因素:**")
                                        for rf in risk_factors:
                                            st.markdown(f"  - ⚠️ {rf}")
                                    
                                    similar_pairs = fake_analysis.get('similar_pairs', [])
                                    if similar_pairs:
                                        st.markdown("**高度相似引用对:**")
                                        for p1, p2, sim in similar_pairs:
                                            st.markdown(f"  - 引用[{p1}] 与 引用[{p2}] 相似度 {sim}")
                                    
                                    recommendations = fake_analysis.get('recommendations', [])
                                    if recommendations:
                                        st.markdown("**建议:**")
                                        for rec in recommendations:
                                            st.markdown(f"  - 💡 {rec}")

                                topic_mismatch_refs = novelty_data.get('topic_mismatch_references', [])
                                if topic_mismatch_refs:
                                    st.markdown("---")
                                    st.markdown("#### 🚨 主题不匹配引用（疑似虚假引用）")
                                    st.error(f"发现 {len(topic_mismatch_refs)} 条引用与论文主题严重不匹配，极可能是虚假引用或AI编造的引用！")
                                    for tmr in topic_mismatch_refs:
                                        idx = tmr.get('index', '?')
                                        raw = tmr.get('raw_text', '')
                                        found_title = tmr.get('found_title', '')
                                        reason = tmr.get('reason', '')
                                        st.markdown(f"**引用[{idx}]**: {raw[:120]}...")
                                        if found_title:
                                            st.markdown(f"  🔍 实际对应的论文: 「{found_title}」")
                                        if reason:
                                            st.markdown(f"  _{reason}_")
                                        st.markdown("---")

                                suspicious_refs = novelty_data.get('suspicious_references', [])
                                if suspicious_refs:
                                    st.markdown("---")
                                    st.markdown("#### ⚠️ 可疑引用详情")
                                    for sr in suspicious_refs:
                                        idx = sr.get('index', '?')
                                        raw = sr.get('raw_text', '')
                                        indicators = sr.get('indicators', [])
                                        detail = sr.get('detail', '')
                                        st.error(f"**引用[{idx}]**: {raw[:100]}...")
                                        for ind in indicators:
                                            st.markdown(f"  - 🔸 {ind}")
                                        if detail:
                                            st.markdown(f"  _{detail}_")

                                unverified_refs = novelty_data.get('unverified_references', [])
                                if unverified_refs:
                                    with st.expander(f"📋 未验证引用列表 ({len(unverified_refs)}条)"):
                                        for ur in unverified_refs:
                                            idx = ur.get('index', '?')
                                            raw = ur.get('raw_text', '')
                                            reason = ur.get('reason', '')
                                            indicators = ur.get('suspicious_indicators', [])
                                            icon = "🔸" if indicators else "🔹"
                                            st.markdown(f"{icon} **[{idx}]** {raw[:120]}...")
                                            if reason:
                                                st.markdown(f"  _原因: {reason}_")

                                verified_details = novelty_data.get('verified_reference_details', [])
                                if verified_details:
                                    with st.expander(f"✅ 已验证引用详情 ({len(verified_details)}条)"):
                                        for vd in verified_details:
                                            idx = vd.get('index', '?')
                                            title = vd.get('title', 'N/A')
                                            year = vd.get('year', 'N/A')
                                            cite_count = vd.get('citation_count', 0)
                                            venue = vd.get('venue', '')
                                            authors = vd.get('authors', [])
                                            source = vd.get('source', '')
                                            st.markdown(f"**[{idx}]** {title}")
                                            st.markdown(f"  年份: {year} | 被引: {cite_count} | 来源: {source}")
                                            if venue:
                                                st.markdown(f"  期刊/会议: {venue}")
                                            if authors:
                                                st.markdown(f"  作者: {', '.join(authors[:3])}")
                                
                                ref_stats = novelty_data.get('reference_statistics', {})
                                if ref_stats:
                                    st.markdown("---")
                                    st.markdown("#### 📊 参考文献统计")
                                    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                                    with col_s1:
                                        st.metric("总引用数", ref_stats.get('total_references', 0))
                                    with col_s2:
                                        st.metric("已验证", ref_stats.get('verified_references', 0))
                                    with col_s3:
                                        st.metric("验证率", f"{ref_stats.get('verification_rate', 0):.1%}")
                                    with col_s4:
                                        suspicious_count = ref_stats.get('suspicious_count', 0)
                                        st.metric("可疑引用", suspicious_count)
                                
                                recency = novelty_data.get('recency_analysis', {})
                                if recency and recency.get('has_year_info'):
                                    st.markdown("#### 📅 引用时效性")
                                    recency_assessment = recency.get('assessment', '')
                                    col_r1, col_r2, col_r3 = st.columns(3)
                                    with col_r1:
                                        st.metric("平均年份", recency.get('avg_year', 'N/A'))
                                    with col_r2:
                                        st.metric("近5年比例", f"{recency.get('recent_5y_ratio', 0):.1%}")
                                    with col_r3:
                                        st.metric("近3年比例", f"{recency.get('recent_3y_ratio', 0):.1%}")
                                    if recency_assessment:
                                        st.info(f"_{recency_assessment}_")
                                
                                citation_quality = novelty_data.get('citation_quality', {})
                                if citation_quality:
                                    st.markdown("#### 📖 引用质量评价")
                                    quality_detail = citation_quality.get('detail', '')
                                    if quality_detail:
                                        st.info(quality_detail)
                                    col_q1, col_q2, col_q3 = st.columns(3)
                                    with col_q1:
                                        st.metric("质量评分", f"{citation_quality.get('quality_score', 0)}分")
                                    with col_q2:
                                        st.metric("平均被引", f"{citation_quality.get('avg_citation_count', 0):.1f}次")
                                    with col_q3:
                                        st.metric("高被引比例", f"{citation_quality.get('high_citation_ratio', 0):.1%}")
                                    lang_balance = citation_quality.get('language_balance', '')
                                    if lang_balance:
                                        st.markdown(f"**语言分布**: {lang_balance}")
                                
                                ref_relevance = novelty_data.get('reference_relevance', {})
                                if ref_relevance:
                                    st.markdown("#### 🎯 引用相关性")
                                    st.metric("相关性评分", f"{ref_relevance.get('relevance_score', 0)}分")
                                    rel_assessment = ref_relevance.get('assessment', '')
                                    if rel_assessment:
                                        st.info(f"_{rel_assessment}_")
                                
                                self_cite = novelty_data.get('self_citation_analysis', {})
                                if self_cite:
                                    st.markdown("#### 🔄 自引检测")
                                    thesis_authors = self_cite.get('thesis_authors', [])
                                    if thesis_authors:
                                        st.markdown(f"**检测到的作者**: {', '.join(thesis_authors)}")
                                    st.markdown(f"- 自引数量: {self_cite.get('self_citation_count', 0)}")
                                    st.markdown(f"- 自引比例: {self_cite.get('self_citation_ratio', 0):.1%}")
                                    assessment = self_cite.get('assessment', '')
                                    if '过高' in assessment:
                                        st.error(f"⚠️ {assessment}")
                                    elif '偏高' in assessment:
                                        st.warning(f"⚡ {assessment}")
                                    else:
                                        st.info(f"✅ {assessment}")
                                    self_cite_details = self_cite.get('self_cite_details', [])
                                    if self_cite_details:
                                        with st.expander("查看自引详情"):
                                            for scd in self_cite_details:
                                                st.markdown(f"- 引用[{scd.get('index', '?')}]: 作者「{scd.get('author', '')}」出现在 {scd.get('raw_text', '')[:80]}...")
                                
                                innovation_verify = novelty_data.get('innovation_verification', [])
                                if innovation_verify:
                                    st.markdown("---")
                                    st.markdown("#### 💡 创新点验证")
                                    for iv in innovation_verify:
                                        status = iv.get('verification_status', '')
                                        innovation_text = iv.get('claimed_innovation', '')[:100]
                                        n_related = iv.get('n_related_works', 0)
                                        
                                        if status == 'likely_novel':
                                            st.success(f"🟢 **可能创新**: {innovation_text}... (找到{n_related}篇相关工作)")
                                        elif status == 'possibly_incremental':
                                            st.warning(f"🟡 **可能增量式改进**: {innovation_text}... (找到{n_related}篇相关工作)")
                                        else:
                                            st.info(f"🔵 **未找到先前工作**: {innovation_text}...")
                                        
                                        related = iv.get('related_prior_works', [])
                                        for rp in related[:2]:
                                            st.markdown(f"  - 相关工作: {rp.get('title', 'N/A')} ({rp.get('year', 'N/A')}, 被引{rp.get('citation_count', 0)}次)")
                        
                        multi_judge_data = enhancement_modules.get('multi_judge', {})
                        if multi_judge_data and multi_judge_data.get('overall_consensus_score') is not None:
                            with st.expander("🤖 多模型共识评审结果", expanded=True):
                                consensus_score = multi_judge_data.get('overall_consensus_score', 0)
                                n_judges = multi_judge_data.get('n_judges', 1)
                                agreement = multi_judge_data.get('agreement_analysis', {})
                                
                                col_j1, col_j2 = st.columns(2)
                                with col_j1:
                                    st.metric("共识评分", f"{consensus_score}分")
                                with col_j2:
                                    st.metric("评审模型数", f"{n_judges}")
                                
                                consensus_scores = multi_judge_data.get('consensus_scores', {})
                                if consensus_scores:
                                    st.markdown("#### 各维度共识评分")
                                    dim_cn = {
                                        "innovation": "创新度",
                                        "research_depth": "研究深度",
                                        "structure": "文章结构",
                                        "method_experiment": "方法与实验",
                                    }
                                    for dim, info in consensus_scores.items():
                                        if isinstance(info, dict) and info.get('score') is not None:
                                            dim_name = dim_cn.get(dim, dim)
                                            score = info['score']
                                            agreement_level = info.get('agreement', 0)
                                            individuals = info.get('individual_scores', [])
                                            
                                            st.markdown(f"**{dim_name}**: {score}分 (一致性: {agreement_level}%)")
                                            if individuals:
                                                for ind in individuals:
                                                    st.markdown(f"  - {ind.get('model', '未知')}: {ind.get('score', 'N/A')}分 (权重{ind.get('weight', 1.0)})")
                                
                                if agreement:
                                    st.markdown("#### 一致性分析")
                                    for dim, info in agreement.items():
                                        dim_name = {"innovation": "创新度", "research_depth": "研究深度", "structure": "文章结构", "method_experiment": "方法与实验"}.get(dim, dim)
                                        level = info.get('agreement_level', 'unknown')
                                        max_dis = info.get('max_disagreement', 0)
                                        level_emoji = {"high": "🟢", "moderate": "🟡", "low": "🔴"}.get(level, "⚪")
                                        st.markdown(f"{level_emoji} **{dim_name}**: 一致性{level}, 最大分歧{max_dis}分")
                        
                        textgrad_data = enhancement_modules.get('textgrad_optimization', {})
                        if textgrad_data and not textgrad_data.get('error'):
                            with st.expander("🔧 TextGrad提示词优化结果", expanded=False):
                                best_consistency = textgrad_data.get('best_consistency', 0)
                                n_iters = textgrad_data.get('n_iterations', 0)
                                st.metric("最佳一致性指标", f"{best_consistency:.4f}")
                                st.metric("优化迭代次数", n_iters)
                                
                                opt_history = textgrad_data.get('optimization_history', [])
                                if opt_history:
                                    st.markdown("#### 优化历史")
                                    for h in opt_history:
                                        st.markdown(f"- 迭代{h.get('iteration', '?')}: 一致性={h.get('consistency', 'N/A')}, 区分度={h.get('discrimination', 'N/A')}")
                        
                        base_eval = result.get('base_evaluation', {})
                        if base_eval:
                            with st.expander("📋 基础分段评估详情", expanded=False):
                                base_overall = base_eval.get('overall_score', 0)
                                base_grade = base_eval.get('grade_level', '')
                                st.metric("基础评分", f"{base_overall}分 ({base_grade})")
                                
                                thesis_structure = base_eval.get('thesis_structure', {})
                                if thesis_structure:
                                    st.markdown(f"**论文类型**: {thesis_structure.get('thesis_type', '未知')}")
                                    st.markdown(f"**章节总数**: {thesis_structure.get('total_sections', 0)}")
                                    main_works = thesis_structure.get('main_works', [])
                                    if main_works:
                                        st.markdown("**主要工作:**")
                                        for w in main_works:
                                            st.markdown(f"- {w}")

                                section_evals = base_eval.get('section_evaluations', [])
                                if section_evals:
                                    st.markdown("---")
                                    st.markdown("### 📖 各章节详细评估")
                                    for se in section_evals:
                                        sec_title = se.get('section_title', '未知章节')
                                        sec_score = se.get('section_score', 0)
                                        sec_grade = se.get('grade_level', '')
                                        sec_type = se.get('section_type', '')
                                        type_name = {"abstract": "摘要", "introduction": "绪论", "literature_review": "文献综述", "methodology": "方法/设计", "implementation": "实现", "experiment": "实验/测试", "results": "结果分析", "conclusion": "结论", "references": "参考文献"}.get(sec_type, sec_type)
                                        
                                        with st.expander(f"{'📌' if sec_score >= 80 else '⚠️' if sec_score < 70 else '📄'} {sec_title} - {sec_score}分 ({sec_grade})", expanded=sec_score < 70):
                                            cq = se.get('content_quality', {})
                                            if cq:
                                                st.markdown(f"**内容质量** ({cq.get('score', 'N/A')}分)")
                                                st.markdown(f"_{cq.get('comment', '')}_")
                                                strengths = cq.get('strengths', [])
                                                if strengths:
                                                    st.markdown("**优点:**")
                                                    for s in strengths:
                                                        st.markdown(f"  - ✅ {s}")
                                                weaknesses = cq.get('weaknesses', [])
                                                if weaknesses:
                                                    st.markdown("**不足:**")
                                                    for w in weaknesses:
                                                        st.markdown(f"  - ❌ {w}")
                                                depth = cq.get('depth_analysis', '')
                                                if depth:
                                                    st.markdown(f"**论述深度**: {depth}")
                                                data_suf = cq.get('data_sufficiency', '')
                                                if data_suf:
                                                    st.markdown(f"**数据充分性**: {data_suf}")
                                            
                                            lc = se.get('logic_coherence', {})
                                            if lc:
                                                st.markdown(f"**逻辑连贯性** ({lc.get('score', 'N/A')}分)")
                                                st.markdown(f"_{lc.get('comment', '')}_")
                                                internal = lc.get('internal_logic', '')
                                                if internal:
                                                    st.markdown(f"**内部逻辑**: {internal}")
                                                cross = lc.get('cross_chapter_logic', '')
                                                if cross:
                                                    st.markdown(f"**跨章节衔接**: {cross}")
                                                issues = lc.get('issues', [])
                                                if issues:
                                                    st.markdown("**逻辑问题:**")
                                                    for iss in issues:
                                                        st.markdown(f"  - ⚠️ {iss}")
                                            
                                            ic = se.get('innovation_contribution', {})
                                            if ic:
                                                st.markdown(f"**创新与贡献** ({ic.get('score', 'N/A')}分)")
                                                st.markdown(f"_{ic.get('comment', '')}_")
                                                st.markdown(f"**创新类型**: {ic.get('novelty_type', 'N/A')}")
                                                contrib = ic.get('concrete_contribution', '')
                                                if contrib:
                                                    st.markdown(f"**具体贡献**: {contrib}")
                                                comp = ic.get('comparison_with_existing', '')
                                                if comp:
                                                    st.markdown(f"**与现有工作对比**: {comp}")
                                            
                                            wq = se.get('writing_quality', {})
                                            if wq:
                                                st.markdown(f"**表达规范性** ({wq.get('score', 'N/A')}分)")
                                                st.markdown(f"_{wq.get('comment', '')}_")
                                                lang_issues = wq.get('language_issues', [])
                                                if lang_issues:
                                                    st.markdown("**语言问题:**")
                                                    for li in lang_issues:
                                                        st.markdown(f"  - 🔸 {li}")
                                                fmt_issues = wq.get('format_issues', [])
                                                if fmt_issues:
                                                    st.markdown("**格式问题:**")
                                                    for fi in fmt_issues:
                                                        st.markdown(f"  - 🔸 {fi}")
                                            
                                            key_points = se.get('key_points', [])
                                            if key_points:
                                                st.markdown("**关键点:**")
                                                for kp in key_points:
                                                    st.markdown(f"  - {kp}")
                                            
                                            suggestions = se.get('improvement_suggestions', [])
                                            if suggestions:
                                                st.markdown("**改进建议:**")
                                                for sug in suggestions:
                                                    if isinstance(sug, dict):
                                                        priority = sug.get('priority', '中')
                                                        icon = "🔴" if priority == "高" else "🟡" if priority == "中" else "🟢"
                                                        st.markdown(f"  {icon} **{sug.get('aspect', '')}**: {sug.get('suggestion', '')}")
                                                        if sug.get('current_issue'):
                                                            st.markdown(f"     _当前问题: {sug['current_issue']}_")
                                                    else:
                                                        st.markdown(f"  - 💡 {sug}")
                                            
                                            evidence = se.get('evidence', '')
                                            if evidence:
                                                st.markdown(f"**评分依据**: {evidence}")
                                            
                                            detailed_reason = se.get('detailed_score_reason', '')
                                            if detailed_reason:
                                                with st.expander("查看详细评分推理"):
                                                    st.markdown(detailed_reason)

                                section_level_details = base_eval.get('section_level_details', [])
                                if section_level_details:
                                    st.markdown("---")
                                    st.markdown("### 📝 章节级深度评价")
                                    for sld in section_level_details:
                                        sld_title = sld.get('section_title', '')
                                        with st.expander(f"🔍 {sld_title}"):
                                            assessment = sld.get('content_assessment', '')
                                            if assessment:
                                                st.markdown(f"**内容评估**: {assessment}")
                                            findings = sld.get('key_findings', [])
                                            if findings:
                                                st.markdown("**主要发现:**")
                                                for f in findings:
                                                    st.markdown(f"  - {f}")
                                            issues = sld.get('specific_issues', [])
                                            if issues:
                                                st.markdown("**具体问题:**")
                                                for iss in issues:
                                                    st.markdown(f"  - ⚠️ {iss}")
                                            advice = sld.get('improvement_advice', '')
                                            if advice:
                                                st.markdown(f"**改进建议**: {advice}")

                                detailed_eval = base_eval.get('detailed_evaluation', {})
                                if detailed_eval:
                                    st.markdown("---")
                                    st.markdown("### 🎯 各部分深度评价")
                                    eval_labels = {
                                        "abstract_evaluation": "📄 摘要",
                                        "introduction_evaluation": "📖 绪论",
                                        "methodology_evaluation": "🔧 方法/设计",
                                        "implementation_evaluation": "⚙️ 实现",
                                        "experiment_evaluation": "🧪 实验",
                                        "conclusion_evaluation": "📝 结论",
                                    }
                                    for key, label in eval_labels.items():
                                        content = detailed_eval.get(key, '')
                                        if content:
                                            st.markdown(f"**{label}**: {content}")

                                quantitative_table = base_eval.get('quantitative_table', {})
                                if quantitative_table:
                                    st.markdown("---")
                                    st.markdown("### 📊 量化评估表")
                                    dims = ['innovation', 'research_depth', 'structure', 'method_experiment']
                                    dim_names = {'innovation': '创新度', 'research_depth': '研究深度', 'structure': '文章结构', 'method_experiment': '方法与实验'}
                                    for dim in dims:
                                        dim_data = quantitative_table.get(dim, {})
                                        if dim_data:
                                            name = dim_names.get(dim, dim)
                                            score = dim_data.get('score', 'N/A')
                                            weight = dim_data.get('weight', 'N/A')
                                            weighted = dim_data.get('weighted_score', 'N/A')
                                            evidence = dim_data.get('core_evidence', '')
                                            st.markdown(f"**{name}** | 权重: {weight} | 得分: {score} | 加权: {weighted}")
                                            if evidence:
                                                st.markdown(f"  _{evidence}_")

                                detailed_analysis = base_eval.get('detailed_analysis', {})
                                if detailed_analysis:
                                    st.markdown("---")
                                    st.markdown("### 🔍 详细评审推导过程")
                                    analysis_labels = {
                                        "innovation_analysis": "💡 创新度评估",
                                        "research_depth_analysis": "📚 研究深度评估",
                                        "structure_analysis": "🏗️ 文章结构评估",
                                        "method_experiment_analysis": "🧪 方法与实验评估",
                                    }
                                    for akey, alabel in analysis_labels.items():
                                        adata = detailed_analysis.get(akey, {})
                                        if adata:
                                            with st.expander(alabel):
                                                for step_key in ['step1', 'step2', 'step3', 'step4']:
                                                    step = adata.get(step_key, {})
                                                    if step:
                                                        q = step.get('question', '')
                                                        a = step.get('answer', '')
                                                        ev = step.get('evidence', '')
                                                        st.markdown(f"**{q}**")
                                                        st.markdown(f"{a}")
                                                        if ev:
                                                            st.markdown(f"  _证据: {ev}_")
                                                        extra_fields = ['innovation_type', 'analysis_type', 'coverage', 'problem_induction', 
                                                                       'literature_quality', 'structure_completeness', 'logic_chain',
                                                                       'argument_coherence', 'expression_quality', 'method_suitability',
                                                                       'reproducibility', 'experiment_design', 'data_analysis',
                                                                       'practical_value', 'academic_value', 'comparison', 'improvement_degree']
                                                        for ef in extra_fields:
                                                            val = step.get(ef)
                                                            if val:
                                                                ef_label = ef.replace('_', ' ').title()
                                                                st.markdown(f"  **{ef_label}**: {val}")
                                                        st.markdown("")
                                                final_score = adata.get('final_score', '')
                                                score_reason = adata.get('score_reason', '')
                                                if final_score:
                                                    st.markdown(f"**综合评分**: {final_score}分")
                                                if score_reason:
                                                    st.markdown(f"**评分理由**: {score_reason}")

                                coherence_analysis = base_eval.get('coherence_analysis', {})
                                if coherence_analysis:
                                    st.markdown("---")
                                    st.markdown("### 🔗 连贯性分析")
                                    coh_score = coherence_analysis.get('overall_coherence_score', 'N/A')
                                    st.metric("整体连贯性", f"{coh_score}分")
                                    major_issues = coherence_analysis.get('major_issues', [])
                                    if major_issues:
                                        st.markdown("**主要问题:**")
                                        for mi in major_issues:
                                            st.markdown(f"  - ⚠️ {mi}")

                                promise_analysis = base_eval.get('promise_fulfillment_analysis', {})
                                if promise_analysis:
                                    st.markdown("---")
                                    st.markdown("### 📋 承诺兑现分析")
                                    fr = promise_analysis.get('fulfillment_rate', 'N/A')
                                    st.metric("兑现率", f"{fr}" if isinstance(fr, str) else f"{fr:.1%}")
                                    unfulfilled = promise_analysis.get('unfulfilled_promises', [])
                                    if unfulfilled:
                                        st.markdown("**未兑现承诺:**")
                                        for uf in unfulfilled:
                                            st.markdown(f"  - ❌ {uf}")
                                    partial = promise_analysis.get('partially_fulfilled', [])
                                    if partial:
                                        st.markdown("**部分兑现:**")
                                        for p in partial:
                                            st.markdown(f"  - ⚡ {p}")
                                    comment = promise_analysis.get('comment', '')
                                    if comment:
                                        st.info(comment)

                        st.markdown("---")
                        st.subheader("💾 保存与导出")
                        save_col1, save_col2, save_col3 = st.columns(3)
                        with save_col1:
                            if st.button("💾 保存评估结果", key="save_enhanced"):
                                try:
                                    save_resp = requests.post(
                                        f"{API_BASE_URL}/save_evaluation_result",
                                        json={
                                            "evaluation_data": result,
                                            "method": "enhanced",
                                            "student_info": student_info,
                                        },
                                        timeout=30,
                                    )
                                    if save_resp.status_code == 200:
                                        save_data = save_resp.json()
                                        st.success(f"✅ 已保存: {save_data.get('filename', '')}")
                                    else:
                                        st.error(f"保存失败: {save_resp.text}")
                                except Exception as e:
                                    st.error(f"保存失败: {str(e)}")
                        with save_col2:
                            export_format = st.selectbox("导出格式", ["markdown", "json", "txt"], key="export_format_enhanced")
                            if st.button("📤 导出报告", key="export_enhanced"):
                                try:
                                    export_resp = requests.post(
                                        f"{API_BASE_URL}/export_evaluation_report",
                                        json={
                                            "evaluation_data": result,
                                            "method": "enhanced",
                                            "student_info": student_info,
                                            "format": export_format,
                                        },
                                        timeout=30,
                                    )
                                    if export_resp.status_code == 200:
                                        export_data = export_resp.json()
                                        st.success(f"✅ 已导出({export_format}): {export_data.get('filename', '')}")
                                        st.info(f"文件路径: {export_data.get('path', '')}")
                                    else:
                                        st.error(f"导出失败: {export_resp.text}")
                                except Exception as e:
                                    st.error(f"导出失败: {str(e)}")
                        with save_col3:
                            if st.button("📋 复制评估摘要", key="copy_enhanced"):
                                summary = _generate_summary_text(result, "enhanced", student_info)
                                st.code(summary, language=None)
                                st.info("请手动复制上方文本")
                    
                    else:
                        try:
                            error_detail = response.json().get('detail', '未知错误')
                        except:
                            error_detail = f"HTTP {response.status_code}"
                        st.error(f"❌ 增强评估失败: {error_detail}")
                except Exception as e:
                    st.error(f"❌ 增强评估失败: {str(e)}")
        elif method_value == "rule_engine":
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
                                                if isinstance(s, dict):
                                                    priority = s.get('priority', '中')
                                                    icon = "🔴" if priority == "高" else "🟡" if priority == "中" else "🟢"
                                                    st.markdown(f"  {icon} **{s.get('aspect', '')}**: {s.get('suggestion', '')}")
                                                    if s.get('current_issue'):
                                                        st.markdown(f"     _当前问题: {s['current_issue']}_")
                                                else:
                                                    st.markdown(f"  - 💡 {s}")
                            
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

                        st.markdown("---")
                        st.subheader("💾 保存与导出")
                        save_col1, save_col2, save_col3 = st.columns(3)
                        with save_col1:
                            if st.button("💾 保存评估结果", key="save_rule"):
                                try:
                                    save_resp = requests.post(
                                        f"{API_BASE_URL}/save_evaluation_result",
                                        json={
                                            "evaluation_data": result,
                                            "method": "rule_engine",
                                            "student_info": student_info,
                                        },
                                        timeout=30,
                                    )
                                    if save_resp.status_code == 200:
                                        save_data = save_resp.json()
                                        st.success(f"✅ 已保存: {save_data.get('filename', '')}")
                                    else:
                                        st.error(f"保存失败: {save_resp.text}")
                                except Exception as e:
                                    st.error(f"保存失败: {str(e)}")
                        with save_col2:
                            export_format = st.selectbox("导出格式", ["markdown", "json", "txt"], key="export_format_rule")
                            if st.button("📤 导出报告", key="export_rule"):
                                try:
                                    export_resp = requests.post(
                                        f"{API_BASE_URL}/export_evaluation_report",
                                        json={
                                            "evaluation_data": result,
                                            "method": "rule_engine",
                                            "student_info": student_info,
                                            "format": export_format,
                                        },
                                        timeout=30,
                                    )
                                    if export_resp.status_code == 200:
                                        export_data = export_resp.json()
                                        st.success(f"✅ 已导出({export_format}): {export_data.get('filename', '')}")
                                        st.info(f"文件路径: {export_data.get('path', '')}")
                                    else:
                                        st.error(f"导出失败: {export_resp.text}")
                                except Exception as e:
                                    st.error(f"导出失败: {str(e)}")
                        with save_col3:
                            if st.button("📋 复制评估摘要", key="copy_rule"):
                                summary = _generate_summary_text(result, "rule_engine", student_info)
                                st.code(summary, language=None)
                                st.info("请手动复制上方文本")

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
                                    
                                    with st.expander(f"{'📌' if section_score >= 80 else '⚠️' if section_score < 70 else '📄'} **{section_title}** - {section_score}分 ({section_grade})", expanded=section_score < 70):
                                        content_quality = sec_eval.get('content_quality', {})
                                        if content_quality:
                                            st.markdown(f"**内容质量:** {content_quality.get('score', 'N/A')}分")
                                            st.markdown(f"_{content_quality.get('comment', '')}_")
                                            strengths = content_quality.get('strengths', [])
                                            if strengths:
                                                st.markdown("**优点:**")
                                                for s in strengths:
                                                    st.markdown(f"  - ✅ {s}")
                                            weaknesses = content_quality.get('weaknesses', [])
                                            if weaknesses:
                                                st.markdown("**不足:**")
                                                for w in weaknesses:
                                                    st.markdown(f"  - ❌ {w}")
                                            depth = content_quality.get('depth_analysis', '')
                                            if depth:
                                                st.markdown(f"**论述深度**: {depth}")
                                            data_suf = content_quality.get('data_sufficiency', '')
                                            if data_suf:
                                                st.markdown(f"**数据充分性**: {data_suf}")
                                        
                                        logic_coherence = sec_eval.get('logic_coherence', {})
                                        if logic_coherence:
                                            st.markdown(f"**逻辑连贯性:** {logic_coherence.get('score', 'N/A')}分")
                                            st.markdown(f"_{logic_coherence.get('comment', '')}_")
                                            internal = logic_coherence.get('internal_logic', '')
                                            if internal:
                                                st.markdown(f"**内部逻辑**: {internal}")
                                            cross = logic_coherence.get('cross_chapter_logic', '')
                                            if cross:
                                                st.markdown(f"**跨章节衔接**: {cross}")
                                            issues = logic_coherence.get('issues', [])
                                            if issues:
                                                st.markdown("**逻辑问题:**")
                                                for issue in issues:
                                                    st.markdown(f"  - ⚠️ {issue}")
                                        
                                        ic = sec_eval.get('innovation_contribution', {})
                                        if ic:
                                            st.markdown(f"**创新与贡献:** {ic.get('score', 'N/A')}分")
                                            st.markdown(f"_{ic.get('comment', '')}_")
                                            st.markdown(f"**创新类型**: {ic.get('novelty_type', 'N/A')}")
                                            contrib = ic.get('concrete_contribution', '')
                                            if contrib:
                                                st.markdown(f"**具体贡献**: {contrib}")
                                            comp = ic.get('comparison_with_existing', '')
                                            if comp:
                                                st.markdown(f"**与现有工作对比**: {comp}")
                                        
                                        wq = sec_eval.get('writing_quality', {})
                                        if wq:
                                            st.markdown(f"**表达规范性:** {wq.get('score', 'N/A')}分")
                                            st.markdown(f"_{wq.get('comment', '')}_")
                                            lang_issues = wq.get('language_issues', [])
                                            if lang_issues:
                                                st.markdown("**语言问题:**")
                                                for li in lang_issues:
                                                    st.markdown(f"  - 🔸 {li}")
                                            fmt_issues = wq.get('format_issues', [])
                                            if fmt_issues:
                                                st.markdown("**格式问题:**")
                                                for fi in fmt_issues:
                                                    st.markdown(f"  - 🔸 {fi}")
                                        
                                        if key_points:
                                            st.markdown("**关键点:**")
                                            for kp in key_points[:5]:
                                                st.markdown(f"- {kp}")
                                        
                                        if improvement_suggestions:
                                            st.markdown("**改进建议:**")
                                            for s in improvement_suggestions:
                                                if isinstance(s, dict):
                                                    priority = s.get('priority', '中')
                                                    icon = "🔴" if priority == "高" else "🟡" if priority == "中" else "🟢"
                                                    st.markdown(f"  {icon} **{s.get('aspect', '')}**: {s.get('suggestion', '')}")
                                                    if s.get('current_issue'):
                                                        st.markdown(f"     _当前问题: {s['current_issue']}_")
                                                else:
                                                    st.markdown(f"  - 💡 {s}")
                                        
                                        evidence = sec_eval.get('evidence', '')
                                        if evidence:
                                            st.markdown(f"**评分依据**: {evidence}")
                                        
                                        detailed_reason = sec_eval.get('detailed_score_reason', '')
                                        if detailed_reason:
                                            with st.expander("查看详细评分推理"):
                                                st.markdown(detailed_reason)
                        
                        coherence_checks = result.get('coherence_checks', [])
                        if coherence_checks:
                            with st.expander("🔗 章节衔接检测结果（逻辑衔接）", expanded=False):
                                st.info("此检测只关注章节之间的逻辑衔接，不包含承诺-兑现检测。承诺-兑现检测在下方单独展示。")
                                for coherence in coherence_checks:
                                    prev_section = coherence.get('prev_section', '')
                                    next_section = coherence.get('next_section', '')
                                    coherence_score = coherence.get('coherence_score', 0)
                                    
                                    with st.expander(f"{'✅' if coherence_score >= 80 else '⚠️' if coherence_score >= 60 else '❌'} **{prev_section}** → **{next_section}** ({coherence_score}分)", expanded=coherence_score < 70):
                                        logic_flow = coherence.get('logic_flow', {})
                                        if logic_flow:
                                            st.markdown(f"**逻辑连贯性:** {logic_flow.get('score', 0)}分")
                                            comment = logic_flow.get('comment', '')
                                            if comment:
                                                st.markdown(f"_{comment}_")
                                            issues = logic_flow.get('issues', [])
                                            if issues:
                                                st.markdown("**⚠️ 逻辑问题:**")
                                                for issue in issues:
                                                    st.markdown(f"- {issue}")
                                            lf_suggestions = logic_flow.get('improvement_suggestions', [])
                                            if lf_suggestions:
                                                st.markdown("**💡 改进建议:**")
                                                for sug in lf_suggestions:
                                                    st.markdown(f"- {sug}")
                                        
                                        content_consistency = coherence.get('content_consistency', {})
                                        if content_consistency:
                                            st.markdown(f"**内容一致性:** {content_consistency.get('score', 0)}分")
                                            comment = content_consistency.get('comment', '')
                                            if comment:
                                                st.markdown(f"_{comment}_")
                                            inconsistencies = content_consistency.get('inconsistencies', [])
                                            if inconsistencies:
                                                st.markdown("**不一致之处:**")
                                                for inc in inconsistencies:
                                                    st.markdown(f"- {inc}")
                                            cc_suggestions = content_consistency.get('improvement_suggestions', [])
                                            if cc_suggestions:
                                                st.markdown("**💡 改进建议:**")
                                                for sug in cc_suggestions:
                                                    st.markdown(f"- {sug}")
                                        
                                        transition_quality = coherence.get('transition_quality', {})
                                        if transition_quality:
                                            st.markdown(f"**过渡质量:** {transition_quality.get('score', 0)}分")
                                            comment = transition_quality.get('comment', '')
                                            if comment:
                                                st.markdown(f"_{comment}_")
                                            missing = transition_quality.get('missing_transition', '')
                                            if missing:
                                                st.markdown(f"**缺失过渡:** {missing}")
                                            tq_suggestions = transition_quality.get('improvement_suggestions', [])
                                            if tq_suggestions:
                                                st.markdown("**💡 改进建议:**")
                                                for sug in tq_suggestions:
                                                    st.markdown(f"- {sug}")
                                        
                                        argument_continuity = coherence.get('argument_continuity', {})
                                        if argument_continuity:
                                            st.markdown(f"**论证连续性:** {argument_continuity.get('score', 0)}分")
                                            comment = argument_continuity.get('comment', '')
                                            if comment:
                                                st.markdown(f"_{comment}_")
                                            issues = argument_continuity.get('issues', [])
                                            if issues:
                                                st.markdown("**论证不连续之处:**")
                                                for issue in issues:
                                                    st.markdown(f"- {issue}")
                                            ac_suggestions = argument_continuity.get('improvement_suggestions', [])
                                            if ac_suggestions:
                                                st.markdown("**💡 改进建议:**")
                                                for sug in ac_suggestions:
                                                    st.markdown(f"- {sug}")
                                        
                                        coherence_suggestions = coherence.get('improvement_suggestions', [])
                                        if coherence_suggestions:
                                            st.markdown("---")
                                            st.markdown("**🎯 衔接改进建议:**")
                                            for sug in coherence_suggestions:
                                                if isinstance(sug, dict):
                                                    priority = sug.get('priority', '中')
                                                    icon = "🔴" if priority == "高" else "🟡" if priority == "中" else "🟢"
                                                    st.markdown(f"  {icon} **{sug.get('aspect', '')}**: {sug.get('suggestion', '')}")
                                                    if sug.get('current_issue'):
                                                        st.markdown(f"     _当前问题: {sug['current_issue']}_")
                                                else:
                                                    st.markdown(f"  - 💡 {sug}")
                                        
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
                                        
                                        with st.expander(f"{status_emoji} **{promise[:50]}{'...' if len(promise) > 50 else ''}** ({fulfillment_degree})", expanded=fulfillment_degree != "完全兑现"):
                                            st.markdown(f"**来源章节:** {source_section}")
                                            st.markdown(f"**兑现程度:** {fulfillment_degree}")
                                            
                                            if fulfillment_section:
                                                st.markdown(f"**兑现章节:** {fulfillment_section}")
                                            
                                            if fulfillment_evidence:
                                                st.markdown(f"**兑现证据:**")
                                                st.markdown(f"> {fulfillment_evidence}")
                                            
                                            if comment:
                                                st.markdown(f"**评价:** {comment}")
                                            
                                            impact = status.get('impact_analysis', '')
                                            if impact:
                                                st.markdown(f"**影响分析:** {impact}")
                                            
                                            imp_sug = status.get('improvement_suggestion', '')
                                            if imp_sug and fulfillment_degree != "完全兑现":
                                                st.markdown(f"**💡 改进建议:** {imp_sug}")
                                
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
                        
                        quantitative_table = result.get('quantitative_table', {})
                        if quantitative_table:
                            with st.expander("📊 量化评估表", expanded=True):
                                st.markdown("| 评审维度 | 权重 | 得分 | 加权得分 | 核心评判依据 |")
                                st.markdown("| :--- | :--- | :--- | :--- | :--- |")
                                
                                for dim_key, dim_data in quantitative_table.items():
                                    if dim_key == 'total_score':
                                        continue
                                    
                                    dim_names = {
                                        'innovation': '创新度评估',
                                        'research_depth': '研究深度评估',
                                        'structure': '文章结构评估',
                                        'method_experiment': '方法与实验评估'
                                    }
                                    
                                    dim_name = dim_names.get(dim_key, dim_key)
                                    weight = dim_data.get('weight', '')
                                    score = dim_data.get('score', 0)
                                    weighted_score = dim_data.get('weighted_score', 0)
                                    core_evidence = dim_data.get('core_evidence', '')
                                    
                                    st.markdown(f"| **{dim_name}** | {weight} | {score}/100 | {weighted_score} | {core_evidence} |")
                                
                                total_score = quantitative_table.get('total_score', 0)
                                st.markdown(f"| **总计得分** | **100%** | | **{total_score}** | **总体评价：{'优秀' if total_score >= 90 else '良好' if total_score >= 80 else '中等' if total_score >= 70 else '及格' if total_score >= 60 else '不及格'}** |")
                        
                        detailed_analysis = result.get('detailed_analysis', {})
                        if detailed_analysis:
                            with st.expander("🔍 详细评审推导过程", expanded=True):
                                dim_titles = {
                                    'innovation_analysis': '创新度评估',
                                    'research_depth_analysis': '研究深度评估',
                                    'structure_analysis': '文章结构评估',
                                    'method_experiment_analysis': '方法与实验评估'
                                }
                                
                                for dim_key, dim_title in dim_titles.items():
                                    dim_data = detailed_analysis.get(dim_key, {})
                                    if not dim_data:
                                        continue
                                    
                                    st.markdown(f"#### {dim_title}")
                                    
                                    for step_num in range(1, 5):
                                        step_key = f'step{step_num}'
                                        step_data = dim_data.get(step_key, {})
                                        if step_data:
                                            question = step_data.get('question', '')
                                            answer = step_data.get('answer', '')
                                            evidence = step_data.get('evidence', '')
                                            
                                            st.markdown(f"**第{step_num}步：{question}**")
                                            st.markdown(f"- 分析：{answer}")
                                            if evidence:
                                                st.markdown(f"- 证据：> {evidence}")
                                            
                                            extra_fields = ['innovation_type', 'practical_value', 'academic_value', 
                                                          'comparison', 'improvement_degree', 'coverage', 
                                                          'analysis_type', 'problem_induction', 'literature_quality',
                                                          'structure_completeness', 'logic_chain', 'argument_coherence',
                                                          'expression_quality', 'method_suitability', 'reproducibility',
                                                          'experiment_design', 'data_analysis']
                                            
                                            for field in extra_fields:
                                                if field in step_data:
                                                    field_names = {
                                                        'innovation_type': '创新类型',
                                                        'practical_value': '实用价值',
                                                        'academic_value': '学术价值',
                                                        'comparison': '对比分析',
                                                        'improvement_degree': '改进程度',
                                                        'coverage': '覆盖范围',
                                                        'analysis_type': '综述方式',
                                                        'problem_induction': '问题归纳',
                                                        'literature_quality': '文献质量',
                                                        'structure_completeness': '结构完整性',
                                                        'logic_chain': '逻辑链条',
                                                        'argument_coherence': '论证连贯性',
                                                        'expression_quality': '表达质量',
                                                        'method_suitability': '方法适用性',
                                                        'reproducibility': '可复现性',
                                                        'experiment_design': '实验设计',
                                                        'data_analysis': '数据分析'
                                                    }
                                                    st.markdown(f"- {field_names.get(field, field)}：{step_data[field]}")
                                            
                                            st.markdown("")
                                    
                                    final_score = dim_data.get('final_score', 0)
                                    score_reason = dim_data.get('score_reason', '')
                                    
                                    st.markdown(f"**综合评分：{final_score}分**")
                                    st.markdown(f"**评分理由：** {score_reason}")
                                    st.markdown("---")
                        
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

                        st.markdown("---")
                        st.subheader("💾 保存与导出")
                        save_col1, save_col2, save_col3 = st.columns(3)
                        with save_col1:
                            if st.button("💾 保存评估结果", key="save_sectioned"):
                                try:
                                    save_resp = requests.post(
                                        f"{API_BASE_URL}/save_evaluation_result",
                                        json={
                                            "evaluation_data": result,
                                            "method": "sectioned",
                                            "student_info": student_info,
                                        },
                                        timeout=30,
                                    )
                                    if save_resp.status_code == 200:
                                        save_data = save_resp.json()
                                        st.success(f"✅ 已保存: {save_data.get('filename', '')}")
                                    else:
                                        st.error(f"保存失败: {save_resp.text}")
                                except Exception as e:
                                    st.error(f"保存失败: {str(e)}")
                        with save_col2:
                            export_format = st.selectbox("导出格式", ["markdown", "json", "txt"], key="export_format_sectioned")
                            if st.button("📤 导出报告", key="export_sectioned"):
                                try:
                                    export_resp = requests.post(
                                        f"{API_BASE_URL}/export_evaluation_report",
                                        json={
                                            "evaluation_data": result,
                                            "method": "sectioned",
                                            "student_info": student_info,
                                            "format": export_format,
                                        },
                                        timeout=30,
                                    )
                                    if export_resp.status_code == 200:
                                        export_data = export_resp.json()
                                        st.success(f"✅ 已导出({export_format}): {export_data.get('filename', '')}")
                                        st.info(f"文件路径: {export_data.get('path', '')}")
                                    else:
                                        st.error(f"导出失败: {export_resp.text}")
                                except Exception as e:
                                    st.error(f"导出失败: {str(e)}")
                        with save_col3:
                            if st.button("📋 复制评估摘要", key="copy_sectioned"):
                                summary = _generate_summary_text(result, "sectioned", student_info)
                                st.code(summary, language=None)
                                st.info("请手动复制上方文本")

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
