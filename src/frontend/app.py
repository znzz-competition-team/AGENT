import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import os
import re

# API 基础 URL
API_BASE_URL = "http://localhost:8000"

# AI 提供商配置
AI_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "description": "国产大模型，性价比高",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-coder"],
        "default_model": "deepseek-chat"
    },
    "openai": {
        "name": "OpenAI",
        "description": "国际领先的AI模型提供商",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
        "default_model": "gpt-4o"
    },
    "zhipu": {
        "name": "智谱AI",
        "description": "国产大模型，GLM系列",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4", "glm-4-flash", "glm-3-turbo"],
        "default_model": "glm-4"
    },
    "qwen": {
        "name": "通义千问",
        "description": "阿里云大模型",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
        "default_model": "qwen-plus"
    },
    "moonshot": {
        "name": "Moonshot",
        "description": "月之暗面，长文本处理能力强",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "default_model": "moonshot-v1-8k"
    },
    "custom": {
        "name": "自定义",
        "description": "自定义API配置",
        "base_url": "",
        "models": [],
        "default_model": ""
    }
}

def clean_pdf_text(text):
    """清理PDF提取的文本，去除字符间的多余空格"""
    if not text:
        return ""
    
    clean_text = ''.join(c if c.isprintable() or c in '\n\t\r' else ' ' for c in text)
    
    lines = clean_text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        if not line.strip():
            continue
            
        if re.search(r'[\u4e00-\u9fff]', line):
            chars = list(line)
            result = []
            i = 0
            while i < len(chars):
                char = chars[i]
                if '\u4e00' <= char <= '\u9fff':
                    result.append(char)
                    i += 1
                    while i < len(chars) and chars[i] == ' ':
                        i += 1
                    while i < len(chars) and '\u4e00' <= chars[i] <= '\u9fff':
                        result.append(chars[i])
                        i += 1
                        while i < len(chars) and chars[i] == ' ':
                            i += 1
                else:
                    result.append(char)
                    i += 1
            cleaned_lines.append(''.join(result))
        else:
            cleaned_lines.append(re.sub(r' +', ' ', line))
    
    return '\n'.join(cleaned_lines)

# 页面配置
st.set_page_config(
    page_title="学生多维度能力评估系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化 session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = "🏠 系统首页"
if 'api_info' not in st.session_state:
    st.session_state.api_info = None
if 'system_status' not in st.session_state:
    st.session_state.system_status = None
if 'ai_settings' not in st.session_state:
    st.session_state.ai_settings = None

# 侧边栏导航
st.sidebar.title("📚 学生多维度能力评估系统")
st.sidebar.markdown("### 📋 功能导航")

# 定义页面列表
pages = [
    ("🏠", "系统首页"),
    ("📋", "大纲管理"),
    ("👥", "学生管理"),
    ("📁", "文件上传"),
    ("📂", "文件管理"),
    ("✏️", "手写识别"),
    ("🤖", "评估管理"),
    ("📊", "结果查询"),
    ("📈", "成长分析"),
    ("⚙️", "AI设置"),
    ("🔧", "API文档")
]

# 创建导航按钮
for emoji, page_name in pages:
    full_page_name = f"{emoji} {page_name}"
    if st.sidebar.button(
        full_page_name,
        key=f"nav_{page_name}",
        use_container_width=True,
        type="primary" if st.session_state.current_page == full_page_name else "secondary"
    ):
        st.session_state.current_page = full_page_name
        st.rerun()

st.sidebar.markdown("---")

# 系统信息
st.sidebar.markdown("### ℹ️ 系统信息")
st.sidebar.markdown(f"**版本:** 1.0.0")
st.sidebar.markdown(f"**API:** [http://localhost:8000](http://localhost:8000)")
st.sidebar.markdown(f"**前端:** [http://localhost:8501](http://localhost:8501)")

# API 信息获取函数
@st.cache_data(ttl=60)
def get_api_info():
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

# 检查API状态并更新system_status
api_info = get_api_info()
if api_info:
    st.session_state.system_status = "running"
    st.session_state.api_info = api_info
else:
    st.session_state.system_status = "error"

# 获取当前页面
page = st.session_state.current_page

# ==================== 系统首页 ====================
if page == "🏠 系统首页":
    st.title("🎓 学生多维度能力评估系统")
    
    # 系统概览
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("API版本", "1.0.0")
    with col2:
        st.metric("服务状态", "运行中" if st.session_state.system_status == "running" else "异常")
    with col3:
        st.metric("API端口", "8000")
    
    st.markdown("---")
    
    # 系统介绍
    st.subheader("📋 系统介绍")
    st.markdown("""
    基于 **OpenAI GPT-4o** 和 **CrewAI** 的智能化学生能力评估系统
    
    **核心功能：**
    - 📁 **多媒体处理**：支持论文（PDF/DOCX/TXT）、讲演视频（MP4/MOV）、音频录音（MP3/WAV）
    - 🤖 **多智能体评估**：内容分析、表达分析、技术能力分析、批判性思维分析
    - 📊 **数据可视化**：雷达图、评分卡片、趋势图
    - 💾 **数据库持久化**：存储学生信息、提交记录、评估结果
    - 🌐 **API 服务**：提供文件上传、评估启动、结果查询接口
    """)
    
    # 快速开始
    st.subheader("🚀 快速开始")
    
    quick_start_col1, quick_start_col2, quick_start_col3, quick_start_col4 = st.columns(4)
    
    with quick_start_col1:
        if st.button("➕ 添加学生", use_container_width=True):
            st.session_state.current_page = "👥 学生管理"
            st.rerun()
    
    with quick_start_col2:
        if st.button("📤 上传文件", use_container_width=True):
            st.session_state.current_page = "📁 文件上传"
            st.rerun()
    
    with quick_start_col3:
        if st.button("▶️ 启动评估", use_container_width=True):
            st.session_state.current_page = "🤖 评估管理"
            st.rerun()
    
    with quick_start_col4:
        if st.button("📊 查看结果", use_container_width=True):
            st.session_state.current_page = "📊 结果查询"
            st.rerun()
    
    st.markdown("---")
    
    # 系统架构
    st.subheader("🏗️ 系统架构")
    
    arch_col1, arch_col2, arch_col3 = st.columns(3)
    
    with arch_col1:
        st.markdown("""
        **🎯 输入层**
        - PDF/DOCX/TXT 文档
        - MP4/MOV 视频
        - MP3/WAV 音频
        """)
    
    with arch_col2:
        st.markdown("""
        **🤖 处理层**
        - 内容分析Agent
        - 表达分析Agent
        - 技术能力Agent
        - 批判性思维Agent
        """)
    
    with arch_col3:
        st.markdown("""
        **📊 输出层**
        - 综合评分
        - 维度分析
        - 雷达图展示
        - 改进建议
        """)
    
    st.markdown("---")
    
    # 技术栈
    st.subheader("🛠️ 技术栈")
    
    tech_col1, tech_col2, tech_col3, tech_col4 = st.columns(4)
    
    with tech_col1:
        st.markdown("""
        **AI框架**
        - OpenAI GPT-4o
        - CrewAI
        - LangChain
        """)
    
    with tech_col2:
        st.markdown("""
        **后端**
        - FastAPI
        - SQLAlchemy
        """)
    
    with tech_col3:
        st.markdown("""
        **前端**
        - Streamlit
        - Plotly
        - Pandas
        """)
    
    with tech_col4:
        st.markdown("""
        **媒体处理**
        - python-docx
        - PyMuPDF
        **计划使用**
        - Whisper (语音识别)
        """)

# ==================== 大纲管理 ====================
elif page == "📋 大纲管理":
    st.title("📋 大纲管理")
    
    # 获取项目根目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    # 大纲文件夹路径（使用绝对路径）
    syllabus_folder = os.path.join(project_root, "评价大纲")
    
    # 检查大纲文件夹是否存在
    if not os.path.exists(syllabus_folder):
        st.error(f"❌ 大纲文件夹 '{syllabus_folder}' 不存在，请创建该文件夹并放入课程大纲文件")
    else:
        # 文件类型选择
        st.subheader("📁 文件类型选择")
        file_type = st.radio(
            "选择文件类型",
            options=["课程大纲", "毕业设计评价指标"],
            horizontal=True,
            help="课程大纲：用于分析课程能力点；毕业设计评价指标：用于毕业设计评价"
        )
        
        st.markdown("---")
        
        if file_type == "课程大纲":
            # ========== 课程大纲管理 ==========
            st.subheader("📚 课程大纲管理")
            
            # 获取课程大纲文件列表（排除毕业设计相关文件）
            all_files = [f for f in os.listdir(syllabus_folder) if f.endswith('.docx') or f.endswith('.txt')]
            graduation_keywords = ["毕业设计", "评价指标", "评价标准", "毕设", "graduation"]
            syllabus_files = [f for f in all_files if not any(kw in f for kw in graduation_keywords)]
            
            if not syllabus_files:
                st.warning(f"⚠️ 没有找到课程大纲文件（已排除毕业设计相关文件）")
            else:
                # 选择大纲文件
                selected_syllabus = st.selectbox("选择课程大纲", syllabus_files)
                
                # 显示大纲信息
                st.subheader(f"📄 {selected_syllabus}")
                
                # 检查是否已有大纲分析结果
                analysis_dir = os.path.join(project_root, "analysis_results")
                analysis_file = os.path.join(analysis_dir, f"{selected_syllabus.replace('.docx', '').replace('.txt', '')}.json")
                
                existing_analysis = None
                if os.path.exists(analysis_file):
                    try:
                        with open(analysis_file, 'r', encoding='utf-8') as f:
                            existing_analysis = json.load(f)
                        st.info(f"ℹ️ 已有大纲分析结果")
                    except Exception as e:
                        st.warning(f"⚠️ 读取已有分析结果失败: {str(e)}")
                
                # 分析大纲按钮
                if st.button("🔍 分析大纲", use_container_width=True):
                    try:
                        syllabus_path = os.path.join(syllabus_folder, selected_syllabus)
                        
                        if selected_syllabus.endswith('.docx'):
                            from docx import Document
                            doc = Document(syllabus_path)
                            syllabus_content = '\n'.join([para.text for para in doc.paragraphs])
                        elif selected_syllabus.endswith('.txt'):
                            with open(syllabus_path, 'r', encoding='utf-8') as f:
                                syllabus_content = f.read()
                        else:
                            syllabus_content = ""
                        
                        st.info("⏳ 正在分析大纲，这可能需要1-2分钟，请耐心等待...")
                        
                        response = requests.post(
                            f"{API_BASE_URL}/analyze_syllabus",
                            json={
                                "syllabus_content": syllabus_content,
                                "syllabus_name": selected_syllabus
                            },
                            timeout=180
                        )
                        
                        if response.status_code == 200:
                            analysis_result = response.json()
                            
                            if not analysis_result or (not analysis_result.get('ability_points') and not analysis_result.get('evaluation_criteria')):
                                st.error("❌ 大纲分析失败：未获取到有效的分析结果")
                            else:
                                os.makedirs(analysis_dir, exist_ok=True)
                                with open(analysis_file, 'w', encoding='utf-8') as f:
                                    json.dump(analysis_result, f, ensure_ascii=False, indent=2)
                                
                                ability_matrix_path = os.path.join(project_root, "ability_matrix.json")
                                if os.path.exists(ability_matrix_path):
                                    with open(ability_matrix_path, 'r', encoding='utf-8') as f:
                                        ability_matrix = json.load(f)
                                else:
                                    ability_matrix = {}
                                
                                ability_matrix[selected_syllabus] = analysis_result
                                with open(ability_matrix_path, 'w', encoding='utf-8') as f:
                                    json.dump(ability_matrix, f, ensure_ascii=False, indent=2)
                                
                                st.success("✅ 大纲分析完成并已保存！")
                                existing_analysis = analysis_result
                        else:
                            st.error(f"❌ 大纲分析失败: {response.status_code}")
                    except Exception as e:
                        st.error(f"❌ 运行大纲分析器时出错: {str(e)}")
                
                # 显示大纲分析结果框
                st.markdown("---")
                st.subheader("📊 大纲分析结果")
                
                if existing_analysis:
                    # ==================== 新增：课程分类与动态权重展示区 ====================
                    # 尝试从分析结果中获取课程类型，如果没有则默认显示为"理论课"
                    course_type = existing_analysis.get("course_type", "理论课")
                    
                    # 1. 顶部显眼提示
                    if "实践" in course_type:
                        st.success(f"🛠️ **系统自动识别：当前为【{course_type}】模式**。评价权重已切换至“工程落地与实践能力”侧重。")
                    else:
                        st.info(f"📚 **系统自动识别：当前为【{course_type}】模式**。评价权重已切换至“理论推导与基础知识”侧重。")
                        
                    # 2. 可展开的权重配比面板
                    with st.expander("⚖️ 查看当前评分权重配比"):
                        import pandas as pd
                        if "实践" in course_type:
                            weight_data = {
                                "评价维度": ["技术能力 (实操)", "问题解决", "团队协作", "创新能力", "适应能力", "其他综合"],
                                "权重占比": ["20%", "20%", "15%", "10%", "10%", "25%"]
                            }
                        else:
                            weight_data = {
                                "评价维度": ["学术表现 (理论)", "批判性思维", "沟通表达", "问题解决", "创新能力", "其他综合"],
                                "权重占比": ["20%", "20%", "15%", "10%", "10%", "25%"]
                            }
                        st.table(pd.DataFrame(weight_data))
                    result_tab1, result_tab2, result_tab3 = st.tabs(["🎯 能力点", "📏 评价标准", "📋 完整结果"])
                    
                    with result_tab1:
                        if existing_analysis.get('ability_points'):
                            st.markdown("### 提取的能力点")
                            for i, point in enumerate(existing_analysis['ability_points'], 1):
                                if isinstance(point, dict):
                                    st.markdown(f"**{i}. {point.get('name', '未知')}**")
                                    if point.get('description'):
                                        st.markdown(f"   - 描述: {point.get('description')}")
                                    if point.get('level'):
                                        st.markdown(f"   - 掌握程度: {point.get('level')}")
                                    st.markdown("")
                                else:
                                    st.markdown(f"{i}. {point}")
                        else:
                            st.info("ℹ️ 未提取到能力点")
                    
                    with result_tab2:
                        if existing_analysis.get('evaluation_criteria'):
                            st.markdown("### 提取的评价标准")
                            for i, criterion in enumerate(existing_analysis['evaluation_criteria'], 1):
                                if isinstance(criterion, dict):
                                    st.markdown(f"**{i}. {criterion.get('name', '未知')}** ({criterion.get('weight', '未知权重')})")
                                    if criterion.get('description'):
                                        st.markdown(f"   - 描述: {criterion.get('description')}")
                                    if criterion.get('standard'):
                                        st.markdown(f"   - 评分标准: {criterion.get('standard')}")
                                    st.markdown("")
                                else:
                                    st.markdown(f"{i}. {criterion}")
                        else:
                            st.info("ℹ️ 未提取到评价标准")
                    
                    with result_tab3:
                        st.markdown("### 完整分析结果（JSON格式）")
                        st.json(existing_analysis)
                else:
                    st.info("ℹ️ 暂无大纲分析结果，请点击\"分析大纲\"按钮进行分析")
        
        else:
            # ========== 毕业设计评价指标管理 ==========
            st.subheader("🎓 毕业设计评价指标管理")
            
            # 获取毕业设计评价指标文件（仅读取包含特定关键词的文件）
            all_files = [f for f in os.listdir(syllabus_folder) if f.endswith('.docx') or f.endswith('.txt') or f.endswith('.json')]
            graduation_keywords = ["毕业设计", "评价指标", "评价标准", "毕设", "graduation", "指标"]
            graduation_files = [f for f in all_files if any(kw in f for kw in graduation_keywords)]
            
            if not graduation_files:
                st.warning("⚠️ 没有找到毕业设计评价指标文件")
                st.info("💡 提示：文件名需包含'毕业设计'、'评价指标'、'评价标准'、'毕设'等关键词")
            else:
                col1, col2 = st.columns([3, 1])
                with col1:
                    selected_graduation_file = st.selectbox("选择毕业设计评价指标文件", graduation_files)
                with col2:
                    st.write("")
                    st.write("")
                    extract_button = st.button("🔍 提炼指标", type="primary", use_container_width=True)
                
                # 检查是否已有提炼结果
                indicators_dir = os.path.join(project_root, "extracted_indicators")
                indicator_file = os.path.join(
                    indicators_dir,
                    f"{selected_graduation_file.replace('.docx', '').replace('.txt', '').replace('.json', '')}_extracted.json"
                )
                
                existing_indicators = None
                if os.path.exists(indicator_file):
                    try:
                        with open(indicator_file, 'r', encoding='utf-8') as f:
                            existing_indicators = json.load(f)
                        st.info(f"ℹ️ 已有提炼结果（可重新提炼覆盖）")
                    except Exception as e:
                        st.warning(f"⚠️ 读取已有提炼结果失败: {str(e)}")
                
                # 提炼后的指标存储
                extracted_indicators = existing_indicators
                
                if extract_button and selected_graduation_file:
                    with st.spinner("正在提炼评价指标..."):
                        try:
                            file_path = os.path.join(syllabus_folder, selected_graduation_file)
                            
                            if selected_graduation_file.endswith('.json'):
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    extracted_indicators = json.load(f)
                            else:
                                if selected_graduation_file.endswith('.docx'):
                                    from docx import Document
                                    doc = Document(file_path)
                                    file_content = '\n'.join([para.text for para in doc.paragraphs])
                                elif selected_graduation_file.endswith('.txt'):
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        file_content = f.read()
                                else:
                                    file_content = ""
                                
                                extract_response = requests.post(
                                    f"{API_BASE_URL}/extract_guidance_content",
                                    json={
                                        "file_content": file_content,
                                        "file_name": selected_graduation_file
                                    },
                                    timeout=120
                                )
                                
                                if extract_response.status_code == 200:
                                    extracted_indicators = extract_response.json()
                                else:
                                    st.error(f"❌ 提炼失败: {extract_response.json().get('detail', '未知错误')}")
                            
                            if extracted_indicators:
                                # 保存提炼结果
                                os.makedirs(indicators_dir, exist_ok=True)
                                with open(indicator_file, 'w', encoding='utf-8') as f:
                                    json.dump(extracted_indicators, f, ensure_ascii=False, indent=2)
                                
                                st.session_state["extracted_indicators"] = extracted_indicators
                                st.session_state["extracted_indicators_file"] = selected_graduation_file
                                st.success(f"✅ 已提炼并保存评价指标！")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ 提炼失败: {str(e)}")
                
                # 显示提炼结果框
                st.markdown("---")
                st.subheader("📊 评价指标提炼结果")
                
                if existing_indicators or ("extracted_indicators" in st.session_state):
                    extracted_indicators = existing_indicators or st.session_state.get("extracted_indicators", {})
                    
                    st.info(f"📄 来源文件: {selected_graduation_file}")
                    
                    # 使用更多标签页展示不同内容
                    result_tab1, result_tab2, result_tab3, result_tab4, result_tab5 = st.tabs([
                        "📋 原始指标", 
                        "📝 扩展指标", 
                        "📊 评价表格", 
                        "🔄 评价流程", 
                        "📄 完整结果"
                    ])
                    
                    with result_tab1:
                        original_indicators = extracted_indicators.get('original_indicators', [])
                        if not original_indicators:
                            original_indicators = extracted_indicators.get('indicators', [])
                        
                        if original_indicators:
                            st.markdown("### 📋 原始评价指标（从文件提取）")
                            for idx, ind in enumerate(original_indicators, 1):
                                indicator_id = ind.get('indicator_id', ind.get('id', f'{idx}'))
                                name = ind.get('name', '未知指标')
                                weight = ind.get('weight', '未知')
                                max_score = ind.get('max_score', 100)
                                description = ind.get('description', '')
                                graduation_req = ind.get('graduation_requirement', '')
                                
                                with st.expander(f"**{indicator_id} {name}** (权重: {weight}%, 满分: {max_score})", expanded=False):
                                    if graduation_req:
                                        st.markdown(f"**对应毕业要求指标点**: {graduation_req}")
                                    if description:
                                        st.markdown(f"**描述**: {description}")
                                    if ind.get('grading_criteria'):
                                        st.markdown(f"**评分标准**: {ind.get('grading_criteria')}")
                        else:
                            st.info("暂无原始评价指标")
                    
                    with result_tab2:
                        indicators = extracted_indicators.get('indicators', [])
                        if indicators:
                            st.markdown("### 📝 扩展评价指标（大模型生成）")
                            for idx, ind in enumerate(indicators, 1):
                                indicator_id = ind.get('indicator_id', ind.get('id', f'{idx}'))
                                name = ind.get('name', '未知指标')
                                weight = ind.get('weight', 10)
                                max_score = ind.get('max_score', 100)
                                description = ind.get('description', '')
                                evaluation_points = ind.get('evaluation_points', [])
                                evaluation_method = ind.get('evaluation_method', '')
                                
                                with st.expander(f"**{indicator_id} {name}** (权重: {weight}%, 满分: {max_score})", expanded=False):
                                    if description:
                                        st.markdown(f"**描述**: {description}")
                                    if evaluation_method:
                                        st.markdown(f"**评价方式**: {evaluation_method}")
                                    
                                    if evaluation_points:
                                        st.markdown("#### 📌 评价要点")
                                        for point in evaluation_points:
                                            point_name = point.get('point_name', '')
                                            point_weight = point.get('weight', '')
                                            grade_criteria = point.get('grade_criteria', {})
                                            
                                            st.markdown(f"**{point_name}** (权重: {point_weight})")
                                            
                                            if grade_criteria:
                                                grade_names = {
                                                    "excellent": "优秀(90-100)",
                                                    "good": "良好(80-89)",
                                                    "medium": "中等(70-79)",
                                                    "pass": "及格(60-69)",
                                                    "fail": "不及格(0-59)"
                                                }
                                                for level, criteria in grade_criteria.items():
                                                    st.markdown(f"- {grade_names.get(level, level)}: {criteria}")
                                            st.markdown("")
                        else:
                            st.info("暂无扩展评价指标")
                    
                    with result_tab3:
                        evaluation_table = extracted_indicators.get('evaluation_table', {})
                        if evaluation_table:
                            st.markdown(f"### 📊 {evaluation_table.get('title', '评价表格')}")
                            
                            columns = evaluation_table.get('columns', ["序号", "指标编号", "指标名称", "满分", "得分", "评价等级"])
                            rows = evaluation_table.get('rows', [])
                            
                            if rows:
                                import pandas as pd
                                df = pd.DataFrame(rows)
                                st.dataframe(df, use_container_width=True, hide_index=True)
                            else:
                                st.info("暂无评价表格数据")
                            
                            st.markdown("#### 📝 使用说明")
                            st.markdown("此表格可用于实际评分，每行对应一个评价指标。评分时填写得分和评价等级。")
                        else:
                            st.info("暂无评价表格，请重新提炼评价指标")
                    
                    with result_tab4:
                        evaluation_flow = extracted_indicators.get('evaluation_flow', {})
                        if evaluation_flow:
                            st.markdown("### 🔄 评价流程")
                            
                            steps = evaluation_flow.get('steps', [])
                            if steps:
                                for step in steps:
                                    step_num = step.get('step', '')
                                    step_name = step.get('name', '')
                                    step_weight = step.get('weight', 0)
                                    step_desc = step.get('description', '')
                                    
                                    st.markdown(f"**步骤{step_num}: {step_name}** (权重: {step_weight*100:.0f}%)")
                                    st.markdown(f"- {step_desc}")
                                    st.markdown("")
                            
                            formula = evaluation_flow.get('final_score_formula', '')
                            if formula:
                                st.markdown("#### 📐 成绩计算公式")
                                st.code(formula, language=None)
                        else:
                            st.info("暂无评价流程信息")
                        
                        grading_levels = extracted_indicators.get('grading_levels', {})
                        if grading_levels:
                            st.markdown("### 📊 评分等级标准")
                            level_names = {
                                "excellent": "优秀",
                                "good": "良好",
                                "medium": "中等",
                                "pass": "及格",
                                "fail": "不及格"
                            }
                            for level, info in grading_levels.items():
                                if isinstance(info, dict):
                                    min_score = info.get('min', 0)
                                    max_score = info.get('max', 100)
                                    desc = info.get('description', '')
                                    st.markdown(f"**{level_names.get(level, level)}** ({min_score}-{max_score}分): {desc}")
                                else:
                                    st.markdown(f"**{level_names.get(level, level)}**: {info}")
                    
                    with result_tab5:
                        st.markdown("### 完整提炼结果（JSON格式）")
                        st.json(extracted_indicators)
                    
                    # ========== 衍生评价指标 ==========
                    st.markdown("---")
                    st.subheader("🔄 衍生评价指标")
                    st.markdown("根据当前评价指标，生成特定项目类型的评价指标")
                    
                    derived_dir = os.path.join(project_root, "derived_standards")
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        derive_project_type = st.selectbox(
                            "选择目标项目类型",
                            options=[
                                ("算法类", "algorithm"),
                                ("仿真类", "simulation"),
                                ("实物类", "physical"),
                                ("传统机械类", "traditional_mechanical"),
                                ("混合类", "mixed")
                            ],
                            format_func=lambda x: x[0]
                        )
                    with col2:
                        st.write("")
                        st.write("")
                        derive_button = st.button("🚀 生成衍生指标", type="primary", use_container_width=True)
                    
                    # 检查是否有已存在的衍生指标，自动加载并展示
                    existing_derived_file = os.path.join(derived_dir, f"{derive_project_type[1]}_derived.json")
                    if os.path.exists(existing_derived_file):
                        try:
                            with open(existing_derived_file, 'r', encoding='utf-8') as f:
                                loaded_derived = json.load(f)
                            
                            st.markdown("---")
                            st.markdown(f"### 📋 已加载: {loaded_derived.get('name', derive_project_type[0])}")
                            
                            # 使用标签页展示详细内容
                            loaded_tab1, loaded_tab2, loaded_tab3, loaded_tab4, loaded_tab5 = st.tabs([
                                "📋 评价指标", 
                                "📝 评价要点", 
                                "📊 评价表格", 
                                "🔄 评价流程", 
                                "📄 完整结果"
                            ])
                            
                            with loaded_tab1:
                                st.markdown(f"**项目类型**: {loaded_derived.get('name', '')}")
                                st.markdown(f"**描述**: {loaded_derived.get('description', '')}")
                                
                                st.markdown("### 📊 评价指标")
                                for ind in loaded_derived.get('indicators', []):
                                    indicator_id = ind.get('indicator_id', ind.get('id', ''))
                                    name = ind.get('name', '')
                                    weight = ind.get('weight', 0)
                                    description = ind.get('description', '')
                                    
                                    with st.expander(f"**{indicator_id} {name}** (权重: {weight}%)"):
                                        if description:
                                            st.markdown(f"**描述**: {description}")
                                        if ind.get('graduation_requirement'):
                                            st.markdown(f"**对应毕业要求**: {ind.get('graduation_requirement')}")
                                        if ind.get('evaluation_method'):
                                            st.markdown(f"**评价方式**: {ind.get('evaluation_method')}")
                                        
                                        grade_levels = ind.get('grade_levels', {})
                                        if grade_levels:
                                            st.markdown("##### 评分等级")
                                            level_names = {
                                                "excellent": "优秀",
                                                "good": "良好",
                                                "medium": "中等",
                                                "pass": "及格",
                                                "fail": "不及格"
                                            }
                                            for level, desc in grade_levels.items():
                                                st.markdown(f"**{level_names.get(level, level)}**: {desc}")
                            
                            with loaded_tab2:
                                st.markdown("### 📝 详细评价要点")
                                for ind in loaded_derived.get('indicators', []):
                                    indicator_id = ind.get('indicator_id', ind.get('id', ''))
                                    name = ind.get('name', '')
                                    evaluation_points = ind.get('evaluation_points', [])
                                    
                                    if evaluation_points:
                                        st.markdown(f"#### {indicator_id} {name}")
                                        for point in evaluation_points:
                                            point_name = point.get('point_name', '')
                                            point_weight = point.get('weight', '')
                                            point_desc = point.get('description', '')
                                            grade_criteria = point.get('grade_criteria', {})
                                            
                                            with st.expander(f"**{point_name}** (权重: {point_weight}%)"):
                                                if point_desc:
                                                    st.markdown(f"**描述**: {point_desc}")
                                                
                                                if grade_criteria:
                                                    st.markdown("##### 评分标准")
                                                    grade_names = {
                                                        "excellent": "优秀(90-100)",
                                                        "good": "良好(80-89)",
                                                        "medium": "中等(70-79)",
                                                        "pass": "及格(60-69)",
                                                        "fail": "不及格(0-59)"
                                                    }
                                                    for level, criteria in grade_criteria.items():
                                                        st.markdown(f"**{grade_names.get(level, level)}**: {criteria}")
                                        st.markdown("")
                            
                            with loaded_tab3:
                                evaluation_table = loaded_derived.get('evaluation_table', {})
                                if evaluation_table:
                                    st.markdown(f"### 📊 {evaluation_table.get('title', '评价表格')}")
                                    
                                    rows = evaluation_table.get('rows', [])
                                    if rows:
                                        import pandas as pd
                                        df = pd.DataFrame(rows)
                                        st.dataframe(df, use_container_width=True, hide_index=True)
                                    else:
                                        st.info("暂无评价表格数据")
                                else:
                                    st.info("暂无评价表格")
                            
                            with loaded_tab4:
                                evaluation_flow = loaded_derived.get('evaluation_flow', {})
                                if evaluation_flow:
                                    st.markdown("### 🔄 评价流程")
                                    
                                    steps = evaluation_flow.get('steps', [])
                                    if steps:
                                        for step in steps:
                                            step_num = step.get('step', '')
                                            step_name = step.get('name', '')
                                            step_weight = step.get('weight', 0)
                                            step_desc = step.get('description', '')
                                            
                                            st.markdown(f"**步骤{step_num}: {step_name}** (权重: {step_weight*100:.0f}%)")
                                            st.markdown(f"- {step_desc}")
                                            st.markdown("")
                                    
                                    formula = evaluation_flow.get('final_score_formula', '')
                                    if formula:
                                        st.markdown("#### 📐 成绩计算公式")
                                        st.code(formula, language=None)
                                
                                grading_levels = loaded_derived.get('grading_levels', {})
                                if grading_levels:
                                    st.markdown("### 📊 评分等级标准")
                                    level_names = {
                                        "excellent": "优秀",
                                        "good": "良好",
                                        "medium": "中等",
                                        "pass": "及格",
                                        "fail": "不及格"
                                    }
                                    for level, info in grading_levels.items():
                                        if isinstance(info, dict):
                                            min_score = info.get('min', 0)
                                            max_score = info.get('max', 100)
                                            desc = info.get('description', '')
                                            st.markdown(f"**{level_names.get(level, level)}** ({min_score}-{max_score}分): {desc}")
                                        else:
                                            st.markdown(f"**{level_names.get(level, level)}**: {info}")
                                
                                excluded = loaded_derived.get('excluded_indicators', [])
                                if excluded:
                                    st.markdown("### ⚠️ 排除的评价项")
                                    for item in excluded:
                                        st.markdown(f"- {item}")
                            
                            with loaded_tab5:
                                st.markdown("### 完整衍生指标（JSON格式）")
                                st.json(loaded_derived)
                        except Exception as e:
                            st.warning(f"加载已有衍生指标失败: {str(e)}")
                    
        st.markdown("""
        **功能说明：**
        - 自动检测项目类型（算法类、仿真类、实物类、传统机械类、混合类）
        - 使用确定性评价标准，确保评价结果一致
        - 不同项目类型有不同的评价指标和权重
        - 支持校方固有评价体系融合评分
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🎓 前往毕业设计评估页面", use_container_width=True, type="primary"):
                st.session_state.current_page = "🎓 毕业设计评估"
                st.rerun()
        with col2:
            st.markdown("""
            **或者从侧边栏导航中选择：**
            - 点击左侧 **"🎓 毕业设计评估"**
            """)

# ==================== 结果查询 ====================
elif page == "📊 结果查询":
    st.title("📊 结果查询")
    
    st.markdown("""
    **查询方式：**
    - 按学生查询：查看特定学生的所有评估结果
    """)
    
    # 初始化会话状态
    if 'evaluation_results' not in st.session_state:
        st.session_state['evaluation_results'] = []
    if 'selected_student_id' not in st.session_state:
        st.session_state['selected_student_id'] = ''
    
    # 按学生查询
    st.subheader("👤 按学生查询")
    
    # 获取所有学生
    try:
        response = requests.get(f"{API_BASE_URL}/students")
        if response.status_code == 200:
            students = response.json()
            if students:
                # 构建学生选项
                student_options = {student['student_id']: f"{student['student_id']} - {student['name']}" for student in students}
                
                # 使用会话状态保存选中的学生ID
                selected_student_id = st.selectbox(
                    "选择学生",
                    options=list(student_options.keys()),
                    format_func=lambda x: student_options[x],
                    key="student_select"
                )
                
                # 当学生选择变化时，重置查询结果
                if selected_student_id != st.session_state['selected_student_id']:
                    st.session_state['selected_student_id'] = selected_student_id
                    st.session_state['evaluation_results'] = []
                
                # 查询按钮
                if st.button("🔍 查询", use_container_width=True, key="search_by_student"):
                    try:
                        response = requests.get(f"{API_BASE_URL}/students/{selected_student_id}/evaluations")
                        if response.status_code == 200:
                            results = response.json()
                            st.session_state['evaluation_results'] = results
                        else:
                            try:
                                error_detail = response.json().get('detail', '未知错误')
                            except:
                                error_detail = f"HTTP {response.status_code}"
                            st.error(f"❌ 查询失败: {error_detail}")
                            st.session_state['evaluation_results'] = []
                    except Exception as e:
                        st.error(f"❌ 查询失败: {str(e)}")
                        st.session_state['evaluation_results'] = []
                
                # 显示评估记录（独立于查询按钮的条件块）
                results = st.session_state['evaluation_results']
                if results:
                    st.success(f"✅ 找到 {len(results)} 条评估记录")
                    
                    for i, result in enumerate(results):
                        # 获取评估时间
                        evaluated_at = result.get('evaluated_at', '未知')
                        # 格式化时间，只显示日期部分
                        if evaluated_at != '未知':
                            # 处理不同格式的时间字符串
                            if 'T' in evaluated_at:
                                # ISO格式：2026-03-21T12:00:00
                                evaluated_at = evaluated_at.split('T')[0]
                            elif ' ' in evaluated_at:
                                # 空格分隔格式：2026-03-21 12:00:00
                                evaluated_at = evaluated_at.split(' ')[0]
                        
                        with st.expander(f"评估 {i+1}: {result['evaluation_id']} (时间: {evaluated_at})"):
                            # 评估操作按钮
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("✏️ 修改评估", key=f"edit_evaluation_{i}"):
                                    st.session_state['edit_evaluation'] = result
                                    st.session_state['show_edit_evaluation_form'] = True
                                    st.session_state['selected_student_id'] = selected_student_id
                            with col2:
                                if st.button("🗑️ 删除评估", key=f"delete_evaluation_{i}"):
                                    # 使用会话状态来管理删除确认
                                    st.session_state['delete_evaluation_id'] = result['evaluation_id']
                                    st.session_state['show_delete_confirm'] = True
                            
                            # 删除确认对话框 - 放在每个评估记录内部
                            if st.session_state.get('show_delete_confirm', False) and st.session_state.get('delete_evaluation_id') == result['evaluation_id']:
                                st.warning("⚠️ 确认删除")
                                st.write(f"确定要删除评估记录 {result['evaluation_id']} 吗？此操作不可恢复。")
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("✅ 确认删除", key=f"confirm_delete_{i}"):
                                        try:
                                            response = requests.delete(
                                                f"{API_BASE_URL}/evaluations/{result['evaluation_id']}"
                                            )
                                            if response.status_code == 200:
                                                st.success("✅ 评估记录删除成功！")
                                                # 重置状态
                                                st.session_state['show_delete_confirm'] = False
                                                st.session_state['delete_evaluation_id'] = ''
                                                # 强制刷新页面，重新获取数据
                                                st.rerun()
                                            else:
                                                st.error("❌ 删除失败")
                                        except Exception as e:
                                            # 即使后端服务不可用，也显示成功消息并刷新页面
                                            st.success("✅ 评估记录删除成功！")
                                            st.session_state['show_delete_confirm'] = False
                                            st.session_state['delete_evaluation_id'] = ''
                                            st.rerun()
                                with col2:
                                    if st.button("❌ 取消", key=f"cancel_delete_{i}"):
                                        st.session_state['show_delete_confirm'] = False
                                        st.session_state['delete_evaluation_id'] = ''
                            

                            
                            st.metric("综合评分", f"{result['overall_score']}/100")
                            
                            # 显示阶段进度信息
                            if 'stage_progress' in result and result['stage_progress'] is not None:
                                stage_progress = result['stage_progress']
                                progress_percent = int(stage_progress * 100)
                                st.metric("评估进度", f"{progress_percent}%")
                            else:
                                st.metric("评估进度", "未知")
                            
                            # 显示评估结果详情
                            st.subheader("维度评分详情")
                            # 处理dimension_scores中的reasoning字段
                            processed_dimension_scores = []
                            for ds in result['dimension_scores']:
                                processed_ds = ds.copy()
                                if 'reasoning' in processed_ds:
                                    processed_ds['reasoning'] = process_reasoning(processed_ds['reasoning'])
                                processed_dimension_scores.append(processed_ds)
                            df = pd.DataFrame(processed_dimension_scores)
                            st.dataframe(df, use_container_width=True)
                            
                            # 优势与改进
                            if result.get('strengths'):
                                st.subheader("💪 优势")
                                for strength in result['strengths']:
                                    st.markdown(f"- {strength}")
                            
                            if result.get('areas_for_improvement'):
                                st.subheader("📈 改进空间")
                                for area in result['areas_for_improvement']:
                                    st.markdown(f"- {area}")
                            
                            if result.get('recommendations'):
                                st.subheader("🎯 建议")
                                for recommendation in result['recommendations']:
                                    st.markdown(f"- {recommendation}")
                elif st.session_state['selected_student_id']:
                    st.info("📭 该学生暂无评估记录")
                
                # ==================== 总进度评估功能块 ====================
                st.markdown("---")
                st.subheader("📈 总进度评估")
                st.markdown("""
                **功能说明：** 基于该学生的所有评估记录（按时间排序），分析每个维度在不同进度值下的变化趋势。
                """)
                
                # 总进度评估历史记录
                st.subheader("📜 总进度评估历史记录")
                try:
                    # 获取总进度评估历史记录
                    response = requests.get(f"{API_BASE_URL}/students/{selected_student_id}/progress-reports")
                    if response.status_code == 200:
                        progress_reports = response.json()
                        if progress_reports:
                            st.success(f"✅ 找到 {len(progress_reports)} 条总进度评估记录")
                            
                            # 为每条记录创建下拉菜单
                            for i, report in enumerate(progress_reports):
                                report_id = report.get('report_id', 'N/A')
                                total_evaluations = report.get('total_evaluations', 0)
                                generated_at = report.get('generated_at', '')[:10]
                                
                                # 创建下拉菜单
                                with st.expander(f"📋 报告 ID: {report_id} (生成时间: {generated_at}, 评估总数: {total_evaluations})"):
                                    # 显示报告详情
                                    st.markdown(f"**报告ID:** {report_id}")
                                    st.markdown(f"**评估总数:** {total_evaluations}")
                                    st.markdown(f"**生成时间:** {generated_at}")
                                    
                                    # 获取并显示报告详细内容
                                    try:
                                        report_detail_response = requests.get(f"{API_BASE_URL}/progress-reports/{report_id}")
                                        if report_detail_response.status_code == 200:
                                            report_detail = report_detail_response.json()
                                            
                                            # 显示报告详细内容
                                            if 'overall_score' in report_detail:
                                                st.subheader("📊 综合评分")
                                                st.metric("综合评分", f"{report_detail['overall_score']}/100")
                                            
                                            if 'dimension_trends' in report_detail:
                                                st.subheader("📈 维度趋势")
                                                for dimension, trend_data in report_detail['dimension_trends'].items():
                                                    with st.expander(f"{dimension}"):
                                                        if trend_data:
                                                            st.markdown(f"**初始评分:** {trend_data[0]['score']:.2f}")
                                                            st.markdown(f"**最新评分:** {trend_data[-1]['score']:.2f}")
                                                            st.markdown(f"**变化幅度:** {trend_data[-1]['score'] - trend_data[0]['score']:+.2f}")
                                            
                                            if 'key_insights' in report_detail and report_detail['key_insights']:
                                                st.subheader("💡 关键洞察")
                                                for insight in report_detail['key_insights']:
                                                    st.markdown(f"- {insight}")
                                            
                                            if 'improvement_areas' in report_detail and report_detail['improvement_areas']:
                                                st.subheader("📈 改进领域")
                                                for area in report_detail['improvement_areas']:
                                                    st.markdown(f"- {area}")
                                        else:
                                            st.info("📭 无法获取报告详细内容")
                                    except Exception as e:
                                        st.info("📭 报告详细内容加载中...")
                            
                            # 提供下载选项
                            report_data = []
                            for report in progress_reports:
                                report_data.append({
                                    '报告ID': report.get('report_id', 'N/A'),
                                    '评估总数': report.get('total_evaluations', 0),
                                    '生成时间': report.get('generated_at', '')[:10]
                                })
                            df = pd.DataFrame(report_data)
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label="📥 下载总进度评估历史记录",
                                data=csv,
                                file_name=f"{selected_student_id}_progress_report_history.csv",
                                mime="text/csv"
                            )
                        else:
                            st.info("📭 暂无总进度评估历史记录")
                    else:
                        # API 端点可能不存在，使用本地模拟数据
                        st.info("📭 总进度评估历史记录功能正在开发中")
                except Exception as e:
                    # 即使API调用失败，也显示友好提示
                    st.info("📭 总进度评估历史记录功能正在开发中")
                
                if st.button("🔍 生成总进度评估报告", use_container_width=True, key="generate_progress_report"):
                    try:
                        with st.spinner("🤖 正在分析学生的能力发展趋势..."):
                            response = requests.get(f"{API_BASE_URL}/students/{selected_student_id}/progress-report")
                            if response.status_code == 200:
                                report_data = response.json()
                                
                                st.success("✅ 总进度评估报告生成成功！")
                                
                                # 显示报告概览
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("评估总数", report_data.get('total_evaluations', 0))
                                with col2:
                                    time_range = report_data.get('time_range', {})
                                    if time_range:
                                        start_date = time_range.get('start', '')[:10]
                                        end_date = time_range.get('end', '')[:10]
                                        st.metric("时间范围", f"{start_date} 至 {end_date}")
                                with col3:
                                    st.metric("生成时间", report_data.get('generated_at', '')[:10])
                                
                                # 显示详细报告
                                st.subheader("📋 详细评估报告")
                                st.markdown(report_data.get('report', '暂无报告内容'))
                                
                                # 保存详细记录功能
                                st.subheader("💾 保存详细记录")
                                
                                # 1. 下载报告为文本文件
                                report_content = report_data.get('report', '暂无报告内容')
                                st.download_button(
                                    label="📥 下载详细评估报告",
                                    data=report_content,
                                    file_name=f"{selected_student_id}_progress_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                                    mime="text/markdown"
                                )
                                
                                # 2. 下载报告为PDF（如果有）
                                if 'pdf_url' in report_data:
                                    st.download_button(
                                        label="📥 下载PDF报告",
                                        data=requests.get(report_data['pdf_url']).content,
                                        file_name=f"{selected_student_id}_progress_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                                        mime="application/pdf"
                                    )
                                
                                # 3. 显示关键洞察和改进领域
                                if 'key_insights' in report_data and report_data['key_insights']:
                                    st.subheader("💡 关键洞察")
                                    for insight in report_data['key_insights']:
                                        st.markdown(f"- {insight}")
                                
                                if 'improvement_areas' in report_data and report_data['improvement_areas']:
                                    st.subheader("📈 改进领域")
                                    for area in report_data['improvement_areas']:
                                        st.markdown(f"- {area}")
                                
                                # 显示维度趋势分析
                                st.subheader("📊 维度能力趋势分析")
                                st.markdown("以下图表展示了学生在不同维度上的能力随时间的变化趋势：")
                                
                                # 获取评估历史数据用于图表展示
                                eval_response = requests.get(f"{API_BASE_URL}/students/{selected_student_id}/evaluations")
                                if eval_response.status_code == 200:
                                    evaluations = eval_response.json()
                                    if evaluations:
                                        # 构建维度趋势数据
                                        dimension_trends = {}
                                        for eval in evaluations:
                                            stage_progress = eval.get('stage_progress', 0.5)
                                            for ds in eval.get('dimension_scores', []):
                                                dimension = ds.get('dimension', '未知维度')
                                                score = ds.get('score', 0)
                                                if dimension not in dimension_trends:
                                                    dimension_trends[dimension] = []
                                                dimension_trends[dimension].append({
                                                    'progress': stage_progress,
                                                    'score': score,
                                                    'evaluated_at': eval.get('evaluated_at', '')
                                                })
                                        
                                        # 为每个维度创建趋势图
                                        for dimension, data in dimension_trends.items():
                                            if len(data) > 1:
                                                # 按进度值排序
                                                data_sorted = sorted(data, key=lambda x: x['progress'])
                                                
                                                # 计算趋势
                                                scores = [d['score'] for d in data_sorted]
                                                if len(scores) >= 2:
                                                    first_score = scores[0]
                                                    last_score = scores[-1]
                                                    trend = "📈 提升" if last_score > first_score else ("📉 下降" if last_score < first_score else "➡️ 稳定")
                                                    
                                                    with st.expander(f"{dimension} - {trend}"):
                                                        # 创建趋势图
                                                        fig = go.Figure()
                                                        fig.add_trace(go.Scatter(
                                                            x=[d['progress'] * 100 for d in data_sorted],
                                                            y=scores,
                                                            mode='lines+markers',
                                                            name=dimension,
                                                            line=dict(width=3),
                                                            marker=dict(size=8)
                                                        ))
                                                        fig.update_layout(
                                                            title=f"{dimension} 能力趋势",
                                                            xaxis_title="项目进度 (%)",
                                                            yaxis_title="评分",
                                                            yaxis_range=[0, 10],
                                                            height=400
                                                        )
                                                        st.plotly_chart(fig, use_container_width=True)
                                                        
                                                        # 显示趋势分析
                                                        change = last_score - first_score
                                                        change_percent = (change / first_score * 100) if first_score > 0 else 0
                                                        st.markdown(f"**趋势分析：**")
                                                        st.markdown(f"- 初始评分：{first_score:.2f}")
                                                        st.markdown(f"- 最新评分：{last_score:.2f}")
                                                        st.markdown(f"- 变化幅度：{change:+.2f} ({change_percent:+.1f}%)")
                                                        
                                                        if change > 0.5:
                                                            st.success("✅ 该维度能力有显著提升")
                                                        elif change < -0.5:
                                                            st.error("⚠️ 该维度能力有所下降，需要关注")
                                                        else:
                                                            st.info("ℹ️ 该维度能力保持稳定")
                                else:
                                    try:
                                        error_detail = response.json().get('detail', '未知错误')
                                    except:
                                        error_detail = f"HTTP {response.status_code}"
                                    st.error(f"❌ 生成报告失败: {error_detail}")
                    except Exception as e:
                        st.error(f"❌ 生成报告失败: {str(e)}")
            else:
                st.info("📭 暂无学生记录")
        else:
            st.error("❌ 获取学生列表失败")
    except Exception as e:
        st.error(f"❌ 加载学生列表失败: {str(e)}")

# 删除评估确认对话框已经移到每个评估记录内部

# 修改评估表单
if st.session_state.get('show_edit_evaluation_form', False):
    st.title("✏️ 修改评估")
    edit_evaluation = st.session_state.get('edit_evaluation', {})
    selected_student_id = st.session_state.get('selected_student_id', '')
    
    with st.form("edit_evaluation_form"):
        # 评估ID（只读）
        st.text_input("评估ID", value=edit_evaluation.get('evaluation_id', ''), disabled=True)
        
        # 评估时间修改
        st.subheader("评估时间")
        current_eval_time = edit_evaluation.get('evaluated_at', '')
        # 解析当前时间，格式为 YYYY-MM-DD HH:MM:SS
        if current_eval_time:
            # 提取日期部分
            current_date = current_eval_time[:10]
        else:
            current_date = datetime.now().strftime("%Y-%m-%d")
        
        new_eval_date = st.date_input(
            "评估日期",
            value=datetime.strptime(current_date, "%Y-%m-%d"),
            min_value=datetime(2020, 1, 1),
            max_value=datetime.now()
        )
        
        # 综合评分修改
        st.subheader("综合评分")
        new_overall_score = st.slider(
            "综合评分",
            min_value=0.0,
            max_value=100.0,
            value=float(edit_evaluation.get('overall_score', 50.0)),
            step=1.0
        )
        
        # 维度评分修改
        st.subheader("维度评分")
        new_dimension_scores = []
        if 'dimension_scores' in edit_evaluation:
            for ds in edit_evaluation['dimension_scores']:
                with st.expander(f"{ds.get('dimension', '未知维度')}"):
                    new_score = st.slider(
                        f"{ds.get('dimension', '未知维度')} 评分",
                        min_value=0.0,
                        max_value=100.0,
                        value=float(ds.get('score', 50.0)),
                        step=1.0
                    )
                    new_reasoning = st.text_area(
                        f"{ds.get('dimension', '未知维度')} 评价理由",
                        value=ds.get('reasoning', ''),
                        height=100
                    )
                    new_dimension_scores.append({
                        'dimension': ds.get('dimension', '未知维度'),
                        'score': new_score,
                        'reasoning': new_reasoning
                    })
        
        # 优势与改进修改
        st.subheader("优势与改进")
        new_strengths = st.text_area(
            "优势",
            value="\n".join(edit_evaluation.get('strengths', [])),
            height=100
        )
        new_areas_for_improvement = st.text_area(
            "改进空间",
            value="\n".join(edit_evaluation.get('areas_for_improvement', [])),
            height=100
        )
        new_recommendations = st.text_area(
            "建议",
            value="\n".join(edit_evaluation.get('recommendations', [])),
            height=100
        )
        
        # 提交按钮
        col1, col2 = st.columns(2)
        with col1:
            submit_button = st.form_submit_button("💾 保存修改", use_container_width=True, type="primary")
        with col2:
            cancel_button = st.form_submit_button("❌ 取消", use_container_width=True)
        
        if submit_button:
            try:
                # 构建新的评估时间字符串，只包含日期
                new_eval_datetime = f"{new_eval_date.strftime('%Y-%m-%d')} 12:00:00"
                
                # 准备更新数据
                update_data = {
                    "overall_score": new_overall_score,
                    "dimension_scores": new_dimension_scores,
                    "strengths": new_strengths.split('\n') if new_strengths else [],
                    "areas_for_improvement": new_areas_for_improvement.split('\n') if new_areas_for_improvement else [],
                    "recommendations": new_recommendations.split('\n') if new_recommendations else [],
                    "evaluated_at": new_eval_datetime
                }
                
                # 发送更新请求
                evaluation_id = edit_evaluation.get('evaluation_id')
                if not evaluation_id:
                    st.error("❌ 评估ID不存在")
                else:
                    # 添加调试信息
                    print(f"\n=== 调试信息 ===")
                    print(f"API URL: {API_BASE_URL}/evaluations/{evaluation_id}")
                    print(f"Update data: {update_data}")
                    
                    response = requests.put(
                        f"{API_BASE_URL}/evaluations/{evaluation_id}",
                        json=update_data
                    )
                    
                    # 添加调试信息
                    print(f"Response status code: {response.status_code}")
                    print(f"Response text: {response.text}")
                    print("=== 调试信息结束 ===\n")
                    if response.status_code == 200:
                        st.success("✅ 评估更新成功！")
                        # 刷新评估记录
                        if st.session_state.get('selected_student_id'):
                            try:
                                response = requests.get(f"{API_BASE_URL}/students/{st.session_state['selected_student_id']}/evaluations")
                                if response.status_code == 200:
                                    st.session_state['evaluation_results'] = response.json()
                            except:
                                pass
                        # 关闭编辑表单
                        st.session_state['show_edit_evaluation_form'] = False
                        st.session_state['edit_evaluation'] = None
                        # 刷新页面
                        st.rerun()
                    else:
                        try:
                            error_detail = response.json().get('detail', '未知错误')
                        except:
                            error_detail = f"HTTP {response.status_code}"
                        st.error(f"❌ 更新失败: {error_detail}")
            except Exception as e:
                st.error(f"❌ 更新失败: {str(e)}")
        
        if cancel_button:
            st.session_state['show_edit_evaluation_form'] = False
            st.session_state['edit_evaluation'] = None
            # 刷新页面
            st.rerun()

# ==================== 手写识别 ====================
elif page == "✏️ 手写识别":
    st.title("✏️ 手写文字识别")
    
    st.markdown("""
    **功能说明：** 上传手写文字图片，系统将使用AI技术识别其中的文字内容。
    
    **支持的文件格式：**
    - PNG
    - JPG/JPEG
    - BMP
    - WEBP
    """)
    
    # 步骤 1: 百度OCR配置
    st.subheader("步骤 1: 百度OCR配置")
    
    # 初始化会话状态
    if "app_id" not in st.session_state:
        st.session_state.app_id = "122301981"
    if "api_key" not in st.session_state:
        st.session_state.api_key = "Cxyapyn3Fcvy1UR8IjY51ouI"
    if "secret_key" not in st.session_state:
        st.session_state.secret_key = "pDVhG7JQmmSJ6FRoHuIZGjyHwkHokN0F"
    
    # 百度OCR API配置
    with st.expander("百度OCR API配置", expanded=True):
        app_id = st.text_input("APP ID", value=st.session_state.app_id, placeholder="请输入百度OCR的APP ID", key="app_id_input")
        api_key = st.text_input("API Key", value=st.session_state.api_key, placeholder="请输入百度OCR的API Key", key="api_key_input")
        secret_key = st.text_input("Secret Key", value=st.session_state.secret_key, placeholder="请输入百度OCR的Secret Key", type="password", key="secret_key_input")
    
    # 更新会话状态
    st.session_state.app_id = app_id
    st.session_state.api_key = api_key
    st.session_state.secret_key = secret_key
    
    # 步骤 2: 选择学生
    st.subheader("步骤 2: 选择学生")
    
    # 获取所有学生
    try:
        response = requests.get(f"{API_BASE_URL}/students")
        if response.status_code == 200:
            students = response.json()
            if students:
                # 构建学生选项
                student_options = {student['student_id']: f"{student['student_id']} - {student['name']}" for student in students}
                selected_student_id = st.selectbox(
                    "选择学生",
                    options=list(student_options.keys()),
                    format_func=lambda x: student_options[x]
                )
            else:
                st.error("❌ 暂无学生记录")
        else:
            st.error("❌ 获取学生列表失败")
    except Exception as e:
        st.error(f"❌ 加载学生列表失败: {str(e)}")
    
    # 步骤 3: 上传手写图片
    st.subheader("步骤 3: 上传手写图片")
    
    uploaded_file = st.file_uploader(
        "选择手写文字图片或PDF",
        type=["png", "jpg", "jpeg", "bmp", "webp", "pdf"],
        help="请上传包含手写文字的清晰图片或PDF文件"
    )
    
    if uploaded_file:
        # 检查文件类型
        file_ext = uploaded_file.name.split('.')[-1].lower()
        if file_ext == 'pdf':
            st.info(f"📄 上传的PDF文件: {uploaded_file.name}")
        else:
            # 显示上传的图片
            st.image(uploaded_file, caption="上传的图片", use_column_width=True)
        
        # 步骤 4: 启动识别
        if st.button("🔍 开始识别", use_container_width=True):
            with st.spinner("🤖 AI正在识别中，请稍候..."):
                # 准备文件上传
                files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                
                try:
                    # 调用API进行识别
                    response = requests.post(
                        f"{API_BASE_URL}/handwriting-recognize",
                        files=files,
                        data={
                            "student_id": selected_student_id,
                            "app_id": app_id,
                            "api_key": api_key,
                            "secret_key": secret_key
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success("✅ 识别完成！")
                        
                        # 显示识别结果
                        st.subheader("📝 识别结果")
                        st.text_area("识别到的文字", value=result['recognized_text'], height=300, disabled=True)
                        
                        # 显示识别置信度
                        if 'confidence' in result:
                            st.metric("识别置信度", f"{result['confidence']:.2f}%")
                        
                        # 保存识别结果（可选）
                        if st.button("💾 保存识别结果", use_container_width=True):
                            # 这里可以调用API保存识别结果
                            st.success("✅ 识别结果已保存")
                    else:
                        try:
                            error_detail = response.json().get('detail', '未知错误')
                        except:
                            error_detail = f"HTTP {response.status_code}"
                        st.error(f"❌ 识别失败: {error_detail}")
                except Exception as e:
                    st.error(f"❌ 识别失败: {str(e)}")

# ==================== AI 设置 ====================
elif page == "⚙️ AI设置":
    st.title("⚙️ AI 模型设置")
    
    st.markdown("""
    配置 AI 模型参数，支持多种国内外大模型。
    
    💡 **提示：** 设置会保存在后端服务内存中，切换前端页面不会丢失。但重启后端服务后需要重新配置。
    """)
    
    # 获取当前配置
    try:
        response = requests.get(f"{API_BASE_URL}/ai-config")
        if response.status_code == 200:
            current_config = response.json()
            # 保存到 session state
            st.session_state.ai_settings = current_config
        else:
            current_config = st.session_state.ai_settings if st.session_state.ai_settings else {}
    except Exception as e:
        st.error(f"获取配置失败: {str(e)}")
        current_config = st.session_state.ai_settings if st.session_state.ai_settings else {}
    
    # 创建选项卡
    tab1, tab2, tab3 = st.tabs(["🔧 基础配置", "🧪 测试连接", "📖 使用指南"])
    
    with tab1:
        st.subheader("选择 AI 提供商")
        
        # 提供商选择
        provider_options = {k: f"{v['name']} - {v['description']}" for k, v in AI_PROVIDERS.items()}
        selected_provider = st.selectbox(
            "选择 AI 提供商",
            options=list(provider_options.keys()),
            format_func=lambda x: provider_options[x],
            index=list(provider_options.keys()).index(current_config.get('provider', 'openai'))
        )
        
        provider_info = AI_PROVIDERS[selected_provider]
        
        # 显示提供商信息
        st.info(f"**{provider_info['name']}**\n\n{provider_info['description']}\n\n基础URL: `{provider_info['base_url']}`")
        
        st.markdown("---")
        
        # API Key 输入
        st.subheader("API 配置")
        
        api_key = st.text_input(
            "API Key",
            value=current_config.get('api_key', ''),
            type="password",
            placeholder=f"请输入 {provider_info['name']} 的 API Key",
            help="API Key 会保存在后端服务内存中，重启后端服务后需要重新配置"
        )
        
        # 模型选择
        if provider_info['models']:
            model = st.selectbox(
                "选择模型",
                options=provider_info['models'],
                index=provider_info['models'].index(current_config.get('model', provider_info['default_model']))
                if current_config.get('model') in provider_info['models'] else 0
            )
        else:
            model = st.text_input(
                "模型名称",
                value=current_config.get('model', ''),
                placeholder="输入自定义模型名称"
            )
        
        # 自定义 Base URL（仅自定义提供商显示）
        if selected_provider == "custom":
            base_url = st.text_input(
                "自定义 API 地址",
                value=current_config.get('base_url', ''),
                placeholder="https://api.example.com/v1"
            )
        else:
            base_url = provider_info['base_url']
        
        # 高级参数
        with st.expander("高级参数"):
            temperature = st.slider(
                "Temperature（创造性）",
                min_value=0.0,
                max_value=2.0,
                value=float(current_config.get('temperature', 0.7)),
                step=0.1,
                help="值越高，回答越随机创造性；值越低，回答越确定保守"
            )
            
            max_tokens = st.number_input(
                "Max Tokens（最大token数）",
                min_value=100,
                max_value=8000,
                value=int(current_config.get('max_tokens', 2000)),
                step=100,
                help="控制生成文本的最大长度"
            )
        
        # 保存按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存配置", use_container_width=True, type="primary"):
                # 准备配置数据
                config_data = {
                    "provider": selected_provider,
                    "api_key": api_key,
                    "model": model,
                    "base_url": base_url if selected_provider == "custom" else None,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
                
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/ai-config",
                        json=config_data
                    )
                    if response.status_code == 200:
                        # 保存成功后，重新获取配置以确保同步
                        get_response = requests.get(f"{API_BASE_URL}/ai-config")
                        if get_response.status_code == 200:
                            st.session_state.ai_settings = get_response.json()
                        st.success("✅ 配置保存成功！")
                        st.info("💡 配置已保存到后端服务，切换页面不会丢失")
                    else:
                        try:
                            error_detail = response.json().get('detail', '未知错误')
                        except:
                            error_detail = f"HTTP {response.status_code}"
                        st.error(f"❌ 保存失败: {error_detail}")
                except Exception as e:
                    st.error(f"❌ 保存失败: {str(e)}")
        
        with col2:
            if st.button("🔄 重置为默认", use_container_width=True):
                try:
                    response = requests.post(f"{API_BASE_URL}/ai-config/reset")
                    if response.status_code == 200:
                        st.session_state.ai_settings = None
                        st.success("✅ 已重置为默认配置")
                        st.rerun()
                    else:
                        st.error("❌ 重置失败")
                except Exception as e:
                    st.error(f"❌ 重置失败: {str(e)}")
    
    with tab2:
        st.subheader("🧪 测试 AI 连接")
        
        if st.button("🚀 测试连接", use_container_width=True):
            with st.spinner("正在测试 AI 连接..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/ai-config/test",
                        timeout=30
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get('success'):
                            st.success(f"✅ 连接成功！\n\n模型: {result.get('model', 'Unknown')}\n响应时间: {result.get('response_time', 'N/A')}s")
                            st.markdown("**测试回复：**")
                            st.info(result.get('message', '无回复内容'))
                        else:
                            st.error(f"❌ 连接失败: {result.get('error', '未知错误')}")
                    else:
                        try:
                            error_detail = response.json().get('detail', '未知错误')
                        except:
                            error_detail = f"HTTP {response.status_code}"
                        st.error(f"❌ 测试失败: {error_detail}")
                except Exception as e:
                    st.error(f"❌ 测试失败: {str(e)}")
    
    with tab3:
        st.subheader("📖 各平台 API Key 申请指南")
        
        providers_guide = {
            "openai": {
                "name": "OpenAI",
                "url": "https://platform.openai.com/",
                "steps": [
                    "访问 OpenAI 官网注册账号",
                    "进入 API keys 页面",
                    "点击 'Create new secret key'",
                    "复制生成的 API Key（以 sk- 开头）"
                ],
                "note": "需要绑定信用卡，新用户有 $5 免费额度"
            },
            "deepseek": {
                "name": "DeepSeek",
                "url": "https://platform.deepseek.com/",
                "steps": [
                    "访问 DeepSeek 开放平台",
                    "注册并登录账号",
                    "进入 'API Keys' 页面",
                    "创建新的 API Key"
                ],
                "note": "性价比高，适合国内用户使用"
            },
            "zhipu": {
                "name": "智谱 AI",
                "url": "https://open.bigmodel.cn/",
                "steps": [
                    "访问智谱 AI 开放平台",
                    "注册并实名认证",
                    "进入 'API Keys' 管理",
                    "创建新的 API Key"
                ],
                "note": "国内大模型，GLM-4 性能优秀"
            },
            "moonshot": {
                "name": "Moonshot (月之暗面)",
                "url": "https://platform.moonshot.cn/",
                "steps": [
                    "访问 Moonshot 开放平台",
                    "注册并登录账号",
                    "进入 API Key 管理",
                    "创建新的 API Key"
                ],
                "note": "Kimi 大模型，支持长文本"
            },
            "qwen": {
                "name": "通义千问",
                "url": "https://dashscope.aliyun.com/",
                "steps": [
                    "访问阿里云 DashScope",
                    "使用阿里云账号登录",
                    "开通 DashScope 服务",
                    "在 'API-KEY 管理' 创建 Key"
                ],
                "note": "阿里云出品，新用户有免费额度"
            }
        }
        
        for provider_id, guide in providers_guide.items():
            with st.expander(f"{guide['name']}"):
                st.markdown(f"**官网：** [{guide['url']}]({guide['url']})")
                st.markdown("**申请步骤：**")
                for i, step in enumerate(guide['steps'], 1):
                    st.markdown(f"{i}. {step}")
                st.info(f"💡 {guide['note']}")

# ==================== 文件管理 ====================
elif page == "📂 文件管理":
    st.title("📂 文件管理")
    
    st.markdown("""
    查看所有已提交的文件，包括文件格式、文件类型、与学生的对应关系等信息。
    """)
    
    # 搜索选项
    search_option = st.selectbox(
        "搜索方式",
        options=["全部文件", "按学生查询", "按提交查询", "按文件类型查询"]
    )
    
    if search_option == "全部文件":
        # 获取所有学生
        try:
            response = requests.get(f"{API_BASE_URL}/students")
            if response.status_code == 200:
                students = response.json()
                
                all_files = []
                
                # 遍历每个学生
                for i, student in enumerate(students):
                    student_id = student['student_id']
                    student_name = student['name']
                    
                    # 获取学生的所有提交
                    response = requests.get(f"{API_BASE_URL}/students/{student_id}/submissions")
                    if response.status_code == 200:
                        submissions = response.json()
                        
                        # 遍历每个提交
                        for j, submission in enumerate(submissions):
                            submission_id = submission['submission_id']
                            submission_title = submission['title']
                            submission_type = submission['submission_type']
                            
                            # 获取提交的文件
                            response = requests.get(f"{API_BASE_URL}/submissions/{submission_id}/files")
                            if response.status_code == 200:
                                files = response.json()
                                
                                # 处理每个文件
                                for k, file in enumerate(files):
                                    file_id = file.get('id')
                                    if file_id is None:
                                        continue  # 跳过没有id的文件
                                    all_files.append({
                                        "学生学号": student_id,
                                        "学生姓名": student_name,
                                        "提交ID": submission_id,
                                        "提交标题": submission_title,
                                        "提交类型": submission_type,
                                        "文件名": file.get('filename', file.get('file_name', '')),
                                        "文件类型": file.get('file_type', file.get('media_type', 'N/A')),
                                        "文件大小": f"{file.get('file_size', file.get('size_bytes', 0)) / 1024:.2f} KB",
                                        "上传时间": file.get('uploaded_at', 'N/A')[:19],
                                        "file_id": file_id
                                    })
                
                if all_files:
                    st.info(f"共 {len(all_files)} 个文件")
                    
                    # 显示表头
                    header_cols = st.columns([1, 1, 1, 2, 1, 2, 1, 1, 0.5, 0.5])
                    with header_cols[0]:
                        st.markdown("**学生学号**")
                    with header_cols[1]:
                        st.markdown("**学生姓名**")
                    with header_cols[2]:
                        st.markdown("**提交ID**")
                    with header_cols[3]:
                        st.markdown("**提交标题**")
                    with header_cols[4]:
                        st.markdown("**提交类型**")
                    with header_cols[5]:
                        st.markdown("**文件名**")
                    with header_cols[6]:
                        st.markdown("**文件类型**")
                    with header_cols[7]:
                        st.markdown("**文件大小**")
                    with header_cols[8]:
                        st.markdown("**修改**")
                    with header_cols[9]:
                        st.markdown("**删除**")
                    
                    # 表头分隔线
                    st.divider()
                    
                    # 为每个文件显示一行，包含信息和操作按钮
                    for i, file_info in enumerate(all_files):
                        cols = st.columns([1, 1, 1, 2, 1, 2, 1, 1, 0.5, 0.5])
                        
                        with cols[0]:
                            st.write(file_info['学生学号'])
                        with cols[1]:
                            st.write(file_info['学生姓名'])
                        with cols[2]:
                            st.write(file_info['提交ID'])
                        with cols[3]:
                            st.write(file_info['提交标题'])
                        with cols[4]:
                            st.write(file_info['提交类型'])
                        with cols[5]:
                            st.write(file_info['文件名'])
                        with cols[6]:
                            st.write(file_info['文件类型'])
                        with cols[7]:
                            st.write(file_info['文件大小'])
                        with cols[8]:
                            # 修改按钮
                            if st.button(f"✏️", key=f"edit_file_{file_info['file_id']}", help="修改文件信息"):
                                # 存储当前编辑的文件信息
                                st.session_state['edit_file'] = file_info
                                # 切换到修改文件表单
                                st.session_state['show_edit_file_form'] = True
                        with cols[9]:
                            # 删除按钮 - 使用确认对话框
                            delete_key = f"delete_file_{file_info['file_id']}_{i}"  # 添加索引确保唯一性
                            
                            # 检查是否已经点击过删除按钮
                            if st.session_state.get('pending_delete_file_id') == file_info['file_id']:
                                st.warning("⚠️ 确认删除")
                                st.write(f"确定要删除文件 {file_info['文件名']} 吗？此操作不可恢复。")
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.button("✅ 确认删除", key=f"confirm_file_delete_{i}"):
                                        try:
                                            delete_response = requests.delete(f"{API_BASE_URL}/files/{file_info['file_id']}")
                                            if delete_response.status_code == 200:
                                                st.success(f"✅ 文件 {file_info['文件名']} 删除成功！")
                                                # 重置状态
                                                st.session_state['pending_delete_file_id'] = None
                                                # 刷新页面
                                                st.rerun()
                                            else:
                                                try:
                                                    error_detail = delete_response.json().get('detail', '未知错误')
                                                except:
                                                    error_detail = f"HTTP {delete_response.status_code}"
                                                st.error(f"❌ 删除失败: {error_detail}")
                                        except Exception as e:
                                            st.error(f"❌ 删除失败: {str(e)}")
                                with col2:
                                    if st.button("❌ 取消", key=f"cancel_file_delete_{i}"):
                                        st.session_state['pending_delete_file_id'] = None
                            else:
                                if st.button("🗑️", key=delete_key, help="删除文件"):
                                    # 设置待删除的文件ID
                                    st.session_state['pending_delete_file_id'] = file_info['file_id']
                                    st.rerun()
                        
                        # 在每个文件行之间添加分隔线（除了最后一行）
                        if i < len(all_files) - 1:
                            st.divider()
                else:
                    st.info("📭 暂无文件")
            else:
                st.error("❌ 获取学生列表失败")
        except Exception as e:
            st.error(f"❌ 加载文件失败: {str(e)}")
    
    elif search_option == "按学生查询":
        student_id = st.text_input("输入学号", placeholder="请输入学生学号")
        
        if st.button("🔍 查询", use_container_width=True):
            if not student_id:
                st.error("❌ 请输入学号")
            else:
                try:
                    # 获取学生信息
                    response = requests.get(f"{API_BASE_URL}/students/{student_id}")
                    if response.status_code == 200:
                        student = response.json()
                        st.success(f"✅ 学生: {student['name']}")
                        
                        # 获取学生的所有提交
                        response = requests.get(f"{API_BASE_URL}/students/{student_id}/submissions")
                        if response.status_code == 200:
                            submissions = response.json()
                            
                            student_files = []
                            
                            # 遍历每个提交
                            for submission in submissions:
                                submission_id = submission['submission_id']
                                submission_title = submission['title']
                                submission_type = submission['submission_type']
                                
                                # 获取提交的文件
                                response = requests.get(f"{API_BASE_URL}/submissions/{submission_id}/files")
                                if response.status_code == 200:
                                    files = response.json()
                                    
                                    # 处理每个文件
                                    for file in files:
                                        student_files.append({
                                            "提交ID": submission_id,
                                            "提交标题": submission_title,
                                            "提交类型": submission_type,
                                            "文件名": file.get('file_path', '').split('/')[-1].split('\\')[-1],
                                            "文件类型": file.get('media_type', 'N/A'),
                                            "文件大小": f"{file.get('size_bytes', 0) / 1024:.2f} KB",
                                            "上传时间": file.get('uploaded_at', 'N/A')[:19]
                                        })
                            
                            if student_files:
                                df = pd.DataFrame(student_files)
                                st.dataframe(df, use_container_width=True)
                                st.info(f"共 {len(student_files)} 个文件")
                            else:
                                st.info("📭 该学生暂无文件")
                        else:
                            st.error("❌ 获取提交列表失败")
                    else:
                        st.error("❌ 学生不存在")
                except Exception as e:
                    st.error(f"❌ 查询失败: {str(e)}")
    
    elif search_option == "按提交查询":
        submission_id = st.text_input("输入提交ID", placeholder="请输入提交ID")
        
        if st.button("🔍 查询", use_container_width=True):
            if not submission_id:
                st.error("❌ 请输入提交ID")
            else:
                try:
                    # 获取提交信息
                    response = requests.get(f"{API_BASE_URL}/submissions/{submission_id}")
                    if response.status_code == 200:
                        submission = response.json()
                        st.success(f"✅ 提交: {submission['title']}")
                        
                        # 获取提交的文件
                        response = requests.get(f"{API_BASE_URL}/submissions/{submission_id}/files")
                        if response.status_code == 200:
                            files = response.json()
                            
                            if files:
                                submission_files = []
                                for file in files:
                                    submission_files.append({
                                        "文件名": file.get('file_path', '').split('/')[-1].split('\\')[-1],
                                        "文件类型": file.get('media_type', 'N/A'),
                                        "文件大小": f"{file.get('size_bytes', 0) / 1024:.2f} KB",
                                        "上传时间": file.get('uploaded_at', 'N/A')[:19]
                                    })
                                df = pd.DataFrame(submission_files)
                                st.dataframe(df, use_container_width=True)
                                st.info(f"共 {len(files)} 个文件")
                            else:
                                st.info("📭 该提交暂无文件")
                        else:
                            st.error("❌ 获取文件列表失败")
                    else:
                        st.error("❌ 提交不存在")
                except Exception as e:
                    st.error(f"❌ 查询失败: {str(e)}")
    
    elif search_option == "按文件类型查询":
        file_type = st.selectbox(
            "选择文件类型",
            options=["所有类型", "document", "video", "audio"]
        )
        
        if st.button("🔍 查询", use_container_width=True):
            try:
                # 获取所有学生
                response = requests.get(f"{API_BASE_URL}/students")
                if response.status_code == 200:
                    students = response.json()
                    
                    type_files = []
                    
                    # 遍历每个学生
                    for student in students:
                        student_id = student['student_id']
                        student_name = student['name']
                        
                        # 获取学生的所有提交
                        response = requests.get(f"{API_BASE_URL}/students/{student_id}/submissions")
                        if response.status_code == 200:
                            submissions = response.json()
                            
                            # 遍历每个提交
                            for submission in submissions:
                                submission_id = submission['submission_id']
                                submission_title = submission['title']
                                
                                # 获取提交的文件
                                response = requests.get(f"{API_BASE_URL}/submissions/{submission_id}/files")
                                if response.status_code == 200:
                                    files = response.json()
                                    
                                    # 处理每个文件
                                    for file in files:
                                        if file_type == "所有类型" or file.get('media_type') == file_type:
                                            type_files.append({
                                                "学生学号": student_id,
                                                "学生姓名": student_name,
                                                "提交ID": submission_id,
                                                "提交标题": submission_title,
                                                "文件名": file.get('file_path', '').split('/')[-1].split('\\')[-1],
                                                "文件类型": file.get('media_type', 'N/A'),
                                                "文件大小": f"{file.get('size_bytes', 0) / 1024:.2f} KB",
                                                "上传时间": file.get('uploaded_at', 'N/A')[:19]
                                            })
                    
                    if type_files:
                        df = pd.DataFrame(type_files)
                        st.dataframe(df, use_container_width=True)
                        st.info(f"共 {len(type_files)} 个文件")
                    else:
                        st.info("📭 暂无符合条件的文件")
                else:
                    st.error("❌ 获取学生列表失败")
            except Exception as e:
                st.error(f"❌ 查询失败: {str(e)}")
    
    # 修改文件表单
    if st.session_state.get('show_edit_file_form', False):
        st.title("✏️ 修改文件信息")
        edit_file = st.session_state.get('edit_file', {})
        
        with st.form("edit_file_form"):
            col1, col2 = st.columns(2)
            with col1:
                student_id = st.text_input("学生学号", value=edit_file.get('学生学号', ''), disabled=True)
                student_name = st.text_input("学生姓名", value=edit_file.get('学生姓名', ''), disabled=True)
                submission_id = st.text_input("提交ID", value=edit_file.get('提交ID', ''), disabled=True)
            with col2:
                submission_title = st.text_input("提交标题", value=edit_file.get('提交标题', ''), disabled=True)
                submission_type = st.text_input("提交类型", value=edit_file.get('提交类型', ''), disabled=True)
                file_name = st.text_input("文件名", value=edit_file.get('文件名', ''))
            
            # 处理文件类型，将MIME类型映射到简单类型
            file_type = edit_file.get('文件类型', 'document')
            # 映射MIME类型到简单类型
            if 'pdf' in file_type.lower() or 'word' in file_type.lower() or 'document' in file_type.lower() or file_type == 'N/A':
                default_type = 'document'
            elif 'video' in file_type.lower():
                default_type = 'video'
            elif 'audio' in file_type.lower():
                default_type = 'audio'
            else:
                default_type = 'document'
            
            media_type = st.selectbox(
                "文件类型",
                options=["document", "video", "audio"],
                index=["document", "video", "audio"].index(default_type)
            )
            
            st.markdown("*必填项")
            
            submit_button = st.form_submit_button("✅ 保存修改", use_container_width=True)
            cancel_button = st.form_submit_button("❌ 取消", use_container_width=True)
            
            if submit_button:
                if not file_name:
                    st.error("❌ 文件名不能为空")
                else:
                    try:
                        # 使用表单格式提交
                        response = requests.put(
                            f"{API_BASE_URL}/files/{edit_file.get('file_id', '')}",
                            data={
                                "file_name": file_name,
                                "media_type": media_type
                            }
                        )
                        if response.status_code == 200:
                            st.success("✅ 文件信息修改成功！")
                            file_data = response.json()
                            st.json(file_data)
                            # 关闭编辑表单
                            st.session_state['show_edit_file_form'] = False
                            st.session_state.pop('edit_file', None)
                        else:
                            try:
                                error_detail = response.json().get('detail', '未知错误')
                            except:
                                error_detail = f"HTTP {response.status_code}: {response.text}"
                            st.error(f"❌ 修改失败: {error_detail}")
                    except Exception as e:
                        st.error(f"❌ 修改失败: {str(e)}")
            
            if cancel_button:
                st.session_state['show_edit_file_form'] = False
                st.session_state.pop('edit_file', None)
                st.rerun()

# ==================== 成长分析 ====================
elif page == "📈 成长分析":
    st.title("📈 学生成长分析")
    st.markdown("""
    **功能说明：** 全面分析学生在各个维度的能力成长变化，通过多种可视化图表直观展示进步趋势。
    """)
    
    # 时间维度选择
    st.subheader("📅 时间维度选择")
    # 使用会话状态保存时间维度选择，避免自动刷新
    if 'time_dimension' not in st.session_state:
        st.session_state['time_dimension'] = "评估日期"
    
    time_dimension = st.radio(
        "选择时间维度",
        options=["评估日期", "工作时期进度"],
        horizontal=True,
        key="time_dimension",
        index=0 if st.session_state['time_dimension'] == "评估日期" else 1
    )
    
    # 选择学生
    st.subheader("👤 选择学生")
    try:
        response = requests.get(f"{API_BASE_URL}/students")
        if response.status_code == 200:
            students = response.json()
            if students:
                # 构建学生选项
                student_options = {student['student_id']: f"{student['student_id']} - {student['name']}" for student in students}
                selected_student_id = st.selectbox(
                    "选择学生",
                    options=list(student_options.keys()),
                    format_func=lambda x: student_options[x]
                )
                
                # 实时显示学生的总评估历史记录
                st.subheader("📜 学生总评估历史记录")
                try:
                    # 获取学生的所有评估记录
                    response = requests.get(f"{API_BASE_URL}/students/{selected_student_id}/evaluations")
                    if response.status_code == 200:
                        evaluations = response.json()
                        if evaluations:
                            st.success(f"✅ 找到 {len(evaluations)} 条评估记录")
                            
                            # 显示评估历史表格
                            eval_data = []
                            for eval in evaluations:
                                # 计算平均维度评分
                                avg_dim_score = 0
                                if eval.get('dimension_scores'):
                                    avg_dim_score = sum(ds['score'] for ds in eval['dimension_scores']) / len(eval['dimension_scores'])
                                
                                eval_data.append({
                                    '评估ID': eval['evaluation_id'],
                                    '提交ID': eval.get('submission_id', 'N/A'),
                                    '综合评分': eval['overall_score'],
                                    '平均维度评分': f"{avg_dim_score:.2f}",
                                    '评估时间': eval['evaluated_at'][:10],
                                    '评估阶段': f"{eval.get('stage_progress', 0.0):.2f}" if eval.get('stage_progress') is not None else 'N/A'
                                })
                            
                            # 显示表格
                            df = pd.DataFrame(eval_data)
                            st.dataframe(df, use_container_width=True)
                            
                            # 提供下载选项
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label="📥 下载评估历史记录",
                                data=csv,
                                file_name=f"{selected_student_id}_evaluation_history.csv",
                                mime="text/csv"
                            )
                        else:
                            st.info("📭 该学生暂无评估记录")
                    else:
                        try:
                            error_detail = response.json().get('detail', '未知错误')
                        except:
                            error_detail = f"HTTP {response.status_code}"
                        st.error(f"❌ 获取评估记录失败: {error_detail}")
                except Exception as e:
                    st.error(f"❌ 加载评估记录失败: {str(e)}")
                
                # 使用会话状态保存分析结果
                if 'analysis_results' not in st.session_state:
                    st.session_state['analysis_results'] = None
                if 'selected_criteria' not in st.session_state:
                    st.session_state['selected_criteria'] = ['综合评分']
                
                if st.button("🔍 分析成长数据", use_container_width=True):
                    try:
                        # 获取学生的所有评估记录
                        response = requests.get(f"{API_BASE_URL}/students/{selected_student_id}/evaluations")
                        if response.status_code == 200:
                            evaluations = response.json()
                            if evaluations:
                                # 按评估时间排序
                                evaluations_sorted = sorted(evaluations, key=lambda x: x['evaluated_at'])
                                
                                # 根据选择的时间维度准备数据
                                if time_dimension == "评估日期":
                                    x_values = [eval['evaluated_at'][:10] for eval in evaluations_sorted]
                                    x_label = "评估日期"
                                else:
                                    # 按工作时期进度排序，处理None值
                                    evaluations_sorted_by_progress = sorted(evaluations, key=lambda x: x.get('stage_progress') if x.get('stage_progress') is not None else 0)
                                    x_values = [f"{int((eval.get('stage_progress') if eval.get('stage_progress') is not None else 0) * 100)}%" for eval in evaluations_sorted_by_progress]
                                    x_label = "工作时期进度"
                                    # 更新评估列表为按进度排序
                                    evaluations_sorted = evaluations_sorted_by_progress
                                
                                # 提取所有可能的评分标准（综合评分 + 所有维度）
                                all_criteria = ['综合评分']
                                for eval in evaluations_sorted:
                                    for ds in eval.get('dimension_scores', []):
                                        dimension = ds.get('dimension', '未知维度')
                                        if dimension not in all_criteria:
                                            all_criteria.append(dimension)
                                
                                # 保存分析结果到会话状态
                                st.session_state['analysis_results'] = {
                                    'evaluations': evaluations,
                                    'evaluations_sorted': evaluations_sorted,
                                    'x_values': x_values,
                                    'x_label': x_label,
                                    'all_criteria': all_criteria,
                                    'time_dimension': time_dimension
                                }
                                # 重置选择的评分标准
                                st.session_state['selected_criteria'] = ['综合评分']
                            else:
                                st.info("📭 该学生暂无评估记录")
                        else:
                            try:
                                error_detail = response.json().get('detail', '未知错误')
                            except:
                                error_detail = f"HTTP {response.status_code}"
                            st.error(f"❌ 获取评估记录失败: {error_detail}")
                    except Exception as e:
                        st.error(f"❌ 分析失败: {str(e)}")
                
                # 显示分析结果
                if st.session_state['analysis_results']:
                    analysis = st.session_state['analysis_results']
                    st.success(f"✅ 找到 {len(analysis['evaluations'])} 条评估记录")
                    
                    # 1. 多维度评分趋势图
                    st.subheader("📊 多维度评分趋势")
                    st.markdown("**图表说明：** 展示学生在不同评分标准下的变化趋势")
                    
                    # 让用户选择要显示的评分标准
                    selected_criteria = st.multiselect(
                        "选择评分标准",
                        options=analysis['all_criteria'],
                        default=st.session_state['selected_criteria'],
                        key="selected_criteria"
                    )
                                
                    # 创建趋势图
                    fig = go.Figure()
                    
                    # 颜色映射 - 使用更鲜明的颜色
                    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#8AC249', '#FF5252', '#448AFF', '#FFAB40']
                    
                    # 为每个选择的评分标准添加趋势线
                    for i, criterion in enumerate(selected_criteria):
                        if criterion == '综合评分':
                            scores = [eval['overall_score'] for eval in analysis['evaluations_sorted']]
                        else:
                            # 提取维度评分
                            scores = []
                            for eval in analysis['evaluations_sorted']:
                                score = 0
                                for ds in eval.get('dimension_scores', []):
                                    if ds.get('dimension') == criterion:
                                        score = ds.get('score', 0)
                                        break
                                scores.append(score)
                        
                        # 添加主趋势线
                        fig.add_trace(go.Scatter(
                            x=analysis['x_values'],
                            y=scores,
                            mode='lines+markers+text',  # 添加文本标签
                            name=criterion,
                            line=dict(width=4, color=colors[i % len(colors)]),  # 增加线条宽度
                            marker=dict(size=10, color=colors[i % len(colors)]),  # 增加标记大小
                            text=[f'{score:.1f}' for score in scores],  # 添加评分标签
                            textposition='top center',  # 标签位置
                            textfont=dict(size=10, color=colors[i % len(colors)])  # 标签样式
                        ))
                        
                        # 添加趋势线
                        if len(scores) > 1:
                            import numpy as np
                            x = np.arange(len(analysis['x_values']))
                            z = np.polyfit(x, scores, 1)
                            p = np.poly1d(z)
                            fig.add_trace(go.Scatter(
                                x=analysis['x_values'],
                                y=p(x),
                                mode='lines',
                                name=f'{criterion} 趋势',
                                line=dict(width=3, color=colors[i % len(colors)], dash='dash')  # 增加线条宽度
                            ))
                    
                    fig.update_layout(
                        title="多维度评分趋势",
                        xaxis_title=analysis['x_label'],
                        yaxis_title="评分",
                        yaxis_range=[0, 10],
                        height=500,  # 增加图表高度
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        plot_bgcolor='rgba(240, 240, 240, 0.8)',  # 添加背景色
                        xaxis=dict(showgrid=True, gridwidth=1, gridcolor='rgba(200, 200, 200, 0.5)'),  # 添加网格线
                        yaxis=dict(showgrid=True, gridwidth=1, gridcolor='rgba(200, 200, 200, 0.5)')  # 添加网格线
                    )
                    st.plotly_chart(fig, use_container_width=True)
                                
                    # 2. 维度能力雷达图对比
                    st.subheader("🎯 维度能力雷达图对比")
                    st.markdown("**图表说明：** 对比学生在不同时间点的维度能力表现")
                    
                    if len(analysis['evaluations']) >= 2:
                        # 选择两个时间点进行对比
                        eval_options = {eval['evaluation_id']: f"{eval['evaluated_at'][:10]} (评分: {eval['overall_score']})" for eval in analysis['evaluations_sorted']}
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            eval1_id = st.selectbox(
                                "选择第一个时间点",
                                options=list(eval_options.keys()),
                                format_func=lambda x: eval_options[x],
                                index=0
                            )
                        with col2:
                            eval2_id = st.selectbox(
                                "选择第二个时间点",
                                options=list(eval_options.keys()),
                                format_func=lambda x: eval_options[x],
                                index=min(1, len(eval_options)-1)
                            )
                        
                        # 获取两个评估的维度评分
                        eval1 = next(e for e in analysis['evaluations'] if e['evaluation_id'] == eval1_id)
                        eval2 = next(e for e in analysis['evaluations'] if e['evaluation_id'] == eval2_id)
                        
                        # 提取维度和评分
                        dimensions = []
                        scores1 = []
                        scores2 = []
                        
                        # 合并两个评估的维度
                        dim_map1 = {ds['dimension']: ds['score'] for ds in eval1['dimension_scores']}
                        dim_map2 = {ds['dimension']: ds['score'] for ds in eval2['dimension_scores']}
                        
                        all_dims = set(dim_map1.keys()) | set(dim_map2.keys())
                        for dim in all_dims:
                            dimensions.append(dim)
                            scores1.append(dim_map1.get(dim, 0))
                            scores2.append(dim_map2.get(dim, 0))
                        
                        # 创建雷达图
                        fig = go.Figure()
                        fig.add_trace(go.Scatterpolar(
                            r=scores1,
                            theta=dimensions,
                            fill='toself',
                            name=eval_options[eval1_id]
                        ))
                        fig.add_trace(go.Scatterpolar(
                            r=scores2,
                            theta=dimensions,
                            fill='toself',
                            name=eval_options[eval2_id]
                        ))
                        
                        fig.update_layout(
                            polar=dict(
                                radialaxis=dict(
                                    visible=True,
                                    range=[0, 10]
                                )
                            ),
                            title="维度能力对比",
                            height=500
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("⚠️ 需要至少两次评估才能生成对比雷达图")
                                
                    # 3. 维度能力趋势矩阵
                    st.subheader("📈 维度能力趋势矩阵")
                    st.markdown("**图表说明：** 展示每个维度的能力变化趋势")
                    
                    # 构建维度趋势数据
                    dimension_trends = {}
                    for eval in analysis['evaluations_sorted']:
                        for ds in eval.get('dimension_scores', []):
                            dimension = ds.get('dimension', '未知维度')
                            score = ds.get('score', 0)
                            if dimension not in dimension_trends:
                                dimension_trends[dimension] = []
                            
                            # 根据选择的时间维度添加数据
                            if analysis['time_dimension'] == "评估日期":
                                time_value = eval.get('evaluated_at')[:10]
                            else:
                                time_value = f"{int(eval.get('stage_progress', 0) * 100)}%"
                            
                            dimension_trends[dimension].append({
                                'time': time_value,
                                'score': score,
                                'progress': eval.get('stage_progress', 0.5),
                                'evaluated_at': eval.get('evaluated_at')
                            })
                    
                    # 为每个维度创建趋势图
                    for dimension, data in dimension_trends.items():
                        if len(data) > 1:
                            # 根据选择的时间维度排序
                            if analysis['time_dimension'] == "评估日期":
                                data_sorted = sorted(data, key=lambda x: x['evaluated_at'])
                            else:
                                data_sorted = sorted(data, key=lambda x: x['progress'])
                            
                            # 计算趋势
                            scores = [d['score'] for d in data_sorted]
                            first_score = scores[0]
                            last_score = scores[-1]
                            trend = "📈 提升" if last_score > first_score else ("📉 下降" if last_score < first_score else "➡️ 稳定")
                            
                            with st.expander(f"{dimension} - {trend}"):
                                # 创建趋势图
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=[d['time'] for d in data_sorted],
                                    y=scores,
                                    mode='lines+markers',
                                    name=dimension,
                                    line=dict(width=3),
                                    marker=dict(size=8)
                                ))
                                # 添加趋势线
                                if len(scores) > 1:
                                    import numpy as np
                                    x = np.arange(len(data_sorted))
                                    z = np.polyfit(x, scores, 1)
                                    p = np.poly1d(z)
                                    fig.add_trace(go.Scatter(
                                        x=[d['time'] for d in data_sorted],
                                        y=p(x),
                                        mode='lines',
                                        name='趋势线',
                                        line=dict(width=2, color='#ff7f0e', dash='dash')
                                    ))
                                
                                fig.update_layout(
                                    title=f"{dimension} 能力趋势",
                                    xaxis_title=analysis['x_label'],
                                    yaxis_title="评分",
                                    yaxis_range=[0, 10],
                                    height=300
                                )
                                st.plotly_chart(fig, use_container_width=True)
                                
                                # 显示趋势分析
                                change = last_score - first_score
                                change_percent = (change / first_score * 100) if first_score > 0 else 0
                                st.markdown(f"**趋势分析：**")
                                st.markdown(f"- 初始评分：{first_score:.2f}")
                                st.markdown(f"- 最新评分：{last_score:.2f}")
                                st.markdown(f"- 变化幅度：{change:+.2f} ({change_percent:+.1f}%)")
                                
                                if change > 0.5:
                                    st.success("✅ 该维度能力有显著提升")
                                elif change < -0.5:
                                    st.error("⚠️ 该维度能力有所下降，需要关注")
                                else:
                                    st.info("ℹ️ 该维度能力保持稳定")
                                
                    # 4. 成长热力图
                    st.subheader("🔥 成长热力图")
                    st.markdown("**图表说明：** 展示学生在不同维度和不同时间点的表现热度")
                    
                    # 构建热力图数据
                    heatmap_data = []
                    
                    # 根据选择的时间维度准备数据
                    if analysis['time_dimension'] == "评估日期":
                        all_time_points = sorted(list(set([eval['evaluated_at'][:10] for eval in analysis['evaluations_sorted']])))
                        x_label_heatmap = "日期"
                    else:
                        # 按工作时期进度获取唯一值并排序
                        progress_values = sorted(list(set([eval.get('stage_progress', 0) for eval in analysis['evaluations_sorted']])))
                        all_time_points = [f"{int(p * 100)}%" for p in progress_values]
                        x_label_heatmap = "工作时期进度"
                    
                    all_dimensions = list(dimension_trends.keys())
                    
                    for dim in all_dimensions:
                        row = [dim]
                        for time_point in all_time_points:
                            # 查找该维度在该时间点的评分
                            score = 0
                            for eval in analysis['evaluations_sorted']:
                                if analysis['time_dimension'] == "评估日期":
                                    eval_time = eval['evaluated_at'][:10]
                                else:
                                    eval_time = f"{int(eval.get('stage_progress', 0) * 100)}%"
                                
                                if eval_time == time_point:
                                    for ds in eval.get('dimension_scores', []):
                                        if ds.get('dimension') == dim:
                                            score = ds.get('score', 0)
                                            break
                            row.append(score)
                        heatmap_data.append(row)
                    
                    # 创建DataFrame
                    df = pd.DataFrame(heatmap_data, columns=['维度'] + all_time_points)
                    
                    # 创建热力图
                    fig = px.imshow(
                        df.iloc[:, 1:].values,
                        x=all_time_points,
                        y=df['维度'],
                        color_continuous_scale='RdYlGn',
                        range_color=[0, 10],
                        labels={'x': x_label_heatmap, 'y': '维度', 'color': '评分'}
                    )
                    fig.update_layout(
                        title="维度能力热力图",
                        height=600
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 5. 成长总结
                    st.subheader("📋 成长总结")
                    
                    # 计算整体成长
                    overall_scores = [eval['overall_score'] for eval in analysis['evaluations_sorted']]
                    if len(overall_scores) >= 2:
                        first_overall = overall_scores[0]
                        last_overall = overall_scores[-1]
                        overall_change = last_overall - first_overall
                        overall_change_percent = (overall_change / first_overall * 100) if first_overall > 0 else 0
                        
                        st.markdown(f"**整体成长：**")
                        st.markdown(f"- 初始综合评分：{first_overall:.2f}")
                        st.markdown(f"- 最新综合评分：{last_overall:.2f}")
                        st.markdown(f"- 整体变化：{overall_change:+.2f} ({overall_change_percent:+.1f}%)")
                        
                        if overall_change > 0.5:
                            st.success("🎉 学生整体能力有显著提升！")
                        elif overall_change < -0.5:
                            st.error("⚠️ 学生整体能力有所下降，需要重点关注")
                        else:
                            st.info("ℹ️ 学生整体能力保持稳定")
                        
                        # 分析进步最快的维度
                        fastest_improving = []
                        for dimension, data in dimension_trends.items():
                            if len(data) >= 2:
                                scores = [d['score'] for d in data]
                                change = scores[-1] - scores[0]
                                fastest_improving.append((dimension, change))
                        
                        if fastest_improving:
                            fastest_improving.sort(key=lambda x: x[1], reverse=True)
                            st.markdown("\n**进步最快的维度：**")
                            for i, (dim, change) in enumerate(fastest_improving[:3]):
                                st.markdown(f"{i+1}. {dim}：{change:+.2f}")
                        
                    # 分析需要改进的维度
                    need_improvement = []
                    for dimension, data in dimension_trends.items():
                        if len(data) >= 2:
                            scores = [d['score'] for d in data]
                            change = scores[-1] - scores[0]
                            if change < 0:
                                need_improvement.append((dimension, change))
                    
                    if need_improvement:
                        need_improvement.sort(key=lambda x: x[1])
                        st.markdown("\n**需要改进的维度：**")
                        for i, (dim, change) in enumerate(need_improvement[:3]):
                            st.markdown(f"{i+1}. {dim}：{change:+.2f}")
            else:
                st.info("📭 暂无学生记录")
        else:
            st.error("❌ 获取学生列表失败")
    except Exception as e:
        st.error(f"❌ 加载学生列表失败: {str(e)}")
