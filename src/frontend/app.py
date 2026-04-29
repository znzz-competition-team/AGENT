import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
import os
import time
import random
import statistics
from PIL import Image, ImageDraw

# API 基础 URL
API_BASE_URL = "http://localhost:8000"

# 初始化 session state
if 'ai_settings' not in st.session_state:
    st.session_state.ai_settings = {}

# 支持的 AI 提供商配置
AI_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default_model": "gpt-4o",
        "description": "OpenAI 官方 API，支持 GPT-4 系列模型"
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
        "description": "DeepSeek 大模型，性价比高"
    },
    "zhipu": {
        "name": "智谱 AI (GLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4", "glm-4-plus", "glm-4-flash", "glm-4v"],
        "default_model": "glm-4",
        "description": "智谱 AI GLM 系列模型"
    },
    "moonshot": {
        "name": "Moonshot (月之暗面)",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "default_model": "moonshot-v1-8k",
        "description": "Moonshot Kimi 大模型"
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            "qwen3.6-plus", "qwen3.5-plus", "qwen3-vl-plus", "qwen3-vl-flash",
            "qwen-vl-ocr-latest", "qwen-turbo", "qwen-plus", "qwen-max", "qvq-max"
        ],
        "default_model": "qwen3.6-plus",
        "description": "阿里云通义千问系列"
    },
    "custom": {
        "name": "自定义 OpenAI 兼容 API",
        "base_url": "",
        "models": [],
        "default_model": "",
        "description": "支持任何 OpenAI 兼容格式的 API"
    }
}

# 辅助函数：处理reasoning字段，移除代码格式，返回纯文本
def process_reasoning(reasoning: str) -> str:
    """处理reasoning字段，移除代码格式，返回纯文本"""
    if not reasoning:
        return ""
    # 移除JSON代码块
    if '```json' in reasoning:
        reasoning = reasoning.replace('```json', '').replace('```', '').strip()
    # 移除JSON格式标记
    if reasoning.strip().startswith('{') and reasoning.strip().endswith('}'):
        try:
            import json
            # 尝试解析JSON并提取reasoning字段
            parsed = json.loads(reasoning)
            if 'reasoning' in parsed:
                reasoning = parsed['reasoning']
        except:
            pass
    return reasoning


def _safe_float(value, default=None):
    """将输入安全转换为 float。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_ocr_box_item(item) -> dict:
    """解析单条 OCR 框记录，兼容多种字段格式。"""
    if not isinstance(item, dict):
        return {}

    x = _safe_float(item.get("x", item.get("left")))
    y = _safe_float(item.get("y", item.get("top")))
    w = _safe_float(item.get("w", item.get("width")))
    h = _safe_float(item.get("h", item.get("height")))

    # 支持 x1,y1,x2,y2 形式
    if (w is None or h is None) and all(
        key in item for key in ("x1", "y1", "x2", "y2")
    ):
        x1 = _safe_float(item.get("x1"))
        y1 = _safe_float(item.get("y1"))
        x2 = _safe_float(item.get("x2"))
        y2 = _safe_float(item.get("y2"))
        if None not in (x1, y1, x2, y2):
            x, y = x1, y1
            w, h = x2 - x1, y2 - y1

    confidence = _safe_float(
        item.get("confidence", item.get("score", item.get("prob")))
    )
    if confidence is not None and confidence <= 1:
        confidence *= 100

    text = str(
        item.get("text", item.get("words", item.get("content", ""))) or ""
    ).strip()

    if None in (x, y, w, h) or w <= 0 or h <= 0:
        return {}

    return {
        "x": int(round(x)),
        "y": int(round(y)),
        "w": int(round(w)),
        "h": int(round(h)),
        "confidence": confidence if confidence is not None else 0.0,
        "text": text,
    }


def parse_ocr_boxes(recognized_text: str, ocr_boxes=None) -> pd.DataFrame:
    """解析 OCR 框：支持后端结构化字段、JSON 文本和 CSV 行文本。"""
    records = []

    if isinstance(ocr_boxes, list):
        for item in ocr_boxes:
            parsed = _parse_ocr_box_item(item)
            if parsed:
                records.append(parsed)

    if not records and recognized_text:
        try:
            maybe_json = json.loads(recognized_text)
            if isinstance(maybe_json, list):
                for item in maybe_json:
                    parsed = _parse_ocr_box_item(item)
                    if parsed:
                        records.append(parsed)
            elif isinstance(maybe_json, dict):
                for key in ("ocr_boxes", "boxes", "lines"):
                    if isinstance(maybe_json.get(key), list):
                        for item in maybe_json[key]:
                            parsed = _parse_ocr_box_item(item)
                            if parsed:
                                records.append(parsed)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    if not records and recognized_text:
        for line in recognized_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(",", 5)
            if len(parts) != 6:
                continue
            x = _safe_float(parts[0].strip())
            y = _safe_float(parts[1].strip())
            w = _safe_float(parts[2].strip())
            h = _safe_float(parts[3].strip())
            confidence = _safe_float(parts[4].strip(), 0.0)
            text = parts[5].strip()
            if None in (x, y, w, h) or w <= 0 or h <= 0:
                continue
            records.append(
                {
                    "x": int(round(x)),
                    "y": int(round(y)),
                    "w": int(round(w)),
                    "h": int(round(h)),
                    "confidence": float(confidence),
                    "text": text,
                }
            )

    if not records:
        return pd.DataFrame()

    ocr_df = pd.DataFrame(records)
    ocr_df["confidence"] = pd.to_numeric(ocr_df["confidence"], errors="coerce").fillna(0.0)
    ocr_df["confidence"] = ocr_df["confidence"].clip(lower=0.0, upper=100.0)
    ocr_df["text"] = ocr_df["text"].fillna("").astype(str)
    return ocr_df.sort_values(by="confidence", ascending=False).reset_index(drop=True)


def draw_ocr_boxes(image_file, ocr_df: pd.DataFrame, min_confidence: float = 0.0):
    """在图片上绘制 OCR 框。"""
    image = Image.open(image_file).convert("RGB")
    draw = ImageDraw.Draw(image)
    line_width = max(2, int(min(image.size) * 0.004))
    img_w, img_h = image.size

    if ocr_df.empty:
        return image

    for _, row in ocr_df.iterrows():
        confidence = _safe_float(row.get("confidence"), 0.0)
        if confidence < float(min_confidence):
            continue

        x1, y1 = int(row["x"]), int(row["y"])
        x2, y2 = x1 + int(row["w"]), y1 + int(row["h"])
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img_w - 1, x2), min(img_h - 1, y2)
        if x2 <= x1 or y2 <= y1:
            continue

        color = "#2ca02c" if confidence >= 90 else "#ff7f0e" if confidence >= 75 else "#d62728"
        draw.rectangle([x1, y1, x2, y2], outline=color, width=line_width)
        label = f"{str(row['text'])[:18]} {confidence:.1f}%".strip()
        draw.text((x1, max(0, y1 - 16)), label, fill=color)

    return image


def summarize_ocr_quality(ocr_df: pd.DataFrame) -> dict:
    """汇总 OCR 质量指标。"""
    if ocr_df.empty:
        return {"total": 0, "high_conf": 0, "avg_conf": 0.0}

    confidence_series = pd.to_numeric(ocr_df["confidence"], errors="coerce").fillna(0.0)
    return {
        "total": int(len(ocr_df)),
        "high_conf": int((confidence_series >= 90).sum()),
        "avg_conf": float(confidence_series.mean()),
    }


def parse_formula_boxes(formula_boxes) -> pd.DataFrame:
    """解析后端返回的公式框列表。"""
    if not formula_boxes or not isinstance(formula_boxes, list):
        return pd.DataFrame()

    records = []
    for item in formula_boxes:
        if not isinstance(item, dict):
            continue
        try:
            page_index = int(item.get("page_index", 1) or 1)
            x = float(item.get("x", 0.0) or 0.0)
            y = float(item.get("y", 0.0) or 0.0)
            w = float(item.get("w", 0.0) or 0.0)
            h = float(item.get("h", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue

        if w <= 0 or h <= 0:
            continue

        confidence = item.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = None

        records.append(
            {
                "page_index": page_index,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "confidence": confidence,
                "text": str(item.get("text", "") or ""),
                "latex": str(item.get("latex", "") or ""),
                "box_type": str(item.get("box_type", "formula") or "formula"),
            }
        )

    return pd.DataFrame(records)


def draw_formula_boxes(image_file, formula_df: pd.DataFrame):
    """将相对坐标公式框叠加到原图。"""
    image = Image.open(image_file).convert("RGB")
    draw = ImageDraw.Draw(image)
    img_w, img_h = image.size

    for _, row in formula_df.iterrows():
        x1 = int(max(0, min(1, float(row["x"]))) * img_w)
        y1 = int(max(0, min(1, float(row["y"]))) * img_h)
        x2 = int(max(0, min(1, float(row["x"] + row["w"]))) * img_w)
        y2 = int(max(0, min(1, float(row["y"] + row["h"]))) * img_h)
        confidence = row.get("confidence")
        if confidence is None:
            color = "#1f77b4"
        else:
            confidence = float(confidence)
            color = "#2ca02c" if confidence >= 0.9 else "#ff7f0e" if confidence >= 0.75 else "#d62728"
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label = str(row.get("latex") or row.get("text") or "formula")
        draw.text((x1, max(0, y1 - 16)), label[:28], fill=color)

    return image


def _extract_message_text(resp_json: dict) -> str:
    choices = (resp_json or {}).get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join([p for p in parts if p])
    return str(content)


def dashscope_call_with_retry(payload: dict, api_key: str, timeout: int = 180, max_retries: int = 2) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    last_error = None

    for attempt in range(max_retries + 1):
        t0 = time.perf_counter()
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            latency = time.perf_counter() - t0
            if response.status_code == 200:
                body = response.json()
                return {
                    "ok": True,
                    "latency": latency,
                    "status_code": 200,
                    "text": _extract_message_text(body),
                    "usage": body.get("usage", {}),
                    "raw": body,
                    "error": "",
                }
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
        except Exception as exc:
            latency = time.perf_counter() - t0
            last_error = f"{type(exc).__name__}: {exc}"

        if attempt < max_retries:
            sleep_s = min(6.0, (2 ** attempt) + random.uniform(0.1, 0.8))
            time.sleep(sleep_s)

    return {
        "ok": False,
        "latency": latency if "latency" in locals() else 0.0,
        "status_code": None,
        "text": "",
        "usage": {},
        "raw": {},
        "error": last_error or "unknown error",
    }


def summarize_stability_results(run_results: list) -> dict:
    total = len(run_results)
    success = sum(1 for item in run_results if item.get("ok"))
    latencies = [item.get("latency", 0.0) for item in run_results if item.get("latency") is not None]
    avg_latency = float(sum(latencies) / len(latencies)) if latencies else 0.0
    p95_latency = float(statistics.quantiles(latencies, n=20)[18]) if len(latencies) >= 20 else (max(latencies) if latencies else 0.0)
    return {
        "total": total,
        "success": success,
        "fail": total - success,
        "success_rate": (success / total * 100.0) if total > 0 else 0.0,
        "avg_latency_s": avg_latency,
        "p95_latency_s": p95_latency,
    }

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

# 系统状态检查
try:
    response = requests.get(f"{API_BASE_URL}/health", timeout=5)
    if response.status_code == 200:
        st.sidebar.success("🟢 系统运行正常")
        st.session_state.system_status = "running"
    else:
        st.sidebar.error("🔴 系统服务异常")
        st.session_state.system_status = "error"
except Exception as e:
    st.sidebar.error(f"🔴 无法连接到系统服务")
    st.session_state.system_status = "offline"

st.sidebar.markdown("---")

# 导航菜单 - 使用按钮而不是下拉框
st.sidebar.markdown("### 📋 功能导航")

# 定义页面列表
pages = [
    ("🏠", "系统首页"),
    ("👥", "学生管理"),
    ("📁", "文件上传"),
    ("📂", "文件管理"),
    ("✏️", "手写识别"),
    ("🤖", "评估管理"),
    ("📊", "结果查询"),
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

# ==================== 学生管理 ====================
elif page == "👥 学生管理":
    st.title("👥 学生管理")
    
    # 选项卡
    tab1, tab2, tab3 = st.tabs(["➕ 添加学生", "🔍 查询学生", "📋 学生列表"])
    
    # 添加学生
    with tab1:
        st.subheader("添加新学生")
        with st.form("add_student_form"):
            col1, col2 = st.columns(2)
            with col1:
                student_id = st.text_input("学号*", placeholder="请输入学号")
                name = st.text_input("姓名*", placeholder="请输入姓名")
                age = st.number_input("年龄", min_value=0, max_value=100, value=0)
            with col2:
                grade = st.text_input("年级", placeholder="如：大一、大二")
                major = st.text_input("专业", placeholder="如：计算机科学")
            
            st.markdown("*必填项")
            
            submit_button = st.form_submit_button("✅ 添加学生", use_container_width=True)
            
            if submit_button:
                if not student_id or not name:
                    st.error("❌ 学号和姓名不能为空")
                else:
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/students",
                            json={
                                "student_id": student_id,
                                "name": name,
                                "age": age if age > 0 else None,
                                "grade": grade if grade else None,
                                "major": major if major else None
                            }
                        )
                        if response.status_code == 200:
                            st.success("✅ 学生添加成功！")
                            student_data = response.json()
                            st.json(student_data)
                        else:
                            try:
                                error_detail = response.json().get('detail', '未知错误')
                            except:
                                error_detail = f"HTTP {response.status_code}: {response.text}"
                            st.error(f"❌ 添加失败: {error_detail}")
                    except Exception as e:
                        st.error(f"❌ 添加失败: {str(e)}")
    
    # 查询学生
    with tab2:
        st.subheader("查询学生信息")
        
        search_col1, search_col2 = st.columns([3, 1])
        with search_col1:
            student_id = st.text_input("输入学号", placeholder="请输入学号进行查询")
        with search_col2:
            st.write("")
            st.write("")
            search_button = st.button("🔍 查询", use_container_width=True)
        
        if search_button:
            if not student_id:
                st.error("❌ 请输入学号")
            else:
                try:
                    response = requests.get(f"{API_BASE_URL}/students/{student_id}")
                    if response.status_code == 200:
                        student = response.json()
                        
                        # 显示学生信息卡片
                        st.success("✅ 查询成功")
                        
                        info_col1, info_col2 = st.columns(2)
                        with info_col1:
                            st.markdown(f"**学号:** {student.get('student_id', 'N/A')}")
                            st.markdown(f"**姓名:** {student.get('name', 'N/A')}")
                            st.markdown(f"**年龄:** {student.get('age', 'N/A')}")
                        with info_col2:
                            st.markdown(f"**年级:** {student.get('grade', 'N/A')}")
                            st.markdown(f"**专业:** {student.get('major', 'N/A')}")
                            st.markdown(f"**创建时间:** {student.get('created_at', 'N/A')}")
                        
                        # 显示完整JSON
                        with st.expander("查看完整数据"):
                            st.json(student)
                    else:
                        try:
                            error_detail = response.json().get('detail', '未知错误')
                        except:
                            error_detail = f"HTTP {response.status_code}"
                        st.error(f"❌ 查询失败: {error_detail}")
                except Exception as e:
                    st.error(f"❌ 查询失败: {str(e)}")
    
    # 学生列表
    with tab3:
        st.subheader("学生列表")
        
        # 默认显示所有学生
        try:
            response = requests.get(f"{API_BASE_URL}/students")
            if response.status_code == 200:
                students = response.json()
                if students:
                    st.info(f"共 {len(students)} 名学生")
                    
                    # 显示表头
                    header_cols = st.columns([1, 1, 0.5, 1, 1, 0.5, 0.5])
                    with header_cols[0]:
                        st.markdown("**学号**")
                    with header_cols[1]:
                        st.markdown("**姓名**")
                    with header_cols[2]:
                        st.markdown("**年龄**")
                    with header_cols[3]:
                        st.markdown("**年级**")
                    with header_cols[4]:
                        st.markdown("**专业**")
                    with header_cols[5]:
                        st.markdown("**修改**")
                    with header_cols[6]:
                        st.markdown("**删除**")
                    
                    # 表头分隔线
                    st.divider()
                    
                    # 为每个学生显示一行，包含信息和操作按钮
                    for i, student in enumerate(students):
                        cols = st.columns([1, 1, 0.5, 1, 1, 0.5, 0.5])
                        
                        with cols[0]:
                            st.write(student['student_id'])
                        with cols[1]:
                            st.write(student['name'])
                        with cols[2]:
                            st.write(student.get('age', 'N/A'))
                        with cols[3]:
                            st.write(student.get('grade', 'N/A'))
                        with cols[4]:
                            st.write(student.get('major', 'N/A'))
                        with cols[5]:
                            # 修改按钮
                            if st.button(f"✏️", key=f"edit_{student['student_id']}", help="修改学生信息"):
                                # 存储当前编辑的学生信息
                                st.session_state['edit_student'] = student
                                # 切换到修改学生表单
                                st.session_state['show_edit_form'] = True
                        with cols[6]:
                            # 删除按钮
                            if st.button(f"🗑️", key=f"delete_{student['student_id']}", help="删除学生"):
                                # 直接执行删除操作
                                try:
                                    delete_response = requests.delete(f"{API_BASE_URL}/students/{student['student_id']}")
                                    if delete_response.status_code == 200:
                                        st.success(f"✅ 学生 {student['name']} 删除成功！")
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
                        
                        # 在每个学生行之间添加分隔线（除了最后一行）
                        if i < len(students) - 1:
                            st.divider()
                else:
                    st.info("📭 暂无学生信息")
            else:
                try:
                    error_detail = response.json().get('detail', '未知错误')
                except:
                    error_detail = f"HTTP {response.status_code}"
                st.error(f"❌ 获取列表失败: {error_detail}")
        except Exception as e:
            st.error(f"❌ 获取列表失败: {str(e)}")
        
        # 刷新按钮
        if st.button("🔄 刷新列表", use_container_width=True):
            st.rerun()
    
    # 修改学生表单
    if st.session_state.get('show_edit_form', False):
        st.title("✏️ 修改学生信息")
        edit_student = st.session_state.get('edit_student', {})
        
        with st.form("edit_student_form"):
            col1, col2 = st.columns(2)
            with col1:
                student_id = st.text_input("学号*", value=edit_student.get('student_id', ''), disabled=True)
                name = st.text_input("姓名*", value=edit_student.get('name', ''))
                age = st.number_input("年龄", min_value=0, max_value=100, value=edit_student.get('age', 0))
            with col2:
                grade = st.text_input("年级", value=edit_student.get('grade', ''))
                major = st.text_input("专业", value=edit_student.get('major', ''))
            
            st.markdown("*必填项")
            
            submit_button = st.form_submit_button("✅ 保存修改", use_container_width=True)
            cancel_button = st.form_submit_button("❌ 取消", use_container_width=True)
            
            if submit_button:
                if not name:
                    st.error("❌ 姓名不能为空")
                else:
                    try:
                        response = requests.put(
                            f"{API_BASE_URL}/students/{student_id}",
                            json={
                                "name": name,
                                "age": age if age > 0 else None,
                                "grade": grade if grade else None,
                                "major": major if major else None
                            }
                        )
                        if response.status_code == 200:
                            st.success("✅ 学生信息修改成功！")
                            student_data = response.json()
                            st.json(student_data)
                            # 关闭编辑表单
                            st.session_state['show_edit_form'] = False
                            st.session_state.pop('edit_student', None)
                        else:
                            try:
                                error_detail = response.json().get('detail', '未知错误')
                            except:
                                error_detail = f"HTTP {response.status_code}: {response.text}"
                            st.error(f"❌ 修改失败: {error_detail}")
                    except Exception as e:
                        st.error(f"❌ 修改失败: {str(e)}")
            
            if cancel_button:
                st.session_state['show_edit_form'] = False
                st.session_state.pop('edit_student', None)
                st.rerun()

# ==================== 文件上传 ====================
elif page == "📁 文件上传":
    st.title("📁 作业提交")
    
    # 步骤指示器
    st.markdown("""
    **提交流程：** 选择提交类型 → 创建提交 → 上传内容 → 关联人员（可选）
    """)
    
    # 步骤 1: 选择提交类型并创建提交
    st.subheader("步骤 1: 创建提交")
    
    # 提交类型选择
    submission_type = st.radio(
        "选择提交类型",
        options=["file", "text"],
        format_func=lambda x: "📁 文件提交" if x == "file" else "📝 文字提交",
        horizontal=True,
        key="submission_type"
    )
    
    with st.form("create_submission_form"):
        title = st.text_input("提交标题*", placeholder="请输入提交标题")
        
        # 根据提交类型显示不同输入
        text_content = None
        uploaded_files = None
        
        if submission_type == "text":
            st.markdown("---")
            st.subheader("📝 文字内容")
            text_content = st.text_area(
                "输入文字内容*",
                placeholder="请输入要提交的文字内容...",
                height=300,
                help="直接输入文字内容进行提交，无需上传文件"
            )
        else:
            st.markdown("---")
            st.subheader("📁 上传文件")
            st.markdown("""
            **支持的文件类型：**
            - 📄 文档：PDF, DOCX, TXT
            - 🎬 视频：MP4, MOV
            - 🎵 音频：MP3, WAV
            - 📊 PPT：PPTX, PPT
            """)
            uploaded_files = st.file_uploader(
                "选择文件上传*",
                accept_multiple_files=True,
                type=["pdf", "docx", "txt", "mp4", "mov", "mp3", "wav", "pptx", "ppt"],
                help="可以上传多个文件"
            )
        
        # 关联人员（必填）
        st.markdown("---")
        st.subheader("👤 关联人员*")
        st.write("选择此提交关联的学生")
        person_id = None
        
        # 获取所有学生
        try:
            response = requests.get(f"{API_BASE_URL}/students")
            if response.status_code == 200:
                students = response.json()
                if students:
                    # 构建学生选项
                    student_options = {student['student_id']: f"{student['student_id']} - {student['name']}" for student in students}
                    person_id = st.selectbox(
                        "选择学生",
                        options=list(student_options.keys()),
                        format_func=lambda x: student_options[x],
                        placeholder="请选择学生"
                    )
                else:
                    st.error("❌ 暂无学生记录，请先添加学生")
            else:
                st.error("❌ 无法获取学生列表")
        except Exception as e:
            st.error("❌ 无法获取学生列表")
        
        st.markdown("*必填项")
        
        submit_button = st.form_submit_button("✅ 创建提交", use_container_width=True)
        
        if submit_button:
            if not title:
                st.error("❌ 标题不能为空")
            elif submission_type == "text" and not text_content:
                st.error("❌ 文字提交必须输入内容")
            elif submission_type == "file" and not uploaded_files:
                st.error("❌ 文件提交必须上传文件")
            elif not person_id:
                st.error("❌ 必须选择关联学生")
            else:
                try:
                    # 创建提交
                    payload = {
                        "title": title,
                        "submission_type": submission_type,
                        "student_id": person_id
                    }
                    
                    # 文字提交添加内容
                    if submission_type == "text" and text_content:
                        payload["text_content"] = text_content
                    
                    response = requests.post(
                        f"{API_BASE_URL}/submissions",
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        submission = response.json()
                        st.session_state.submission = submission
                        st.success("✅ 提交创建成功！")
                        
                        # 显示提交信息
                        info_col1, info_col2 = st.columns(2)
                        with info_col1:
                            st.metric("提交类型", "文字提交" if submission['submission_type'] == 'text' else "文件提交")
                        with info_col2:
                            st.metric("提交ID", submission['submission_id'])
                        
                        # 如果是文件提交，上传文件
                        if submission_type == "file" and uploaded_files:
                            st.markdown("---")
                            st.subheader("📤 上传文件中...")
                            progress_bar = st.progress(0)
                            success_count = 0
                            
                            for i, file in enumerate(uploaded_files):
                                st.write(f"📄 正在上传: {file.name}")
                                
                                # 上传文件到服务器
                                files = {"file": (file.name, file, file.type)}
                                try:
                                    response = requests.post(
                                        f"{API_BASE_URL}/submissions/{submission['submission_id']}/files",
                                        files=files
                                    )
                                    if response.status_code == 200:
                                        st.success(f"✅ 文件 {file.name} 上传成功")
                                        success_count += 1
                                    else:
                                        try:
                                            error_detail = response.json().get('detail', '未知错误')
                                        except:
                                            error_detail = f"HTTP {response.status_code}"
                                        st.error(f"❌ 文件 {file.name} 上传失败: {error_detail}")
                                except Exception as e:
                                    st.error(f"❌ 文件 {file.name} 上传失败: {str(e)}")
                                
                                # 更新进度条
                                progress_bar.progress((i + 1) / len(uploaded_files))
                            
                            # 显示上传结果
                            st.markdown("---")
                            if success_count == len(uploaded_files):
                                st.success(f"✅ 所有文件上传成功！共 {success_count} 个文件")
                                # 清空提交区
                                if 'submission' in st.session_state:
                                    del st.session_state.submission
                                st.success("📋 提交区已清空，可继续上传新的提交")
                            else:
                                st.warning(f"⚠️ 文件上传完成，成功 {success_count}/{len(uploaded_files)} 个文件")
                        
                        # 如果是文字提交，显示内容预览
                        if submission['submission_type'] == 'text' and submission.get('text_content'):
                            with st.expander("查看文字内容预览"):
                                st.text(submission['text_content'][:500] + "..." if len(submission['text_content']) > 500 else submission['text_content'])
                        
                        # 提示用户可以稍后关联人员
                        if not person_id:
                            st.markdown("---")
                            st.info("📝 提交已创建，您可以稍后在文件管理页面为提交关联人员")
                    else:
                        try:
                            error_detail = response.json().get('detail', '未知错误')
                        except:
                            error_detail = f"HTTP {response.status_code}"
                        st.error(f"❌ 创建失败: {error_detail}")
                except Exception as e:
                    st.error(f"❌ 创建失败: {str(e)}")
    
    # 查看已上传文件（仅文件提交）
    if 'submission' in st.session_state and st.session_state.submission.get('submission_type') == 'file':
        st.markdown("---")
        if st.button("📋 查看已上传文件", use_container_width=True):
            try:
                response = requests.get(
                    f"{API_BASE_URL}/submissions/{st.session_state.submission['submission_id']}/files"
                )
                if response.status_code == 200:
                    files = response.json()
                    if files:
                        # 简化文件信息显示
                        simplified_files = []
                        for file in files:
                            simplified_files.append({
                                "文件名": file.get('file_path', '').split('/')[-1].split('\\')[-1],
                                "文件类型": file.get('media_type', 'N/A'),
                                "文件大小": f"{file.get('size_bytes', 0) / 1024:.2f} KB",
                                "上传时间": file.get('uploaded_at', 'N/A')[:19]
                            })
                        df = pd.DataFrame(simplified_files)
                        st.dataframe(df, use_container_width=True)
                        st.info(f"共 {len(files)} 个文件")
                    else:
                        st.info("📭 暂无上传文件")
                else:
                    try:
                        error_detail = response.json().get('detail', '未知错误')
                    except:
                        error_detail = f"HTTP {response.status_code}"
                    st.error(f"❌ 获取文件失败: {error_detail}")
            except Exception as e:
                st.error(f"❌ 获取文件失败: {str(e)}")
    
    # 文字提交完成提示
    if 'submission' in st.session_state and st.session_state.submission.get('submission_type') == 'text':
        st.markdown("---")
        st.success("✅ 文字提交已完成！")
        # 清空提交区
        if 'submission' in st.session_state:
            del st.session_state.submission
        st.success("📋 提交区已清空，可继续上传新的提交")

# ==================== 评估管理 ====================
elif page == "🤖 评估管理":
    st.title("🤖 评估管理")
    
    st.markdown("""
    **评估流程：**
    - 阶段评估：选择特定报告，根据学生工作时期进行评估
    - 整体评估：对学生的所有提交进行综合评估
    
    系统将使用AI对学生提交的材料进行评估，包括：
    - 📚 学术表现分析
    - 💬 沟通能力分析
    - 👥 领导力分析
    - 🤝 团队协作分析
    - 💡 创新能力分析
    - 🧩 问题解决分析
    """)
    
    # 评估类型选择
    eval_type = st.selectbox(
        "选择评估类型",
        options=["阶段评估", "整体评估"]
    )
    
    if eval_type == "阶段评估":
        st.subheader("📊 阶段评估")
        st.markdown("对特定报告进行评估，根据学生工作时期调整评估标准")
        
        # 获取所有提交
        try:
            response = requests.get(f"{API_BASE_URL}/submissions")
            if response.status_code == 200:
                submissions = response.json()
                if submissions:
                    # 构建提交选项
                    submission_options = {sub['submission_id']: f"{sub['title']} (学生ID: {sub.get('student_id', '未知')})" for sub in submissions}
                    selected_submission_id = st.selectbox(
                        "选择报告",
                        options=list(submission_options.keys()),
                        format_func=lambda x: submission_options[x]
                    )
                    
                    # 学生工作时期设置
                    st.markdown("---")
                    st.subheader("📅 学生工作时期设置")
                    
                    # 自由拖动的进度条（0-100%）
                    st.write("选择学生工作时期:")
                    progress_percent = st.slider(
                        "工作时期进度",
                        min_value=0,
                        max_value=100,
                        value=50,
                        step=1,
                        format="%d%%"
                    )
                    
                    # 转换为0.0-1.0的进度值
                    stage_progress = progress_percent / 100.0
                    
                    # 显示进度值
                    st.write(f"当前工作时期进度: {stage_progress:.2f}")
                    
                    # 根据进度值显示时期说明
                    if stage_progress < 0.33:
                        st.info("💡 初期阶段 - 评分相对宽松，重点关注学习态度和基础掌握")
                    elif stage_progress < 0.66:
                        st.info("⚖️ 中期阶段 - 评分适中，平衡考察进展和协作能力")
                    else:
                        st.info("🎯 最终阶段 - 评分相对严格，重点关注成果质量和专业性")
                    
                    if st.button("▶️ 启动阶段评估", use_container_width=True):
                        # 准备评估请求
                        eval_payload = {
                            "submission_id": selected_submission_id,
                            "stage_progress": stage_progress
                        }
                        
                        st.info(f"📊 将使用工作时期进度 {stage_progress:.2f} 进行评估")
                        
                        # 启动评估
                        with st.spinner("🤖 AI正在评估中，请稍候..."):
                            progress_bar = st.progress(0)
                            
                            # 模拟评估进度
                            import time
                            for i in range(100):
                                time.sleep(0.05)
                                progress_bar.progress(i + 1)
                            
                            response = requests.post(
                                f"{API_BASE_URL}/evaluate",
                                json=eval_payload
                            )
                            
                            if response.status_code == 200:
                                evaluation_result = response.json()
                                st.session_state.evaluation_result = evaluation_result
                                st.success("✅ 评估完成！")
                                
                                # 显示评估结果摘要
                                st.subheader("📊 评估结果摘要")
                                
                                result_col1, result_col2, result_col3, result_col4 = st.columns(4)
                                with result_col1:
                                    st.metric("综合评分", f"{evaluation_result['overall_score']}/10")
                                with result_col2:
                                    st.metric("评估维度", len(evaluation_result['dimension_scores']))
                                with result_col3:
                                    st.metric("评估时间", evaluation_result['evaluated_at'][:10])
                                with result_col4:
                                    # 显示阶段进度信息
                                    stage_progress = evaluation_result.get('stage_progress', 0.5)
                                    progress_percent = int(stage_progress * 100)
                                    st.metric("工作时期进度", f"{progress_percent}%")
                                
                                # 显示阶段评估说明
                                stage_progress = evaluation_result.get('stage_progress', 0.5)
                                if stage_progress < 0.33:
                                    st.info("💡 初期阶段评估 - 评分相对宽松，重点关注学习态度和基础掌握")
                                elif stage_progress < 0.66:
                                    st.info("⚖️ 中期阶段评估 - 评分适中，平衡考察进展和协作能力")
                                else:
                                    st.info("🎯 最终阶段评估 - 评分相对严格，重点关注成果质量和专业性")
                                
                                # 显示详细结果
                                with st.expander("查看详细结果"):
                                    st.json(evaluation_result)
                            else:
                                try:
                                    error_detail = response.json().get('detail', '未知错误')
                                except:
                                    error_detail = f"HTTP {response.status_code}"
                                st.error(f"❌ 评估失败: {error_detail}")
                else:
                    st.info("📭 暂无提交记录")
            else:
                st.error("❌ 获取提交记录失败")
        except Exception as e:
            st.error(f"❌ 加载提交记录失败: {str(e)}")
    
    elif eval_type == "整体评估":
        st.subheader("🎯 整体评估")
        st.markdown("对学生的所有提交进行综合评估，给出整体表现评价")
        
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
                    
                    if st.button("▶️ 启动整体评估", use_container_width=True):
                        # 检查学生是否有提交记录
                        response = requests.get(f"{API_BASE_URL}/students/{selected_student_id}/submissions")
                        if response.status_code == 200:
                            submissions = response.json()
                            if not submissions:
                                st.error("❌ 该学生暂无提交记录")
                            else:
                                # 准备评估请求（使用第一个提交作为基础，实际会评估所有提交）
                                selected_submission_id = submissions[0]['submission_id']
                                eval_payload = {
                                    "submission_id": selected_submission_id,
                                    "stage_progress": 1.0  # 整体评估使用最终阶段标准
                                }
                                
                                st.info("📊 将对学生的所有提交进行综合评估")
                                
                                # 启动评估
                                with st.spinner("🤖 AI正在评估中，请稍候..."):
                                    progress_bar = st.progress(0)
                                    
                                    # 模拟评估进度
                                    import time
                                    for i in range(100):
                                        time.sleep(0.05)
                                        progress_bar.progress(i + 1)
                                    
                                    response = requests.post(
                                        f"{API_BASE_URL}/evaluate",
                                        json=eval_payload
                                    )
                                    
                                    if response.status_code == 200:
                                        evaluation_result = response.json()
                                        st.session_state.evaluation_result = evaluation_result
                                        st.success("✅ 评估完成！")
                                        
                                        # 显示评估结果摘要
                                        st.subheader("📊 评估结果摘要")
                                        
                                        result_col1, result_col2, result_col3 = st.columns(3)
                                        with result_col1:
                                            st.metric("综合评分", f"{evaluation_result['overall_score']}/10")
                                        with result_col2:
                                            st.metric("评估维度", len(evaluation_result['dimension_scores']))
                                        with result_col3:
                                            st.metric("评估时间", evaluation_result['evaluated_at'][:10])
                                        
                                        st.info("🎯 整体评估 - 基于学生的所有提交进行综合评价")
                                        
                                        # 显示详细结果
                                        with st.expander("查看详细结果"):
                                            st.json(evaluation_result)
                                    else:
                                        try:
                                            error_detail = response.json().get('detail', '未知错误')
                                        except:
                                            error_detail = f"HTTP {response.status_code}"
                                        st.error(f"❌ 评估失败: {error_detail}")
                        else:
                            st.error("❌ 获取学生提交记录失败")
                else:
                    st.info("📭 暂无学生记录")
            else:
                st.error("❌ 获取学生列表失败")
        except Exception as e:
            st.error(f"❌ 加载学生列表失败: {str(e)}")

# ==================== 结果查询 ====================
elif page == "📊 结果查询":
    st.title("📊 结果查询")
    
    st.markdown("""
    **查询方式：**
    - 按学生查询：查看特定学生的所有评估结果
    """)
    
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
                selected_student_id = st.selectbox(
                    "选择学生",
                    options=list(student_options.keys()),
                    format_func=lambda x: student_options[x]
                )
                
                if st.button("🔍 查询", use_container_width=True, key="search_by_student"):
                    try:
                        response = requests.get(f"{API_BASE_URL}/students/{selected_student_id}/evaluations")
                        if response.status_code == 200:
                            results = response.json()
                            
                            if results:
                                st.success(f"✅ 找到 {len(results)} 条评估记录")
                                
                                for i, result in enumerate(results):
                                    with st.expander(f"评估 {i+1}: {result['evaluation_id']}"):
                                        st.metric("综合评分", f"{result['overall_score']}/10")
                                        
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
                            else:
                                st.info("📭 该学生暂无评估记录")
                        else:
                            try:
                                error_detail = response.json().get('detail', '未知错误')
                            except:
                                error_detail = f"HTTP {response.status_code}"
                            st.error(f"❌ 查询失败: {error_detail}")
                    except Exception as e:
                        st.error(f"❌ 查询失败: {str(e)}")
            else:
                st.info("📭 暂无学生记录")
        else:
            st.error("❌ 获取学生列表失败")
    except Exception as e:
        st.error(f"❌ 加载学生列表失败: {str(e)}")
    
    # ==================== 总进度评估功能块 ====================
    st.markdown("---")
    st.subheader("📈 总进度评估")
    st.markdown("""
    **功能说明：** 基于该学生的所有评估记录（按时间排序），分析每个维度在不同进度值下的变化趋势。
    """)
    
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
                    
                    # 显示关键洞察
                    if report_data.get('key_insights'):
                        st.subheader("💡 关键洞察")
                        for insight in report_data['key_insights']:
                            st.markdown(f"- {insight}")
                    
                    # 显示改进领域
                    if report_data.get('improvement_areas'):
                        st.subheader("📈 改进领域")
                        for area in report_data['improvement_areas']:
                            st.markdown(f"- {area}")
                    
                    # 下载报告按钮
                    report_content = report_data.get('report', '暂无报告内容')
                    download_content = f"# 学生进度报告\n\n"
                    download_content += f"## 基本信息\n"
                    download_content += f"- 学生ID: {selected_student_id}\n"
                    download_content += f"- 评估总数: {report_data.get('total_evaluations', 0)}\n"
                    download_content += f"- 生成时间: {report_data.get('generated_at', '')}\n"
                    
                    time_range = report_data.get('time_range', {})
                    if time_range:
                        start_date = time_range.get('start', '')[:10]
                        end_date = time_range.get('end', '')[:10]
                        download_content += f"- 时间范围: {start_date} 至 {end_date}\n"
                    
                    download_content += f"\n## 报告内容\n"
                    download_content += report_content
                    
                    if report_data.get('key_insights'):
                        download_content += f"\n## 关键洞察\n"
                        for insight in report_data['key_insights']:
                            download_content += f"- {insight}\n"
                    
                    if report_data.get('improvement_areas'):
                        download_content += f"\n## 改进领域\n"
                        for area in report_data['improvement_areas']:
                            download_content += f"- {area}\n"
                    
                    # 生成文件名
                    generated_at = report_data.get('generated_at', '')[:10]
                    filename = f"学生进度报告_{selected_student_id}_{generated_at}.txt"
                    
                    # 添加下载按钮
                    st.download_button(
                        label="📥 下载报告",
                        data=download_content,
                        file_name=filename,
                        mime="text/plain",
                        key="download_new_report"
                    )
                    
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
    
    # ==================== 历史进度报告 ====================
    st.markdown("---")
    st.subheader("📋 历史进度报告")
    st.markdown("""
    **功能说明：** 查看该学生的历史进度评估报告记录。
    """)
    
    if st.button("🔍 查看历史报告", use_container_width=True, key="view_history_reports"):
        try:
            with st.spinner("正在加载历史报告..."):
                response = requests.get(f"{API_BASE_URL}/students/{selected_student_id}/progress-reports")
                if response.status_code == 200:
                    reports = response.json()
                    
                    if reports:
                        st.success(f"✅ 找到 {len(reports)} 份历史报告")
                        
                        for i, report in enumerate(reports):
                            with st.expander(f"报告 {i+1}: {report.get('generated_at', '')[:10]}"):
                                # 显示报告概览
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("评估总数", report.get('total_evaluations', 0))
                                with col2:
                                    time_range = report.get('time_range', {})
                                    if time_range:
                                        start_date = time_range.get('start', '')[:10]
                                        end_date = time_range.get('end', '')[:10]
                                        st.metric("时间范围", f"{start_date} 至 {end_date}")
                                with col3:
                                    st.metric("生成时间", report.get('generated_at', '')[:10])
                                
                                # 显示报告内容
                                st.markdown("**报告内容：**")
                                report_content = report.get('report', '暂无报告内容')
                                st.markdown(report_content)
                                
                                # 显示关键洞察
                                if report.get('key_insights'):
                                    st.markdown("**关键洞察：**")
                                    for insight in report['key_insights']:
                                        st.markdown(f"- {insight}")
                                
                                # 显示改进领域
                                if report.get('improvement_areas'):
                                    st.markdown("**改进领域：**")
                                    for area in report['improvement_areas']:
                                        st.markdown(f"- {area}")
                                
                                # 下载报告按钮
                                report_content = report.get('report', '暂无报告内容')
                                download_content = f"# 学生进度报告\n\n"
                                download_content += f"## 基本信息\n"
                                download_content += f"- 学生ID: {selected_student_id}\n"
                                download_content += f"- 评估总数: {report.get('total_evaluations', 0)}\n"
                                download_content += f"- 生成时间: {report.get('generated_at', '')}\n"
                                
                                time_range = report.get('time_range', {})
                                if time_range:
                                    start_date = time_range.get('start', '')[:10]
                                    end_date = time_range.get('end', '')[:10]
                                    download_content += f"- 时间范围: {start_date} 至 {end_date}\n"
                                
                                download_content += f"\n## 报告内容\n"
                                download_content += report_content
                                
                                if report.get('key_insights'):
                                    download_content += f"\n## 关键洞察\n"
                                    for insight in report['key_insights']:
                                        download_content += f"- {insight}\n"
                                
                                if report.get('improvement_areas'):
                                    download_content += f"\n## 改进领域\n"
                                    for area in report['improvement_areas']:
                                        download_content += f"- {area}\n"
                                
                                # 生成文件名
                                generated_at = report.get('generated_at', '')[:10]
                                filename = f"学生进度报告_{selected_student_id}_{generated_at}.txt"
                                
                                # 添加下载按钮
                                st.download_button(
                                    label="📥 下载报告",
                                    data=download_content,
                                    file_name=filename,
                                    mime="text/plain",
                                    key=f"download_report_{i}"
                                )
                    else:
                        st.info("📭 暂无历史进度报告")
                else:
                    try:
                        error_detail = response.json().get('detail', '未知错误')
                    except:
                        error_detail = f"HTTP {response.status_code}"
                    st.error(f"❌ 加载历史报告失败: {error_detail}")
        except Exception as e:
            st.error(f"❌ 加载历史报告失败: {str(e)}")



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
    
    # 步骤 1: 识别引擎配置
    st.subheader("步骤 1: 识别引擎配置")
    
    # 初始化会话状态
    if "app_id" not in st.session_state:
        st.session_state.app_id = "122301981"
    if "api_key" not in st.session_state:
        st.session_state.api_key = "Cxyapyn3Fcvy1UR8IjY51ouI"
    if "secret_key" not in st.session_state:
        st.session_state.secret_key = "pDVhG7JQmmSJ6FRoHuIZGjyHwkHokN0F"
    
    current_ai_config = {}
    try:
        ai_response = requests.get(f"{API_BASE_URL}/ai-config", timeout=10)
        if ai_response.status_code == 200:
            current_ai_config = ai_response.json()
    except Exception:
        current_ai_config = {}

    current_model = current_ai_config.get("model", "")
    if current_model:
        st.info(f"当前 AI 识别模型：`{current_model}`")
    else:
        st.warning("当前未读取到 AI 设置，将回退到百度 OCR（如果已填写百度配置）。")

    with st.expander("百度 OCR 备用配置（仅在当前 AI 模型不支持图像识别时使用）", expanded=False):
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
                        if result.get("engine"):
                            st.caption(f"识别引擎：{result['engine']}")

                        ocr_df = parse_ocr_boxes(result.get("recognized_text", ""))
                        if not ocr_df.empty:
                            st.subheader("📍 OCR 可视化")
                            vis_col1, vis_col2 = st.columns([2, 1])
                            with vis_col1:
                                if file_ext != 'pdf':
                                    uploaded_file.seek(0)
                                    boxed_image = draw_ocr_boxes(uploaded_file, ocr_df)
                                    st.image(boxed_image, caption="识别框叠加预览", use_container_width=True)
                                else:
                                    st.info("当前文件为 PDF，已解析出坐标结果。图片叠框预览建议先上传单页截图。")
                            with vis_col2:
                                st.dataframe(
                                    ocr_df[["text", "confidence", "x", "y", "w", "h"]],
                                    use_container_width=True,
                                    hide_index=True,
                                )
                        else:
                            st.caption("当前返回结果不包含标准坐标框格式，因此只展示纯文本识别结果。")
                        
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

# 试卷批改
    st.markdown("---")
    st.subheader("🧠 手写试卷批改")
    st.warning("请先在 `AI设置` 页面配置支持图像输入的模型，例如 `gpt-4o` 或 `glm-4v`。")

    grading_student_options = {"": "不绑定学生"}
    try:
        response = requests.get(f"{API_BASE_URL}/students", timeout=10)
        if response.status_code == 200:
            students = response.json()
            grading_student_options.update({
                item["student_id"]: f'{item["student_id"]} - {item["name"]}'
                for item in students
            })
    except Exception:
        pass

    with st.form("grade_handwriting_exam_form"):
        st.markdown("**交互流程：结构化输入 → 多模态推理 → 可解释校验输出**")
        selected_grading_student_id = st.selectbox(
            "关联学生",
            options=list(grading_student_options.keys()),
            format_func=lambda x: grading_student_options[x]
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            subject = st.text_input("科目", placeholder="如：数学、语文、英语")
        with col2:
            total_score = st.text_input("试卷总分", placeholder="如：100，可留空")
        with col3:
            recognition_mode = st.selectbox(
                "识别模式",
                options=["general", "formula"],
                format_func=lambda x: "通用批改模式" if x == "general" else "公式识别专用模式",
                help="公式识别专用模式会输出公式框选坐标和 LaTeX，便于直接可视化核对。"
            )

        exam_files = st.file_uploader(
            "上传试卷图片",
            type=["png", "jpg", "jpeg", "bmp", "webp"],
            accept_multiple_files=True,
            key="handwriting_exam_files",
            help="支持多页试卷，一次可上传多张图片"
        )

        answer_key = st.text_area(
            "参考答案",
            placeholder="按题号填写标准答案，例如：\n1. A\n2. x=2\n3. 论点包括 ...",
            height=220
        )
        rubric = st.text_area(
            "评分细则",
            placeholder="可选，例如：选择题每题 5 分；计算题按步骤给分；字迹模糊处酌情扣分。",
            height=140
        )
        extra_requirements = st.text_area(
            "额外要求",
            placeholder="可选，例如：重点检查单位是否正确；作文按立意、结构、语言三项评分。",
            height=100
        )

        st.markdown("**结构化输入区**")
        input_tab1, input_tab2, input_tab3 = st.tabs(["文本补充输入框", "系统功能说明区", "关系结构输入区"])
        with input_tab1:
            context_text = st.text_area(
                "context_text",
                placeholder="可选：补充题干背景、已知条件、关键定义等。",
                height=120
            )
        with input_tab2:
            system_functions = st.text_area(
                "系统功能说明",
                placeholder="可选：描述系统包含的功能模块、职责和边界。",
                height=120
            )
        with input_tab3:
            system_relationships = st.text_area(
                "关系结构输入",
                placeholder="可选：描述模块间输入输出、依赖、因果链与约束关系。",
                height=120
            )
        validate_derivation = st.checkbox(
            "启用公式推导合理性校验",
            value=True,
            help="开启后会逐题检查公式推导是否自洽，并返回 valid/invalid/uncertain。"
        )
        st.markdown("**高级识别参数（Qwen/DashScope）**")
        adv_col1, adv_col2, adv_col3 = st.columns(3)
        with adv_col1:
            enable_thinking = st.checkbox("开启思考模式", value=True)
            vl_high_resolution_images = st.checkbox("高分辨率图像模式", value=True)
        with adv_col2:
            thinking_budget = st.number_input("thinking_budget", min_value=0, max_value=120000, value=81920, step=1024)
            retry_count = st.number_input("失败重试次数", min_value=0, max_value=8, value=2, step=1)
        with adv_col3:
            request_timeout = st.number_input("单次请求超时(秒)", min_value=30, max_value=900, value=300, step=10)

        grade_submit = st.form_submit_button("开始批改试卷", use_container_width=True)

        if grade_submit:
            if not exam_files:
                st.error("请至少上传一张试卷图片。")
            elif not answer_key.strip():
                st.error("请填写参考答案。")
            else:
                try:
                    data = {
                        "answer_key": answer_key,
                        "rubric": rubric,
                        "subject": subject,
                        "student_id": selected_grading_student_id,
                        "total_score": total_score,
                        "extra_requirements": extra_requirements,
                        "recognition_mode": recognition_mode,
                        "context_text": context_text,
                        "system_functions": system_functions,
                        "system_relationships": system_relationships,
                        "validate_derivation": str(validate_derivation).lower(),
                        "enable_thinking": str(enable_thinking).lower(),
                        "thinking_budget": str(int(thinking_budget)),
                        "vl_high_resolution_images": str(vl_high_resolution_images).lower(),
                        "retry_count": str(int(retry_count)),
                        "request_timeout": str(int(request_timeout)),
                    }
                    files = [
                        ("files", (uploaded_file.name, uploaded_file, uploaded_file.type))
                        for uploaded_file in exam_files
                    ]

                    with st.spinner("结构化输入已提交，正在执行多模态推理与可解释校验..."):
                        response = requests.post(
                            f"{API_BASE_URL}/agent/grade-handwriting-exam",
                            data=data,
                            files=files,
                            timeout=300
                        )

                    if response.status_code == 200:
                        result = response.json()
                        st.success("试卷批改完成。")

                        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                        with metric_col1:
                            st.metric("总得分", f"{result.get('total_score', 0)}")
                        with metric_col2:
                            st.metric("满分", f"{result.get('max_score', 0)}")
                        with metric_col3:
                            st.metric("模型", result.get("model", "N/A"))
                        with metric_col4:
                            mode_label = "公式专用" if result.get("recognition_mode") == "formula" else "通用"
                            st.metric("识别模式", mode_label)

                        if result.get("overall_comment"):
                            st.subheader("总体评语")
                            st.write(result["overall_comment"])

                        if result.get("course_achievement_comment"):
                            st.subheader("课程达成度评价")
                            st.write(result["course_achievement_comment"])

                        if result.get("strengths"):
                            st.subheader("亮点")
                            for item in result["strengths"]:
                                st.markdown(f"- {item}")

                        if result.get("areas_for_improvement"):
                            st.subheader("待改进")
                            for item in result["areas_for_improvement"]:
                                st.markdown(f"- {item}")

                        if result.get("recognized_text"):
                            with st.expander("查看识别出的试卷文本"):
                                st.text_area("识别文本", value=result.get("recognized_text", ""), height=320)

                        formula_df = parse_formula_boxes(result.get("formula_boxes", []))
                        if not formula_df.empty:
                            st.subheader("📐 公式框选可视化")
                            st.caption("以下叠框来自后端返回的相对坐标（0~1），已映射到原图。")

                            page_tabs = st.tabs([f"第 {idx} 页" for idx in range(1, len(exam_files) + 1)])
                            for page_index, page_tab in enumerate(page_tabs, start=1):
                                with page_tab:
                                    uploaded_file = exam_files[page_index - 1]
                                    page_formula_df = formula_df[formula_df["page_index"] == page_index]
                                    uploaded_file.seek(0)
                                    if page_formula_df.empty:
                                        st.info("当前页暂无公式框。")
                                        st.image(uploaded_file, caption=f"第 {page_index} 页原图", use_container_width=True)
                                    else:
                                        boxed_image = draw_formula_boxes(uploaded_file, page_formula_df)
                                        st.image(boxed_image, caption=f"第 {page_index} 页公式框叠加", use_container_width=True)

                            st.subheader("公式框表格")
                            table_df = formula_df.copy()
                            if "confidence" in table_df.columns:
                                table_df["confidence"] = table_df["confidence"].apply(
                                    lambda x: round(x, 4) if pd.notna(x) else None
                                )
                            st.dataframe(
                                table_df[["page_index", "box_type", "confidence", "text", "latex", "x", "y", "w", "h"]],
                                use_container_width=True,
                                hide_index=True
                            )

                        derivation_checks = result.get("derivation_checks", [])
                        if derivation_checks:
                            st.subheader("公式推导校验结果表")
                            check_df = pd.DataFrame(derivation_checks)
                            check_df["status"] = check_df.get("status", "uncertain").astype(str).str.strip().str.lower()
                            check_df["step"] = check_df.get("question_number", "").astype(str).str.strip()
                            check_df["valid"] = check_df["status"].eq("valid")

                            # 若后端未提供 issue，则按状态兜底
                            check_df["error_type"] = check_df.get("issue", "").fillna("").astype(str).str.strip()
                            check_df.loc[check_df["error_type"] == "", "error_type"] = check_df["status"].map(
                                lambda x: "" if x == "valid" else ("uncertain" if x == "uncertain" else "invalid")
                            )

                            evidence_col = check_df.get("evidence", "").fillna("").astype(str).str.strip()
                            suggestion_col = check_df.get("suggestion", "").fillna("").astype(str).str.strip()
                            formula_col = check_df.get("checked_formula", "").fillna("").astype(str).str.strip()

                            check_df["explanation"] = evidence_col
                            check_df.loc[(check_df["explanation"] == "") & (formula_col != ""), "explanation"] = (
                                "校验公式: " + formula_col
                            )
                            check_df.loc[(check_df["explanation"] == "") & (suggestion_col != ""), "explanation"] = suggestion_col
                            check_df.loc[(check_df["explanation"] != "") & (suggestion_col != ""), "explanation"] = (
                                check_df["explanation"] + "；建议: " + suggestion_col
                            )

                            status_order = {"invalid": 0, "uncertain": 1, "valid": 2}
                            check_df["status_order"] = check_df["status"].map(
                                lambda x: status_order.get(str(x).strip().lower(), 1)
                            )
                            check_df = check_df.sort_values(
                                by=["status_order", "step"],
                                ascending=[True, True]
                            )

                            st.dataframe(
                                check_df[["step", "valid", "error_type", "explanation"]],
                                use_container_width=True,
                                hide_index=True
                            )

                        question_results = result.get("question_results", [])
                        if question_results:
                            st.subheader("逐题结果")
                            for question in question_results:
                                title = (
                                    f"第 {question.get('question_number', '?')} 题"
                                    f" | 得分 {question.get('score', 0)}/{question.get('max_score', 0)}"
                                )
                                with st.expander(title):
                                    st.markdown("**学生答案**")
                                    st.write(question.get("recognized_answer", ""))
                                    if question.get("reference_answer"):
                                        st.markdown("**参考答案**")
                                        st.write(question.get("reference_answer"))
                                    st.markdown("**评分理由**")
                                    st.write(question.get("reasoning", ""))
                                    if question.get("strengths"):
                                        st.markdown("**本题亮点**")
                                        for item in question["strengths"]:
                                            st.markdown(f"- {item}")
                                    if question.get("mistakes"):
                                        st.markdown("**本题失分点**")
                                        for item in question["mistakes"]:
                                            st.markdown(f"- {item}")
                    else:
                        try:
                            error_detail = response.json().get("detail", "未知错误")
                        except Exception:
                            error_detail = f"HTTP {response.status_code}: {response.text}"
                        st.error(f"批改失败: {error_detail}")
                except Exception as e:
                    st.error(f"批改失败: {str(e)}")

# 复杂能力稳定性测试
    st.markdown("---")
    st.subheader("公式识别与图像理解稳定性测试")
    st.caption("用于压测 OCR/公式识别、多图理解、视频理解、思考模式等复杂场景，输出成功率与时延指标。")

    default_dashscope_key = os.getenv("DASHSCOPE_API_KEY", "sk-8ac33a82e02b42429a5b30b3ced6dfe3")
    if "dashscope_test_api_key" not in st.session_state:
        st.session_state.dashscope_test_api_key = default_dashscope_key

    with st.form("dashscope_stability_test_form"):
        test_col1, test_col2 = st.columns(2)
        with test_col1:
            dashscope_api_key = st.text_input(
                "DashScope API Key",
                value=st.session_state.dashscope_test_api_key,
                type="password",
                help="默认读取 DASHSCOPE_API_KEY 环境变量，若为空则使用你提供的默认 Key。"
            )
            test_rounds = st.slider("每个场景测试轮数", min_value=1, max_value=10, value=3)
        with test_col2:
            enable_thinking = st.checkbox("开启思考模式（qwen3.6-plus）", value=True)
            thinking_budget = st.number_input("thinking_budget", min_value=0, max_value=120000, value=81920, step=1024)

        st.markdown("**测试场景开关**")
        case_col1, case_col2, case_col3, case_col4 = st.columns(4)
        with case_col1:
            run_formula_ocr = st.checkbox("公式/OCR 识别", value=True)
        with case_col2:
            run_multi_image = st.checkbox("多图理解", value=True)
        with case_col3:
            run_video = st.checkbox("视频理解", value=True)
        with case_col4:
            run_highres = st.checkbox("高分辨率图像", value=True)

        run_stability_test = st.form_submit_button("开始稳定性测试", use_container_width=True)

    st.session_state.dashscope_test_api_key = dashscope_api_key

    if run_stability_test:
        if not dashscope_api_key.strip():
            st.error("请先填写 DashScope API Key。")
        else:
            scenarios = []
            if run_formula_ocr:
                scenarios.append({
                    "name": "公式/OCR",
                    "payload": {
                        "model": "qwen-vl-ocr-latest",
                        "messages": [{
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": "https://img.alicdn.com/imgextra/i2/O1CN01ktT8451iQutqReELT_!!6000000004408-0-tps-689-487.jpg"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": "提取图片中的关键信息，并给出包含可能公式或数字字段的结构化JSON。"
                                }
                            ]
                        }],
                        "max_tokens": 2048
                    }
                })
            if run_multi_image:
                scenarios.append({
                    "name": "多图理解",
                    "payload": {
                        "model": "qwen3.6-plus",
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"}},
                                {"type": "image_url", "image_url": {"url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/tiger.png"}},
                                {"type": "text", "text": "对比两张图片的主体、场景、动作和情绪差异。"}
                            ]
                        }],
                        "max_tokens": 1500
                    }
                })
            if run_video:
                scenarios.append({
                    "name": "视频理解",
                    "payload": {
                        "model": "qwen3.6-plus",
                        "messages": [{
                            "role": "user",
                            "content": [
                                {
                                    "type": "video_url",
                                    "video_url": {"url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241115/cqqkru/1.mp4"},
                                    "fps": 2
                                },
                                {"type": "text", "text": "总结这段视频的主要事件、角色和时间顺序。"}
                            ]
                        }],
                        "max_tokens": 2000
                    }
                })
            if run_highres:
                scenarios.append({
                    "name": "高分辨率细节",
                    "payload": {
                        "model": "qwen3.6-plus",
                        "messages": [{
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250212/earbrt/vcg_VCG211286867973_RF.jpg"}
                                },
                                {"type": "text", "text": "识别图中的节日氛围和关键细节，并说明依据。"}
                            ]
                        }],
                        "extra_body": {"vl_high_resolution_images": True},
                        "max_tokens": 1500
                    }
                })

            if enable_thinking:
                scenarios.append({
                    "name": "思考模式",
                    "payload": {
                        "model": "qwen3.6-plus",
                        "messages": [{"role": "user", "content": "请简洁说明：稳定性压测时应该如何设置重试、超时和退避策略？"}],
                        "extra_body": {"enable_thinking": True, "thinking_budget": int(thinking_budget)},
                        "max_tokens": 1200
                    }
                })

            if not scenarios:
                st.warning("至少选择一个测试场景。")
            else:
                all_rows = []
                with st.spinner("正在执行稳定性测试，请稍候..."):
                    for scenario in scenarios:
                        run_results = []
                        for _ in range(test_rounds):
                            run_results.append(
                                dashscope_call_with_retry(
                                    payload=scenario["payload"],
                                    api_key=dashscope_api_key.strip(),
                                    timeout=240,
                                    max_retries=2,
                                )
                            )
                        summary = summarize_stability_results(run_results)
                        errors = [r.get("error", "") for r in run_results if not r.get("ok")]
                        sample_output = next((r.get("text", "") for r in run_results if r.get("ok") and r.get("text")), "")
                        all_rows.append({
                            "场景": scenario["name"],
                            "轮数": summary["total"],
                            "成功数": summary["success"],
                            "失败数": summary["fail"],
                            "成功率(%)": round(summary["success_rate"], 2),
                            "平均耗时(s)": round(summary["avg_latency_s"], 2),
                            "P95耗时(s)": round(summary["p95_latency_s"], 2),
                            "错误示例": errors[0][:180] if errors else "",
                            "返回示例": sample_output[:200],
                        })

                result_df = pd.DataFrame(all_rows)
                st.dataframe(result_df, use_container_width=True, hide_index=True)
                st.download_button(
                    label="下载稳定性测试结果(JSON)",
                    data=json.dumps(all_rows, ensure_ascii=False, indent=2),
                    file_name=f"dashscope_stability_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )

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
                            submission_type = submission['submission_type']
                            
                            # 获取提交的文件
                            response = requests.get(f"{API_BASE_URL}/submissions/{submission_id}/files")
                            if response.status_code == 200:
                                files = response.json()
                                
                                # 处理每个文件
                                for file in files:
                                    all_files.append({
                                        "学生学号": student_id,
                                        "学生姓名": student_name,
                                        "提交ID": submission_id,
                                        "提交标题": submission_title,
                                        "提交类型": submission_type,
                                        "文件名": file.get('file_path', '').split('/')[-1].split('\\')[-1],
                                        "文件类型": file.get('media_type', 'N/A'),
                                        "文件大小": f"{file.get('size_bytes', 0) / 1024:.2f} KB",
                                        "上传时间": file.get('uploaded_at', 'N/A')[:19],
                                        "file_id": file.get('id', '')
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
                            # 删除按钮
                            if st.button(f"🗑️", key=f"delete_file_{file_info['file_id']}", help="删除文件"):
                                # 直接执行删除操作
                                try:
                                    delete_response = requests.delete(f"{API_BASE_URL}/files/{file_info['file_id']}")
                                    if delete_response.status_code == 200:
                                        st.success(f"✅ 文件 {file_info['文件名']} 删除成功！")
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
            
            media_type = st.selectbox(
                "文件类型",
                options=["document", "video", "audio"],
                index=["document", "video", "audio"].index(edit_file.get('文件类型', 'document'))
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

# ==================== API文档 ====================
elif page == "🔧 API文档":
    st.title("🔧 API 文档")
    
    st.markdown("""
    学生多维度能力评估系统提供完整的 RESTful API 接口
    
    **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
    
    **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
    """)
    
    st.markdown("---")
    
    # API 端点列表
    st.subheader("📚 API 端点")
    
    endpoints = [
        {
            "method": "GET",
            "path": "/",
            "description": "API 欢迎页面",
            "params": "无"
        },
        {
            "method": "GET",
            "path": "/health",
            "description": "健康检查",
            "params": "无"
        },
        {
            "method": "GET",
            "path": "/ai-config",
            "description": "获取当前 AI 配置",
            "params": "无"
        },
        {
            "method": "POST",
            "path": "/ai-config",
            "description": "更新 AI 配置",
            "params": "provider, api_key, model, base_url, temperature, max_tokens"
        },
        {
            "method": "POST",
            "path": "/ai-config/test",
            "description": "测试 AI 连接",
            "params": "无"
        },
        {
            "method": "POST",
            "path": "/students",
            "description": "创建学生",
            "params": "student_id, name, age, grade, major"
        },
        {
            "method": "GET",
            "path": "/students/{student_id}",
            "description": "获取学生信息",
            "params": "student_id (路径参数)"
        },
        {
            "method": "GET",
            "path": "/students",
            "description": "获取所有学生列表",
            "params": "skip, limit (查询参数)"
        },
        {
            "method": "PUT",
            "path": "/students/{student_id}",
            "description": "更新学生信息",
            "params": "student_id (路径参数), name, age, grade, major"
        },
        {
            "method": "POST",
            "path": "/submissions",
            "description": "创建提交",
            "params": "student_id, title, description"
        },
        {
            "method": "GET",
            "path": "/submissions/{submission_id}",
            "description": "获取提交信息",
            "params": "submission_id (路径参数)"
        },
        {
            "method": "POST",
            "path": "/submissions/{submission_id}/files",
            "description": "上传文件",
            "params": "submission_id (路径参数), file (文件)"
        },
        {
            "method": "GET",
            "path": "/submissions/{submission_id}/files",
            "description": "获取提交的文件列表",
            "params": "submission_id (路径参数)"
        },
        {
            "method": "POST",
            "path": "/evaluate",
            "description": "启动评估",
            "params": "submission_id"
        },
        {
            "method": "GET",
            "path": "/evaluations/{evaluation_id}",
            "description": "获取评估结果",
            "params": "evaluation_id (路径参数)"
        },
        {
            "method": "GET",
            "path": "/students/{student_id}/evaluations",
            "description": "获取学生的所有评估",
            "params": "student_id (路径参数)"
        },
        {
            "method": "GET",
            "path": "/submissions/{submission_id}/evaluation",
            "description": "获取提交的评估结果",
            "params": "submission_id (路径参数)"
        }
    ]
    
    for endpoint in endpoints:
        with st.expander(f"{endpoint['method']} {endpoint['path']}"):
            st.markdown(f"**描述:** {endpoint['description']}")
            st.markdown(f"**参数:** {endpoint['params']}")
    
    st.markdown("---")
    
    # 请求示例
    st.subheader("📝 请求示例")
    
    st.markdown("**更新 AI 配置:**")
    st.code("""
POST /ai-config
Content-Type: application/json

{
    "provider": "deepseek",
    "api_key": "sk-your-api-key",
    "model": "deepseek-chat",
    "temperature": 0.7,
    "max_tokens": 2000
}
    """, language="http")
    
    st.markdown("**创建学生:**")
    st.code("""
POST /students
Content-Type: application/json

{
    "student_id": "2024001",
    "name": "张三",
    "age": 20,
    "grade": "大二",
    "major": "计算机科学"
}
    """, language="http")
    
    st.markdown("**创建提交:**")
    st.code("""
POST /submissions
Content-Type: application/json

{
    "student_id": "2024001",
    "title": "机器学习论文",
    "description": "关于深度学习的期末论文"
}
    """, language="http")
    
    st.markdown("**启动评估:**")
    st.code("""
POST /evaluate
Content-Type: application/json

{
    "submission_id": "SUB_XXXXXXXX"
}
    """, language="http")
