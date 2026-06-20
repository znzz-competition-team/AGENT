"""
论文评估智能体 - 基于大模型自主推理的研究型评估

核心理念（区别于固定工作流）：
1. 大模型自主决定评估重点和策略，而非固定Pass流水线
2. 搜寻研究现状作为前后文，将论文置于学术背景下评价
3. 智能体可自主调用工具（搜索、检索、分析），按需获取信息
4. 输出兆级别详细评价内容与修改建议

架构：
- 智能体循环：思考→行动→观察→再思考（ReAct模式）
- 工具集：搜索研究现状、检索论文段落、获取表格/公式/图片
- 多轮展开：每轮聚焦不同维度，逐步深入，生成详细报告

使用方式：
    from src.evaluation.thesis_evaluation_agent import ThesisEvaluationAgent

    agent = ThesisEvaluationAgent()
    result = agent.evaluate(content, file_path="...")
"""

import json
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ThesisEvaluationAgent:

    def __init__(self):
        self.client = None
        self.ai_config = None
        self.knowledge_base = None
        self.research_context = None
        self._tool_results = {}

    def _ensure_client(self):
        if self.client is None:
            from src.config import get_ai_config
            self.ai_config = get_ai_config()
            import openai
            self.client = openai.OpenAI(
                api_key=self.ai_config["api_key"],
                base_url=self.ai_config["base_url"],
                timeout=300.0
            )

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 8000) -> str:
        self._ensure_client()
        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def _call_llm_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 8000) -> dict:
        self._ensure_client()
        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start != -1 and end > start:
                try:
                    return json.loads(raw[start:end])
                except json.JSONDecodeError:
                    pass
            return {"raw_content": raw}

    def evaluate(
        self,
        content: str,
        student_info: Dict = None,
        indicators: Dict = None,
        dimension_weights: Dict = None,
        file_path: str = None,
    ) -> Dict:
        start_time = time.time()
        student_info = student_info or {}
        indicators = indicators or {}

        logger.info("=" * 60)
        logger.info("智能体评估启动：研究现状搜索 + 自主推理评估")
        logger.info("=" * 60)

        logger.info("[阶段1] 构建本地知识库...")
        self._build_knowledge_base(file_path, content)

        logger.info("[阶段2] 搜寻研究现状...")
        self._search_research_context(content)

        logger.info("[阶段2.5] 提取并锁定论文研究范围...")
        research_scope = self._extract_research_scope(content)

        logger.info("[阶段3] 智能体自主理解论文...")
        understanding = self._agent_understand(content, research_scope)

        logger.info("[阶段4] 智能体自主评估（多维度展开）...")
        evaluation = self._agent_evaluate(content, understanding, research_scope)

        logger.info("[阶段4.5] 智能体分段评估（逐章节深入分析）...")
        section_evaluations = self._agent_section_evaluate(content, understanding, research_scope)

        logger.info("[阶段5] 智能体生成详细修改建议...")
        suggestions = self._agent_suggest(content, understanding, evaluation, section_evaluations, research_scope)

        logger.info("[阶段6] 智能体展开详细报告...")
        detailed_report = self._agent_expand_report(content, understanding, evaluation, suggestions, section_evaluations, research_scope)

        elapsed = time.time() - start_time
        logger.info(f"智能体评估完成，总耗时: {elapsed:.1f}秒")

        kb_stats = self.knowledge_base.get_stats() if self.knowledge_base else {}
        research_data = {}
        if self.research_context:
            research_data = {
                "papers_found": self.research_context.get("papers_count", 0),
                "key_topics": self.research_context.get("key_topics", []),
                "context_document": self.research_context.get("context_document", ""),
                "related_papers": self.research_context.get("related_papers", []),
                "research_landscape": self.research_context.get("research_landscape", {}),
            }

        return {
            "evaluation_method": "agent_evaluation",
            "research_scope": research_scope,
            "understanding": understanding,
            "evaluation": evaluation,
            "section_evaluations": section_evaluations,
            "suggestions": suggestions,
            "detailed_report": detailed_report,
            "research_context": research_data,
            "knowledge_base_stats": kb_stats,
            "elapsed_seconds": round(elapsed, 1),
            "student_info": student_info,
        }

    def _build_knowledge_base(self, file_path: str, content: str):
        if not file_path:
            logger.info("未提供文件路径，跳过知识库构建")
            return

        try:
            from src.evaluation.thesis_knowledge_base import ThesisKnowledgeBase
            self.knowledge_base = ThesisKnowledgeBase()
            stats = self.knowledge_base.build_from_file(file_path, content)
            logger.info(f"知识库构建完成: {stats}")
        except Exception as e:
            logger.warning(f"知识库构建失败: {str(e)}")
            self.knowledge_base = None

    def _search_research_context(self, content: str):
        try:
            from src.evaluation.research_context_builder import ResearchContextBuilder
            builder = ResearchContextBuilder()
            self.research_context = builder.build_context(content)
            logger.info(f"研究现状搜索完成: 找到{self.research_context.get('papers_count', 0)}篇相关论文")
        except Exception as e:
            logger.warning(f"研究现状搜索失败: {str(e)}")
            self.research_context = None

    def _get_kb_context(self) -> str:
        if not self.knowledge_base:
            return ""
        return self.knowledge_base.get_full_evaluation_context()

    def _get_research_context(self) -> str:
        if not self.research_context:
            return ""
        return self.research_context.get("context_document", "")

    def _extract_research_scope(self, content: str) -> Dict:
        system_prompt = """你是一位学术研究范围分析专家。你的任务是精确提取论文明确声明的研究范围。

【核心目标】
从论文的标题和摘要中，提取这篇论文**明确声明**要研究的内容，以及**明确排除**的内容。
这将作为后续评估的"范围锁"——评估时不得建议研究范围外的内容。

【关键原则】
1. 只提取论文明确声明的内容，不要推测
2. 如果标题说"基于A的B研究"，那么研究范围就是A和B，不包括C、D
3. 如果摘要说"本文研究X在Y条件下的Z特性"，那么范围就是X、Y、Z
4. 明确区分"论文研究的内容"和"论文未研究但相关的内容"
5. 不要把"可以扩展的方向"当作"论文的研究范围"

请输出JSON格式。"""

        title_and_abstract = content[:5000]

        user_prompt = f"""请从以下论文的标题和摘要中，精确提取论文的研究范围：

## 论文标题和摘要
{title_and_abstract}

请输出如下JSON格式：
{{
    "title": "论文标题",
    "explicit_research_scope": {{
        "research_object": "研究对象（如：玉米淀粉粉尘、碳酸钙惰化剂等）",
        "research_problem": "研究问题（如：爆炸参数预测、惰化比优化等）",
        "research_method": "研究方法（如：机器学习、PINN、实验等）",
        "research_conditions": "研究条件/约束（如：特定浓度范围、特定温度等）",
        "research_goal": "研究目标（如：建立预测模型、确定最佳惰化比等）"
    }},
    "scope_boundaries": {{
        "what_is_in_scope": ["论文明确研究的内容1", "论文明确研究的内容2"],
        "what_is_out_of_scope": ["论文明确不研究或未涉及的内容1", "论文明确不研究或未涉及的内容2"]
    }},
    "scope_statement": "用一句话概括论文的研究范围（如：本文仅研究A条件下的B方法对C对象的影响，不涉及D、E等）",
    "scope_warning": "评估时绝对不能建议的内容（如：不能建议研究其他粉尘、不能建议研究其他惰化剂、不能建议研究其他方法等）"
}}"""

        return self._call_llm_json(system_prompt, user_prompt, temperature=0.1, max_tokens=4000)

    def _format_scope_constraint(self, research_scope: Dict) -> str:
        if not research_scope:
            return ""
        parts = []
        scope = research_scope.get("explicit_research_scope", {})
        if scope:
            parts.append("【论文明确声明的研究范围】")
            if scope.get("research_object"):
                parts.append(f"- 研究对象: {scope['research_object']}")
            if scope.get("research_problem"):
                parts.append(f"- 研究问题: {scope['research_problem']}")
            if scope.get("research_method"):
                parts.append(f"- 研究方法: {scope['research_method']}")
            if scope.get("research_conditions"):
                parts.append(f"- 研究条件: {scope['research_conditions']}")
            if scope.get("research_goal"):
                parts.append(f"- 研究目标: {scope['research_goal']}")

        boundaries = research_scope.get("scope_boundaries", {})
        if boundaries:
            in_scope = boundaries.get("what_is_in_scope", [])
            out_scope = boundaries.get("what_is_out_of_scope", [])
            if in_scope:
                parts.append("\n【论文研究范围内】")
                for item in in_scope:
                    parts.append(f"  ✓ {item}")
            if out_scope:
                parts.append("\n【论文研究范围外——评估时不得建议研究这些内容】")
                for item in out_scope:
                    parts.append(f"  ✗ {item}")

        scope_statement = research_scope.get("scope_statement", "")
        if scope_statement:
            parts.append(f"\n【范围声明】{scope_statement}")

        scope_warning = research_scope.get("scope_warning", "")
        if scope_warning:
            parts.append(f"\n【范围警告】{scope_warning}")

        return "\n".join(parts)

    def _agent_understand(self, content: str, research_scope: Dict = None) -> Dict:
        kb_ctx = self._get_kb_context()
        research_ctx = self._get_research_context()

        scope_constraint = self._format_scope_constraint(research_scope) if research_scope else ""

        system_prompt = """你是一位资深学术研究方法论专家。你正在深入理解一篇学术论文，目的是为后续评估做准备。

【你的任务】
自主分析这篇论文，理解其研究思路和工作内容。你不是在按固定模板填空，而是像一位真正的审稿人一样，先通读论文，理解作者想做什么、怎么做的、做成了什么。

【理解重点】
1. 作者要解决什么问题？这个问题在领域内的重要性如何？
2. 作者选择了什么研究路线？为什么选这条路线？有没有其他可能的路线？
3. 核心技术方法是什么？创新点在哪里？
4. 实验设计如何？验证了什么？结果如何？
5. 研究的逻辑链条是否完整？有没有跳跃或缺失？
6. 这篇论文在当前研究 landscape 中处于什么位置？

【关键原则】
- 你是在理解论文，不是在评价
- 尽可能从作者的角度理解研究意图
- 结合提供的研究现状信息，理解论文的学术定位
- 结合知识库中的表格、公式、图片信息，理解论文的实际研究内容
- 如果信息不足，明确指出哪些方面信息不足
- 【范围锁定】你必须严格在论文声明的研究范围内理解论文。论文只研究A，你就只理解A，不要去想B和C

请输出JSON格式。"""

        kb_section = f"\n## 本地知识库信息（表格/公式/图片/研究链条）\n{kb_ctx[:5000]}\n" if kb_ctx else ""
        research_section = f"\n## 研究现状上下文（从学术数据库搜索的相关研究）\n{research_ctx[:5000]}\n" if research_ctx else ""
        scope_section = f"\n## ⚠️ 论文研究范围锁定（你必须严格在此范围内理解论文）\n{scope_constraint}\n" if scope_constraint else ""

        user_prompt = f"""请深入理解以下论文：

## 论文内容
{content[:40000]}
{scope_section}
{kb_section}
{research_section}
请自主分析并输出如下JSON格式（内容要详细，每个字段至少200字）：
{{
    "research_problem": {{
        "core_question": "核心研究问题",
        "importance_in_field": "在领域内的重要性分析",
        "problem_novelty": "问题的新颖性分析",
        "practical_significance": "实际应用意义"
    }},
    "research_route": {{
        "chosen_route": "作者选择的研究路线",
        "why_this_route": "选择这条路线的原因分析",
        "route_rationality": "路线合理性评价"
    }},
    "technical_methods": [
        {{
            "name": "方法名称",
            "core_idea": "核心思想",
            "innovation_point": "创新点",
            "implementation_detail": "实现细节",
            "advantages": "优势",
            "limitations": "局限性"
        }}
    ],
    "experimental_design": {{
        "overall_setup": "实验整体设计",
        "datasets_and_scenarios": "数据集/场景",
        "baselines": "对比基线",
        "metrics": "评估指标",
        "results_summary": "结果概述",
        "fairness_analysis": "实验公平性分析"
    }},
    "logic_chain": {{
        "problem_to_method": "从问题到方法的逻辑",
        "method_to_experiment": "从方法到实验的逻辑",
        "experiment_to_conclusion": "从实验到结论的逻辑",
        "logic_gaps": "逻辑链条中的跳跃或缺失",
        "unsubstantiated_claims": "缺乏充分论证的结论"
    }},
    "academic_positioning": {{
        "position_in_landscape": "在当前研究 landscape 中的位置",
        "comparison_with_sota": "与最先进方法的对比",
        "contribution_type": "贡献类型（方法创新/应用创新/改进创新/工程实现）",
        "contribution_significance": "贡献的学术意义"
    }},
    "key_insights": "你对这篇论文最重要的3个洞察",
    "information_gaps": "信息不足的方面"
}}"""

        return self._call_llm_json(system_prompt, user_prompt, temperature=0.2, max_tokens=10000)

    def _agent_evaluate(self, content: str, understanding: Dict, research_scope: Dict = None) -> Dict:
        kb_ctx = self._get_kb_context()
        research_ctx = self._get_research_context()
        understanding_str = json.dumps(understanding, ensure_ascii=False, indent=2)[:6000]
        scope_constraint = self._format_scope_constraint(research_scope) if research_scope else ""

        scope_instruction = ""
        if scope_constraint:
            scope_instruction = f"""
【⚠️ 研究范围硬约束 - 必须严格遵守】
{scope_constraint}

你必须在此范围内评估论文。具体规则：
1. 如果论文标题和摘要明确只研究A，你不能因为"还应该研究B和C"而扣分
2. 你不能建议论文扩大研究范围（如"应增加其他粉尘类型"、"应研究其他惰化剂"等）
3. 你只能在论文声明的范围内评价其研究深度和方法质量
4. 如果论文在其声明的范围内做得好，应该给予肯定
5. "研究范围有限"不是不足——除非论文自身声称研究范围更广但实际没做到
"""

        system_prompt = f"""你是一位资深的学术论文评审专家。你刚刚深入理解了一篇论文，现在要对其进行全面评估。

【评估哲学 - 不要像填表一样评估】
你不是在按固定模板打分，而是像一位真正的审稿人一样，基于你对论文的理解和研究现状的把握，自主决定评估的重点和深度。

【评估原则】
1. 基于你对论文的理解和研究现状，自主决定哪些方面值得深入评价
2. 评价要聚焦学术实质：研究方法是否严谨、实验设计是否合理、创新性是否真实、逻辑推理是否严密
3. 不要纠结于文字笔误、格式细节等表面问题
4. 每个评价点必须有论文原文中的具体证据支撑
5. 结合研究现状，评价论文的学术贡献和创新性
6. 如果论文在某些方面做得好，要给予肯定；如果存在实质性问题，要深入分析
{scope_instruction}
请输出JSON格式。"""

        kb_section = f"\n## 知识库信息\n{kb_ctx[:3000]}\n" if kb_ctx else ""
        research_section = f"\n## 研究现状\n{research_ctx[:4000]}\n" if research_ctx else ""

        user_prompt = f"""请基于你对论文的理解，进行全面评估：

## 论文理解
{understanding_str}

## 论文内容（供引用证据）
{content[:30000]}
{kb_section}
{research_section}
请自主评估并输出详细JSON（每个评价点至少300字，包含具体证据，优势至少5个，不足至少5个）：
{{
    "overall_assessment": {{
        "score": 0-100,
        "grade": "优秀/良好/中等/及格/不及格",
        "summary": "总体评价（800字以上，聚焦学术质量和研究深度）"
    }},
    "evaluation_focus": "你自主决定的评估重点和理由",
    "strengths": [
        {{
            "aspect": "优势方面",
            "detail": "详细分析（300字以上，引用原文证据）",
            "significance": "这个优势的学术意义"
        }}
    ],
    "weaknesses": [
        {{
            "aspect": "不足方面",
            "detail": "详细分析（300字以上，引用原文证据）",
            "severity": "严重/中等/轻微",
            "impact": "这个问题对论文质量的影响",
            "evidence": "支撑此判断的原文具体内容"
        }}
    ],
    "methodology_evaluation": {{
        "rigor": "方法严谨性分析（300字以上）",
        "appropriateness": "方法选择适当性分析（300字以上）",
        "innovation_authenticity": "创新性真实性分析（300字以上，结合研究现状）",
        "comparison_with_sota": "与最先进方法的对比分析（300字以上）"
    }},
    "experiment_evaluation": {{
        "design_quality": "实验设计质量分析（300字以上）",
        "baseline_fairness": "基线对比公平性分析（300字以上）",
        "result_depth": "结果分析深度（300字以上）",
        "reproducibility": "可复现性分析"
    }},
    "logic_evaluation": {{
        "chain_completeness": "逻辑链完整性分析（300字以上）",
        "reasoning_rigor": "推理严密性分析（300字以上）",
        "unsubstantiated_claims": "缺乏充分论证的结论（详细列举）"
    }},
    "academic_contribution": {{
        "contribution_type": "贡献类型分析",
        "contribution_degree": "贡献程度分析（结合研究现状，300字以上）",
        "potential_impact": "潜在学术影响"
    }}
}}"""

        return self._call_llm_json(system_prompt, user_prompt, temperature=0.2, max_tokens=16000)

    def _agent_section_evaluate(self, content: str, understanding: Dict, research_scope: Dict = None) -> Dict:
        """分段评估：对论文的每个主要章节进行独立深入评估，每章节单独调用LLM"""
        kb_ctx = self._get_kb_context()
        understanding_str = json.dumps(understanding, ensure_ascii=False, indent=2)[:4000]
        scope_constraint = self._format_scope_constraint(research_scope) if research_scope else ""

        # 从知识库获取章节信息
        sections_info = []
        if self.knowledge_base and hasattr(self.knowledge_base, 'structured_index'):
            sections_info = self.knowledge_base.structured_index.get("sections", [])

        # 如果没有知识库章节，从内容中提取
        if not sections_info:
            sections_info = self._extract_sections_from_content(content)

        if not sections_info:
            logger.warning("无法提取章节信息，跳过分段评估")
            return {"sections": [], "section_summary": "无法提取章节信息，跳过分段评估"}

        scope_instruction = ""
        if scope_constraint:
            scope_instruction = f"""
【⚠️ 研究范围硬约束】
{scope_constraint}
评估时必须严格遵守研究范围，不得建议范围外的内容。
"""

        # 逐章节独立评估，每个章节单独调用LLM
        all_section_results = []
        for i, sec in enumerate(sections_info[:10]):  # 最多处理10个章节
            title = sec.get("title", f"章节{i+1}")
            sec_type = sec.get("type", "")
            char_count = sec.get("char_count", 0)
            # 增加内容预览长度到3000字符
            content_preview = sec.get("content", "")[:3000]

            logger.info(f"  分段评估: {title} ({i+1}/{min(len(sections_info), 10)})")

            section_system_prompt = f"""你是一位资深的学术论文评审专家。你正在对论文的某个章节进行独立深入评估。

【分段评估原则】
1. 对该章节进行独立、深入的评估，聚焦该章节特有的问题
2. 评估要具体到段落级别，引用该章节的原文内容
3. 评估要关注：内容完整性、逻辑连贯性、论证充分性、表达清晰性、与前后章节的衔接
4. 必须给出至少5条具体的改进方向和修改建议
5. 注意区分不同章节的评估重点（如引言重在问题阐述，方法重在严谨性，实验重在设计合理性）
6. 每条建议必须包含修改前后的对比示例
{scope_instruction}
请输出JSON格式。"""

            kb_section = f"\n## 知识库信息\n{kb_ctx[:2000]}\n" if kb_ctx else ""

            # 根据章节类型调整评估重点
            type_specific_guidance = ""
            if sec_type == "introduction":
                type_specific_guidance = "本章节是引言/绪论，评估重点：研究问题是否清晰、文献综述是否全面、研究动机是否充分、研究目标是否明确"
            elif sec_type == "methodology":
                type_specific_guidance = "本章节是方法论，评估重点：方法描述是否完整可复现、方法选择是否有充分理由、创新点是否真实、公式/算法是否正确"
            elif sec_type == "experiment":
                type_specific_guidance = "本章节是实验/结果，评估重点：实验设计是否合理、对比基线是否公平、结果分析是否深入、结论是否有数据支撑"
            elif sec_type == "conclusion":
                type_specific_guidance = "本章节是结论，评估重点：结论是否与实验结果一致、是否总结了核心贡献、局限性是否坦诚、未来工作是否合理"
            else:
                type_specific_guidance = "评估该章节的内容完整性、逻辑连贯性和表达质量"

            section_user_prompt = f"""请对以下论文章节进行独立深入评估：

## 论文整体理解
{understanding_str}

## 当前评估章节: {title}
- 章节类型: {sec_type}
- 字数: {char_count}
- 评估重点: {type_specific_guidance}

## 章节内容
{content_preview}
{kb_section}

请输出如下JSON格式（评估内容至少600字，改进建议至少5条，每条建议至少150字）：
{{
    "section_title": "{title}",
    "section_type": "{sec_type}",
    "content_completeness": {{
        "assessment": "内容完整性评估（300字以上，该章节是否完整覆盖了应包含的内容）",
        "missing_elements": ["缺失的内容要素1", "缺失的内容要素2", "缺失的内容要素3"]
    }},
    "logic_coherence": {{
        "assessment": "逻辑连贯性评估（300字以上，章节内部逻辑是否清晰连贯）",
        "logic_issues": ["逻辑问题1", "逻辑问题2", "逻辑问题3"]
    }},
    "argument_quality": {{
        "assessment": "论证充分性评估（300字以上，论点是否有充分的数据/文献/推理支撑）",
        "weak_arguments": ["论证不足的论点1", "论证不足的论点2", "论证不足的论点3"]
    }},
    "expression_clarity": {{
        "assessment": "表达清晰性评估（200字以上，语言表达是否准确、简洁、专业）",
        "expression_issues": ["表达问题1", "表达问题2"]
    }},
    "connection_with_adjacent": "与前后章节的衔接评估（200字以上）",
    "strengths": [
        {{
            "point": "该章节的优势点",
            "evidence": "原文证据",
            "significance": "这个优势的意义"
        }}
    ],
    "weaknesses": [
        {{
            "point": "该章节的不足点",
            "evidence": "原文证据",
            "severity": "严重/中等/轻微",
            "impact": "对论文整体的影响"
        }}
    ],
    "specific_suggestions": [
        {{
            "suggestion": "具体修改建议（150字以上，包含问题分析和修改方向）",
            "priority": "高/中/低",
            "location": "建议修改的具体位置",
            "before_example": "修改前的原文片段",
            "after_example": "修改后的示例片段"
        }}
    ],
    "section_score": 0-100
}}"""

            try:
                result = self._call_llm_json(section_system_prompt, section_user_prompt, temperature=0.2, max_tokens=8000)
                all_section_results.append(result)
            except Exception as e:
                logger.warning(f"章节 '{title}' 评估失败: {str(e)}")
                all_section_results.append({
                    "section_title": title,
                    "section_type": sec_type,
                    "error": str(e),
                    "section_score": 0
                })

        # 生成跨章节分析和总结
        logger.info("  生成分段评估总结和跨章节分析...")
        summary_system_prompt = f"""你是一位资深的学术论文评审专家。你刚刚逐章评估了一篇论文，现在需要生成总结和跨章节分析。

{scope_instruction}
请输出JSON格式。"""

        # 构建各章节评估摘要
        section_summaries = ""
        for i, sec_result in enumerate(all_section_results):
            title = sec_result.get("section_title", f"章节{i+1}")
            score = sec_result.get("section_score", "N/A")
            # 提取关键问题
            weaknesses = sec_result.get("weaknesses", [])
            weakness_points = [w.get("point", "") if isinstance(w, dict) else str(w) for w in weaknesses[:3]]
            suggestions = sec_result.get("specific_suggestions", [])
            suggestion_points = [s.get("suggestion", "")[:80] if isinstance(s, dict) else str(s)[:80] for s in suggestions[:3]]
            section_summaries += f"\n### {title} (得分: {score})\n主要不足: {'; '.join(weakness_points)}\n关键建议: {'; '.join(suggestion_points)}\n"

        summary_user_prompt = f"""请基于以下各章节评估结果，生成总结和跨章节分析：

## 各章节评估摘要
{section_summaries}

请输出如下JSON格式：
{{
    "section_summary": "分段评估总结（800字以上，概括各章节的整体质量、最关键的改进方向、各章节的相对优劣）",
    "cross_section_issues": [
        {{
            "issue": "跨章节问题（如前后矛盾、重复论述、逻辑断裂、术语不一致等）",
            "involved_sections": "涉及的章节",
            "detail": "问题详细描述（200字以上）",
            "suggestion": "解决建议（200字以上，包含具体操作步骤）"
        }}
    ],
    "overall_structure_assessment": "论文整体结构评估（500字以上，结构是否合理、章节安排是否得当、篇幅分配是否均衡）",
    "priority_improvement_areas": [
        {{
            "area": "优先改进领域",
            "reason": "为什么这是优先改进的（200字以上）",
            "affected_sections": "涉及的章节",
            "improvement_direction": "改进方向（200字以上）"
        }}
    ]
}}"""

        try:
            summary_result = self._call_llm_json(summary_system_prompt, summary_user_prompt, temperature=0.2, max_tokens=8000)
        except Exception as e:
            logger.warning(f"分段评估总结生成失败: {str(e)}")
            summary_result = {
                "section_summary": "分段评估总结生成失败",
                "cross_section_issues": [],
                "overall_structure_assessment": "",
                "priority_improvement_areas": []
            }

        return {
            "sections": all_section_results,
            "section_summary": summary_result.get("section_summary", ""),
            "cross_section_issues": summary_result.get("cross_section_issues", []),
            "overall_structure_assessment": summary_result.get("overall_structure_assessment", ""),
            "priority_improvement_areas": summary_result.get("priority_improvement_areas", [])
        }

    def _extract_sections_from_content(self, content: str) -> List[Dict]:
        """从纯文本内容中提取章节信息（当知识库不可用时的备用方案）"""
        import re
        sections = []

        # 检测章节标题
        chapter_pattern = re.compile(r'(?:^|\n)\s*(第[一二三四五六七八九十\d]+\s*章[^\n]*)', re.MULTILINE)
        abstract_pattern = re.compile(r'(?:^|\n)\s*(摘\s*要)\s*(?:\n|：:|$)', re.MULTILINE)

        all_matches = []
        for m in chapter_pattern.finditer(content):
            title = m.group(1).strip()
            all_matches.append({"title": title, "offset": m.start()})
        for m in abstract_pattern.finditer(content):
            all_matches.append({"title": "摘要", "offset": m.start()})

        all_matches.sort(key=lambda x: x["offset"])

        if not all_matches:
            # 如果没有检测到章节，按字数均分
            chunk_size = max(len(content) // 5, 3000)
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i+chunk_size]
                sections.append({
                    "title": f"第{len(sections)+1}部分",
                    "type": "other",
                    "char_count": len(chunk),
                    "content": chunk[:2000]
                })
            return sections

        for i, match in enumerate(all_matches):
            start = match["offset"]
            end = all_matches[i+1]["offset"] if i+1 < len(all_matches) else len(content)
            section_content = content[start:end]
            title = match["title"]

            # 推断章节类型
            sec_type = "other"
            title_lower = title.lower()
            if any(k in title for k in ["绪论", "引言", "研究背景", "摘要"]):
                sec_type = "introduction"
            elif any(k in title for k in ["方法", "模型", "算法", "设计", "理论", "框架"]):
                sec_type = "methodology"
            elif any(k in title for k in ["实验", "结果", "分析", "验证", "测试"]):
                sec_type = "experiment"
            elif any(k in title for k in ["结论", "总结", "展望"]):
                sec_type = "conclusion"
            elif any(k in title for k in ["参考文献"]):
                sec_type = "references"

            sections.append({
                "title": title,
                "type": sec_type,
                "char_count": len(section_content),
                "content": section_content[:2000]
            })

        return sections

    def _agent_suggest(self, content: str, understanding: Dict, evaluation: Dict, section_evaluations: Dict = None, research_scope: Dict = None) -> Dict:
        understanding_str = json.dumps(understanding, ensure_ascii=False, indent=2)[:4000]
        evaluation_str = json.dumps(evaluation, ensure_ascii=False, indent=2)[:8000]
        section_eval_str = json.dumps(section_evaluations, ensure_ascii=False, indent=2)[:6000] if section_evaluations else ""
        research_ctx = self._get_research_context()
        scope_constraint = self._format_scope_constraint(research_scope) if research_scope else ""

        scope_instruction = ""
        if scope_constraint:
            scope_instruction = f"""
【⚠️ 研究范围硬约束 - 修改建议必须严格遵守】
{scope_constraint}

修改建议的范围规则：
1. 你绝对不能建议论文研究范围外的内容（如论文只研究A，不能建议"还应研究B和C"）
2. 你不能建议扩大研究对象、研究问题或研究方法
3. 你只能在论文声明的范围内，建议如何做得更好、更深入、更严谨
4. "扩大研究范围"类的建议是禁止的，除非论文自身声称要研究但没做到
5. 你可以建议的是：在当前范围内深化分析、改进方法、完善实验、加强论证
"""

        system_prompt = f"""你是一位学术论文修改指导专家。你刚刚评估了一篇论文，现在要为作者提供详细的修改建议。

【建议原则】
1. 每条建议必须具体、可操作，不能泛泛而谈
2. 建议要基于你对论文的理解、评估和分段评估结果，以及研究现状
3. 对于每个问题，提供具体的修改方案和修改后的示例
4. 建议要区分优先级：哪些是必须修改的，哪些是建议修改的
5. 结合研究现状，建议作者如何提升论文的学术贡献
6. 每条建议至少300字，包含问题分析、修改方案、修改示例
7. 必须修改建议至少8条，建议修改至少8条
8. 每条建议都要引用论文原文作为问题证据
9. 每条建议都要给出修改前后的对比示例
{scope_instruction}
请输出JSON格式。"""

        research_section = f"\n## 研究现状（供参考）\n{research_ctx[:4000]}\n" if research_ctx else ""
        section_section = f"\n## 分段评估结果（供参考，针对各章节的具体问题）\n{section_eval_str}\n" if section_eval_str else ""

        user_prompt = f"""请为这篇论文提供详细的修改建议：

## 论文理解
{understanding_str}

## 评估结果
{evaluation_str}
{section_section}
## 论文内容（供引用和生成修改示例）
{content[:30000]}
{research_section}
请输出详细JSON（必须修改至少8条，建议修改至少8条，每条至少300字）：
{{
    "critical_suggestions": [
        {{
            "aspect": "修改方面",
            "problem": "当前存在的具体问题（引用原文）",
            "why_critical": "为什么这个问题必须修改（150字以上）",
            "solution": "具体修改方案（400字以上，包含操作步骤）",
            "before_example": "修改前的原文片段",
            "after_example": "修改后的示例（200字以上）",
            "expected_improvement": "预期改进效果（150字以上）"
        }}
    ],
    "recommended_suggestions": [
        {{
            "aspect": "修改方面",
            "problem": "当前存在的问题（引用原文）",
            "why_recommended": "为什么建议修改（100字以上）",
            "solution": "具体修改方案（300字以上）",
            "before_example": "修改前",
            "after_example": "修改后（150字以上）",
            "expected_improvement": "预期改进效果（100字以上）"
        }}
    ],
    "section_specific_suggestions": [
        {{
            "section": "针对的章节",
            "suggestions": [
                {{
                    "aspect": "修改方面",
                    "problem": "该章节的具体问题（引用原文）",
                    "solution": "具体修改方案（250字以上）",
                    "before_example": "修改前",
                    "after_example": "修改后"
                }}
            ]
        }}
    ],
    "research_enhancement": {{
        "literature_gap": "文献综述方面需要补充的内容（结合研究现状，400字以上）",
        "methodology_enhancement": "方法论方面可以加强的内容（400字以上）",
        "experiment_enhancement": "实验方面可以补充的内容（400字以上）",
        "sota_comparison": "建议增加的与最先进方法的对比（400字以上）"
    }},
    "writing_improvement": {{
        "structure_optimization": "论文结构优化建议（400字以上）",
        "expression_improvement": "表达改进建议（400字以上）",
        "figure_table_improvement": "图表改进建议（400字以上）"
    }},
    "priority_roadmap": "修改优先级路线图（按紧急程度排序，800字以上，分为紧急/重要/建议三个层级）"
}}"""

        return self._call_llm_json(system_prompt, user_prompt, temperature=0.2, max_tokens=24000)

    def _agent_expand_report(self, content: str, understanding: Dict, evaluation: Dict, suggestions: Dict, section_evaluations: Dict = None, research_scope: Dict = None) -> Dict:
        """展开详细报告：拆分为多次LLM调用，每个部分独立生成，最后合并"""
        understanding_str = json.dumps(understanding, ensure_ascii=False, indent=2)[:3000]
        evaluation_str = json.dumps(evaluation, ensure_ascii=False, indent=2)[:5000]
        suggestions_str = json.dumps(suggestions, ensure_ascii=False, indent=2)[:5000]
        section_eval_str = json.dumps(section_evaluations, ensure_ascii=False, indent=2)[:5000] if section_evaluations else ""
        research_ctx = self._get_research_context()
        scope_constraint = self._format_scope_constraint(research_scope) if research_scope else ""

        scope_instruction = ""
        if scope_constraint:
            scope_instruction = f"""
【⚠️ 研究范围硬约束 - 报告中必须严格遵守】
{scope_constraint}

报告中不得出现以下内容：
1. 建议论文研究范围外的对象、问题或方法
2. 因为"研究范围有限"而扣分或批评
3. "还应研究X"、"可以扩展到Y"等越界建议
"""

        research_section = f"\n## 研究现状\n{research_ctx[:3000]}\n" if research_ctx else ""
        content_for_quote = content[:25000]

        # 定义报告各部分的生成任务
        report_parts = {}

        # ===== 第1部分：执行摘要 + 研究背景 =====
        logger.info("  报告生成: 执行摘要与研究背景...")
        part1_system = f"""你是一位学术写作专家。请撰写论文评估报告的"执行摘要"和"研究背景分析"部分。

【要求】
1. 执行摘要要全面概括论文的核心发现、总体评价和最关键的改进方向
2. 研究背景分析要将论文置于当前学术 landscape 中，结合研究现状进行定位
3. 大量引用论文原文作为证据
4. 执行摘要至少1500字，研究背景分析至少1500字
{scope_instruction}
请输出JSON格式。"""

        part1_user = f"""请撰写评估报告的执行摘要和研究背景分析：

## 论文理解
{understanding_str}

## 评估结果
{evaluation_str}

## 论文原文（供引用）
{content_for_quote}
{research_section}

请输出JSON：
{{
    "executive_summary": "执行摘要（1500字以上，包含：论文总体评价、核心发现、最关键的优势和不足、最重要的改进方向）",
    "research_context_analysis": "研究背景分析（1500字以上，包含：论文在当前研究landscape中的定位、与相关研究的对比、研究问题的学术价值、论文的学术贡献程度）"
}}"""

        try:
            part1 = self._call_llm_json(part1_system, part1_user, temperature=0.2, max_tokens=16000)
            report_parts.update(part1)
        except Exception as e:
            logger.warning(f"报告第1部分生成失败: {str(e)}")
            report_parts["executive_summary"] = "执行摘要生成失败"
            report_parts["research_context_analysis"] = "研究背景分析生成失败"

        # ===== 第2部分：方法论深度分析 + 实验深度分析 =====
        logger.info("  报告生成: 方法论与实验深度分析...")
        part2_system = f"""你是一位学术写作专家。请撰写论文评估报告的"方法论深度分析"和"实验深度分析"部分。

【要求】
1. 方法论分析要深入剖析研究方法的选择理由、实现细节、创新性和局限性
2. 实验分析要深入剖析实验设计、数据处理、结果分析和结论可靠性
3. 大量引用论文原文作为证据
4. 方法论分析至少1500字，实验分析至少1500字
{scope_instruction}
请输出JSON格式。"""

        part2_user = f"""请撰写评估报告的方法论深度分析和实验深度分析：

## 论文理解
{understanding_str}

## 评估结果
{evaluation_str}

## 论文原文（供引用）
{content_for_quote}
{research_section}

请输出JSON：
{{
    "methodology_deep_dive": "方法论深度分析（1500字以上，包含：研究方法的选择与合理性、方法实现的技术细节、创新点的真实性分析、方法局限性分析、与同类方法的对比）",
    "experiment_deep_dive": "实验深度分析（1500字以上，包含：实验设计质量、数据集/场景的代表性、对比基线的公平性、结果分析的深度、结论的可靠性、可复现性评估）"
}}"""

        try:
            part2 = self._call_llm_json(part2_system, part2_user, temperature=0.2, max_tokens=16000)
            report_parts.update(part2)
        except Exception as e:
            logger.warning(f"报告第2部分生成失败: {str(e)}")
            report_parts["methodology_deep_dive"] = "方法论分析生成失败"
            report_parts["experiment_deep_dive"] = "实验分析生成失败"

        # ===== 第3部分：逻辑链分析 + 创新性评估 =====
        logger.info("  报告生成: 逻辑链与创新性分析...")
        part3_system = f"""你是一位学术写作专家。请撰写论文评估报告的"逻辑链分析"和"创新性评估"部分。

【要求】
1. 逻辑链分析要追踪论文从问题到结论的推理过程，找出逻辑跳跃和论证缺失
2. 创新性评估要客观评价论文的创新点是否真实、有多大价值
3. 大量引用论文原文作为证据
4. 逻辑链分析至少1500字，创新性评估至少1500字
{scope_instruction}
请输出JSON格式。"""

        part3_user = f"""请撰写评估报告的逻辑链分析和创新性评估：

## 论文理解
{understanding_str}

## 评估结果
{evaluation_str}

## 论文原文（供引用）
{content_for_quote}
{research_section}

请输出JSON：
{{
    "logic_chain_analysis": "逻辑链分析（1500字以上，包含：问题→方法的逻辑、方法→实验的逻辑、实验→结论的逻辑、逻辑跳跃和缺失、缺乏充分论证的结论、推理严密性总体评价）",
    "innovation_assessment": "创新性评估（1500字以上，包含：论文声称的创新点、创新点的真实性分析、创新程度评价、与最先进方法的差异、创新性的学术价值、创新性提升建议）"
}}"""

        try:
            part3 = self._call_llm_json(part3_system, part3_user, temperature=0.2, max_tokens=16000)
            report_parts.update(part3)
        except Exception as e:
            logger.warning(f"报告第3部分生成失败: {str(e)}")
            report_parts["logic_chain_analysis"] = "逻辑链分析生成失败"
            report_parts["innovation_assessment"] = "创新性评估生成失败"

        # ===== 第4部分：详细优势 + 详细不足 =====
        logger.info("  报告生成: 优势与不足分析...")
        part4_system = f"""你是一位学术写作专家。请撰写论文评估报告的"详细优势分析"和"详细不足分析"部分。

【要求】
1. 优势分析要深入展开每个优势点，说明其学术意义和对论文质量的贡献
2. 不足分析要深入展开每个不足点，说明其严重程度和对论文质量的影响
3. 大量引用论文原文作为证据
4. 优势分析至少1500字，不足分析至少1500字
5. 至少分析5个优势和5个不足
{scope_instruction}
请输出JSON格式。"""

        part4_user = f"""请撰写评估报告的详细优势分析和详细不足分析：

## 论文理解
{understanding_str}

## 评估结果
{evaluation_str}

## 论文原文（供引用）
{content_for_quote}

请输出JSON：
{{
    "detailed_strengths": "详细优势分析（1500字以上，至少分析5个优势点，每个优势包含：具体表现、原文证据、学术意义、对论文质量的贡献）",
    "detailed_weaknesses": "详细不足分析（1500字以上，至少分析5个不足点，每个不足包含：具体问题、原文证据、严重程度、对论文质量的影响、改进方向）"
}}"""

        try:
            part4 = self._call_llm_json(part4_system, part4_user, temperature=0.2, max_tokens=16000)
            report_parts.update(part4)
        except Exception as e:
            logger.warning(f"报告第4部分生成失败: {str(e)}")
            report_parts["detailed_strengths"] = "优势分析生成失败"
            report_parts["detailed_weaknesses"] = "不足分析生成失败"

        # ===== 第5部分：逐章节深度分析 =====
        logger.info("  报告生成: 逐章节深度分析...")
        part5_system = f"""你是一位学术写作专家。请撰写论文评估报告的"逐章节深度分析"部分。

【要求】
1. 对论文的每个主要章节进行深度分析
2. 每个章节的分析包含：内容概述、质量评价、具体问题、改进建议
3. 大量引用论文原文作为证据
4. 总计至少3000字
{scope_instruction}
请输出JSON格式。"""

        part5_user = f"""请撰写评估报告的逐章节深度分析：

## 论文理解
{understanding_str}

## 分段评估结果
{section_eval_str}

## 评估结果
{evaluation_str}

## 论文原文（供引用）
{content_for_quote}

请输出JSON：
{{
    "section_by_section_analysis": "逐章节深度分析（总计3000字以上，对每个主要章节分别分析，每章包含：①内容概述（该章节做了什么）②质量评价（做得怎么样）③具体问题（存在哪些问题，引用原文）④改进建议（如何改进，给出具体方向））",
    "cross_section_analysis": "跨章节问题分析（800字以上，分析章节间的逻辑衔接、内容重复、前后矛盾、术语不一致、数据不一致等问题，给出具体解决建议）"
}}"""

        try:
            part5 = self._call_llm_json(part5_system, part5_user, temperature=0.2, max_tokens=16000)
            report_parts.update(part5)
        except Exception as e:
            logger.warning(f"报告第5部分生成失败: {str(e)}")
            report_parts["section_by_section_analysis"] = "逐章节分析生成失败"
            report_parts["cross_section_analysis"] = "跨章节分析生成失败"

        # ===== 第6部分：修改指导 + 学术提升路线图 =====
        logger.info("  报告生成: 修改指导与提升路线图...")
        part6_system = f"""你是一位学术写作专家。请撰写论文评估报告的"修改指导"和"学术提升路线图"部分。

【要求】
1. 修改指导要按章节组织，给出具体的修改前后对比示例
2. 学术提升路线图要给出从当前水平到更高水平的具体路径
3. 大量引用论文原文和修改建议
4. 修改指导至少2500字，学术提升路线图至少1500字
{scope_instruction}
请输出JSON格式。"""

        part6_user = f"""请撰写评估报告的修改指导和学术提升路线图：

## 论文理解
{understanding_str}

## 评估结果
{evaluation_str}

## 修改建议
{suggestions_str}

## 分段评估结果
{section_eval_str}

## 论文原文（供引用和生成修改示例）
{content_for_quote}

请输出JSON：
{{
    "modification_guide": "修改指导（2500字以上，按章节组织，每个章节列出：①必须修改的问题（含修改前后对比示例）②建议修改的问题（含修改前后对比示例）③修改优先级排序）",
    "academic_improvement_roadmap": "学术提升路线图（1500字以上，包含：①短期改进（1-2周可完成的关键修改）②中期提升（1-2个月可完成的深度改进）③长期规划（3个月以上的学术提升方向）④预期效果评估）"
}}"""

        try:
            part6 = self._call_llm_json(part6_system, part6_user, temperature=0.2, max_tokens=16000)
            report_parts.update(part6)
        except Exception as e:
            logger.warning(f"报告第6部分生成失败: {str(e)}")
            report_parts["modification_guide"] = "修改指导生成失败"
            report_parts["academic_improvement_roadmap"] = "学术提升路线图生成失败"

        # ===== 第7部分：总结性评价 =====
        logger.info("  报告生成: 总结性评价...")
        part7_system = f"""你是一位学术写作专家。请撰写论文评估报告的"总结性评价"部分。

【要求】
1. 总结性评价要全面回顾评估的核心发现
2. 要给出明确的总体评价和改进优先级
3. 要对论文的学术价值做出客观判断
4. 至少1500字
{scope_instruction}
请输出JSON格式。"""

        # 构建前面各部分的摘要供总结参考
        prev_summary = ""
        for key in ["executive_summary", "methodology_deep_dive", "experiment_deep_dive",
                     "logic_chain_analysis", "innovation_assessment",
                     "detailed_strengths", "detailed_weaknesses"]:
            val = report_parts.get(key, "")
            if val and len(val) > 50:
                prev_summary += f"\n【{key}】{val[:300]}...\n"

        part7_user = f"""请撰写评估报告的总结性评价：

## 前面各部分摘要
{prev_summary}

## 评估结果
{evaluation_str}

## 修改建议
{suggestions_str}

请输出JSON：
{{
    "conclusion": "总结性评价（1500字以上，包含：①论文总体评价和等级②核心优势总结③核心不足总结④最关键的3-5个改进方向⑤改进后的预期效果⑥对作者的最终建议）"
}}"""

        try:
            part7 = self._call_llm_json(part7_system, part7_user, temperature=0.2, max_tokens=8000)
            report_parts.update(part7)
        except Exception as e:
            logger.warning(f"报告第7部分生成失败: {str(e)}")
            report_parts["conclusion"] = "总结性评价生成失败"

        logger.info("  报告各部分生成完成，合并中...")
        return report_parts
