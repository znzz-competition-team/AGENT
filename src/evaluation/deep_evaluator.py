"""
深度评估器 - 多Pass分解 + Self-Refine迭代 + 差异化修改路线图

三大核心策略：
1. 多Pass分解评估（思路一）：将评估拆分为多个专注的Pass，每个Pass聚焦一个维度
2. Self-Refine自我迭代（思路二）：生成→批评→修订，三轮迭代提升深度
3. 差异化修改路线图（思路六）：量化问题影响→优先级排序→修改前后对比

使用方式：
    from src.evaluation.deep_evaluator import DeepEvaluator

    evaluator = DeepEvaluator()
    result = evaluator.evaluate(content, student_info=...)
"""

from typing import Dict, List, Optional
import json
import logging
import os
import copy
import time

logger = logging.getLogger(__name__)


class DeepEvaluator:

    def __init__(self, llm_evaluator=None):
        self._llm_evaluator = llm_evaluator
        self.client = None
        self.ai_config = None

    def _ensure_client(self):
        if self.client is None:
            from src.config import get_ai_config
            self.ai_config = get_ai_config()
            if self._llm_evaluator:
                self.client = self._llm_evaluator._initialize_client(self.ai_config)
            else:
                from src.evaluation.llm_evaluator import LLMEvaluator
                self._llm_evaluator = LLMEvaluator()
                self.client = self._llm_evaluator._initialize_client(self.ai_config)

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.1, max_tokens: int = 8000) -> str:
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
        return response.choices[0].message.content

    def _safe_json_parse(self, raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass
        import re
        raw = re.sub(r',\s*}', '}', raw)
        raw = re.sub(r',\s*]', ']', raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw_content": raw}

    def evaluate(
        self,
        content: str,
        student_info: Dict = None,
        indicators: Dict = None,
        dimension_weights: Dict = None,
        file_path: str = None,
    ) -> Dict:
        logger.info("=" * 60)
        logger.info("开始深度评估流程（多Pass分解 + Self-Refine + 修改路线图）")
        logger.info("=" * 60)

        start_time = time.time()
        student_info = student_info or {}
        indicators = indicators or {}

        knowledge_base = None
        kb_context = ""
        visual_context = ""
        if file_path:
            try:
                from src.evaluation.thesis_knowledge_base import ThesisKnowledgeBase
                knowledge_base = ThesisKnowledgeBase()
                kb_stats = knowledge_base.build_from_file(file_path, content)
                logger.info(f"知识库构建完成: {kb_stats}")
                kb_context = knowledge_base.get_full_evaluation_context()
                visual_context = knowledge_base.visual_index.get("tables", []) or knowledge_base.visual_index.get("figures", []) or knowledge_base.visual_index.get("formulas", [])
                if isinstance(visual_context, list):
                    visual_context = ""
                logger.info(f"知识库上下文{len(kb_context)}字符")
            except Exception as e:
                logger.warning(f"知识库构建失败（不影响主流程）: {str(e)}")
                knowledge_base = None
                kb_context = ""
                try:
                    from src.evaluation.thesis_vision_analyzer import ThesisVisionAnalyzer
                    vision_analyzer = ThesisVisionAnalyzer()
                    visual_context = vision_analyzer.get_visual_context_for_evaluation(file_path)
                    logger.info(f"视觉分析完成（回退方案），生成上下文{len(visual_context)}字符")
                except Exception as e2:
                    logger.warning(f"视觉分析也失败: {str(e2)}")
                    visual_context = ""

        pass0_comprehension = self._pass0_thesis_comprehension(content, visual_context, knowledge_base)
        logger.info(f"Pass0完成: 论文结构化理解")

        pass1_structure = self._pass1_structure_identification(content)
        logger.info(f"Pass1完成: 识别到{pass1_structure.get('total_sections', 0)}个章节")

        pass2_sections = self._pass2_section_deep_eval(content, pass1_structure, knowledge_base)
        logger.info(f"Pass2完成: 评估了{len(pass2_sections)}个章节")

        pass3_promise = self._pass3_promise_tracking(content, pass1_structure, pass2_sections)
        logger.info(f"Pass3完成: 追踪了{len(pass3_promise.get('fulfillment_status', []))}个承诺")

        content_existence_map = self._pre_verify_content_existence(content, pass1_structure)
        logger.info(f"预验证完成: 确认{len(content_existence_map.get('confirmed_terms', []))}个术语在全文中存在")

        pass4_diagnosis = self._pass4_comprehensive_diagnosis(
            content, pass1_structure, pass2_sections, pass3_promise, content_existence_map, pass0_comprehension, visual_context, kb_context
        )
        logger.info("Pass4完成: 综合诊断")

        pass5_verified = self._pass5_fact_verification(pass4_diagnosis, content, content_existence_map)
        logger.info("Pass5完成: 事实核查验证")

        pass6_citation_format = self._pass6_citation_format_check(content)
        logger.info("Pass6完成: 引用格式检查")

        refined_result = self._self_refine(pass5_verified, content, pass2_sections)
        logger.info("Self-Refine迭代完成")

        roadmap = self._generate_modification_roadmap(refined_result, content)
        logger.info("修改路线图生成完成")

        elapsed = time.time() - start_time
        logger.info(f"深度评估总耗时: {elapsed:.1f}秒")

        kb_stats = knowledge_base.get_stats() if knowledge_base else {}
        return {
            "evaluation_method": "deep_evaluation",
            "thesis_comprehension": pass0_comprehension,
            "thesis_structure": pass1_structure,
            "section_evaluations": pass2_sections,
            "promise_tracking": pass3_promise,
            "diagnosis": refined_result,
            "modification_roadmap": roadmap,
            "fact_verification": pass5_verified.get("_verification_summary", {}),
            "citation_format_check": pass6_citation_format,
            "elapsed_seconds": round(elapsed, 1),
            "student_info": student_info,
            "visual_context_length": len(visual_context) if visual_context else 0,
            "knowledge_base_stats": kb_stats,
        }

    # ================================================================
    # Pass 0: 论文结构化理解
    # ================================================================
    def _pass0_thesis_comprehension(self, content: str, visual_context: str = "", knowledge_base=None) -> Dict:
        self._ensure_client()

        content_preview = content[:30000]

        kb_section = ""
        if knowledge_base:
            research_chain = knowledge_base.get_research_chain_context()
            tables_ctx = knowledge_base.get_all_tables_context()
            figures_ctx = knowledge_base.get_all_figures_context()
            formulas_ctx = knowledge_base.get_all_formulas_context()
            key_terms = knowledge_base.structured_index.get("key_terms", [])

            if research_chain:
                kb_section += f"\n{research_chain}\n"
            if tables_ctx:
                kb_section += f"\n## 论文中的表格数据（从PDF结构化提取）\n{tables_ctx[:3000]}\n"
            if figures_ctx:
                kb_section += f"\n## 论文中的图表信息\n{figures_ctx[:2000]}\n"
            if formulas_ctx:
                kb_section += f"\n## 论文中的公式信息\n{formulas_ctx[:2000]}\n"
            if key_terms:
                terms_str = ", ".join([f"{t['term']}({t['count']}次)" for t in key_terms[:15]])
                kb_section += f"\n## 关键技术术语\n{terms_str}\n"

        visual_section = ""
        if visual_context:
            visual_section = f"""
## 视觉分析结果（基于论文页面图像识别，补充文本提取无法获取的表格/公式/图片信息）
{visual_context}
"""

        system_prompt = """你是一位资深的学术研究方法论专家。你的任务是对一篇学术论文进行深度的结构化理解，而非评估。

你的目标是理解论文的研究思路和工作内容，包括：
1. 研究问题是什么？为什么这个问题重要？
2. 作者采用了什么研究路线？为什么选择这条路线？
3. 核心技术方法是什么？如何解决问题的？
4. 实验设计是怎样的？验证了什么？
5. 主要发现和贡献是什么？
6. 研究的逻辑链条是什么？（问题→方法→实验→结论）

【核心原则】
1. 你是在理解论文，不是在评价论文
2. 尽可能从论文作者的角度理解其研究意图
3. 如果某些内容在提供的文本中找不到，说明"文本中未涉及"，不要推测
4. 如果文本被截断（出现"..."），对截断部分不做判断
5. 【关键】下方提供了从PDF中结构化提取的表格数据、图表信息、公式信息和关键技术术语。这些信息来自PDF解析，是可靠的。请利用这些信息理解论文的实际研究内容，而非仅看表面文字
6. 表格中的数据反映了论文的实际实验结果或方法对比，请据此理解论文的研究深度
7. 公式反映了论文的核心技术方法，请据此理解论文的技术路线

请输出JSON格式结果。"""

        visual_section = ""
        if visual_context:
            visual_section = f"""
## 视觉分析结果（基于论文页面图像识别，补充文本提取无法获取的表格/公式/图片信息）
{visual_context}
"""

        user_prompt = f"""请对以下论文进行结构化理解：

## 论文内容
{content_preview}
{kb_section}
{visual_section}
请输出如下JSON格式：
{{
    "research_problem": {{
        "core_question": "核心研究问题",
        "importance": "为什么这个问题重要",
        "problem_scope": "问题范围和边界"
    }},
    "research_route": {{
        "overall_strategy": "整体研究策略和路线",
        "why_this_route": "为什么选择这条研究路线",
        "key_decisions": ["关键研究决策1", "关键研究决策2"]
    }},
    "technical_methods": [
        {{
            "name": "方法名称",
            "purpose": "解决什么问题",
            "key_idea": "核心思想",
            "implementation_summary": "实现概述"
        }}
    ],
    "experimental_design": {{
        "overall_setup": "实验整体设计",
        "datasets": "使用的数据集/场景",
        "baselines": "对比基线方法",
        "metrics": "评估指标",
        "validation_approach": "验证方式"
    }},
    "key_findings": [
        {{
            "finding": "主要发现",
            "evidence": "支撑证据",
            "significance": "意义"
        }}
    ],
    "logic_chain": {{
        "problem_to_method": "从问题到方法的逻辑",
        "method_to_experiment": "从方法到实验的逻辑",
        "experiment_to_conclusion": "从实验到结论的逻辑",
        "logic_gaps": ["逻辑链条中可能存在的跳跃或不足"]
    }},
    "thesis_contribution_summary": "用2-3句话概括论文的核心贡献",
    "research_workflow": "论文的研究工作流程（问题提出→文献调研→方法设计→实现→实验→分析→结论）"
}}"""

        raw = self._call_llm(system_prompt, user_prompt, temperature=0.2, max_tokens=8000)
        return self._safe_json_parse(raw)

    # ================================================================
    # Pass 1: 论文结构识别与承诺提取
    # ================================================================
    def _pass1_structure_identification(self, content: str) -> Dict:
        self._ensure_client()
        content_preview = content[:25000]

        chapter_headers = []
        import re
        for m in re.finditer(r'(第[一二三四五六七八九十\d]+\s*章[^\n]*|摘\s*要|ABSTRACT|引言|绪论|结论|总结|参考文献|致谢)', content):
            chapter_headers.append(m.group().strip())

        system_prompt = """你是一位专业的学术论文结构分析专家。你的任务是深入分析论文结构，识别各章节，并从绪论中提取作者承诺要完成的工作。

【核心原则 - 忠实于原文】
1. 只从论文原文中提取信息，不要推测或编造
2. 章节识别必须基于原文中实际出现的标题
3. 承诺提取必须基于原文中明确表述的内容
4. 如果论文中有表格编号（如表4.1）、图编号（如图3.2）、算法编号（如算法1），记录它们的存在
5. 必须识别论文中所有图表和图例，包括表格编号、图编号、算法编号，以及图注/表注的内容

请仔细分析并输出JSON格式结果。"""

        user_prompt = f"""请分析以下论文的结构，识别章节并提取承诺：

## 论文内容
{content_preview}

## 检测到的章节标题
{chr(10).join(chapter_headers)}

请输出如下JSON格式：
{{
    "thesis_type": "论文类型（如：仿真分析类、算法设计类、实物制作类等）",
    "total_sections": 章节数,
    "main_works": ["主要工作1", "主要工作2"],
    "key_promises": [
        {{
            "promise": "承诺要完成的工作内容",
            "source_location": "出现在哪个章节/段落",
            "promise_type": "方法承诺/实验承诺/分析承诺/结论承诺"
        }}
    ],
    "sections": [
        {{
            "title": "章节标题",
            "section_type": "abstract/introduction/literature_review/methodology/implementation/experiment/results/conclusion/references/other",
            "section_type_name": "摘要/绪论/文献综述/方法/实现/实验/结果/结论/参考文献/其他",
            "start_marker": "章节起始标记文本",
            "end_marker": "下一章节起始标记文本",
            "estimated_content": "该章节大致内容描述"
        }}
    ],
    "structure_analysis": "论文整体结构分析说明",
    "figures_and_tables": [
        {{
            "type": "图/表/算法",
            "number": "编号如3.2",
            "caption": "图注/表注内容",
            "location": "所在章节"
        }}
    ]
}}"""

        raw = self._call_llm(system_prompt, user_prompt, max_tokens=8000)
        return self._safe_json_parse(raw)

    # ================================================================
    # Pass 2: 逐章深度评估（每章单独调用，带前后文上下文）
    # ================================================================
    def _pass2_section_deep_eval(self, content: str, structure: Dict, knowledge_base=None) -> List[Dict]:
        self._ensure_client()
        sections = structure.get('sections', [])
        if not sections:
            return []

        results = []
        for i, sec_info in enumerate(sections):
            sec_title = sec_info.get('title', '')
            sec_type = sec_info.get('section_type', 'other')
            sec_type_name = sec_info.get('section_type_name', '其他')

            section_content = self._extract_section_content(content, sec_info, sections, i)

            prev_context = ""
            if i > 0:
                prev_sec = sections[i - 1]
                prev_content = self._extract_section_content(content, prev_sec, sections, i - 1)
                prev_context = prev_content[:1500] if prev_content else ""

            next_context = ""
            if i < len(sections) - 1:
                next_sec = sections[i + 1]
                next_content = self._extract_section_content(content, next_sec, sections, i + 1)
                next_context = next_content[:1500] if next_content else ""

            kb_section_context = ""
            if knowledge_base:
                kb_section_context = knowledge_base.get_context_for_query(sec_title, top_k=3)

            eval_result = self._evaluate_single_section(
                sec_title, sec_type, sec_type_name, section_content, prev_context, next_context, i, len(sections), kb_section_context
            )
            results.append(eval_result)
            logger.info(f"  章节{i+1}/{len(sections)}: {sec_title} - {eval_result.get('section_score', 0)}分")

        return results

    def _extract_section_content(self, content: str, sec_info: Dict, sections: List[Dict], idx: int) -> str:
        start_marker = sec_info.get('start_marker', '')
        end_marker = sec_info.get('end_marker', '')

        start_idx = 0
        if start_marker and start_marker in content:
            start_idx = content.find(start_marker)

        end_idx = len(content)
        if end_marker and end_marker in content:
            candidate = content.find(end_marker, start_idx + len(start_marker))
            if candidate > start_idx:
                end_idx = candidate

        extracted = content[start_idx:end_idx].strip()
        if len(extracted) > 16000:
            extracted = extracted[:8000] + "\n...\n" + extracted[-6000:]
        return extracted

    def _evaluate_single_section(
        self, title, sec_type, sec_type_name, content, prev_context, next_context, idx, total, kb_section_context=""
    ) -> Dict:
        system_prompt = """你是一位极其严格的学术论文审稿专家。你正在对论文的每个章节进行深度评估。

【核心原则 - 绝对禁止幻觉】
1. 你只能基于提供的章节内容做出判断，绝不能凭想象或推测
2. 声称"缺少"某内容时，必须先确认该内容确实不在提供的文本中
3. 声称"仅"有某内容时，必须确认没有遗漏文本中的其他内容
4. 每个判断必须引用原文中的具体文字作为证据
5. 如果文本被截断（出现"..."），不要对截断部分的内容做出判断
6. 不要假设论文没有包含某些内容——如果文本中提到了表格、图表、算法，就认为它们存在
7. 注意：表格和图片可能以文字描述、引用编号（如表4.1、图3.2）的形式出现，这些都表明它们存在
8. 附录中的表格和图片同样有效，不应声称缺失

【评估重点 - 聚焦学术实质】
评估应聚焦于学术质量和研究深度，而非表面文字错误：
- 高优先级：方法论严谨性、实验设计合理性、逻辑推理严密性、数据分析深度、创新性真实性
- 中优先级：文献综述全面性、技术路线合理性、研究问题定义清晰度
- 低优先级（仅记录不影响评分）：文字笔误、格式细节、标点问题
- 你已获得论文的结构化理解（研究问题、技术方法、实验设计等），请基于这些理解评估章节内容，而非仅看表面文字

评估要求：
1. 每个评分必须有论文原文中的具体证据支撑
2. 发现的问题必须指出具体位置和具体内容
3. 改进建议必须具体可操作，不能泛泛而谈
4. 必须考虑该章节与前后章节的逻辑关系
5. 不要对论文的研究设计方向提出质疑（如"为什么只研究一种粉尘"），除非论文自身声称研究了多种但实际只做了
6. 评估章节中图表和图例的质量，包括图注是否完整、图例是否清晰、表格是否规范

请输出JSON格式的评估结果。"""

        context_info = ""
        if prev_context:
            context_info += f"\n## 上一章节内容片段（供衔接参考）\n{prev_context[:600]}\n"
        if next_context:
            context_info += f"\n## 下一章节内容片段（供衔接参考）\n{next_context[:600]}\n"

        kb_info = ""
        if kb_section_context:
            kb_info = f"\n## 知识库检索到的相关上下文（来自论文其他部分的表格/公式/图片信息）\n{kb_section_context[:2000]}\n"

        user_prompt = f"""请对以下章节进行深度评估：

## 当前章节: {title}（{sec_type_name}，第{idx+1}/{total}章）

## 章节内容
{content}
{context_info}
{kb_info}

请输出如下JSON格式：
{{
    "section_title": "{title}",
    "section_type": "{sec_type}",
    "section_score": 0-100的整数评分,
    "grade_level": "优秀/良好/中等/及格/不及格",
    "content_quality": {{
        "score": 0-100,
        "comment": "内容质量总体评价",
        "strengths": ["优点1", "优点2"],
        "weaknesses": ["不足1", "不足2"],
        "depth_analysis": "论述深度分析：是否深入分析了问题，还是停留在表面描述",
        "data_sufficiency": "数据/证据充分性分析：是否有足够的数据支撑论点"
    }},
    "logic_coherence": {{
        "score": 0-100,
        "comment": "逻辑连贯性评价",
        "internal_logic": "内部逻辑分析：本章节内部论证是否自洽",
        "cross_chapter_logic": "跨章节衔接分析：与前后章节的逻辑关系",
        "issues": ["逻辑问题1", "逻辑问题2"]
    }},
    "innovation_contribution": {{
        "score": 0-100,
        "comment": "创新与贡献评价",
        "novelty_type": "创新类型：方法创新/应用创新/改进创新/无创新",
        "concrete_contribution": "具体贡献描述",
        "comparison_with_existing": "与已有工作的对比（如有）"
    }},
    "writing_quality": {{
        "score": 0-100,
        "comment": "表达规范性评价",
        "language_issues": ["语言问题1"],
        "format_issues": ["格式问题1"],
        "figure_table_issues": ["图表问题1"]
    }},
    "key_points": ["该章节的关键论点1", "关键论点2"],
    "improvement_suggestions": [
        {{
            "aspect": "改进方面",
            "current_issue": "当前存在的具体问题（引用原文）",
            "suggestion": "具体的修改方案",
            "priority": "高/中/低",
            "estimated_score_impact": 估计可提升的分数
        }}
    ],
    "evidence": "评分的核心依据（引用原文关键内容）",
    "detailed_score_reason": "详细的评分推理过程"
}}"""

        raw = self._call_llm(system_prompt, user_prompt, max_tokens=8000)
        return self._safe_json_parse(raw)

    # ================================================================
    # Pass 3: 承诺-兑现追踪
    # ================================================================
    def _pass3_promise_tracking(self, content: str, structure: Dict, section_evals: List[Dict]) -> Dict:
        self._ensure_client()
        promises = structure.get('key_promises', [])
        if not promises:
            intro_sections = [s for s in structure.get('sections', []) if s.get('section_type') in ('introduction', 'abstract')]
            if intro_sections:
                intro_content = self._extract_section_content(content, intro_sections[0], structure.get('sections', []), 0)
                promises = self._extract_promises_from_intro(intro_content)

        if not promises:
            return {"fulfillment_status": [], "overall_fulfillment_rate": 1.0, "summary": "未检测到明确承诺"}

        system_prompt = """你是一位学术论文承诺兑现追踪专家。你的任务是检查论文绪论中承诺的工作是否在正文中得到了兑现。

【核心原则 - 忠实于原文】
1. 判断承诺是否兑现时，必须在原文中找到具体的证据
2. 不要声称承诺未兑现，除非你在原文中确实找不到相关内容
3. 表格编号、图编号、算法编号的出现意味着相关工作已经完成
4. 附录中的内容同样算作兑现证据

评估标准：
- 完全兑现：承诺的工作在正文中完整实现，有明确的结果和证据
- 部分兑现：承诺的工作在正文中有部分实现，但不够完整
- 未兑现：承诺的工作在正文中没有实现或只有空话

请输出JSON格式结果。"""

        promises_text = "\n".join([
            f"{i+1}. {p.get('promise', p) if isinstance(p, dict) else p} (来源: {p.get('source_location', '未知') if isinstance(p, dict) else '未知'})"
            for i, p in enumerate(promises)
        ])

        content_for_check = content[:30000]

        user_prompt = f"""请追踪以下承诺的兑现情况：

## 论文承诺列表
{promises_text}

## 论文全文（供验证）
{content_for_check}

请输出如下JSON格式：
{{
    "fulfillment_status": [
        {{
            "promise": "承诺内容",
            "source_section": "承诺来源章节",
            "fulfillment_degree": "完全兑现/部分兑现/未兑现",
            "fulfillment_section": "兑现所在章节",
            "fulfillment_evidence": "正文中支撑兑现的具体证据（引用原文）",
            "comment": "兑现情况评价",
            "impact_analysis": "未兑现/部分兑现对论文质量的影响",
            "improvement_suggestion": "如未完全兑现，如何改进"
        }}
    ],
    "overall_fulfillment_rate": 0.0-1.0的兑现率,
    "unfulfilled_promises": ["未兑现的承诺1"],
    "partially_fulfilled_promises": ["部分兑现的承诺1"],
    "summary": "承诺兑现总体评价"
}}"""

        raw = self._call_llm(system_prompt, user_prompt, max_tokens=6000)
        return self._safe_json_parse(raw)

    def _extract_promises_from_intro(self, intro_content: str) -> List[Dict]:
        system_prompt = """你是一位学术论文分析专家。请从论文的绪论/引言部分提取作者承诺要完成的工作。

请输出JSON格式。"""

        user_prompt = f"""请从以下绪论内容中提取作者承诺要完成的工作：

{intro_content[:10000]}

请输出如下JSON格式：
{{
    "key_promises": [
        {{
            "promise": "承诺内容",
            "source_location": "出现位置",
            "promise_type": "方法承诺/实验承诺/分析承诺/结论承诺"
        }}
    ]
}}"""

        raw = self._call_llm(system_prompt, user_prompt, max_tokens=4000)
        result = self._safe_json_parse(raw)
        return result.get('key_promises', [])

    def _pre_verify_content_existence(self, content: str, structure: Dict) -> Dict:
        import re

        result = {
            "confirmed_terms": [],
            "confirmed_figures": [],
            "confirmed_tables": [],
            "confirmed_algorithms": [],
            "term_locations": {},
        }

        abstract_sections = [s for s in structure.get('sections', []) if s.get('section_type') in ('abstract',)]
        intro_sections = [s for s in structure.get('sections', []) if s.get('section_type') in ('introduction',)]
        key_sections = abstract_sections + intro_sections

        key_content = ""
        for sec in key_sections:
            idx = structure.get('sections', []).index(sec)
            extracted = self._extract_section_content(content, sec, structure.get('sections', []), idx)
            key_content += extracted + "\n"

        if not key_content:
            key_content = content[:5000]

        technical_patterns = [
            r'(?:应用|采用|使用|基于|利用|提出|设计|实现|构建|开发|研究|分析|求解|预测|仿真|模拟)[，,]?\s*([^\s，,。；;]{2,30}(?:方程|模型|方法|算法|网络|框架|系统|技术|理论|策略|方案|体系|平台|装置|设备|结构|机理|机制|原理|准则|标准|规范))',
            r'(?:物理信息神经网络|PINN|深度学习|机器学习|神经网络|卷积网络|循环网络|Transformer|注意力机制|随机森林|支持向量机|贝叶斯|遗传算法|强化学习|迁移学习|联邦学习|知识蒸馏|图神经网络|生成对抗|自编码器|LSTM|GRU|CNN|RNN|GAN|VAE|扩散模型)',
            r'(?:Navier-Stokes|N-S|波动方程|热传导方程|拉普拉斯方程|泊松方程|欧拉方程|麦克斯韦方程|薛定谔方程|扩散方程|对流方程|输运方程)',
            r'(?:有限元|有限差分|有限体积|谱方法|边界元|无网格|格子Boltzmann|SPH|DEM|CFD|DNS|LES|RANS)',
        ]

        found_terms = set()
        for pattern in technical_patterns:
            for m in re.finditer(pattern, key_content):
                term = m.group(0) if m.lastindex is None else m.group(m.lastindex)
                if len(term) >= 2:
                    found_terms.add(term)

        for term in found_terms:
            escaped = re.escape(term)
            occurrences = [m.start() for m in re.finditer(escaped, content)]
            if occurrences:
                result["confirmed_terms"].append(term)
                result["term_locations"][term] = {
                    "count": len(occurrences),
                    "first_offset": occurrences[0],
                    "in_abstract": bool(re.search(escaped, key_content)),
                    "in_body": len(occurrences) > (len([m for m in re.finditer(escaped, key_content)]) if key_content else 0),
                }

        fig_pattern = r'图\s*(\d+[\.\-]\d+|\d+)'
        for m in re.finditer(fig_pattern, content):
            fig_num = m.group(1)
            if fig_num not in result["confirmed_figures"]:
                result["confirmed_figures"].append(fig_num)

        tab_pattern = r'表\s*(\d+[\.\-]\d+|\d+)'
        for m in re.finditer(tab_pattern, content):
            tab_num = m.group(1)
            if tab_num not in result["confirmed_tables"]:
                result["confirmed_tables"].append(tab_num)

        algo_pattern = r'算法\s*(\d+[\.\-]\d+|\d+)'
        for m in re.finditer(algo_pattern, content):
            algo_num = m.group(1)
            if algo_num not in result["confirmed_algorithms"]:
                result["confirmed_algorithms"].append(algo_num)

        return result

    # ================================================================
    # Pass 4: 综合诊断
    # ================================================================
    def _pass4_comprehensive_diagnosis(
        self, content, structure, section_evals, promise_tracking, content_existence_map=None, comprehension=None, visual_context="", kb_context=""
    ) -> Dict:
        self._ensure_client()

        section_summary = ""
        for i, se in enumerate(section_evals):
            section_summary += f"\n章节{i+1}: {se.get('section_title', '未知')} - {se.get('section_score', 0)}分 ({se.get('grade_level', '')})\n"
            cq = se.get('content_quality', {})
            if cq:
                section_summary += f"  内容质量: {cq.get('score', 'N/A')}分 - {cq.get('comment', '')}\n"
                for w in cq.get('weaknesses', []):
                    section_summary += f"  ❌ {w}\n"
            lc = se.get('logic_coherence', {})
            if lc:
                section_summary += f"  逻辑连贯: {lc.get('score', 'N/A')}分\n"
                for iss in lc.get('issues', []):
                    section_summary += f"  ⚠️ {iss}\n"
            for sug in se.get('improvement_suggestions', []):
                if isinstance(sug, dict):
                    section_summary += f"  💡 [{sug.get('priority', '中')}] {sug.get('aspect', '')}: {sug.get('suggestion', '')}\n"

        promise_summary = ""
        for fs in promise_tracking.get('fulfillment_status', []):
            promise_summary += f"\n{fs.get('promise', '')}: {fs.get('fulfillment_degree', '')}\n"
            if fs.get('comment'):
                promise_summary += f"  {fs['comment']}\n"
            if fs.get('improvement_suggestion'):
                promise_summary += f"  💡 {fs['improvement_suggestion']}\n"

        system_prompt = """你是一位资深学术论文评审专家。你将基于前面多个Pass的评估结果，进行综合诊断。

【核心原则 - 绝对禁止幻觉】
1. 你只能基于提供的评估摘要和论文原文做出判断
2. 声称论文"缺少"某内容时，必须先在原文中确认该内容确实不存在
3. 声称论文"仅有"某内容时，必须确认没有遗漏
4. 每个问题必须引用原文中的具体文字作为证据
5. 不要质疑论文的研究设计方向（如"为什么只研究一种粉尘"），除非论文自身承诺了更多
6. 如果论文中提到了表格编号（如表4.1）、图编号（如图3.2）、算法编号（如算法1），就认为它们存在
7. 不要声称摘要与正文不一致，除非你能指出具体的不一致之处并引用原文
8. 附录中的内容同样有效
9. 【关键】下方提供的"已确认存在内容清单"中的术语/图表/算法，已在论文全文中通过文本搜索确认存在，你绝对不能声称它们不存在或缺失
10. 【关键】下方提供了"论文结构化理解"，这是对论文研究思路和工作内容的深度分析。你的评估必须基于对论文研究内容的理解，而非仅看表面文字。评估应聚焦于：研究方法是否严谨、实验设计是否合理、逻辑推理是否严密、创新性是否真实等学术实质问题。

【评估重点 - 聚焦学术实质】
你的评估必须聚焦于论文的学术质量和研究深度，而非表面文字错误。请按以下优先级评估：

**高优先级问题（严重影响论文质量）：**
1. 研究方法论是否严谨：实验设计是否合理、对比基线是否充分、变量控制是否得当
2. 创新性是否真实：声称的创新是否真正有别于已有工作，还是只是简单套用
3. 实验验证是否充分：是否有充分的实验/仿真验证，结果是否可复现，对比实验是否公平
4. 逻辑推理是否严密：从数据到结论的推理链是否有跳跃，因果关系是否成立
5. 数据分析是否深入：是否只是罗列数据，还是进行了深入分析和合理解释

**中优先级问题：**
6. 文献综述是否全面：是否遗漏了关键的相关工作
7. 研究问题定义是否清晰：问题边界是否明确
8. 技术路线是否合理：所选方法是否适合解决研究问题

**低优先级问题（仅记录，不影响评分）：**
9. 文字笔误、格式不统一、标点错误等表面问题
10. 图表标注细节问题

请输出JSON格式结果。"""

        existence_info = ""
        if content_existence_map:
            confirmed_terms = content_existence_map.get("confirmed_terms", [])
            confirmed_figures = content_existence_map.get("confirmed_figures", [])
            confirmed_tables = content_existence_map.get("confirmed_tables", [])
            confirmed_algorithms = content_existence_map.get("confirmed_algorithms", [])

            if confirmed_terms:
                existence_info += "\n### 已确认在全文中存在的关键技术术语（绝对不能声称缺失）\n"
                for term in confirmed_terms:
                    loc = content_existence_map.get("term_locations", {}).get(term, {})
                    count = loc.get("count", 0)
                    in_body = loc.get("in_body", False)
                    existence_info += f"- **{term}** (出现{count}次"
                    if in_body:
                        existence_info += "，摘要与正文均有"
                    existence_info += ")\n"

            if confirmed_figures:
                existence_info += f"\n### 已确认存在的图编号: {', '.join(['图' + f for f in confirmed_figures])}\n"
            if confirmed_tables:
                existence_info += f"\n### 已确认存在的表编号: {', '.join(['表' + t for t in confirmed_tables])}\n"
            if confirmed_algorithms:
                existence_info += f"\n### 已确认存在的算法编号: {', '.join(['算法' + a for a in confirmed_algorithms])}\n"

        comprehension_info = ""
        if comprehension:
            comp_json = json.dumps(comprehension, ensure_ascii=False, indent=2)[:3000]
            comprehension_info = f"""
## 论文结构化理解（Pass0生成，帮助你理解论文的研究思路）
{comp_json}
"""

        if visual_context:
            comprehension_info += f"""
## 视觉分析结果（基于论文页面图像识别）
{visual_context[:3000]}
"""

        if kb_context:
            comprehension_info += f"""
## 本地知识库上下文（从PDF结构化提取的表格/公式/图片/研究链条信息）
{kb_context[:5000]}
"""

        user_prompt = f"""请基于以下多Pass评估结果，进行综合诊断：

## 论文类型: {structure.get('thesis_type', '未知')}
## 章节数: {structure.get('total_sections', 0)}

## 各章节评估摘要
{section_summary}

## 承诺兑现追踪摘要
兑现率: {promise_tracking.get('overall_fulfillment_rate', 'N/A')}
{promise_summary}
{existence_info}
{comprehension_info}
请输出如下JSON格式：
{{
    "overall_score": 0-100的整数,
    "grade_level": "优秀/良好/中等/及格/不及格",
    "overall_comment": "总体评价（200字以上，聚焦学术质量、研究深度、创新性，而非表面文字问题）",
    "strengths": ["优势1", "优势2", "优势3"],
    "weaknesses": ["不足1", "不足2", "不足3"],
    "quantified_issues": [
        {{
            "issue": "问题描述（聚焦学术实质问题）",
            "location": "问题所在位置",
            "severity": "严重/中等/轻微",
            "score_impact": 估计影响的分数（正整数）,
            "evidence": "支撑此判断的原文证据"
        }}
    ],
    "section_scores_summary": [
        {{
            "section_title": "章节名",
            "score": 分数,
            "grade": "等级"
        }}
    ],
    "improvement_suggestions": [
        {{
            "aspect": "改进方面（优先方法论、实验设计、逻辑推理等学术问题）",
            "current_issue": "当前具体问题",
            "suggestion": "具体修改方案",
            "priority": "高/中/低",
            "estimated_score_impact": 估计可提升的分数,
            "difficulty": "容易/中等/困难"
        }}
    ],
    "detailed_analysis": {{
        "innovation_analysis": "创新性分析（100字以上：创新点是否真实、是否有别于已有工作、创新程度如何）",
        "depth_analysis": "研究深度分析（100字以上：分析是否深入、实验是否充分、结论是否有数据支撑）",
        "structure_analysis": "结构完整性分析（100字以上：论证链条是否完整、各章节逻辑关系是否紧密）",
        "methodology_analysis": "方法论分析（100字以上：方法选择是否合理、实验设计是否严谨、对比基线是否充分）"
    }}
}}"""

        raw = self._call_llm(system_prompt, user_prompt, max_tokens=8000)
        return self._safe_json_parse(raw)

    # ================================================================
    # Pass 5: 事实核查验证 - 检查评估中的判断是否与原文一致
    # ================================================================
    def _pass5_fact_verification(self, diagnosis: Dict, content: str, content_existence_map: Dict = None) -> Dict:
        import re

        auto_corrected = []
        if content_existence_map:
            confirmed_terms = content_existence_map.get("confirmed_terms", [])
            confirmed_figures = content_existence_map.get("confirmed_figures", [])
            confirmed_tables = content_existence_map.get("confirmed_tables", [])
            confirmed_algorithms = content_existence_map.get("confirmed_algorithms", [])

            for term in confirmed_terms:
                for i, w in enumerate(diagnosis.get('weaknesses', [])):
                    if term in w and ('缺少' in w or '未' in w or '缺失' in w or '没有' in w or '不存在' in w):
                        auto_corrected.append({
                            "claim": w,
                            "is_accurate": False,
                            "reason": f"术语'{term}'已在全文中通过文本搜索确认存在（出现{content_existence_map.get('term_locations', {}).get(term, {}).get('count', '?')}次），该判断不准确",
                            "correction": f"术语'{term}'在论文中确实存在"
                        })

            for fig_num in confirmed_figures:
                fig_label = f"图{fig_num}"
                for i, w in enumerate(diagnosis.get('weaknesses', [])):
                    if fig_label in w and ('缺少' in w or '未' in w or '缺失' in w or '没有' in w):
                        auto_corrected.append({
                            "claim": w,
                            "is_accurate": False,
                            "reason": f"{fig_label}已在全文中确认存在，该判断不准确",
                            "correction": f"{fig_label}在论文中确实存在"
                        })

            for tab_num in confirmed_tables:
                tab_label = f"表{tab_num}"
                for i, w in enumerate(diagnosis.get('weaknesses', [])):
                    if tab_label in w and ('缺少' in w or '未' in w or '缺失' in w or '没有' in w or '仅有编号' in w):
                        auto_corrected.append({
                            "claim": w,
                            "is_accurate": False,
                            "reason": f"{tab_label}已在全文中确认存在，该判断不准确",
                            "correction": f"{tab_label}在论文中确实存在"
                        })

            for i, qi in enumerate(diagnosis.get('quantified_issues', [])):
                issue_text = qi.get('issue', '')
                for term in confirmed_terms:
                    if term in issue_text and ('缺少' in issue_text or '未' in issue_text or '缺失' in issue_text or '没有' in issue_text or '不存在' in issue_text):
                        already = any(ac['claim'] == issue_text for ac in auto_corrected)
                        if not already:
                            auto_corrected.append({
                                "claim": issue_text,
                                "is_accurate": False,
                                "reason": f"术语'{term}'已在全文中确认存在，该判断不准确",
                                "correction": f"术语'{term}'在论文中确实存在"
                            })

                for fig_num in confirmed_figures:
                    fig_label = f"图{fig_num}"
                    if fig_label in issue_text and ('缺少' in issue_text or '未' in issue_text or '缺失' in issue_text):
                        already = any(ac['claim'] == issue_text for ac in auto_corrected)
                        if not already:
                            auto_corrected.append({
                                "claim": issue_text,
                                "is_accurate": False,
                                "reason": f"{fig_label}已在全文中确认存在，该判断不准确",
                                "correction": f"{fig_label}在论文中确实存在"
                            })

                for tab_num in confirmed_tables:
                    tab_label = f"表{tab_num}"
                    if tab_label in issue_text and ('缺少' in issue_text or '未' in issue_text or '缺失' in issue_text or '仅有编号' in issue_text):
                        already = any(ac['claim'] == issue_text for ac in auto_corrected)
                        if not already:
                            auto_corrected.append({
                                "claim": issue_text,
                                "is_accurate": False,
                                "reason": f"{tab_label}已在全文中确认存在，该判断不准确",
                                "correction": f"{tab_label}在论文中确实存在"
                            })

        self._ensure_client()

        issues_to_verify = []
        for weakness in diagnosis.get('weaknesses', []):
            issues_to_verify.append({"claim": weakness, "type": "weakness"})
        for qi in diagnosis.get('quantified_issues', []):
            issues_to_verify.append({
                "claim": qi.get('issue', ''),
                "evidence": qi.get('evidence', ''),
                "type": "quantified_issue",
            })
        for sug in diagnosis.get('improvement_suggestions', []):
            current_issue = sug.get('current_issue', '')
            if current_issue:
                issues_to_verify.append({"claim": current_issue, "type": "suggestion_issue"})

        if not issues_to_verify:
            diagnosis["_verification_summary"] = {
                "total_claims": 0,
                "verified_claims": 0,
                "corrected_claims": 0,
                "removed_claims": [],
            }
            return diagnosis

        claims_text = ""
        for i, item in enumerate(issues_to_verify):
            claims_text += f"\n判断{i+1}（{item['type']}）: {item['claim']}"
            if item.get('evidence'):
                claims_text += f"\n  声称的证据: {item['evidence']}"

        content_for_verify = content[:35000]

        system_prompt = """你是一位严格的事实核查专家。你的任务是检查一份论文评估报告中的每个判断是否与论文原文一致。

【核查原则】
1. 如果评估声称论文"缺少"某内容（如表格、图表、算法、文献），你必须在原文中搜索确认该内容确实不存在
2. 如果评估声称论文"仅有"某内容（如"仅用一种粉尘"、"仅提及少数算法"），你必须在原文中搜索确认是否真的只有这些
3. 如果评估声称"摘要与正文不一致"，你必须在原文中找到具体的不一致之处
4. 如果评估声称"未引用对比文献"，你必须在原文中搜索参考文献部分确认
5. 表格编号（如表4.1、表4.3）、图编号（如图3.2）、算法编号（如算法1）的出现意味着这些内容存在
6. 附录中的内容同样有效
7. 如果原文被截断，对于截断部分的内容不能做出判断

请逐条核查，输出JSON格式结果。"""

        user_prompt = f"""请核查以下评估判断是否与论文原文一致：

## 待核查的判断
{claims_text}

## 论文原文（供核查）
{content_for_verify}

请输出如下JSON格式：
{{
    "verification_results": [
        {{
            "claim": "被核查的判断",
            "is_accurate": true/false,
            "reason": "判断是否准确的理由（引用原文具体内容）",
            "correction": "如果判断不准确，给出正确的描述；如果准确则为空字符串"
        }}
    ],
    "inaccurate_claims_count": 不准确判断的数量,
    "summary": "核查总结"
}}"""

        raw = self._call_llm(system_prompt, user_prompt, temperature=0.1, max_tokens=6000)
        verification = self._safe_json_parse(raw)

        verification_results = verification.get('verification_results', [])
        inaccurate_claims = [v for v in verification_results if not v.get('is_accurate', True)]

        for ac in auto_corrected:
            already_in_llm = any(
                v.get('claim', '') == ac['claim'] and not v.get('is_accurate', True)
                for v in verification_results
            )
            if not already_in_llm:
                verification_results.append(ac)
                inaccurate_claims.append(ac)

        corrected_diagnosis = copy.deepcopy(diagnosis)

        removed_weaknesses = []
        new_weaknesses = []
        for v in verification_results:
            if not v.get('is_accurate', True) and v.get('correction'):
                claim = v.get('claim', '')
                correction = v.get('correction', '')
                removed_weaknesses.append(claim)

                for i, w in enumerate(corrected_diagnosis.get('weaknesses', [])):
                    if claim in w or w in claim:
                        corrected_diagnosis['weaknesses'][i] = f"~~{w}~~ → 修正: {correction}"
                        break

                for i, qi in enumerate(corrected_diagnosis.get('quantified_issues', [])):
                    if claim in qi.get('issue', '') or qi.get('issue', '') in claim:
                        corrected_diagnosis['quantified_issues'][i]['issue'] = f"~~{qi['issue']}~~ → 修正: {correction}"
                        corrected_diagnosis['quantified_issues'][i]['score_impact'] = max(0, qi.get('score_impact', 0) // 3)
                        corrected_diagnosis['quantified_issues'][i]['evidence'] = f"原判断不准确，修正为: {correction}"
                        break

                for i, sug in enumerate(corrected_diagnosis.get('improvement_suggestions', [])):
                    ci = sug.get('current_issue', '')
                    if claim in ci or ci in claim:
                        corrected_diagnosis['improvement_suggestions'][i]['current_issue'] = f"~~{ci}~~ → 修正: {correction}"
                        corrected_diagnosis['improvement_suggestions'][i]['priority'] = '低'
                        break

        if inaccurate_claims:
            score_penalty = sum(
                qi.get('score_impact', 0) for qi in corrected_diagnosis.get('quantified_issues', [])
                if any(v.get('claim', '') in qi.get('issue', '') for v in inaccurate_claims)
            )
            if score_penalty > 0:
                corrected_diagnosis['overall_score'] = min(100, corrected_diagnosis.get('overall_score', 0) + score_penalty // 2)

        corrected_diagnosis["_verification_summary"] = {
            "total_claims": len(verification_results),
            "verified_claims": len(verification_results) - len(inaccurate_claims),
            "corrected_claims": len(inaccurate_claims),
            "removed_claims": removed_weaknesses,
            "corrections": [
                {"original": v.get('claim', ''), "correction": v.get('correction', ''), "reason": v.get('reason', '')}
                for v in inaccurate_claims
            ],
        }

        return corrected_diagnosis

    # ================================================================
    # Pass 6: 引用格式检查
    # ================================================================
    def _pass6_citation_format_check(self, content: str) -> Dict:
        logger.info("Pass6: 引用格式检查...")
        try:
            from src.evaluation.citation_novelty_verifier import NoveltyVerifier
            verifier = NoveltyVerifier()
            result = verifier.check_citation_format(content)
            return result
        except Exception as e:
            logger.error(f"引用格式检查失败: {str(e)}")
            return {"error": str(e)}

    # ================================================================
    # Self-Refine: 生成 → 批评 → 修订
    # ================================================================
    def _self_refine(self, diagnosis: Dict, content: str, section_evals: List[Dict]) -> Dict:
        logger.info("Self-Refine Round 2: 批评初始诊断...")
        criticism = self._refine_criticism(diagnosis, content)
        logger.info("Self-Refine Round 3: 根据批评修订诊断...")
        refined = self._refine_revise(diagnosis, criticism, content)
        refined["_refine_meta"] = {
            "criticism_summary": criticism.get("criticism_summary", ""),
            "issues_found_in_original": len(criticism.get("omitted_issues", [])),
            "refinement_applied": True
        }
        return refined

    def _refine_criticism(self, diagnosis: Dict, content: str) -> Dict:
        system_prompt = """你是一位极其严格的学术论文评审批评家。你的任务是对一份已有的评估报告进行严格审查，找出其中的遗漏、不足和可改进之处。

你必须找出至少3个问题。不要客气，越严格越好。

【核心审查原则 - 反幻觉】
1. 重点检查评估报告中是否存在"幻觉判断"——即声称论文缺少某内容，但实际原文中存在
2. 检查是否有"仅"类判断（如"仅用一种"、"仅提及少数"），但原文实际有更多
3. 检查是否有"不一致"类判断（如"摘要与正文不一致"），但实际是一致的
4. 检查是否有声称"未引用文献"但实际引用了的判断
5. 如果评估中存在上述幻觉判断，必须指出并要求修正

审查要点：
1. 是否遗漏了重要的质量问题？
2. 评分依据是否充分？是否有"凭感觉"评分的嫌疑？
3. 改进建议是否足够具体？是否只是泛泛而谈？
4. 对论文的批评是否公正？是否过于宽松或过于严苛？
5. 是否考虑了论文的学科特点和难度？
6. 是否存在与原文不符的虚假判断？

请输出JSON格式。"""

        diag_str = json.dumps(diagnosis, ensure_ascii=False, indent=2)[:8000]
        content_preview = content[:10000]

        user_prompt = f"""请对以下评估报告进行严格批评：

## 评估报告
{diag_str}

## 论文原文片段（供验证）
{content_preview}

请输出如下JSON格式：
{{
    "criticism_summary": "批评总结",
    "omitted_issues": [
        {{
            "issue": "被遗漏的问题",
            "evidence": "论文原文中的证据",
            "severity": "严重/中等/轻微",
            "suggested_score_impact": 建议扣分
        }}
    ],
    "weak_evidence_scores": [
        {{
            "item": "评分依据不足的项目",
            "current_evidence": "当前依据",
            "required_evidence": "应该提供的依据"
        }}
    ],
    "vague_suggestions": [
        {{
            "original_suggestion": "原建议内容",
            "why_vague": "为什么不够具体",
            "how_to_improve": "如何改进"
        }}
    ],
    "bias_assessment": {{
        "too_lenient": ["过于宽松的评价1"],
        "too_harsh": ["过于严苛的评价1"],
        "fair_assessment": "整体评价是否公正的判断"
    }},
    "missing_perspectives": ["缺失的评审视角1", "缺失的评审视角2"]
}}"""

        raw = self._call_llm(system_prompt, user_prompt, temperature=0.3, max_tokens=6000)
        return self._safe_json_parse(raw)

    def _refine_revise(self, diagnosis: Dict, criticism: Dict, content: str) -> Dict:
        system_prompt = """你是一位资深学术论文评审专家。你之前生成了一份评估报告，现在有一位批评家指出了其中的问题。

你的任务是根据批评意见修订评估报告，使其更加全面、准确、具体。

【核心修订原则 - 反幻觉】
1. 如果批评指出某判断与原文不符（幻觉判断），必须删除或修正该判断
2. 声称论文"缺少"某内容时，必须先在原文中确认该内容确实不存在
3. 声称论文"仅有"某内容时，必须确认没有遗漏
4. 不要质疑论文的研究设计方向（如"为什么只研究一种粉尘"），除非论文自身承诺了更多
5. 表格编号、图编号、算法编号的出现意味着这些内容存在
6. 附录中的内容同样有效
7. 不要声称摘要与正文不一致，除非能指出具体的不一致之处

修订原则：
1. 被遗漏的问题必须补充进来
2. 评分依据不足的必须补充证据
3. 泛泛建议必须改为具体可操作的建议
4. 如果批评合理，调整评分；如果不合理，说明理由
5. 补充缺失的评审视角
6. 删除与原文不符的虚假判断，并相应调整评分

请输出修订后的完整JSON格式评估结果。"""

        diag_str = json.dumps(diagnosis, ensure_ascii=False, indent=2)[:6000]
        crit_str = json.dumps(criticism, ensure_ascii=False, indent=2)[:6000]
        content_preview = content[:10000]

        user_prompt = f"""请根据批评意见修订评估报告：

## 原始评估报告
{diag_str}

## 批评意见
{crit_str}

## 论文原文片段（供验证）
{content_preview}

请输出修订后的完整评估结果（JSON格式，结构与原始报告相同，但内容更全面准确）：
{{
    "overall_score": 0-100的整数,
    "grade_level": "优秀/良好/中等/及格/不及格",
    "overall_comment": "修订后的总体评价（200字以上）",
    "strengths": ["优势1", "优势2", "优势3"],
    "weaknesses": ["不足1", "不足2", "不足3"],
    "quantified_issues": [
        {{
            "issue": "问题描述",
            "location": "问题所在位置",
            "severity": "严重/中等/轻微",
            "score_impact": 影响分数,
            "evidence": "原文证据"
        }}
    ],
    "section_scores_summary": [
        {{
            "section_title": "章节名",
            "score": 分数,
            "grade": "等级"
        }}
    ],
    "improvement_suggestions": [
        {{
            "aspect": "改进方面",
            "current_issue": "当前具体问题（引用原文）",
            "suggestion": "具体修改方案（包含修改步骤）",
            "priority": "高/中/低",
            "estimated_score_impact": 可提升分数,
            "difficulty": "容易/中等/困难"
        }}
    ],
    "detailed_analysis": {{
        "innovation_analysis": "创新性分析（150字以上）",
        "depth_analysis": "研究深度分析（150字以上）",
        "structure_analysis": "结构完整性分析（150字以上）",
        "methodology_analysis": "方法论分析（150字以上）"
    }}
}}"""

        raw = self._call_llm(system_prompt, user_prompt, temperature=0.2, max_tokens=8000)
        return self._safe_json_parse(raw)

    # ================================================================
    # 差异化修改路线图
    # ================================================================
    def _generate_modification_roadmap(self, diagnosis: Dict, content: str) -> Dict:
        logger.info("生成差异化修改路线图...")

        issues = diagnosis.get('quantified_issues', [])
        suggestions = diagnosis.get('improvement_suggestions', [])

        prioritized_issues = sorted(issues, key=lambda x: x.get('score_impact', 0), reverse=True)
        prioritized_suggestions = sorted(
            suggestions,
            key=lambda x: {"高": 3, "中": 2, "低": 1}.get(x.get('priority', '中'), 2),
            reverse=True
        )

        total_impact = sum(iss.get('score_impact', 0) for iss in prioritized_issues)

        roadmap_items = []
        for i, (issue, suggestion) in enumerate(
            zip(prioritized_issues, prioritized_suggestions + [None] * max(0, len(prioritized_issues) - len(prioritized_suggestions)))
        ):
            item = {
                "rank": i + 1,
                "issue": issue.get('issue', ''),
                "location": issue.get('location', ''),
                "severity": issue.get('severity', '中等'),
                "score_impact": issue.get('score_impact', 0),
                "evidence": issue.get('evidence', ''),
            }
            if suggestion:
                item["suggestion"] = suggestion.get('suggestion', '')
                item["aspect"] = suggestion.get('aspect', '')
                item["difficulty"] = suggestion.get('difficulty', '中等')
                item["current_issue"] = suggestion.get('current_issue', '')
            roadmap_items.append(item)

        for i in range(len(prioritized_suggestions)):
            if i >= len(prioritized_issues):
                sug = prioritized_suggestions[i]
                roadmap_items.append({
                    "rank": len(roadmap_items) + 1,
                    "issue": sug.get('current_issue', sug.get('aspect', '')),
                    "location": "",
                    "severity": "中等",
                    "score_impact": sug.get('estimated_score_impact', 0),
                    "evidence": "",
                    "suggestion": sug.get('suggestion', ''),
                    "aspect": sug.get('aspect', ''),
                    "difficulty": sug.get('difficulty', '中等'),
                    "current_issue": sug.get('current_issue', ''),
                })

        before_after = self._generate_before_after_examples(roadmap_items[:5], content)

        current_score = diagnosis.get('overall_score', 0)
        potential_score = min(100, current_score + total_impact)

        return {
            "current_score": current_score,
            "potential_score": potential_score,
            "total_improvable_points": total_impact,
            "items": roadmap_items,
            "before_after_examples": before_after,
            "roadmap_summary": self._generate_roadmap_summary(roadmap_items, current_score, potential_score),
        }

    def _generate_before_after_examples(self, top_items: List[Dict], content: str) -> List[Dict]:
        if not top_items:
            return []

        self._ensure_client()

        items_desc = ""
        for item in top_items:
            items_desc += f"\n问题{item['rank']}: {item['issue']}\n位置: {item.get('location', '')}\n建议: {item.get('suggestion', '无')}\n"

        system_prompt = """你是一位学术论文修改专家。你的任务是为论文的关键问题生成"修改前后对比"示例。

要求：
1. 从论文原文中找到相关片段作为"修改前"
2. 给出具体的修改版本作为"修改后"
3. 修改后版本必须保留原文核心内容，只改进指出的问题

请输出JSON格式。"""

        content_preview = content[:8000]

        user_prompt = f"""请为以下关键问题生成修改前后对比：

## 关键问题
{items_desc}

## 论文原文片段
{content_preview}

请输出如下JSON格式：
{{
    "examples": [
        {{
            "issue_rank": 问题编号,
            "issue_description": "问题描述",
            "before": "论文原文中的相关片段（尽可能引用原文）",
            "after": "修改后的版本",
            "change_explanation": "修改说明：改了什么，为什么这样改"
        }}
    ]
}}"""

        raw = self._call_llm(system_prompt, user_prompt, max_tokens=6000)
        result = self._safe_json_parse(raw)
        return result.get('examples', [])

    def _generate_roadmap_summary(self, items: List[Dict], current_score: int, potential_score: int) -> str:
        if not items:
            return "未发现需要修改的问题。"

        high_items = [it for it in items if it.get('severity') == '严重']
        medium_items = [it for it in items if it.get('severity') == '中等']

        summary = f"当前评分{current_score}分，通过修改可提升至约{potential_score}分。"
        if high_items:
            summary += f"\n\n🔴 第一优先级（严重问题，共{len(high_items)}项）："
            for it in high_items[:3]:
                summary += f"\n  - {it['issue']}（影响{it.get('score_impact', '?')}分）"
        if medium_items:
            summary += f"\n\n🟡 第二优先级（中等问题，共{len(medium_items)}项）："
            for it in medium_items[:3]:
                summary += f"\n  - {it['issue']}（影响{it.get('score_impact', '?')}分）"
        return summary
