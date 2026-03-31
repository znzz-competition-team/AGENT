import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from src.config import get_ai_config

logger = logging.getLogger(__name__)


class HandwritingExamGradingAgent:
    """Use a multimodal model to read handwritten exam images and grade them."""

    def __init__(self, ai_config: Optional[Dict[str, Any]] = None):
        self.ai_config = ai_config or get_ai_config()
        if not self.ai_config.get("api_key"):
            raise ValueError("AI API Key 未配置，无法进行试卷批改")

        self.client = OpenAI(
            api_key=self.ai_config["api_key"],
            base_url=self.ai_config.get("base_url"),
        )

    def grade_exam(
        self,
        image_paths: List[str],
        answer_key: str,
        rubric: Optional[str] = None,
        subject: Optional[str] = None,
        total_score: Optional[float] = None,
        extra_requirements: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not image_paths:
            raise ValueError("至少需要上传一张试卷图片")

        prompt = self._build_prompt(
            answer_key=answer_key,
            rubric=rubric,
            subject=subject,
            total_score=total_score,
            extra_requirements=extra_requirements,
        )

        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image_path in image_paths:
            content.append(self._build_image_content(image_path))

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名严谨的试卷批改 agent。"
                        "你需要先识别手写内容，再严格按照答案和评分标准评分。"
                        "如果图片模糊或信息不足，要在结果里明确指出不确定性。"
                    ),
                },
                {"role": "user", "content": content},
            ],
            temperature=min(float(self.ai_config.get("temperature", 0.2)), 0.3),
            max_tokens=max(int(self.ai_config.get("max_tokens", 2000)), 2500),
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content
        result = json.loads(raw_content)
        return self._normalize_result(result, total_score)

    def _build_prompt(
        self,
        answer_key: str,
        rubric: Optional[str],
        subject: Optional[str],
        total_score: Optional[float],
        extra_requirements: Optional[str],
    ) -> str:
        score_hint = (
            f"整张试卷总分为 {total_score} 分。"
            if total_score is not None
            else "请根据题目拆分后的分值自行汇总总分。"
        )

        return f"""
请完成一份手写试卷的图像识别与批改。

要求：
1. 先尽可能完整识别学生手写答案，按题目整理。
2. 再依据标准答案和评分标准逐题评分。
3. 对于识别不清、答案歧义、图片遮挡的地方，要在 reasoning 或 overall_comment 中明确标出。
4. 输出必须是 JSON 对象，不要输出 markdown，不要输出额外说明。

科目：{subject or "未提供"}
评分说明：{score_hint}

标准答案：
{answer_key}

评分细则：
{rubric or "未提供额外细则，请按标准答案、步骤完整性、结论正确性和表达清晰度综合评分。"}

额外要求：
{extra_requirements or "无"}

请返回以下 JSON 结构：
{{
  "recognized_text": "整份试卷识别出的文字，尽量按题号分段",
  "total_score": 0,
  "max_score": 0,
  "overall_comment": "对整份试卷的总体评价",
  "strengths": ["优点1", "优点2"],
  "areas_for_improvement": ["问题1", "问题2"],
  "question_results": [
    {{
      "question_number": "1",
      "max_score": 10,
      "score": 8,
      "recognized_answer": "学生本题答案",
      "reference_answer": "标准答案或要点",
      "reasoning": "扣分/给分原因",
      "strengths": ["本题亮点"],
      "mistakes": ["本题错误"]
    }}
  ]
}}
""".strip()

    def _build_image_content(self, image_path: str) -> Dict[str, Any]:
        file_path = Path(image_path)
        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "image/png"

        with open(file_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")

        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{encoded}",
            },
        }

    def _normalize_result(self, result: Dict[str, Any], requested_total_score: Optional[float]) -> Dict[str, Any]:
        question_results = result.get("question_results") or []
        normalized_questions: List[Dict[str, Any]] = []
        accumulated_score = 0.0
        accumulated_max = 0.0

        for idx, item in enumerate(question_results, start=1):
            max_score = float(item.get("max_score", 0) or 0)
            score = float(item.get("score", 0) or 0)
            score = max(0.0, min(score, max_score if max_score > 0 else score))
            accumulated_score += score
            accumulated_max += max_score

            normalized_questions.append(
                {
                    "question_number": str(item.get("question_number", idx)),
                    "max_score": max_score,
                    "score": score,
                    "recognized_answer": item.get("recognized_answer", ""),
                    "reference_answer": item.get("reference_answer"),
                    "reasoning": item.get("reasoning", ""),
                    "strengths": item.get("strengths") or [],
                    "mistakes": item.get("mistakes") or [],
                }
            )

        max_score = float(result.get("max_score", 0) or 0)
        if max_score <= 0:
            max_score = requested_total_score if requested_total_score is not None else accumulated_max

        total_score = float(result.get("total_score", accumulated_score) or 0)
        if max_score > 0:
            total_score = max(0.0, min(total_score, max_score))

        normalized = {
            "recognized_text": result.get("recognized_text", ""),
            "total_score": round(total_score, 2),
            "max_score": round(float(max_score or accumulated_max), 2),
            "overall_comment": result.get("overall_comment", ""),
            "strengths": result.get("strengths") or [],
            "areas_for_improvement": result.get("areas_for_improvement") or [],
            "question_results": normalized_questions,
            "model": self.ai_config["model"],
        }

        logger.info(
            "Handwriting exam grading completed: model=%s total_score=%s max_score=%s",
            self.ai_config["model"],
            normalized["total_score"],
            normalized["max_score"],
        )
        return normalized
