# src/course_classifier.py
import re
from typing import Dict, Tuple


def _count_weighted_keywords(text: str, keywords: Dict[str, float]) -> float:
    score = 0.0
    for keyword, weight in keywords.items():
        score += text.count(keyword) * weight
    return score


def _extract_hours_score(text: str) -> Tuple[float, float]:
    """
    根据课时信息给理论/实践加权，例如：
    - 理论学时 32，实验学时 16
    - 课内实验 24 学时
    """
    theory_score = 0.0
    practice_score = 0.0

    # 常见格式：理论学时32 / 实验学时16 / 实践学时16
    hour_patterns = [
        (r"(理论学时|理论课时)\s*[：: ]\s*(\d+)", "theory"),
        (r"(实验学时|实践学时|上机学时|实训学时|课内实验)\s*[：: ]\s*(\d+)", "practice"),
    ]
    for pattern, tag in hour_patterns:
        for _, hours in re.findall(pattern, text):
            value = float(hours)
            if tag == "theory":
                theory_score += value * 0.35
            else:
                practice_score += value * 0.35

    return theory_score, practice_score


def classify_course_type_with_meta(text_content: str) -> Dict[str, float | str]:
    """
    更鲁棒的课程类型识别：
    1) 优先读取“课程性质”明确描述
    2) 融合课时结构（理论/实验学时）
    3) 结合加权关键词统计
    """
    if not text_content:
        return {"course_type": "理论课", "theory_score": 0.0, "practice_score": 0.0, "confidence": 0.0}

    text = re.sub(r"\s+", "", text_content)

    # 1) 显式规则：课程性质
    nature_match = re.search(r"课程性质[：:]\s*([^\n\r。；;]{1,40})", text_content)
    if nature_match:
        nature = nature_match.group(1)
        if any(k in nature for k in ["实验", "实践", "实训", "课程设计", "竞赛", "项目制", "上机"]):
            return {"course_type": "实践课", "theory_score": 0.0, "practice_score": 1.0, "confidence": 1.0}
        if any(k in nature for k in ["理论", "基础", "导论", "概论", "原理"]):
            return {"course_type": "理论课", "theory_score": 1.0, "practice_score": 0.0, "confidence": 1.0}

    # 2) 关键词加权
    practice_keywords = {
        "实验": 2.8, "实践": 2.4, "实训": 2.8, "上机": 2.5, "课程设计": 2.8, "竞赛": 2.2,
        "项目": 1.8, "实现": 1.5, "开发": 1.3, "调试": 1.5, "动手": 1.7, "工艺": 1.2, "操作": 1.3
    }
    theory_keywords = {
        "理论": 2.8, "原理": 2.4, "概念": 2.1, "推导": 2.2, "证明": 2.0, "模型分析": 1.8,
        "方法论": 1.6, "综述": 1.4, "知识体系": 1.8, "基础": 1.6
    }

    practice_score = _count_weighted_keywords(text, practice_keywords)
    theory_score = _count_weighted_keywords(text, theory_keywords)

    # 3) 课时结构加权
    theory_hours_score, practice_hours_score = _extract_hours_score(text_content)
    theory_score += theory_hours_score
    practice_score += practice_hours_score

    # 4) 结果与置信度
    total = theory_score + practice_score
    if total <= 0:
        return {"course_type": "理论课", "theory_score": 0.0, "practice_score": 0.0, "confidence": 0.0}

    diff = abs(theory_score - practice_score)
    confidence = min(1.0, diff / total)
    course_type = "实践课" if practice_score > theory_score else "理论课"

    return {
        "course_type": course_type,
        "theory_score": round(theory_score, 3),
        "practice_score": round(practice_score, 3),
        "confidence": round(confidence, 3)
    }


def classify_course_type(text_content: str) -> str:
    return classify_course_type_with_meta(text_content)["course_type"]