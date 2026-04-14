from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
import shutil
from datetime import datetime
import sys
import time
import logging
import uuid
from src.course_classifier import classify_course_type, classify_course_type_with_meta

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('api_debug.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 添加项目根目录到 Python 路径
current_file = os.path.abspath(__file__)
api_dir = os.path.dirname(current_file)
src_dir = os.path.dirname(api_dir)
project_root = os.path.dirname(src_dir)

# 确保 src 目录和项目根目录都在 Python 路径中
for path in [src_dir, project_root]:
    if path not in sys.path:
        sys.path.insert(0, path)

from src.config import settings, AI_PROVIDERS, get_ai_config
from src.database import get_db, DatabaseService, init_db
from src.database.models import Student, Submission, MediaFile, EvaluationResult, ProgressReport
from src.models.schemas import (
    StudentCreate, StudentUpdate, StudentResponse,
    SubmissionCreate, SubmissionResponse, SubmissionStatus, SubmissionType, SubmissionPurpose,
    MediaFileResponse,
    EvaluationResultResponse, DimensionScoreResponse,
    EvaluationRequest, EvaluationResponse, ProgressReportResponse,
    EvaluationDimension
)
from src.models.schemas import EvaluationResult as SchemaEvaluationResult
# 移除对CrewAI和MediaProcessor的依赖，避免CV2依赖
# from src.agents.crew_manager import StudentEvaluationCrew
# from src.utils.media_processor import MediaProcessor
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
import json
import re
from typing import Union

# 增加文件大小限制
from starlette.middleware.base import BaseHTTPMiddleware

# 辅助函数：处理evidence字段，确保返回List[str]类型
def process_evidence(evidence: Union[str, list, None]) -> list:
    """处理evidence字段，确保返回List[str]类型"""
    if isinstance(evidence, str):
        # 如果是字符串，分割成列表
        return [item.strip() for item in evidence.split(",") if item.strip()]
    elif isinstance(evidence, list):
        # 如果已经是列表，直接返回
        return evidence
    else:
        # 如果是None或其他类型，返回空列表
        return []

def process_string_list(value: Union[str, list, None]) -> list:
    """处理字符串列表字段，确保返回List[str]类型"""
    if isinstance(value, str):
        # 如果是字符串，分割成列表
        return [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, list):
        # 如果已经是列表，直接返回
        return value
    else:
        # 如果是None或其他类型，返回空列表
        return []

def _get_course_weight_profile(course_type: str) -> Dict[str, Any]:
    """根据课程类型返回动态评价权重"""
    if "实践" in course_type:
        weights = [
            {"dimension": "工程实践与实现质量", "weight": 0.30, "description": "实现完整性、可运行性、工程规范"},
            {"dimension": "问题解决与调试能力", "weight": 0.25, "description": "定位问题、修复问题、方案有效性"},
            {"dimension": "设计与创新能力", "weight": 0.20, "description": "方案设计合理性、创新点与优化"},
            {"dimension": "文档表达与汇报", "weight": 0.15, "description": "报告质量、表达清晰度、论证逻辑"},
            {"dimension": "理论基础与分析", "weight": 0.10, "description": "关键原理理解与分析深度"}
        ]
    else:
        weights = [
            {"dimension": "理论基础与概念体系", "weight": 0.30, "description": "核心概念、原理和体系化理解"},
            {"dimension": "分析推理与批判思维", "weight": 0.25, "description": "论证严谨性、推理链条、对比分析"},
            {"dimension": "知识应用与问题解决", "weight": 0.20, "description": "理论迁移、案例分析、问题拆解"},
            {"dimension": "学习成果表达", "weight": 0.15, "description": "报告结构、表达清晰度、证据引用"},
            {"dimension": "实践理解与拓展", "weight": 0.10, "description": "实践环节认知、改进方向与拓展"}
        ]
    return {"course_type": course_type, "weights": weights}

def _is_valid_ability_description(text: str) -> bool:
    """过滤掉章节标题，保留毕业要求指标点内容。"""
    if not text:
        return False
    normalized = re.sub(r"\s+", "", str(text))
    if len(normalized) < 16:
        return False

    blocked_keywords = [
        "课程教学目标与毕业要求对应关系",
        "课程内容教学要求学时分配和教学手段",
        "实验教学项目学时分配",
        "课程立德树人内涵",
        "考核方式与成绩评定",
        "教学方法与手段",
    ]
    if any(k in normalized for k in blocked_keywords):
        return False

    # 能力点内容通常是陈述性句子，而不是章节标题
    semantic_keywords = ["能够", "使学生", "学生", "掌握", "理解", "具备", "应用", "分析", "设计", "建模"]
    if not any(k in normalized for k in semantic_keywords):
        return False
    return True

def _extract_text_based_ability_points(syllabus_content: str, max_items: int = 10) -> List[Dict[str, Any]]:
    """仅从“3.课程所支撑的毕业要求指标点”下方表格提取能力点描述。"""
    raw_lines = [ln for ln in re.split(r"[\r\n]+", syllabus_content) if ln and ln.strip()]
    lines: List[str] = []
    for ln in raw_lines:
        cleaned = str(ln).replace("↵", " ").replace("\u00a0", " ")
        cleaned = re.sub(r"[│¦]", "|", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" |")
        if cleaned:
            lines.append(cleaned)

    results: List[Dict[str, Any]] = []
    seen = set()
    serial_only_pattern = re.compile(r"^\d{1,2}$")
    indicator_cell_pattern = re.compile(r"^[A-Za-z]?\d+(?:[\.．-]\d+){1,2}")

    # 优先：直接定位“毕业要求指标点内容”表头所在行
    table_header_idx = -1
    for idx, line in enumerate(lines):
        compact = re.sub(r"\s+", "", line)
        if "毕业要求指标点" in compact and "毕业要求指标点内容" in compact and "序号" in compact:
            table_header_idx = idx
            break

    if table_header_idx == -1:
        return results

    i = table_header_idx + 1
    started = False
    while i < len(lines):
        line = lines[i]
        cells = [c.strip() for c in re.split(r"\s*\|\s*", line) if c.strip()]
        if len(cells) < 3:
            # 未开始提取前跳过噪声；开始后遇到非表格行则终止
            if started:
                break
            i += 1
            continue

        first_cell = re.sub(r"\s+", "", cells[0])
        second_cell = re.sub(r"\s+", "", cells[1])
        if not (serial_only_pattern.fullmatch(first_cell) and indicator_cell_pattern.match(second_cell)):
            if started:
                break
            i += 1
            continue

        started = True
        second_raw = cells[1].strip()
        ability_name = re.sub(r"^[A-Za-z]?\d+(?:[\.．-]\d+){1,2}\s*", "", second_raw).strip()
        ability_name = re.sub(r"\s+", "", ability_name) or re.sub(r"\s+", "", second_raw)

        candidate = re.sub(r"\s+", "", cells[2]).strip("：:;；-— ")
        if _is_valid_ability_description(candidate) and candidate not in seen:
            seen.add(candidate)
            results.append({
                "name": ability_name,
                "description": candidate
            })
            if len(results) >= max_items:
                break
        i += 1

    return results

def _extract_text_based_evaluation_criteria(ability_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按能力点兜底生成三条评价标准。"""
    def _focus_triplet(ability_name: str, ability_desc: str) -> List[str]:
        text = f"{ability_name}{ability_desc}"
        if any(k in text for k in ["建模", "模型"]):
            return [
                "问题抽象、关键变量与约束定义是否完整且准确",
                "模型或方法选择是否有依据，过程是否可复现",
                "结果解释、误差分析与改进建议是否充分"
            ]
        if any(k in text for k in ["分析", "推理", "评价"]):
            return [
                "分析框架是否清晰，核心结论是否建立在有效证据上",
                "论证链条是否完整，是否能够对比不同方案并说明取舍",
                "是否能识别局限并提出具有可操作性的优化路径"
            ]
        if any(k in text for k in ["设计", "开发", "实现"]):
            return [
                "方案设计是否满足需求，结构划分是否合理",
                "实现过程是否规范，关键步骤与结果是否可验证",
                "是否完成性能、稳定性或可维护性层面的改进说明"
            ]
        return [
            "核心概念与关键要求理解是否准确，表达是否专业清晰",
            "是否能将能力点要求落实到具体任务，过程与结果是否可信",
            "是否能基于结果进行反思与优化，并给出明确改进依据"
        ]

    results: List[Dict[str, Any]] = []
    for idx, ability in enumerate(ability_points, 1):
        desc = ""
        ability_name = ""
        if isinstance(ability, dict):
            desc = str(ability.get("description", "")).strip()
            ability_name = str(ability.get("name", "")).strip()
        elif isinstance(ability, str):
            desc = ability.strip()
        if not desc:
            continue

        display_name = ability_name or f"能力点{idx}"
        f1, f2, f3 = _focus_triplet(display_name, desc)
        standards = [
            f"基础达成：围绕“{display_name}”，学生应准确理解并清晰表述{f1}，提交内容中需体现术语使用规范、要点完整，且无明显事实或逻辑错误。",
            f"应用达成：学生应能在具体任务中落实“{display_name}”要求，重点考查{f2}；评分依据包括关键步骤说明、方法选择理由、过程记录与结果质量。",
            f"高阶达成：学生应基于任务结果开展反思与优化，重点体现{f3}；高分表现需给出对比分析、改进策略及可验证的效果说明。"
        ]
        results.append({
            "ability_description": desc,
            "name": f"{display_name}评价标准",
            "description": f"围绕能力点“{display_name}”的分层评价标准",
            "standards": standards,
            "standard": "\n".join([f"{i + 1}. {s}" for i, s in enumerate(standards)])
        })
    return results

def _extract_text_based_knowledge_points(syllabus_content: str, max_items: int = 20) -> List[str]:
    """从“二、课程内容、教学要求、学时分配和教学手段”下方表格提取知识点/能力点。"""
    raw_lines = [ln for ln in re.split(r"[\r\n]+", syllabus_content) if ln and ln.strip()]
    lines: List[str] = []
    for ln in raw_lines:
        cleaned = str(ln).replace("↵", " ").replace("\u00a0", " ")
        cleaned = re.sub(r"[│¦]", "|", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" |")
        if cleaned:
            lines.append(cleaned)

    section_started = False
    header_idx = -1
    kp_col_idx = -1
    for idx, line in enumerate(lines):
        compact = re.sub(r"\s+", "", line)
        if ("二" in compact and "课程内容" in compact and "教学要求" in compact) or ("课程内容、教学要求、学时分配和教学手段" in compact):
            section_started = True
            continue
        if section_started and "|" in line and "知识点" in line and "能力点" in line:
            header_cells = [c.strip() for c in re.split(r"\s*\|\s*", line) if c.strip()]
            for ci, hc in enumerate(header_cells):
                hc_compact = re.sub(r"\s+", "", hc)
                if "知识点" in hc_compact and "能力点" in hc_compact:
                    kp_col_idx = ci
                    header_idx = idx
                    break
            if header_idx != -1:
                break

    if header_idx == -1 or kp_col_idx == -1:
        return []

    knowledge_points: List[str] = []
    seen = set()
    serial_pattern = re.compile(r"^\d{1,2}$")
    non_table_count = 0
    for line in lines[header_idx + 1:]:
        if "|" not in line:
            non_table_count += 1
            if non_table_count >= 3 and knowledge_points:
                break
            continue
        non_table_count = 0
        cells = [c.strip() for c in re.split(r"\s*\|\s*", line)]
        if len(cells) <= kp_col_idx:
            continue
        first = re.sub(r"\s+", "", cells[0]) if cells else ""
        if first and not serial_pattern.fullmatch(first):
            # 课程内容表通常首列是序号
            if knowledge_points:
                break
            continue

        point = re.sub(r"\s+", "", str(cells[kp_col_idx])).strip("：:;；-— ")
        if not point or len(point) < 2:
            continue
        if point in seen:
            continue
        seen.add(point)
        knowledge_points.append(point)
        if len(knowledge_points) >= max_items:
            break
    return knowledge_points

def _parse_score_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return min(100.0, max(0.0, float(value)))
    except Exception:
        return None

def _calculate_ability_average_score(dimension_scores: List[Dict[str, Any]], ability_points: List[Dict[str, Any]], fallback_score: float = 0.0) -> float:
    valid_scores: List[float] = []
    for item in dimension_scores:
        if isinstance(item, dict):
            score = _parse_score_value(item.get("score"))
            if score is not None:
                valid_scores.append(score)
    avg_all = sum(valid_scores) / len(valid_scores) if valid_scores else fallback_score

    if not ability_points:
        return avg_all

    matched_scores: List[float] = []
    for ability in ability_points:
        if not isinstance(ability, dict):
            continue
        ability_name = str(ability.get("name", "")).strip()
        ability_desc = str(ability.get("description", "")).strip()
        key = re.sub(r"\s+", "", ability_name or ability_desc)
        if not key:
            continue

        matched = None
        for dim in dimension_scores:
            if not isinstance(dim, dict):
                continue
            dim_name = re.sub(r"\s+", "", str(dim.get("dimension", "")).strip())
            if dim_name and (key in dim_name or dim_name in key):
                matched = _parse_score_value(dim.get("score"))
                if matched is not None:
                    break
        matched_scores.append(matched if matched is not None else avg_all)

    if not matched_scores:
        return avg_all
    return round(sum(matched_scores) / len(matched_scores), 2)

def _calculate_course_assignment_overall_score(
    evaluation_result: Dict[str, Any],
    syllabus_analysis: Optional[Dict[str, Any]],
    stage_progress: float
) -> Optional[float]:
    """课程作业评分策略：
    - 理论课：50%能力点平均分 + 25%知识理解 + 25%知识应用
    - 实践课：50%能力点平均分 + 50%阶段完成度
    """
    if not isinstance(evaluation_result, dict) or not isinstance(syllabus_analysis, dict):
        return None

    course_type = str(syllabus_analysis.get("course_type", "理论课"))
    ability_points = syllabus_analysis.get("ability_points", []) if isinstance(syllabus_analysis.get("ability_points"), list) else []
    dimension_scores = evaluation_result.get("dimension_scores", []) if isinstance(evaluation_result.get("dimension_scores"), list) else []
    base_overall = _parse_score_value(evaluation_result.get("overall_score")) or 0.0
    ability_avg = _calculate_ability_average_score(dimension_scores, ability_points, fallback_score=base_overall)

    if "实践" in course_type:
        phase_completion_score = _parse_score_value(evaluation_result.get("phase_completion_score"))
        if phase_completion_score is None:
            completion_rate = _parse_score_value(
                (evaluation_result.get("task_completion", {}) or {}).get("completion_rate", 0.0)
            )
            # completion_rate 通常是 0~1
            if completion_rate is not None:
                phase_completion_score = completion_rate * 100.0 if completion_rate <= 1 else completion_rate
        if phase_completion_score is None:
            phase_completion_score = base_overall

        final_score = round(ability_avg * 0.5 + phase_completion_score * 0.5, 2)
        evaluation_result["score_policy"] = "practice_stage_process"
        evaluation_result["score_breakdown"] = {
            "course_type": course_type,
            "stage_progress": stage_progress,
            "ability_component": round(ability_avg, 2),
            "phase_completion_component": round(phase_completion_score, 2),
            "formula": "overall = 0.5 * ability_component + 0.5 * phase_completion_component"
        }
        return final_score

    understanding_score = _parse_score_value(evaluation_result.get("knowledge_understanding_score"))
    application_score = _parse_score_value(evaluation_result.get("knowledge_application_score"))

    knowledge_assessment = evaluation_result.get("knowledge_assessment", {})
    if understanding_score is None and isinstance(knowledge_assessment, dict):
        understanding_score = _parse_score_value(knowledge_assessment.get("understanding_score"))
    if application_score is None and isinstance(knowledge_assessment, dict):
        application_score = _parse_score_value(knowledge_assessment.get("application_score"))

    if understanding_score is None:
        understanding_score = base_overall
    if application_score is None:
        application_score = base_overall

    final_score = round(ability_avg * 0.5 + understanding_score * 0.25 + application_score * 0.25, 2)
    evaluation_result["score_policy"] = "theory_ability_knowledge_split"
    evaluation_result["score_breakdown"] = {
        "course_type": course_type,
        "ability_component": round(ability_avg, 2),
        "knowledge_understanding_component": round(understanding_score, 2),
        "knowledge_application_component": round(application_score, 2),
        "formula": "overall = 0.5 * ability_component + 0.25 * knowledge_understanding + 0.25 * knowledge_application"
    }
    return final_score

def _analysis_results_dir() -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, "analysis_results")

def _parse_weight_to_ratio(weight_value: Any) -> Optional[float]:
    if weight_value is None:
        return None
    if isinstance(weight_value, (int, float)):
        value = float(weight_value)
        if value <= 0:
            return None
        return value if value <= 1 else value / 100.0

    text = str(weight_value).strip()
    if not text:
        return None

    percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if percent_match:
        return float(percent_match.group(1)) / 100.0

    score_match = re.search(r"(\d+(?:\.\d+)?)\s*分", text)
    if score_match:
        # 按总分100近似换算
        return float(score_match.group(1)) / 100.0

    num_match = re.search(r"\d+(?:\.\d+)?", text)
    if num_match:
        value = float(num_match.group(0))
        return value if value <= 1 else value / 100.0
    return None

def _load_syllabus_analysis(syllabus_name: str) -> Optional[Dict[str, Any]]:
    if not syllabus_name:
        return None

    analysis_dir = _analysis_results_dir()
    if not os.path.exists(analysis_dir):
        return None

    candidate_files = []
    if syllabus_name.endswith(".json"):
        candidate_files.append(syllabus_name)
    else:
        base_name = os.path.splitext(syllabus_name)[0]
        candidate_files.append(f"{base_name}.json")
        candidate_files.append(syllabus_name)

    for file_name in candidate_files:
        file_path = os.path.join(analysis_dir, file_name)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
    return None

def _calculate_weighted_overall_score(dimension_scores: List[Dict[str, Any]], syllabus_analysis: Optional[Dict[str, Any]]) -> Optional[float]:
    if not dimension_scores or not syllabus_analysis:
        return None

    raw_weight_pairs: List[tuple[str, float]] = []

    for criterion in syllabus_analysis.get("evaluation_criteria", []) if isinstance(syllabus_analysis, dict) else []:
        if isinstance(criterion, dict):
            name = str(criterion.get("name", "")).strip()
            ratio = _parse_weight_to_ratio(criterion.get("weight"))
            if name and ratio:
                raw_weight_pairs.append((name, ratio))

    if not raw_weight_pairs:
        profile = syllabus_analysis.get("evaluation_weights", {}) if isinstance(syllabus_analysis, dict) else {}
        for item in profile.get("weights", []) if isinstance(profile, dict) else []:
            if isinstance(item, dict):
                name = str(item.get("dimension", "")).strip()
                ratio = _parse_weight_to_ratio(item.get("weight"))
                if name and ratio:
                    raw_weight_pairs.append((name, ratio))

    if not raw_weight_pairs:
        return None

    total_ratio = sum(w for _, w in raw_weight_pairs)
    if total_ratio <= 0:
        return None
    normalized_weights = [(name, w / total_ratio) for name, w in raw_weight_pairs]

    weighted_sum = 0.0
    matched_weight_sum = 0.0
    unmatched_scores: List[float] = []

    for score_info in dimension_scores:
        if not isinstance(score_info, dict):
            continue
        dim_name = str(score_info.get("dimension", "")).strip()
        score = float(score_info.get("score", 0.0))
        matched = False

        for weight_name, weight_ratio in normalized_weights:
            if dim_name and (dim_name in weight_name or weight_name in dim_name):
                weighted_sum += score * weight_ratio
                matched_weight_sum += weight_ratio
                matched = True
                break
        if not matched:
            unmatched_scores.append(score)

    remaining_ratio = max(0.0, 1.0 - matched_weight_sum)
    if unmatched_scores and remaining_ratio > 0:
        avg_unmatched = sum(unmatched_scores) / len(unmatched_scores)
        weighted_sum += avg_unmatched * remaining_ratio
        matched_weight_sum += remaining_ratio

    if matched_weight_sum <= 0:
        return None
    return round(weighted_sum / matched_weight_sum, 2)

# 文档内容提取函数
def extract_document_content(file_path: str) -> str:
    """提取文档内容"""
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == ".pdf":
            return extract_pdf_content(file_path)
        elif file_ext == ".docx":
            return extract_docx_content(file_path)
        elif file_ext == ".doc":
            return extract_doc_content(file_path)
        elif file_ext == ".txt":
            return extract_txt_content(file_path)
        else:
            return ""
    except Exception as e:
        logger.error(f"提取文件内容失败: {str(e)}")
        return ""

def extract_pdf_content(file_path: str) -> str:
    """提取PDF文件内容"""
    try:
        import PyPDF2
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text()
            return text
    except Exception as e:
        logger.error(f"提取PDF内容失败: {str(e)}")
        return ""

def extract_docx_content(file_path: str) -> str:
    """提取DOCX文件内容"""
    try:
        from docx import Document
        doc = Document(file_path)
        paragraph_texts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        table_lines: List[str] = []
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells if cell.text and cell.text.strip()]
                if cells:
                    table_lines.append(" | ".join(cells))
        return "\n".join(paragraph_texts + table_lines)
    except Exception as e:
        logger.error(f"提取DOCX内容失败: {str(e)}")
        return ""

def extract_doc_content(file_path: str) -> str:
    """提取DOC文件内容"""
    try:
        import docx2txt
        text = docx2txt.process(file_path)
        return text
    except Exception as e:
        logger.error(f"提取DOC内容失败: {str(e)}")
        return ""

def extract_txt_content(file_path: str) -> str:
    """提取TXT文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    except Exception as e:
        logger.error(f"提取TXT内容失败: {str(e)}")
        return ""

# 初始化数据库
init_db()

app = FastAPI(
    title="学生多维度能力评估系统 API",
    description="基于 OpenAI GPT-4o 和 CrewAI 的学生能力评估系统",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置文件上传大小限制
app.max_request_size = 500 * 1024 * 1024  # 500MB

# 确保上传目录存在
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 创建数据库表
from src.database.database import Base, engine
Base.metadata.create_all(bind=engine)

# 依赖项
def get_database_service(db: Session = Depends(get_db)) -> DatabaseService:
    return DatabaseService(db)

# 根路径 - API 欢迎页面
@app.get("/")
async def root():
    return {
        "message": "欢迎使用学生多维度能力评估系统 API",
        "version": "1.0.0",
        "docs": "http://localhost:8000/docs",
        "health": "http://localhost:8000/health",
        "endpoints": {
            "students": "/students",
            "submissions": "/submissions",
            "evaluations": "/evaluate",
            "files": "/submissions/{submission_id}/files"
        }
    }

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# 学生相关路由
@app.post("/students", response_model=StudentResponse)
async def create_student(
    student: StudentCreate,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 检查学生是否已存在
    existing_student = db_service.get_student_by_id(student.student_id)
    if existing_student:
        raise HTTPException(status_code=400, detail="学生已存在")
    
    # 创建学生
    new_student = db_service.create_student(
        student_id=student.student_id,
        name=student.name,
        age=student.age,
        grade=student.grade,
        major=student.major
    )
    
    return StudentResponse(
        id=new_student.id,
        student_id=new_student.student_id,
        name=new_student.name,
        age=new_student.age,
        grade=new_student.grade,
        major=new_student.major,
        created_at=new_student.created_at,
        updated_at=new_student.updated_at
    )

@app.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    student = db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    return StudentResponse(
        id=student.id,
        student_id=student.student_id,
        name=student.name,
        age=student.age,
        grade=student.grade,
        major=student.major,
        created_at=student.created_at,
        updated_at=student.updated_at
    )

@app.get("/students", response_model=List[StudentResponse])
async def get_all_students(
    skip: int = 0,
    limit: int = 100,
    db_service: DatabaseService = Depends(get_database_service)
):
    students = db_service.get_all_students(skip=skip, limit=limit)
    return [
        StudentResponse(
            id=student.id,
            student_id=student.student_id,
            name=student.name,
            age=student.age,
            grade=student.grade,
            major=student.major,
            created_at=student.created_at,
            updated_at=student.updated_at
        )
        for student in students
    ]

@app.put("/students/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: str,
    student_update: StudentUpdate,
    db_service: DatabaseService = Depends(get_database_service)
):
    student = db_service.update_student(
        student_id=student_id,
        **student_update.dict(exclude_unset=True)
    )
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    return StudentResponse(
        id=student.id,
        student_id=student.student_id,
        name=student.name,
        age=student.age,
        grade=student.grade,
        major=student.major,
        created_at=student.created_at,
        updated_at=student.updated_at
    )

@app.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    try:
        deleted = db_service.delete_student(student_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="学生不存在")
        
        return {"message": "学生删除成功"}
    except Exception as e:
        logger.error(f"删除学生失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除学生失败: {str(e)}")

# 提交相关路由
@app.post("/submissions", response_model=SubmissionResponse)
async def create_submission(
    submission: SubmissionCreate,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 检查学生是否存在（如果提供了 student_id）
    student = None
    if submission.student_id:
        student = db_service.get_student_by_id(submission.student_id)
        if not student:
            raise HTTPException(status_code=404, detail="学生不存在")
    
    # 验证提交类型
    if submission.submission_type == SubmissionType.TEXT and not submission.text_content:
        raise HTTPException(status_code=400, detail="文字提交必须提供内容")

    # 验证课程大纲分析文件是否可用
    if submission.syllabus_name:
        if not _load_syllabus_analysis(submission.syllabus_name):
            raise HTTPException(status_code=400, detail=f"课程大纲分析结果不存在或不可读: {submission.syllabus_name}")
    
    # 创建提交
    new_submission = db_service.create_submission(
        title=submission.title,
        description=submission.description,
        student_id=submission.student_id,
        submission_type=submission.submission_type.value,
        submission_purpose=submission.submission_purpose.value,
        text_content=submission.text_content,
        syllabus_name=submission.syllabus_name
    )
    
    return SubmissionResponse(
        id=new_submission.id,
        submission_id=new_submission.submission_id,
        student_id=student.student_id if student else None,
        title=new_submission.title,
        description=new_submission.description,
        submission_type=SubmissionType(new_submission.submission_type),
        submission_purpose=SubmissionPurpose(new_submission.submission_purpose),
        text_content=new_submission.text_content,
        syllabus_name=new_submission.syllabus_name,
        status=SubmissionStatus(new_submission.status),
        created_at=new_submission.created_at,
        updated_at=new_submission.updated_at
    )

@app.get("/submissions", response_model=List[SubmissionResponse])
async def get_all_submissions(
    skip: int = 0,
    limit: int = 100,
    db_service: DatabaseService = Depends(get_database_service)
):
    submissions = db_service.get_all_submissions(skip=skip, limit=limit)
    
    result = []
    for submission in submissions:
        student = None
        if submission.student_id:
            student = db_service.get_student_by_internal_id(submission.student_id)
        
        result.append(SubmissionResponse(
            id=submission.id,
            submission_id=submission.submission_id,
            student_id=student.student_id if student else None,
            title=submission.title,
            description=submission.description,
            submission_type=SubmissionType(submission.submission_type),
            submission_purpose=SubmissionPurpose(getattr(submission, 'submission_purpose', 'normal')),
            text_content=submission.text_content,
            syllabus_name=getattr(submission, "syllabus_name", None),
            status=SubmissionStatus(submission.status),
            created_at=submission.created_at,
            updated_at=submission.updated_at
        ))
    
    return result

@app.get("/submissions/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    submission = db_service.get_submission_by_id(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")
    
    student = None
    if submission.student_id:
        student = db_service.get_student_by_internal_id(submission.student_id)
        if not student:
            raise HTTPException(status_code=404, detail="学生不存在")
    
    return SubmissionResponse(
        id=submission.id,
        submission_id=submission.submission_id,
        student_id=student.student_id if student else None,
        title=submission.title,
        description=submission.description,
        submission_type=SubmissionType(submission.submission_type),
        submission_purpose=SubmissionPurpose(getattr(submission, 'submission_purpose', 'normal')),
        text_content=submission.text_content,
        syllabus_name=getattr(submission, "syllabus_name", None),
        status=SubmissionStatus(submission.status),
        created_at=submission.created_at,
        updated_at=submission.updated_at
    )

@app.get("/students/{student_id}/submissions", response_model=List[SubmissionResponse])
async def get_student_submissions(
    student_id: str,
    skip: int = 0,
    limit: int = 100,
    db_service: DatabaseService = Depends(get_database_service)
):
    submissions = db_service.get_submissions_by_student_id(student_id, skip=skip, limit=limit)
    
    return [
        SubmissionResponse(
            id=submission.id,
            submission_id=submission.submission_id,
            student_id=student_id,
            title=submission.title,
            description=submission.description,
            submission_type=SubmissionType(submission.submission_type),
            submission_purpose=SubmissionPurpose(getattr(submission, 'submission_purpose', 'normal')),
            text_content=submission.text_content,
            syllabus_name=getattr(submission, "syllabus_name", None),
            status=SubmissionStatus(submission.status),
            created_at=submission.created_at,
            updated_at=submission.updated_at
        )
        for submission in submissions
    ]

@app.delete("/submissions/{submission_id}")
async def delete_submission(
    submission_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """删除提交记录及其相关的媒体文件和评估结果"""
    deleted = db_service.delete_submission(submission_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="提交不存在")
    
    return {"message": "提交删除成功"}

# 手写文字识别路由
@app.post("/handwriting-recognize")
async def handwriting_recognize(
    student_id: str = Form(...),
    app_id: str = Form(...),
    api_key: str = Form(...),
    secret_key: str = Form(...),
    file: UploadFile = File(...),
    db_service: DatabaseService = Depends(get_database_service)
):
    """识别手写文字"""
    # 检查学生是否存在
    student = db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    # 保存上传的图片
    file_path = os.path.join(UPLOAD_DIR, f"handwriting_{student_id}_{file.filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 检查文件类型
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".pdf"]:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        
        # 处理PDF文件
        if file_ext == ".pdf":
            # 使用PyMuPDF将PDF转换为图片，然后调用百度OCR识别
            logger.info("开始处理PDF文件")
            recognized_text = ""
            
            try:
                # 使用PyMuPDF将PDF转换为图片
                logger.info("使用PyMuPDF将PDF转换为图片")
                import fitz
                
                # 打开PDF文件
                doc = fitz.open(file_path)
                page_count = len(doc)
                logger.info(f"PDF文件共 {page_count} 页")
                
                # 将每一页转换为图片并调用百度OCR
                for page_num in range(page_count):
                    page = doc[page_num]
                    
                    # 将页面转换为图片
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 使用2倍分辨率提高识别率
                    img_data = pix.tobytes("png")
                    
                    # 调用百度OCR的手写文字识别接口
                    from aip import AipOcr
                    client = AipOcr(app_id, api_key, secret_key)
                    result = client.handwriting(img_data)
                    
                    # 打印识别结果用于调试
                    logger.info(f"第{page_num+1}页识别结果: {result}")
                    
                    # 提取识别结果
                    if 'words_result' in result and result['words_result']:
                        page_text = '\n'.join([item['words'] for item in result['words_result']])
                        recognized_text += f"第{page_num+1}页:\n{page_text}\n\n"
                    else:
                        # 如果没有识别到文字，记录错误信息
                        error_msg = result.get('error_msg', '未知错误')
                        error_code = result.get('error_code', '未知错误码')
                        logger.warning(f"第{page_num+1}页识别失败: {error_msg} (错误码: {error_code})")
                
                # 关闭PDF文档
                doc.close()
                
                logger.info(f"PDF识别完成，共处理 {page_count} 页")
                
                if not recognized_text:
                    raise HTTPException(status_code=400, detail="PDF文件中未提取到文字，请确保PDF包含可识别的文字内容")
                
                confidence = 90.0
                logger.info("PDF处理完成")
            except Exception as e:
                logger.error(f"PDF处理失败: {str(e)}")
                import traceback
                error_detail = traceback.format_exc()
                logger.error(f"详细错误: {error_detail}")
                raise HTTPException(status_code=500, detail=f"PDF处理失败: {str(e)}")
        else:
            # 使用百度OCR进行手写文字识别
            from aip import AipOcr
            
            # 使用前端传递的百度OCR API配置
            # 初始化百度OCR客户端
            client = AipOcr(app_id, api_key, secret_key)
            
            # 读取图片文件
            with open(file_path, 'rb') as f:
                image = f.read()
            
            # 调用百度OCR的手写文字识别接口
            result = client.handwriting(image)
            
            # 提取识别结果
            if 'words_result' in result:
                recognized_text = '\n'.join([item['words'] for item in result['words_result']])
                confidence = 95.0
            else:
                error_msg = result.get('error_msg', '未知错误')
                error_code = result.get('error_code', '未知错误码')
                raise HTTPException(status_code=400, detail=f"百度OCR识别失败：{error_msg} (错误码: {error_code})")
        
        # 保存识别记录
        record = {
            "student_id": student_id,
            "file_name": file.filename,
            "recognized_text": recognized_text,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }
        db_service.add_handwriting_record(record)
        
        return {
            "student_id": student_id,
            "recognized_text": recognized_text,
            "confidence": confidence,
            "file_name": file.filename
        }
    except HTTPException:
        # 清理临时文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise
    except Exception as e:
        # 清理临时文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        # 记录详细错误信息
        import traceback
        error_detail = traceback.format_exc()
        print(f"识别失败: {error_detail}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
    finally:
        # 清理临时文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

# 文件上传路由
@app.post("/submissions/{submission_id}/files", response_model=MediaFileResponse)
async def upload_file(
    submission_id: str,
    file: UploadFile = File(...),
    db_service: DatabaseService = Depends(get_database_service)
):
    # 检查提交是否存在（submission_id 为 SUB_XXXXXX 格式）
    submission = db_service.get_submission_by_id(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存在")

    # 文件类型判断
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext in [".pdf", ".docx", ".doc", ".txt", ".ppt", ".pptx"]:
        media_type = "document"
    elif file_ext in [".mp4", ".mov"]:
        media_type = "video"
    elif file_ext in [".mp3", ".wav"]:
        media_type = "audio"
    else:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    # 保存文件（避免重名覆盖）
    safe_name = os.path.basename(file.filename)
    unique_name = f"{submission_id}_{uuid.uuid4().hex[:8]}_{safe_name}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 获取文件大小
    size_bytes = os.path.getsize(file_path)

    # 创建媒体文件记录
    media_file = db_service.create_media_file(
        submission_id=submission_id,
        file_path=file_path,
        file_name=safe_name,
        media_type=media_type,
        size_bytes=size_bytes
    )

    # 尝试提取文档内容并自动判别课程类型（失败不影响上传主流程）
    if media_type == "document":
        try:
            extracted_text = ""
            if file_ext in [".pdf", ".docx", ".doc", ".txt"]:
                extracted_text = extract_document_content(file_path)

            if extracted_text:
                existing_content = submission.text_content or ""
                submission.text_content = (existing_content + "\n\n" + extracted_text).strip() if existing_content else extracted_text

                detected_type = classify_course_type(extracted_text)
                submission.course_type = detected_type

                db_service.db.commit()
                db_service.db.refresh(submission)
        except Exception as e:
            logger.warning(f"文件上传后自动提取/分类失败，不影响主流程: {str(e)}")

    return MediaFileResponse(
        id=media_file.id,
        submission_id=media_file.submission_id,
        file_path=media_file.file_path,
        file_name=media_file.file_name,
        media_type=media_file.media_type,
        size_bytes=media_file.size_bytes,
        duration=media_file.duration,
        processed=media_file.processed,
        uploaded_at=media_file.created_at
    )

@app.get("/submissions/{submission_id}/files", response_model=List[MediaFileResponse])
async def get_submission_files(
    submission_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    media_files = db_service.get_media_files_by_submission_id(submission_id)
    
    return [
        MediaFileResponse(
            id=file.id,
            submission_id=file.submission_id,
            file_path=file.file_path,
            file_name=file.file_name,
            media_type=file.media_type,
            size_bytes=file.size_bytes,
            duration=file.duration,
            processed=file.processed,
            uploaded_at=file.created_at
        )
        for file in media_files
    ]

# 文件修改路由
@app.put("/files/{file_id}", response_model=MediaFileResponse)
async def update_file(
    file_id: int,
    file_name: str = Form(..., description="文件名"),
    media_type: str = Form(..., description="文件类型") ,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 验证输入
    if not file_name or not media_type:
        raise HTTPException(status_code=400, detail="文件名和文件类型为必填项")
    
    # 检查文件是否存在
    media_file = db_service.get_media_file_by_id(file_id)
    if not media_file:
        raise HTTPException(status_code=404, detail=f"文件ID {file_id} 不存在")
    
    try:
        # 更新文件信息
        updated_file = db_service.update_media_file(
            file_id=file_id,
            file_name=file_name,
            media_type=media_type
        )
        
        return MediaFileResponse(
            id=updated_file.id,
            submission_id=updated_file.submission_id,
            file_path=updated_file.file_path,
            file_name=updated_file.file_name,
            media_type=updated_file.media_type,
            size_bytes=updated_file.size_bytes,
            duration=updated_file.duration,
            processed=updated_file.processed,
            uploaded_at=updated_file.created_at
        )
    except Exception as e:
        logger.error(f"更新文件信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新文件信息失败: {str(e)}")

# 文件删除路由
@app.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    db_service: DatabaseService = Depends(get_database_service)
):
    deleted = db_service.delete_media_file(file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return {"message": "文件删除成功"}

# 评估相关路由
@app.post("/analyze_syllabus")
async def analyze_syllabus(
    request: Dict = Body(...)
):
    """
    使用大模型分析课程大纲
    自动检测文档类型并使用对应的提示词进行分析
    """
    try:
        from src.evaluation.llm_evaluator import llm_evaluator
        from src.evaluation.syllabus_analyzer import SyllabusAnalyzer

        syllabus_content = (request.get("syllabus_content", "") or "").strip()
        syllabus_name = request.get("syllabus_name", "")
        if not syllabus_content:
            raise HTTPException(status_code=400, detail="大纲内容为空，无法分析")

        # 规则提取（严格文本依据）
        rule_ability_points = _extract_text_based_ability_points(syllabus_content)
        rule_knowledge_points = _extract_text_based_knowledge_points(syllabus_content)
        manual_course_type = (request.get("course_type_override", "") or "").strip()
        course_type_meta = classify_course_type_with_meta(syllabus_content)
        if manual_course_type in ["理论课", "实践课"]:
            course_type = manual_course_type
            course_type_source = "manual"
        else:
            course_type = course_type_meta.get("course_type", "理论课")
            course_type_source = "auto"

        analyzer = SyllabusAnalyzer("")
        doc_type = analyzer.detect_document_type(syllabus_content)
        logger.info(
            f"检测到文档类型: {doc_type}, 课程类型: {course_type}, 来源: {course_type_source}, "
            f"理论分: {course_type_meta.get('theory_score')}, 实践分: {course_type_meta.get('practice_score')}"
        )

        if doc_type == "graduation_requirements":
            prompt = analyzer.build_graduation_requirements_prompt(syllabus_content)
        elif doc_type == "course_evaluation":
            prompt = analyzer.build_course_evaluation_prompt(syllabus_content)
        else:
            prompt = analyzer.build_syllabus_analysis_prompt(syllabus_content)

        strict_suffix = """

【严格约束】
1) ability_points 仅能来自“毕业要求指标点”表格；每项只保留 description（可做等价改写），不得输出 level。
2) evaluation_criteria 必须按能力点逐一生成，每个能力点恰好3条标准（standards数组长度=3）。
3) 不得返回“课程教学目标与毕业要求对应关系、课程内容/学时分配、立德树人”等章节标题作为能力点。
4) 评价标准禁止使用重复套话模板（如“能准确说明并正确应用……”的机械复用），三条标准需体现层次递进（基础理解→应用实施→分析改进）。
5) 每条标准都要包含：评价对象、达成条件、判定依据，语言要自然、专业、可执行。
6) knowledge_points 应优先从“二、课程内容、教学要求、学时分配和教学手段”表格中的“知识点/能力点”列提取。
7) 可结合课程场景补充合理细节，但不得偏离能力点原意。
8) 不得虚构文档不存在的毕业要求指标点；若无法定位则返回空数组。
9) 结果优先准确性，不追求数量。
"""
        analysis_result: Dict[str, Any] = {}
        llm_error = None
        try:
            result = llm_evaluator.generate_report(prompt + strict_suffix, max_tokens=4000)
            try:
                analysis_result = json.loads(result)
            except Exception:
                start_idx = result.find("{")
                end_idx = result.rfind("}") + 1
                if start_idx != -1 and end_idx != -1:
                    analysis_result = json.loads(result[start_idx:end_idx])
        except Exception as e:
            llm_error = str(e)
            logger.warning(f"大模型分析失败，回退到文本规则提取: {llm_error}")

        llm_ability_points = analysis_result.get("ability_points", []) if isinstance(analysis_result, dict) else []
        llm_evaluation_criteria = analysis_result.get("evaluation_criteria", []) if isinstance(analysis_result, dict) else []
        llm_knowledge_points = analysis_result.get("knowledge_points", []) if isinstance(analysis_result, dict) else []
        graduation_requirements = analysis_result.get("graduation_requirements", []) if isinstance(analysis_result, dict) else []

        normalized_ability_points: List[Dict[str, Any]] = []
        # 优先采用规则提取（可稳定拿到“毕业要求指标点”列中的能力点名称）
        source_points = rule_ability_points if rule_ability_points else llm_ability_points
        for item in source_points:
            if isinstance(item, dict):
                desc = item.get("description") or item.get("name") or ""
                if not desc:
                    continue
                ability_name = str(item.get("name", "")).strip()
                desc = re.sub(r"\s+", "", str(desc)).strip()
                if not _is_valid_ability_description(desc):
                    continue
                normalized_ability_points.append({
                    "name": re.sub(r"\s+", "", ability_name) if ability_name else "",
                    "description": desc
                })
            elif isinstance(item, str) and item.strip():
                text = re.sub(r"\s+", "", item).strip()
                if _is_valid_ability_description(text):
                    normalized_ability_points.append({
                        "name": "",
                        "description": text
                    })

        if not normalized_ability_points:
            normalized_ability_points = rule_ability_points

        # 评价标准兜底：若模型缺失或不完整，按能力点补齐每项三条
        rule_evaluation_criteria = _extract_text_based_evaluation_criteria(normalized_ability_points)
        normalized_evaluation_criteria: List[Dict[str, Any]] = []
        source_criteria = llm_evaluation_criteria if llm_evaluation_criteria else rule_evaluation_criteria

        llm_criteria_map: Dict[str, Dict[str, Any]] = {}
        for item in source_criteria:
            if isinstance(item, dict):
                desc = item.get("ability_description") or item.get("description") or item.get("standard") or item.get("name") or ""
                if not desc:
                    continue
                standards = item.get("standards", [])
                if isinstance(standards, str):
                    standards = [s.strip() for s in re.split(r"[；;\n]+", standards) if s.strip()]
                if not isinstance(standards, list):
                    standards = []
                standards = [str(s).strip() for s in standards if str(s).strip()]
                if len(standards) < 3:
                    fallback = item.get("standard", "")
                    if fallback:
                        standards.append(str(fallback).strip())
                llm_criteria_map[re.sub(r"\s+", "", desc)] = {
                    "ability_description": desc,
                    "standards": standards[:3]
                }
            elif isinstance(item, str) and item.strip():
                text = item.strip()
                llm_criteria_map[re.sub(r"\s+", "", text)] = {
                    "ability_description": text,
                    "standards": [text]
                }

        rule_criteria_map = {
            re.sub(r"\s+", "", str(item.get("ability_description", ""))): item
            for item in rule_evaluation_criteria
            if isinstance(item, dict) and item.get("ability_description")
        }

        for idx, ability in enumerate(normalized_ability_points, 1):
            ability_desc = str(ability.get("description", "")).strip() if isinstance(ability, dict) else str(ability).strip()
            if not ability_desc:
                continue
            key = re.sub(r"\s+", "", ability_desc)
            matched = llm_criteria_map.get(key) or next(
                (v for k, v in llm_criteria_map.items() if key in k or k in key),
                None
            )
            fallback_item = rule_criteria_map.get(key) or next(
                (v for k, v in rule_criteria_map.items() if key in k or k in key),
                None
            )

            standards: List[str] = []
            if matched:
                standards = matched.get("standards", [])
            if len(standards) < 3 and fallback_item:
                for s in fallback_item.get("standards", []):
                    if s and s not in standards:
                        standards.append(s)
            if len(standards) < 3:
                standards.extend([
                    f"能准确理解并表达“{ability_desc}”对应的核心要求。",
                    f"能在作业中正确应用“{ability_desc}”并给出有效过程与结果。",
                    f"能基于“{ability_desc}”完成自检与改进，结果可验证。"
                ])
            standards = standards[:3]
            normalized_evaluation_criteria.append({
                "ability_description": ability_desc,
                "name": f"能力点{idx}评价标准",
                "description": f"围绕能力点“{ability_desc}”的评价标准",
                "standards": standards,
                "standard": "\n".join([f"{i + 1}. {s}" for i, s in enumerate(standards)])
            })

        normalized_knowledge_points: List[str] = []
        source_knowledge_points = llm_knowledge_points if isinstance(llm_knowledge_points, list) and llm_knowledge_points else rule_knowledge_points
        seen_kp = set()
        for item in source_knowledge_points:
            if isinstance(item, dict):
                point = str(item.get("name") or item.get("description") or "").strip()
            else:
                point = str(item).strip()
            point = re.sub(r"\s+", "", point)
            if not point or len(point) < 2 or point in seen_kp:
                continue
            seen_kp.add(point)
            normalized_knowledge_points.append(point)

        has_content = bool(normalized_ability_points or normalized_evaluation_criteria or graduation_requirements)
        if not has_content:
            raise Exception("未获取到有效的分析结果")

        return {
            "syllabus_name": syllabus_name,
            "document_type": doc_type,
            "course_type": course_type,
            "course_type_source": course_type_source,
            "course_type_meta": course_type_meta,
            "strict_text_based": True,
            "ability_points": normalized_ability_points,
            "evaluation_criteria": normalized_evaluation_criteria,
            "knowledge_points": normalized_knowledge_points,
            "graduation_requirements": graduation_requirements if isinstance(graduation_requirements, list) else [],
            "evaluation_weights": _get_course_weight_profile(course_type),
            "llm_error": llm_error
        }
    except Exception as e:
        # 直接返回错误，不使用模拟数据
        error_message = str(e)
        if "API密钥未设置" in error_message:
            raise HTTPException(status_code=400, detail=f"大纲分析失败: API密钥未设置，请在AI设置页面中配置API密钥")
        elif "400" in error_message or "Bad Request" in error_message:
            raise HTTPException(status_code=400, detail=f"大纲分析失败: 请求参数错误，请检查输入内容")
        elif "timeout" in error_message.lower() or "timed out" in error_message.lower():
            raise HTTPException(status_code=504, detail=f"大纲分析失败: 请求超时，请稍后重试")
        else:
            raise HTTPException(status_code=500, detail=f"大纲分析失败: {error_message}")

@app.post("/analyze_graduation_project")
async def analyze_graduation_project(
    request: Dict = Body(...)
):
    """
    多轮迭代分析毕业设计大纲
    通过三轮调用大模型，逐步完善评价提示词
    """
    try:
        from src.evaluation.llm_evaluator import llm_evaluator
        from src.evaluation.syllabus_analyzer import SyllabusAnalyzer
        
        syllabus_content = request.get('syllabus_content', '')
        syllabus_name = request.get('syllabus_name', '')
        max_rounds = request.get('max_rounds', 3)
        
        analyzer = SyllabusAnalyzer("")
        results = {
            "syllabus_name": syllabus_name,
            "rounds": [],
            "final_result": None
        }
        
        # 第一轮：初步分析
        print(f"开始第一轮分析: {syllabus_name}")
        round1_prompt = analyzer.build_graduation_project_initial_analysis_prompt(syllabus_content)
        round1_result = llm_evaluator.generate_report(round1_prompt, max_tokens=3000)
        
        try:
            initial_result = json.loads(round1_result)
            results["rounds"].append({
                "round": 1,
                "type": "initial_analysis",
                "result": initial_result
            })
            print(f"第一轮分析完成")
        except Exception as e:
            raise Exception(f"第一轮分析结果解析失败: {str(e)}")
        
        # 第二轮：详细分析
        print(f"开始第二轮分析: {syllabus_name}")
        round2_prompt = analyzer.build_graduation_project_detailed_analysis_prompt(syllabus_content, initial_result)
        round2_result = llm_evaluator.generate_report(round2_prompt, max_tokens=4000)
        
        try:
            detailed_result = json.loads(round2_result)
            results["rounds"].append({
                "round": 2,
                "type": "detailed_analysis",
                "result": detailed_result
            })
            print(f"第二轮分析完成")
        except Exception as e:
            raise Exception(f"第二轮分析结果解析失败: {str(e)}")
        
        # 第三轮：提示词优化
        if max_rounds >= 3:
            print(f"开始第三轮分析: {syllabus_name}")
            round3_prompt = analyzer.build_graduation_project_prompt_refinement_prompt(syllabus_content, detailed_result)
            round3_result = llm_evaluator.generate_report(round3_prompt, max_tokens=4000)
            
            try:
                refined_result = json.loads(round3_result)
                results["rounds"].append({
                    "round": 3,
                    "type": "prompt_refinement",
                    "result": refined_result
                })
                print(f"第三轮分析完成")
                
                # 使用优化后的结果作为最终结果
                results["final_result"] = {
                    "ability_points": refined_result.get("optimized_ability_points", []),
                    "evaluation_criteria": refined_result.get("optimized_evaluation_criteria", []),
                    "evaluation_prompt_template": refined_result.get("evaluation_prompt_template", ""),
                    "optimization_notes": refined_result.get("optimization_notes", "")
                }
            except Exception as e:
                # 如果第三轮失败，使用第二轮结果
                print(f"第三轮分析结果解析失败: {str(e)}，使用第二轮结果")
                results["final_result"] = detailed_result
        else:
            results["final_result"] = detailed_result
        
        return results
        
    except Exception as e:
        error_message = str(e)
        if "API密钥未设置" in error_message:
            raise HTTPException(status_code=400, detail=f"毕业设计分析失败: API密钥未设置，请在AI设置页面中配置API密钥")
        elif "400" in error_message or "Bad Request" in error_message:
            raise HTTPException(status_code=400, detail=f"毕业设计分析失败: 请求参数错误，请检查输入内容")
        elif "timeout" in error_message.lower() or "timed out" in error_message.lower():
            raise HTTPException(status_code=504, detail=f"毕业设计分析失败: 请求超时，请稍后重试")
        else:
            raise HTTPException(status_code=500, detail=f"毕业设计分析失败: {error_message}")

@app.post("/evaluate_graduation_project")
async def evaluate_graduation_project(
    request: Dict = Body(...)
):
    """
    使用确定性评价标准评价毕业设计
    自动检测项目类型并使用对应的评价标准
    """
    try:
        from src.evaluation.llm_evaluator import llm_evaluator
        from src.evaluation.evaluation_standards import (
            ProjectType,
            PROJECT_TYPE_NAMES,
            detect_project_type
        )
        
        submission_content = request.get('submission_content', '')
        project_type = request.get('project_type', None)
        student_info = request.get('student_info', {})
        guidance_content = request.get('guidance_content', None)
        
        if not submission_content:
            raise HTTPException(status_code=400, detail="提交内容不能为空")
        
        title = student_info.get("title", "") if student_info else ""
        
        if project_type:
            try:
                detected_type = ProjectType(project_type)
            except ValueError:
                detected_type = detect_project_type(title, submission_content)
        else:
            detected_type = detect_project_type(title, submission_content)
        
        type_name = PROJECT_TYPE_NAMES.get(detected_type, "未知类型")
        print(f"检测到项目类型: {type_name}")
        
        result = llm_evaluator.evaluate_with_deterministic_standards(
            submission_content=submission_content,
            project_type=detected_type.value,
            student_info=student_info,
            guidance_content=guidance_content
        )
        
        result["detected_project_type"] = detected_type.value
        result["project_type_name"] = type_name
        
        return result
        
    except Exception as e:
        error_message = str(e)
        if "API密钥未设置" in error_message:
            raise HTTPException(status_code=400, detail=f"评价失败: API密钥未设置，请在AI设置页面中配置API密钥")
        elif "400" in error_message or "Bad Request" in error_message:
            raise HTTPException(status_code=400, detail=f"评价失败: 请求参数错误，请检查输入内容")
        elif "timeout" in error_message.lower() or "timed out" in error_message.lower():
            raise HTTPException(status_code=504, detail=f"评价失败: 请求超时，请稍后重试")
        else:
            raise HTTPException(status_code=500, detail=f"评价失败: {error_message}")

@app.get("/project_types")
async def get_project_types():
    """
    获取所有项目类型
    """
    from src.evaluation.evaluation_standards import ProjectType, PROJECT_TYPE_NAMES, EVALUATION_STANDARDS
    
    types = []
    for pt in ProjectType:
        if pt != ProjectType.UNKNOWN:
            type_config = EVALUATION_STANDARDS.get(pt.value, {})
            types.append({
                "value": pt.value,
                "name": PROJECT_TYPE_NAMES.get(pt, "未知类型"),
                "description": type_config.get("description", ""),
                "indicators_count": len(type_config.get("indicators", []))
            })
    
    return {"project_types": types}

@app.get("/evaluation_standards/{project_type}")
async def get_evaluation_standards_by_type(project_type: str):
    """
    获取指定项目类型的评价标准
    """
    from src.evaluation.evaluation_standards import (
        ProjectType,
        PROJECT_TYPE_NAMES,
        EVALUATION_STANDARDS
    )
    
    try:
        pt = ProjectType(project_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的项目类型: {project_type}")
    
    standards = EVALUATION_STANDARDS.get(pt.value)
    if not standards:
        raise HTTPException(status_code=404, detail=f"未找到项目类型 {project_type} 的评价标准")
    
    return {
        "project_type": pt.value,
        "project_type_name": PROJECT_TYPE_NAMES.get(pt, "未知类型"),
        "standards": standards
    }

@app.post("/extract_guidance_content")
async def extract_guidance_content(
    request: Dict = Body(...)
):
    """
    使用大模型提炼评价指导文件的内容
    """
    try:
        from src.evaluation.llm_evaluator import llm_evaluator
        
        file_content = request.get('file_content', '')
        file_name = request.get('file_name', '')
        
        if not file_content:
            raise HTTPException(status_code=400, detail="文件内容不能为空")
        
        result = llm_evaluator.extract_guidance_content(
            file_content=file_content,
            file_name=file_name
        )
        
        return result
        
    except Exception as e:
        error_message = str(e)
        if "API密钥未设置" in error_message:
            raise HTTPException(status_code=400, detail=f"提炼失败: API密钥未设置，请在AI设置页面中配置API密钥")
        elif "timeout" in error_message.lower() or "timed out" in error_message.lower():
            raise HTTPException(status_code=504, detail=f"提炼失败: 请求超时，请稍后重试")
        else:
            raise HTTPException(status_code=500, detail=f"提炼失败: {error_message}")

@app.post("/generate_evaluation_standards")
async def generate_evaluation_standards(
    request: Dict = Body(...)
):
    """
    使用大模型生成项目评价指标
    """
    try:
        from src.evaluation.llm_evaluator import llm_evaluator
        
        file_content = request.get('file_content', '')
        file_name = request.get('file_name', '')
        project_type = request.get('project_type', 'mixed')
        
        if not file_content:
            raise HTTPException(status_code=400, detail="文件内容不能为空")
        
        result = llm_evaluator.generate_evaluation_standards(
            file_content=file_content,
            file_name=file_name,
            project_type=project_type
        )
        
        return result
        
    except Exception as e:
        error_message = str(e)
        if "API密钥未设置" in error_message:
            raise HTTPException(status_code=400, detail=f"生成失败: API密钥未设置，请在AI设置页面中配置API密钥")
        elif "timeout" in error_message.lower() or "timed out" in error_message.lower():
            raise HTTPException(status_code=504, detail=f"生成失败: 请求超时，请稍后重试")
        else:
            raise HTTPException(status_code=500, detail=f"生成失败: {error_message}")

@app.get("/syllabus_files")
async def get_syllabus_files():
    """
    获取大纲管理页面的文件列表
    """
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    syllabus_folder = os.path.join(project_root, "评价大纲")
    
    if not os.path.exists(syllabus_folder):
        return {"files": [], "folder_path": syllabus_folder}
    
    files = []
    for f in os.listdir(syllabus_folder):
        if f.endswith('.docx') or f.endswith('.doc') or f.endswith('.pdf') or f.endswith('.txt'):
            file_path = os.path.join(syllabus_folder, f)
            files.append({
                "name": f,
                "path": file_path,
                "size": os.path.getsize(file_path),
                "modified": os.path.getmtime(file_path)
            })
    
    return {"files": files, "folder_path": syllabus_folder}

@app.post("/syllabus_files/upload")
async def upload_syllabus_file(file: UploadFile = File(...)):
    """
    上传课程大纲文件到 `评价大纲` 目录
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    syllabus_folder = os.path.join(project_root, "评价大纲")
    os.makedirs(syllabus_folder, exist_ok=True)

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    file_ext = os.path.splitext(file.filename)[1].lower()
    allowed_ext = {".docx", ".doc", ".pdf", ".txt", ".json"}
    if file_ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="不支持的文件格式，仅支持 docx/doc/pdf/txt/json")

    safe_name = os.path.basename(file.filename)
    target_path = os.path.join(syllabus_folder, safe_name)

    if os.path.exists(target_path):
        base_name, ext = os.path.splitext(safe_name)
        safe_name = f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        target_path = os.path.join(syllabus_folder, safe_name)

    try:
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        return {
            "message": "大纲上传成功",
            "file_name": safe_name,
            "path": target_path,
            "size": os.path.getsize(target_path)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"大纲上传失败: {str(e)}")

@app.post("/read_syllabus_file")
async def read_syllabus_file(
    request: Dict = Body(...)
):
    """
    读取大纲文件内容
    """
    import os
    file_name = request.get('file_name', '')
    
    if not file_name:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = os.path.join(project_root, "评价大纲", file_name)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_name}")
    
    try:
        if file_name.endswith('.docx'):
            from docx import Document
            doc = Document(file_path)
            paragraph_text = [para.text.strip() for para in doc.paragraphs if para.text and para.text.strip()]
            table_text = []
            for table in doc.tables:
                for row in table.rows:
                    cells = [cell.text.strip().replace("\n", " ") for cell in row.cells if cell.text and cell.text.strip()]
                    if cells:
                        table_text.append(" | ".join(cells))
            content = "\n".join(paragraph_text + table_text)
        elif file_name.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif file_name.endswith('.pdf'):
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                content = ""
                for page in reader.pages:
                    content += page.extract_text() + "\n"
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file_name}")
        
        return {"file_name": file_name, "content": content}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")

@app.post("/evaluate_with_rule_engine")
async def evaluate_with_rule_engine(
    request: Dict = Body(...)
):
    """
    使用规则引擎进行确定性评分
    确保相同输入产生相同输出，解决评价结果不一致问题
    """
    try:
        from src.evaluation.rule_engine import rule_engine
        
        submission_content = request.get('submission_content', '')
        indicators = request.get('indicators', {})
        student_info = request.get('student_info', {})
        
        if not submission_content:
            raise HTTPException(status_code=400, detail="提交内容不能为空")
        
        if not indicators:
            raise HTTPException(status_code=400, detail="评价指标不能为空，请先选择评价指标")
        
        rule_engine.load_rules_from_indicators(indicators)
        
        result = rule_engine.evaluate(submission_content)
        
        result["student_info"] = student_info
        result["evaluation_method"] = "rule_engine"
        result["is_deterministic"] = True
        
        strengths = []
        weaknesses = []
        
        for dim in result.get("dimension_scores", []):
            if dim.get("score", 0) >= 80:
                strengths.append(f"{dim.get('indicator_id', '')}表现良好({dim.get('score')}分)")
            elif dim.get("score", 0) < 60:
                weaknesses.append(f"{dim.get('indicator_id', '')}需要改进({dim.get('score')}分)")
        
        result["strengths"] = strengths if strengths else ["整体表现符合要求"]
        result["weaknesses"] = weaknesses if weaknesses else ["无明显短板"]
        
        return result
        
    except Exception as e:
        error_message = str(e)
        raise HTTPException(status_code=500, detail=f"规则引擎评分失败: {error_message}")

@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_submission(
    request: EvaluationRequest,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 使用大模型进行评估
    logger.info(f"开始评估提交: {request.submission_id}, 阶段: {request.stage}, 进度: {request.stage_progress}")
    
    try:
        # 检查提交是否存在
        submission = db_service.get_submission_by_id(request.submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="提交不存在")
        
        # 检查学生是否存在
        student = db_service.get_student_by_internal_id(submission.student_id)
        if not student:
            raise HTTPException(status_code=404, detail="学生不存在")
        
        # 导入大模型评估器
        from src.evaluation.llm_evaluator import llm_evaluator
        
        # 确定阶段进度（默认为0.5，即中期）
        stage_progress = request.stage_progress or 0.5
        # 确保进度值在0-1之间
        stage_progress = max(0.0, min(1.0, stage_progress))
        
        # 准备评估内容
        submission_content = submission.text_content or ""
        
        # 提取上传文件的内容
        media_files = db_service.get_media_files_by_submission_id(request.submission_id)
        logger.info(f"找到 {len(media_files)} 个媒体文件")
        if media_files:
            file_contents = []
            for media_file in media_files:
                logger.info(f"处理媒体文件: {media_file.file_name}, 类型: {media_file.media_type}, 路径: {media_file.file_path}")
                if media_file.media_type == "document":
                    file_content = extract_document_content(media_file.file_path)
                    logger.info(f"提取文件内容长度: {len(file_content)}")
                    if file_content:
                        file_contents.append(f"文件 {media_file.file_name} 的内容:\n{file_content}")
            
            if file_contents:
                logger.info(f"成功提取 {len(file_contents)} 个文件的内容")
                if submission_content:
                    submission_content += "\n\n" + "\n\n".join(file_contents)
                else:
                    submission_content = "\n\n".join(file_contents)
            else:
                logger.info("没有提取到文件内容")
        else:
            logger.info("没有找到媒体文件")
        
        # 如果仍然没有内容，返回错误
        if not submission_content or submission_content == "无内容":
            raise HTTPException(status_code=400, detail="提交内容为空，无法进行评估。请确保提交包含文件或文字内容。")
        
        # 准备学生信息
        student_info = {
            "student_id": student.student_id,
            "name": student.name,
            "grade": student.grade,
            "major": student.major
        }
        
        # 获取自定义提示词（如果有）
        custom_prompts = getattr(request, 'custom_prompts', None)
        
        # 优先使用提交绑定的大纲分析结果（确保评估严格按绑定课程大纲执行）
        syllabus_analysis = None
        if getattr(submission, "syllabus_name", None):
            syllabus_analysis = _load_syllabus_analysis(submission.syllabus_name)

        # 向后兼容：如果提交未绑定大纲，才允许请求传入
        if not syllabus_analysis:
            syllabus_analysis = getattr(request, 'syllabus_analysis', None)

        # 普通作业必须绑定课程大纲
        if submission.submission_purpose == SubmissionPurpose.NORMAL.value and not syllabus_analysis:
            raise HTTPException(
                status_code=400,
                detail="该提交未绑定可用课程大纲分析结果，请在作业上传时选择课程大纲后重试"
            )
        
        # 使用大模型进行评估
        evaluation_result = llm_evaluator.evaluate_submission(
            submission_content=submission_content,
            stage_progress=stage_progress,
            student_info=student_info,
            custom_prompts=custom_prompts,
            syllabus_analysis=syllabus_analysis
        )

        # 课程作业评分策略：
        # - 理论课：50%能力点评分 + 25%知识理解 + 25%知识应用
        # - 实践课：50%能力点评分 + 50%阶段完成度
        policy_overall = None
        if submission.submission_purpose == SubmissionPurpose.NORMAL.value:
            policy_overall = _calculate_course_assignment_overall_score(
                evaluation_result=evaluation_result,
                syllabus_analysis=syllabus_analysis,
                stage_progress=stage_progress
            )

        if policy_overall is not None:
            evaluation_result["overall_score"] = policy_overall
        else:
            # 非课程作业或缺少策略数据时，按大纲权重重算（若可用）
            weighted_overall = _calculate_weighted_overall_score(
                evaluation_result.get("dimension_scores", []),
                syllabus_analysis
            )
            if weighted_overall is not None:
                evaluation_result["overall_score"] = weighted_overall
        
        # 记录API接收到的评估结果
        print("=== API接收到的评估结果 ===")
        print(f"类型: {type(evaluation_result)}")
        print(f"内容: {evaluation_result}")
        print(f"dimension_scores类型: {type(evaluation_result.get('dimension_scores'))}")
        if 'dimension_scores' in evaluation_result:
            print(f"dimension_scores内容: {evaluation_result['dimension_scores']}")
        
        # 生成评估ID
        import uuid
        evaluation_id = f"EVAL_{uuid.uuid4().hex[:8].upper()}"
        
        # 保存评估结果到数据库
        # 确保strengths、areas_for_improvement和recommendations是列表
        strengths = evaluation_result.get("strengths", [])
        if not isinstance(strengths, list):
            strengths = [str(strengths)]
        
        # 处理weaknesses字段
        weaknesses = evaluation_result.get("weaknesses", [])
        if not isinstance(weaknesses, list):
            weaknesses = [str(weaknesses)]
        
        # 如果没有areas_for_improvement，使用weaknesses
        areas_for_improvement = evaluation_result.get("areas_for_improvement", weaknesses)
        if not isinstance(areas_for_improvement, list):
            areas_for_improvement = [str(areas_for_improvement)]
        
        recommendations = evaluation_result.get("recommendations", [])
        if not isinstance(recommendations, list):
            recommendations = [str(recommendations)]
        
        db_evaluation = db_service.create_evaluation_result(
            submission_id=request.submission_id,
            overall_score=evaluation_result["overall_score"],
            strengths=", ".join(strengths),
            areas_for_improvement=", ".join(areas_for_improvement),
            recommendations=", ".join(recommendations),
            stage=request.stage,
            stage_progress=stage_progress
        )
        
        # 保存维度评分
        from src.models.schemas import EvaluationDimension
        dimension_mapping = {
            "学术表现": EvaluationDimension.ACADEMIC_PERFORMANCE,
            "沟通能力": EvaluationDimension.COMMUNICATION_SKILLS,
            "领导力": EvaluationDimension.LEADERSHIP,
            "团队协作": EvaluationDimension.TEAMWORK,
            "创新能力": EvaluationDimension.CREATIVITY,
            "问题解决": EvaluationDimension.PROBLEM_SOLVING,
            "时间管理": EvaluationDimension.TIME_MANAGEMENT,
            "适应能力": EvaluationDimension.ADAPTABILITY,
            "技术能力": EvaluationDimension.TECHNICAL_SKILLS,
            "批判性思维": EvaluationDimension.CRITICAL_THINKING
        }
        
        # 构建维度评分响应
        dimension_scores_response = []
        dimension_scores = evaluation_result["dimension_scores"]
        
        # 现在dimension_scores总是列表格式
        print(f"处理dimension_scores，类型: {type(dimension_scores)}")
        if isinstance(dimension_scores, list):
            for score_info in dimension_scores:
                if isinstance(score_info, dict):
                    dimension_name = score_info.get("dimension", "未知")
                    # 不再限制为预定义维度，直接使用能力点名称
                    dimension = dimension_mapping.get(dimension_name)
                    dimension_value = dimension.value if dimension else dimension_name
                    
                    score = score_info.get("score", 0.0)
                    reasoning = score_info.get("reasoning", "由大模型生成的评估结果")
                    evidence = score_info.get("evidence", [])
                    confidence = score_info.get("confidence", 0.9)
                    
                    # 保存维度评分到数据库
                    db_service.create_dimension_score(
                        evaluation_id=db_evaluation.evaluation_id,
                        dimension=dimension_value,
                        score=score,
                        confidence=confidence,
                        evidence=", ".join(evidence) if isinstance(evidence, list) else str(evidence),
                        reasoning=reasoning
                    )
                    
                    # 构建维度评分响应
                    dimension_score_response = DimensionScoreResponse(
                        dimension=dimension_value,
                        score=score,
                        confidence=confidence,
                        evidence=evidence if isinstance(evidence, list) else [str(evidence)],
                        reasoning=reasoning
                    )
                    dimension_scores_response.append(dimension_score_response)
        else:
            print(f"警告：dimension_scores不是列表类型！类型: {type(dimension_scores)}")
        
        # 更新提交状态
        db_service.update_submission_status(request.submission_id, SubmissionStatus.COMPLETED)
        
        # 构建响应
        # 确保strengths、areas_for_improvement和recommendations是列表类型
        response_strengths = evaluation_result.get("strengths", [])
        if not isinstance(response_strengths, list):
            response_strengths = [str(response_strengths)]
        
        response_areas_for_improvement = evaluation_result.get("areas_for_improvement", [])
        if not isinstance(response_areas_for_improvement, list):
            response_areas_for_improvement = [str(response_areas_for_improvement)]
        
        response_recommendations = evaluation_result.get("recommendations", [])
        if not isinstance(response_recommendations, list):
            response_recommendations = [str(response_recommendations)]
        
        response = EvaluationResponse(
            evaluation_id=evaluation_id,
            student_id=student.student_id,
            overall_score=evaluation_result["overall_score"],
            strengths=response_strengths,
            areas_for_improvement=response_areas_for_improvement,
            recommendations=response_recommendations,
            dimension_scores=dimension_scores_response,
            knowledge_understanding_score=evaluation_result.get("knowledge_understanding_score"),
            knowledge_application_score=evaluation_result.get("knowledge_application_score"),
            phase_completion_score=evaluation_result.get("phase_completion_score"),
            score_policy=evaluation_result.get("score_policy"),
            score_breakdown=evaluation_result.get("score_breakdown"),
            evaluated_at=datetime.utcnow().isoformat(),
            evaluator_agent="llm_evaluator",
            stage=f"progress_{stage_progress:.2f}",
            stage_progress=stage_progress
        )
        
        logger.info(f"评估完成: 进度={stage_progress:.2f}, 综合评分={evaluation_result['overall_score']}")
        
        return response
    except HTTPException as he:
        # 更新提交状态为失败
        try:
            db_service.update_submission_status(request.submission_id, SubmissionStatus.FAILED)
        except:
            pass
        raise
    except Exception as e:
        # 更新提交状态为失败
        try:
            db_service.update_submission_status(request.submission_id, SubmissionStatus.FAILED)
        except:
            pass
        # 记录详细的错误信息
        import traceback
        logger.error(f"评估过程中出错: {str(e)}")
        logger.error(f"错误类型: {type(e)}")
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"评估过程中出错: {str(e)}")

@app.get("/evaluations/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 获取评估结果
    evaluation = db_service.get_evaluation_result_by_id(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估结果不存在")
    
    # 获取学生信息
    student = db_service.get_student_by_internal_id(evaluation.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    # 获取维度评分
    dimension_scores = db_service.get_dimension_scores_by_evaluation_id(evaluation_id)
    
    # 构建维度评分响应
    dimension_scores_response = [
        DimensionScoreResponse(
            dimension=ds.dimension,
            score=ds.score,
            confidence=ds.confidence,
            evidence=process_evidence(ds.evidence),
            reasoning=ds.reasoning
        )
        for ds in dimension_scores
    ]
    
    # 检查evaluation对象是否有stage和stage_progress属性
    stage = None
    stage_progress = None
    
    if hasattr(evaluation, 'stage'):
        stage = evaluation.stage
    
    if hasattr(evaluation, 'stage_progress'):
        stage_progress = evaluation.stage_progress
    
    return EvaluationResponse(
        evaluation_id=evaluation.evaluation_id,
        student_id=student.student_id,
        overall_score=evaluation.overall_score,
        strengths=process_string_list(evaluation.strengths),
        areas_for_improvement=process_string_list(evaluation.areas_for_improvement),
        recommendations=process_string_list(evaluation.recommendations),
        dimension_scores=dimension_scores_response,
        evaluated_at=evaluation.evaluated_at,
        evaluator_agent=evaluation.evaluator_agent,
        stage=stage,
        stage_progress=stage_progress
    )

@app.get("/students/{student_id}/evaluations", response_model=List[EvaluationResponse])
async def get_student_evaluations(
    student_id: str,
    skip: int = 0,
    limit: int = 100,
    db_service: DatabaseService = Depends(get_database_service)
):
    try:
        # 获取学生的评估结果，按时间排序
        evaluations = db_service.get_evaluation_results_by_student_id_sorted(student_id)
        
        response = []
        for evaluation in evaluations:
            # 获取维度评分
            dimension_scores = db_service.get_dimension_scores_by_evaluation_id(evaluation.evaluation_id)
            
            # 构建维度评分响应
            dimension_scores_response = [
                DimensionScoreResponse(
                    dimension=ds.dimension,
                    score=ds.score,
                    confidence=ds.confidence,
                    evidence=process_evidence(ds.evidence),
                    reasoning=ds.reasoning
                )
                for ds in dimension_scores
            ]
            
            # 检查evaluation对象是否有stage和stage_progress属性
            stage = None
            stage_progress = None
            
            if hasattr(evaluation, 'stage'):
                stage = evaluation.stage
            
            if hasattr(evaluation, 'stage_progress'):
                stage_progress = evaluation.stage_progress
            
            # 获取学生信息
            student = db_service.get_student_by_internal_id(evaluation.student_id)
            if not student:
                continue
            
            response.append(EvaluationResponse(
                evaluation_id=evaluation.evaluation_id,
                student_id=student.student_id,
                overall_score=evaluation.overall_score,
                strengths=process_string_list(evaluation.strengths),
                areas_for_improvement=process_string_list(evaluation.areas_for_improvement),
                recommendations=process_string_list(evaluation.recommendations),
                dimension_scores=dimension_scores_response,
                evaluated_at=evaluation.evaluated_at,
                evaluator_agent=evaluation.evaluator_agent,
                stage=stage,
                stage_progress=stage_progress
            ))
        
        return response
    except Exception as e:
        logger.error(f"获取学生评估记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取学生评估记录失败: {str(e)}")

@app.delete("/evaluations/{evaluation_id}")
async def delete_evaluation(
    evaluation_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """删除评估记录及其相关的维度评分"""
    success = db_service.delete_evaluation_result(evaluation_id)
    if not success:
        raise HTTPException(status_code=404, detail="评估记录不存在")
    
    return {"message": "评估记录已成功删除"}

@app.put("/evaluations/{evaluation_id}", response_model=EvaluationResponse)
async def update_evaluation(
    evaluation_id: str,
    update_data: dict,
    db_service: DatabaseService = Depends(get_database_service)
):
    """更新评估记录"""
    # 更新评估结果
    evaluation = db_service.update_evaluation_result(evaluation_id, **update_data)
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估结果不存在")
    
    # 获取学生信息
    student = db_service.get_student_by_internal_id(evaluation.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    # 获取维度评分
    dimension_scores = db_service.get_dimension_scores_by_evaluation_id(evaluation_id)
    
    # 构建维度评分响应
    dimension_scores_response = [
        DimensionScoreResponse(
            dimension=ds.dimension,
            score=ds.score,
            confidence=ds.confidence,
            evidence=process_evidence(ds.evidence),
            reasoning=ds.reasoning
        )
        for ds in dimension_scores
    ]
    
    # 检查evaluation对象是否有stage和stage_progress属性
    stage = None
    stage_progress = None
    
    if hasattr(evaluation, 'stage'):
        stage = evaluation.stage
    
    if hasattr(evaluation, 'stage_progress'):
        stage_progress = evaluation.stage_progress
    
    return EvaluationResponse(
        evaluation_id=evaluation.evaluation_id,
        student_id=student.student_id,
        overall_score=evaluation.overall_score,
        strengths=process_string_list(evaluation.strengths),
        areas_for_improvement=process_string_list(evaluation.areas_for_improvement),
        recommendations=process_string_list(evaluation.recommendations),
        dimension_scores=dimension_scores_response,
        evaluated_at=evaluation.evaluated_at,
        evaluator_agent=evaluation.evaluator_agent,
        stage=stage,
        stage_progress=stage_progress
    )

@app.get("/students/{student_id}/progress-report", response_model=ProgressReportResponse)
async def generate_student_progress_report(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """
    生成学生的整体进度报告，根据之前的不同进度的作业评价，
    将其输入大模型后获得对该学生的，在时间线上的能力进步
    """
    # 获取学生的所有评估结果，按时间排序
    evaluations = db_service.get_evaluation_results_by_student_id_sorted(student_id)
    
    if not evaluations:
        raise HTTPException(status_code=404, detail="该学生没有评估记录")
    
    # 构建评估历史数据
    evaluation_history = []
    for eval in evaluations:
        dimension_scores = db_service.get_dimension_scores_by_evaluation_id(eval.evaluation_id)
        dimension_data = [
            {
                "dimension": ds.dimension,
                "score": ds.score,
                "confidence": ds.confidence,
                "reasoning": ds.reasoning
            }
            for ds in dimension_scores
        ]
        
        evaluation_history.append({
            "evaluation_id": eval.evaluation_id,
            "evaluated_at": eval.evaluated_at.isoformat(),
            "overall_score": eval.overall_score,
            "strengths": process_string_list(eval.strengths),
            "areas_for_improvement": process_string_list(eval.areas_for_improvement),
            "recommendations": process_string_list(eval.recommendations),
            "dimension_scores": dimension_data
        })
    
    # 构建提示词
    prompt = f"""你是一位专业的教育评估专家，擅长分析学生在时间线上的能力进步。

请根据以下学生的评估历史数据，生成一份详细的整体进度报告：

学生ID: {student_id}

评估历史（按时间顺序）：
{json.dumps(evaluation_history, ensure_ascii=False, indent=2)}

报告要求：
1. 分析学生在各个维度上的能力变化趋势
2. 识别学生的优势和持续改进的领域
3. 提供关于学生能力发展的关键洞察
4. 给出基于历史数据的未来发展建议
5. 报告应该结构清晰，语言专业但易于理解
6. 包含具体的数据支持和分析

请生成一份全面的进度报告，帮助教师和学生了解能力发展情况。"""
    
    try:
        # 调用大模型生成报告
        from src.evaluation.llm_evaluator import llm_evaluator
        report = llm_evaluator.generate_report(prompt)
        
        # 提取关键信息
        key_insights = ["学生能力发展趋势分析", "优势领域识别", "改进空间分析"]
        improvement_areas = ["需要持续关注的能力维度"]
        
        # 构建时间范围
        time_range = {
            "start": evaluations[0].evaluated_at.isoformat(),
            "end": evaluations[-1].evaluated_at.isoformat()
        }
        
        # 保存进度报告到数据库
        db_service.create_progress_report(
            student_id=student_id,
            report=report,
            total_evaluations=len(evaluations),
            time_range=time_range,
            key_insights=key_insights,
            improvement_areas=improvement_areas
        )
        
        return ProgressReportResponse(
            student_id=student_id,
            report=report,
            generated_at=datetime.utcnow(),
            total_evaluations=len(evaluations),
            time_range=time_range,
            key_insights=key_insights,
            improvement_areas=improvement_areas
        )
    except Exception as e:
        logger.error(f"生成进度报告失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成进度报告失败: {str(e)}")

@app.get("/students/{student_id}/progress-reports", response_model=List[ProgressReportResponse])
async def get_student_progress_reports(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """
    获取学生的历史进度报告
    """
    import json
    
    # 获取学生的所有进度报告
    reports = db_service.get_progress_reports_by_student_id(student_id)
    
    if not reports:
        return []
    
    # 构建响应
    response = []
    for report in reports:
        # 解析 JSON 字段
        time_range = {}
        key_insights = []
        improvement_areas = []
        
        try:
            if report.time_range:
                time_range = json.loads(report.time_range)
            if report.key_insights:
                key_insights = json.loads(report.key_insights)
            if report.improvement_areas:
                improvement_areas = json.loads(report.improvement_areas)
        except:
            pass
        
        response.append(ProgressReportResponse(
            student_id=student_id,
            report=report.report,
            generated_at=report.generated_at,
            total_evaluations=report.total_evaluations,
            time_range=time_range,
            key_insights=key_insights,
            improvement_areas=improvement_areas,
            report_id=report.report_id  # 添加report_id
        ))
    
    return response

# Pydantic model for updating progress report
class ProgressReportUpdate(BaseModel):
    generated_at: Optional[datetime] = None
    report: Optional[str] = None
    time_range: Optional[Dict[str, str]] = None
    key_insights: Optional[List[str]] = None
    improvement_areas: Optional[List[str]] = None

@app.put("/progress-reports/{report_id}")
async def update_progress_report(
    report_id: str,
    report_update: ProgressReportUpdate,
    db_service: DatabaseService = Depends(get_database_service)
):
    """
    更新进度报告
    """
    # 构建更新数据
    update_data = {}
    if report_update.generated_at is not None:
        update_data['generated_at'] = report_update.generated_at
    if report_update.report is not None:
        update_data['report'] = report_update.report
    if report_update.time_range is not None:
        update_data['time_range'] = report_update.time_range
    if report_update.key_insights is not None:
        update_data['key_insights'] = report_update.key_insights
    if report_update.improvement_areas is not None:
        update_data['improvement_areas'] = report_update.improvement_areas
    
    # 更新报告
    updated_report = db_service.update_progress_report(report_id, **update_data)
    
    if not updated_report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # 构建响应
    import json
    time_range = {}
    key_insights = []
    improvement_areas = []
    
    try:
        if updated_report.time_range:
            time_range = json.loads(updated_report.time_range)
        if updated_report.key_insights:
            key_insights = json.loads(updated_report.key_insights)
        if updated_report.improvement_areas:
            improvement_areas = json.loads(updated_report.improvement_areas)
    except:
        pass
    
    return ProgressReportResponse(
        student_id="",  # 这里需要从报告中获取学生ID，但当前模型没有直接关联
        report=updated_report.report,
        generated_at=updated_report.generated_at,
        total_evaluations=updated_report.total_evaluations,
        time_range=time_range,
        key_insights=key_insights,
        improvement_areas=improvement_areas,
        report_id=updated_report.report_id
    )

@app.delete("/progress-reports/{report_id}")
async def delete_progress_report(
    report_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """删除进度报告"""
    deleted = db_service.delete_progress_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="进度报告不存在")
    
    return {"message": "进度报告删除成功"}

@app.get("/submissions/{submission_id}/evaluation", response_model=EvaluationResponse)
async def get_submission_evaluation(
    submission_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 获取提交的评估结果
    evaluation = db_service.get_evaluation_result_by_submission_id(submission_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估结果不存在")
    
    # 获取学生信息
    student = db_service.get_student_by_internal_id(evaluation.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    # 获取维度评分
    dimension_scores = db_service.get_dimension_scores_by_evaluation_id(evaluation.evaluation_id)
    
    # 构建维度评分响应
    dimension_scores_response = [
        DimensionScoreResponse(
            dimension=ds.dimension,
            score=ds.score,
            confidence=ds.confidence,
            evidence=process_evidence(ds.evidence),
            reasoning=ds.reasoning
        )
        for ds in dimension_scores
    ]
    
    # 检查evaluation对象是否有stage属性
    stage = None
    if hasattr(evaluation, 'stage'):
        stage = evaluation.stage
    
    return EvaluationResponse(
            evaluation_id=evaluation.evaluation_id,
            student_id=student.student_id,
            overall_score=evaluation.overall_score,
            strengths=process_string_list(evaluation.strengths),
            areas_for_improvement=process_string_list(evaluation.areas_for_improvement),
            recommendations=process_string_list(evaluation.recommendations),
            dimension_scores=dimension_scores_response,
            evaluated_at=evaluation.evaluated_at,
            evaluator_agent=evaluation.evaluator_agent,
            stage=stage
        )

@app.get("/students/{student_id}/evaluations/comparison")
async def compare_student_evaluations(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """获取学生的评估结果对比"""
    # 获取学生信息
    student = db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    # 获取按阶段排序的评估结果
    evaluations = db_service.get_evaluation_results_by_student_id_sorted(student_id)
    
    if not evaluations:
        raise HTTPException(status_code=404, detail="暂无评估记录")
    
    # 构建对比响应
    comparison_data = {
        "student_id": student_id,
        "student_name": student.name,
        "evaluations": []
    }
    
    for evaluation in evaluations:
        # 获取维度评分
        dimension_scores = db_service.get_dimension_scores_by_evaluation_id(evaluation.evaluation_id)
        
        # 构建维度评分响应
        dimension_scores_response = [
            {
                "dimension": ds.dimension,
                "score": ds.score,
                "confidence": ds.confidence
            }
            for ds in dimension_scores
        ]
        
        evaluation_data = {
            "evaluation_id": evaluation.evaluation_id,
            "overall_score": evaluation.overall_score,
            "evaluated_at": evaluation.evaluated_at,
            "dimension_scores": dimension_scores_response,
            "strengths": process_string_list(evaluation.strengths),
            "areas_for_improvement": process_string_list(evaluation.areas_for_improvement),
            "recommendations": process_string_list(evaluation.recommendations)
        }
        
        comparison_data["evaluations"].append(evaluation_data)
    
    # 计算评分变化
    if len(evaluations) > 1:
        score_changes = []
        for i in range(1, len(evaluations)):
            prev_evaluation = evaluations[i-1]
            current_evaluation = evaluations[i]
            
            score_change = {
                "from_evaluation": prev_evaluation.evaluation_id,
                "to_evaluation": current_evaluation.evaluation_id,
                "overall_score_change": current_evaluation.overall_score - prev_evaluation.overall_score,
                "dimension_score_changes": []
            }
            
            # 计算维度评分变化
            prev_dimensions = {ds.dimension: ds.score for ds in db_service.get_dimension_scores_by_evaluation_id(prev_evaluation.evaluation_id)}
            current_dimensions = {ds.dimension: ds.score for ds in db_service.get_dimension_scores_by_evaluation_id(current_evaluation.evaluation_id)}
            
            for dimension in set(prev_dimensions.keys()) | set(current_dimensions.keys()):
                prev_score = prev_dimensions.get(dimension, 0)
                current_score = current_dimensions.get(dimension, 0)
                
                score_change["dimension_score_changes"].append({
                    "dimension": dimension,
                    "change": current_score - prev_score
                })
            
            score_changes.append(score_change)
        
        comparison_data["score_changes"] = score_changes
    
    return comparison_data

# AI 配置相关的 Pydantic 模型
class AIConfigRequest(BaseModel):
    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000

class AIConfigResponse(BaseModel):
    provider: str
    model: str
    base_url: str
    temperature: float
    max_tokens: int
    has_api_key: bool

class TestAIResponse(BaseModel):
    success: bool
    message: str
    model: Optional[str] = None
    response_time: Optional[float] = None
    error: Optional[str] = None

# 内存中存储的 AI 配置（实际生产环境应该使用更安全的方式）
_current_ai_config: Dict[str, Any] = None

def get_current_ai_config():
    """获取当前 AI 配置"""
    global _current_ai_config
    if _current_ai_config is None:
        # 使用默认配置
        config = get_ai_config()
        _current_ai_config = {
            "provider": settings.ai_provider,
            "api_key": config.get("api_key", ""),
            "model": config.get("model", settings.ai_model),
            "base_url": config.get("base_url", ""),
            "temperature": config.get("temperature", settings.ai_temperature),
            "max_tokens": config.get("max_tokens", settings.ai_max_tokens)
        }
    return _current_ai_config

# AI 配置相关路由
@app.get("/ai-config")
async def get_ai_configuration():
    """获取当前 AI 配置"""
    config = get_current_ai_config()
    return {
        "provider": config["provider"],
        "model": config["model"],
        "base_url": config["base_url"],
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
        "api_key": config["api_key"],  # 返回 API Key 以便前端使用
        "has_api_key": bool(config["api_key"])
    }

@app.post("/ai-config")
async def update_ai_configuration(config: AIConfigRequest):
    """更新 AI 配置"""
    global _current_ai_config
    
    # 验证提供商
    if config.provider not in AI_PROVIDERS and config.provider != "custom":
        raise HTTPException(status_code=400, detail=f"不支持的 AI 提供商: {config.provider}")
    
    # 获取提供商信息
    provider_info = AI_PROVIDERS.get(config.provider, {})
    
    # 确定 base_url
    if config.provider == "custom":
        if not config.base_url:
            raise HTTPException(status_code=400, detail="自定义提供商必须提供 base_url")
        base_url = config.base_url
    else:
        base_url = config.base_url or provider_info.get("base_url", "")
    
    # 保存配置
    _current_ai_config = {
        "provider": config.provider,
        "api_key": config.api_key,
        "model": config.model,
        "base_url": base_url,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens
    }
    
    # 更新环境变量（供其他模块使用）
    os.environ["AI_PROVIDER"] = config.provider
    os.environ["AI_API_KEY"] = config.api_key
    os.environ["AI_MODEL"] = config.model
    os.environ["AI_BASE_URL"] = base_url
    os.environ["AI_TEMPERATURE"] = str(config.temperature)
    os.environ["AI_MAX_TOKENS"] = str(config.max_tokens)
    
    # 同时设置OpenAI的环境变量，确保兼容性
    os.environ["OPENAI_API_KEY"] = config.api_key
    os.environ["OPENAI_MODEL"] = config.model
    if base_url:
        os.environ["OPENAI_BASE_URL"] = base_url
    
    return {"message": "AI 配置已更新", "provider": config.provider, "model": config.model}

@app.post("/ai-config/reset")
async def reset_ai_configuration():
    """重置 AI 配置为默认值"""
    global _current_ai_config
    _current_ai_config = None
    
    # 清除环境变量
    for key in ["AI_PROVIDER", "AI_API_KEY", "AI_MODEL", "AI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"]:
        if key in os.environ:
            del os.environ[key]
    
    return {"message": "AI 配置已重置为默认值"}

@app.post("/ai-config/test", response_model=TestAIResponse)
async def test_ai_connection():
    """测试 AI 连接"""
    config = get_current_ai_config()
    
    if not config["api_key"]:
        return TestAIResponse(
            success=False,
            message="",
            error="未配置 API Key"
        )
    
    try:
        start_time = time.time()
        
        # 根据提供商使用不同的测试方式
        if config["provider"] in ["openai", "deepseek", "zhipu", "moonshot", "qwen", "custom"]:
            # 使用 OpenAI 兼容格式测试
            from openai import OpenAI
            
            client = OpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"]
            )
            
            response = client.chat.completions.create(
                model=config["model"],
                messages=[
                    {"role": "system", "content": "你是一个 helpful assistant."},
                    {"role": "user", "content": "你好，请回复'连接测试成功'"}
                ],
                temperature=config["temperature"],
                max_tokens=config["max_tokens"]
            )
            
            response_time = time.time() - start_time
            message = response.choices[0].message.content
            
            return TestAIResponse(
                success=True,
                message=message,
                model=config["model"],
                response_time=round(response_time, 2)
            )
        else:
            return TestAIResponse(
                success=False,
                message="",
                error=f"不支持的提供商: {config['provider']}"
            )
            
    except Exception as e:
        return TestAIResponse(
            success=False,
            message="",
            error=f"连接测试失败: {str(e)}"
        )

# 主入口
@app.delete("/evaluations/{evaluation_id}")
async def delete_evaluation(
    evaluation_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """
    删除评估记录
    """
    try:
        # 删除评估记录
        if db_service.delete_evaluation_result(evaluation_id):
            return {"message": "评估记录删除成功"}
        else:
            raise HTTPException(status_code=404, detail="评估记录不存在")
    except Exception as e:
        logger.error(f"删除评估记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除评估记录失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
        reload_dirs=[os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    )