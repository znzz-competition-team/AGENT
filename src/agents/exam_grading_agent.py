import base64
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from src.config import get_ai_config

logger = logging.getLogger(__name__)

GRADUATION_DESIGN_KEYWORDS = (
    "毕业设计",
    "毕业论文",
    "毕业设计（论文）",
    "课程达成度",
    "达成度评价",
    "文献分析",
    "设计方法",
    "针对需求设计",
    "创新与权衡",
    "专业沟通",
    "国际化视野",
)


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
        recognition_mode: str = "general",
        context_text: Optional[str] = None,
        system_functions: Optional[str] = None,
        system_relationships: Optional[str] = None,
        validate_derivation: bool = True,
    ) -> Dict[str, Any]:
        if not image_paths:
            raise ValueError("至少需要上传一张试卷图片")
        recognition_mode = (recognition_mode or "general").strip().lower()
        if recognition_mode not in {"general", "formula"}:
            recognition_mode = "general"

        include_course_achievement = self._should_include_course_achievement(
            answer_key=answer_key,
            rubric=rubric,
            subject=subject,
            extra_requirements=extra_requirements,
        )

        prompt = self._build_prompt(
            answer_key=answer_key,
            rubric=rubric,
            subject=subject,
            total_score=total_score,
            extra_requirements=extra_requirements,
            include_course_achievement=include_course_achievement,
            recognition_mode=recognition_mode,
            context_text=context_text,
            system_functions=system_functions,
            system_relationships=system_relationships,
            validate_derivation=validate_derivation,
        )

        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        context_blocks = self._build_context_blocks(
            context_text=context_text,
            system_functions=system_functions,
            system_relationships=system_relationships,
        )
        for block in context_blocks:
            content.append({"type": "text", "text": block})
        for image_path in image_paths:
            content.append(self._build_image_content(image_path))

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {
                    "role": "system",
                    "content": self._build_system_prompt(recognition_mode),
                },
                {"role": "user", "content": content},
            ],
            temperature=min(float(self.ai_config.get("temperature", 0.2)), 0.3),
            max_tokens=max(int(self.ai_config.get("max_tokens", 2000)), 2500),
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content
        result = self._parse_json_response(raw_content)
        return self._normalize_result(
            result=result,
            requested_total_score=total_score,
            include_course_achievement=include_course_achievement,
            recognition_mode=recognition_mode,
            validate_derivation=validate_derivation,
        )

    def _build_prompt(
        self,
        answer_key: str,
        rubric: Optional[str],
        subject: Optional[str],
        total_score: Optional[float],
        extra_requirements: Optional[str],
        include_course_achievement: bool,
        recognition_mode: str,
        context_text: Optional[str],
        system_functions: Optional[str],
        system_relationships: Optional[str],
        validate_derivation: bool,
    ) -> str:
        score_hint = (
            f"整张试卷总分为 {total_score} 分。"
            if total_score is not None
            else "请根据题目拆分后的分值自行汇总总分。"
        )

        course_achievement_instruction = ""
        if include_course_achievement:
            course_achievement_instruction = """

毕业设计（论文）课程达成度补充评价要求：
请在完成常规批改后，再基于整份作答表现补充一段“课程达成度评价”，重点围绕以下 6 个课程目标/毕业要求指标点展开：
1. 文献分析（毕业要求指标点 2.3）：能否通过文献研究理解研究问题的影响因素、已有进展和替代方案。
2. 设计方法（毕业要求指标点 3.1）：能否体现工程设计和产品开发全周期、全流程的方法与技术意识。
3. 针对需求设计（毕业要求指标点 3.2）：能否围绕指定需求完成机械系统、零部件或制造工艺设计。
4. 创新与权衡（毕业要求指标点 3.3）：能否体现创新意识，并从社会、健康、安全、法律、文化、环境等角度进行权衡。
5. 专业沟通（毕业要求指标点 10.1）：能否通过文稿、图表、论述等方式准确表达专业观点。
6. 国际化视野（毕业要求指标点 10.2）：能否体现对国际发展趋势、研究热点及跨文化交流能力的理解。

补充评价生成规则：
1. 这段评价应写成 1 段到 2 段完整中文，不要只列提纲。
2. 评价要结合学生当前答卷表现，指出相对达成较好的维度和仍需加强的维度。
3. 如果题面或答卷证据不足，必须明确说明“仅基于当前答卷可见信息判断”。
4. 要特别关注“创新与权衡”维度；若表现一般，应给出持续改进建议。
"""

        prompt_header = (
            "请完成一份手写试卷的图像识别与批改。"
            if recognition_mode == "general"
            else "请完成一份手写试卷的公式识别增强批改（公式识别专用模式）。"
        )
        mode_instruction = ""
        if recognition_mode == "formula":
            mode_instruction = """

公式识别专用模式要求（必须严格执行）：
1. 重点识别数学表达式（分式、根号、上下标、积分、求和、矩阵、向量、极限、不等式等），优先保证公式结构准确。
2. 每识别到一个核心公式，都要输出到 formula_boxes 中，并提供：
   - page_index：该公式所在页（从 1 开始）；
   - x,y,w,h：框坐标，使用相对坐标（范围 0~1，对应整页宽高）；
   - text：公式原文（尽量贴近学生书写）；
   - latex：规范化 LaTeX（无法确定时可为空字符串）；
   - confidence：0~1；
   - box_type：固定为 formula。
3. 若同一题中有多个公式，分别输出多个框；不要把整段文本都框成一个大框。
4. 若公式看不清，text 中用 [不清] 标记，并降低 confidence，但仍尽量给出框。
"""

        derivation_instruction = ""
        if validate_derivation:
            derivation_instruction = """

公式推导合理性校验要求（必须执行）：
1. 对每道包含公式或计算步骤的题，检查推导是否自洽，重点核对符号变形、等价变换、边界条件、单位量纲和最终结论一致性。
2. 如果图像存在遮挡或字迹不清，允许标记为 uncertain，但不能把 uncertain 当作正确。
3. 在 derivation_checks 输出逐题校验结果，status 仅允许：valid / invalid / uncertain。
4. evidence 需引用学生答案中的关键式子或步骤片段；issue 说明主要问题；suggestion 给出可执行改进建议。
"""

        context_instruction = ""
        if any(part and str(part).strip() for part in [context_text, system_functions, system_relationships]):
            context_instruction = """

补充文字信息使用要求：
1. 下面会提供“补充文字说明 / 系统功能 / 系统关系”文本，请与图像识别结果联合判断，不可忽略。
2. 若文字与图像冲突，以图像可见证据优先，并在 reasoning 或 overall_comment 明确指出冲突点。
3. 涉及系统结构题时，优先依据系统功能与系统关系文本核对逻辑闭环和因果链条。
"""

        return f"""
{prompt_header}

要求：
1. 先尽可能完整识别学生手写答案，按题号、小问、跨页连续内容整理。
2. 识别时尽量保留原意，不要臆测补全；对看不清的字、符号、公式用 [不清] 标记。
3. 对公式、单位、序号、涂改痕迹和跨页答案要特别留意，避免遗漏。
4. 再依据标准答案和评分标准逐题评分。
5. 对于识别不清、答案歧义、图片遮挡的地方，要在 reasoning 或 overall_comment 中明确标出。
6. 输出必须是 JSON 对象，不要输出 markdown，不要输出额外说明。

科目：{subject or "未提供"}
评分说明：{score_hint}

标准答案：
{answer_key}

评分细则：
{rubric or "未提供额外细则，请按标准答案、步骤完整性、结论正确性和表达清晰度综合评分。"}

额外要求：
{extra_requirements or "无"}
{mode_instruction}
{derivation_instruction}
{context_instruction}
{course_achievement_instruction}

请返回以下 JSON 结构：
{{
  "recognized_text": "整份试卷识别出的文字，尽量按题号分段",
  "total_score": 0,
  "max_score": 0,
  "overall_comment": "对整份试卷的总体评价",
  "course_achievement_comment": "可选，当题目或要求涉及毕业设计（论文）课程达成度时输出补充评价，否则为空字符串",
  "strengths": ["优点1", "优点2"],
  "areas_for_improvement": ["问题1", "问题2"],
  "formula_boxes": [
    {{
      "page_index": 1,
      "x": 0.1,
      "y": 0.2,
      "w": 0.3,
      "h": 0.08,
      "coordinate_type": "relative",
      "confidence": 0.92,
      "text": "x^2 + y^2 = z^2",
      "latex": "x^2+y^2=z^2",
      "box_type": "formula"
    }}
  ],
  "derivation_checks": [
    {{
      "question_number": "1",
      "status": "valid",
      "checked_formula": "x^2+y^2=z^2",
      "evidence": "由已识别的中间步骤可还原推导链",
      "issue": "",
      "suggestion": ""
    }}
  ],
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

    def _build_context_blocks(
        self,
        context_text: Optional[str],
        system_functions: Optional[str],
        system_relationships: Optional[str],
    ) -> List[str]:
        blocks: List[str] = []
        mapping = [
            ("补充文字说明", context_text),
            ("系统功能", system_functions),
            ("系统关系", system_relationships),
        ]
        for title, value in mapping:
            text = (value or "").strip()
            if text:
                blocks.append(f"{title}：\n{text}")
        return blocks

    def _build_system_prompt(self, recognition_mode: str) -> str:
        if recognition_mode == "formula":
            return (
                "你是一名严谨的手写试卷批改 agent，当前工作在公式识别专用模式。"
                "你需要先做高精度公式识别与定位，再按答案和评分细则评分。"
                "只输出 JSON，不要输出 markdown。"
            )
        return (
            "你是一名严谨的试卷批改 agent。"
            "你需要先识别手写内容，再严格按照答案和评分标准评分。"
            "如果图片模糊或信息不足，要在结果里明确指出不确定性。"
        )

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

    def _normalize_result(
        self,
        result: Dict[str, Any],
        requested_total_score: Optional[float],
        include_course_achievement: bool,
        recognition_mode: str,
        validate_derivation: bool,
    ) -> Dict[str, Any]:
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

        course_achievement_comment = (result.get("course_achievement_comment") or "").strip()
        if include_course_achievement and not course_achievement_comment:
            course_achievement_comment = self._build_fallback_course_achievement_comment(
                total_score=total_score,
                max_score=max_score,
                strengths=result.get("strengths") or [],
                areas_for_improvement=result.get("areas_for_improvement") or [],
            )

        normalized = {
            "recognition_mode": recognition_mode,
            "recognized_text": result.get("recognized_text", ""),
            "total_score": round(total_score, 2),
            "max_score": round(float(max_score or accumulated_max), 2),
            "overall_comment": result.get("overall_comment", ""),
            "course_achievement_comment": course_achievement_comment,
            "strengths": result.get("strengths") or [],
            "areas_for_improvement": result.get("areas_for_improvement") or [],
            "question_results": normalized_questions,
            "formula_boxes": self._normalize_formula_boxes(result.get("formula_boxes") or []),
            "derivation_checks": self._normalize_derivation_checks(
                result.get("derivation_checks") or [],
                normalized_questions=normalized_questions,
                should_validate=validate_derivation,
            ),
            "model": self.ai_config["model"],
        }

        logger.info(
            "Handwriting exam grading completed: model=%s total_score=%s max_score=%s",
            self.ai_config["model"],
            normalized["total_score"],
            normalized["max_score"],
        )
        return normalized

    def _parse_json_response(self, raw_content: Any) -> Dict[str, Any]:
        """尽量稳健地解析模型返回的 JSON。"""
        if isinstance(raw_content, dict):
            return raw_content
        if not isinstance(raw_content, str):
            raise ValueError("模型返回内容不是字符串，无法解析为 JSON")

        candidates = []
        text = raw_content.strip()
        candidates.append(text)

        fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        if fenced and fenced not in candidates:
            candidates.append(fenced)

        start = fenced.find("{")
        end = fenced.rfind("}")
        if start != -1 and end != -1 and end > start:
            sliced = fenced[start:end + 1].strip()
            if sliced not in candidates:
                candidates.append(sliced)

        errors = []
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                errors.append(f"{exc.msg} at line {exc.lineno} column {exc.colno}")

        preview = text[:500]
        logger.error("Failed to parse grading JSON. Raw preview: %s", preview)
        raise ValueError(f"模型返回的批改结果不是合法 JSON。解析失败详情：{' | '.join(errors)}")

    def _normalize_formula_boxes(self, formula_boxes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized_boxes: List[Dict[str, Any]] = []
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

            confidence_raw = item.get("confidence")
            confidence = None
            if confidence_raw is not None:
                try:
                    confidence = max(0.0, min(float(confidence_raw), 1.0))
                except (TypeError, ValueError):
                    confidence = None

            normalized_boxes.append(
                {
                    "page_index": max(1, page_index),
                    "x": max(0.0, min(x, 1.0)),
                    "y": max(0.0, min(y, 1.0)),
                    "w": max(0.0, min(w, 1.0)),
                    "h": max(0.0, min(h, 1.0)),
                    "coordinate_type": "relative",
                    "confidence": confidence,
                    "text": str(item.get("text", "") or ""),
                    "latex": (item.get("latex") or None),
                    "box_type": str(item.get("box_type", "formula") or "formula"),
                }
            )
        return normalized_boxes

    def _normalize_derivation_checks(
        self,
        derivation_checks: List[Dict[str, Any]],
        normalized_questions: List[Dict[str, Any]],
        should_validate: bool,
    ) -> List[Dict[str, str]]:
        if not should_validate:
            return []

        allowed_status = {"valid", "invalid", "uncertain"}
        normalized: List[Dict[str, str]] = []
        for item in derivation_checks:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "uncertain") or "uncertain").strip().lower()
            if status not in allowed_status:
                status = "uncertain"

            normalized.append(
                {
                    "question_number": str(item.get("question_number", "") or ""),
                    "status": status,
                    "checked_formula": str(item.get("checked_formula", "") or ""),
                    "evidence": str(item.get("evidence", "") or ""),
                    "issue": str(item.get("issue", "") or ""),
                    "suggestion": str(item.get("suggestion", "") or ""),
                }
            )

        if normalized:
            return normalized

        fallback: List[Dict[str, str]] = []
        for question in normalized_questions:
            fallback.append(
                {
                    "question_number": str(question.get("question_number", "") or ""),
                    "status": "uncertain",
                    "checked_formula": "",
                    "evidence": "",
                    "issue": "",
                    "suggestion": "",
                }
            )
        return fallback

    def _should_include_course_achievement(
        self,
        answer_key: str,
        rubric: Optional[str],
        subject: Optional[str],
        extra_requirements: Optional[str],
    ) -> bool:
        combined_text = "\n".join(
            part for part in [subject or "", answer_key, rubric or "", extra_requirements or ""] if part
        )
        return any(keyword in combined_text for keyword in GRADUATION_DESIGN_KEYWORDS)

    def _build_fallback_course_achievement_comment(
        self,
        total_score: float,
        max_score: float,
        strengths: List[str],
        areas_for_improvement: List[str],
    ) -> str:
        ratio = (total_score / max_score) if max_score else 0.0
        if ratio >= 0.85:
            attainment_level = "整体达成情况较好"
        elif ratio >= 0.7:
            attainment_level = "整体达到课程目标基本要求"
        else:
            attainment_level = "当前达成情况偏弱，仍需进一步强化"

        strengths_text = "；".join(strengths[:2]) if strengths else "当前答卷能体现一定的专业基础与方案表达能力"
        improvement_text = (
            "；".join(areas_for_improvement[:2])
            if areas_for_improvement
            else "建议继续加强创新性表达、设计约束权衡与规范化论证"
        )

        return (
            f"结合本次答卷表现，毕业设计（论文）课程目标达成度{attainment_level}。"
            f"仅基于当前答卷可见信息判断，学生在文献分析、设计方法、针对需求设计、专业沟通等方面已有一定基础，"
            f"其中较突出的表现为：{strengths_text}。"
            f"后续仍建议重点提升创新与权衡、国际化视野及复杂工程情境下的综合论证能力，"
            f"尤其应围绕实际工程约束进一步增强方案比较与创新意识。当前需要持续改进的方向主要包括：{improvement_text}。"
        )
