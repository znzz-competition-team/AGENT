"""
增强评估器 - 整合TextGrad、多模型评审、引用网络新颖度验证

在现有评估流程基础上，增加三个高级模块：
1. TextGrad提示词自动优化 - 让评估提示词持续进化
2. 专用评审模型集成 - 多模型共识评审 + 偏置校正
3. 引用网络新颖度验证 - 基于外部知识验证创新性

使用方式：
    from src.evaluation.enhanced_evaluator import EnhancedEvaluator

    evaluator = EnhancedEvaluator()
    result = evaluator.evaluate(content, student_info=..., indicators=...)
"""

from typing import Dict, List, Optional
import json
import logging
import os

logger = logging.getLogger(__name__)


class EnhancedEvaluator:
    """增强评估器 - 整合三大高级模块"""

    def __init__(
        self,
        enable_textgrad: bool = True,
        enable_multi_judge: bool = True,
        enable_novelty_verification: bool = True,
        semantic_scholar_api_key: str = None,
        optimized_prompt_path: str = None,
    ):
        self.enable_textgrad = enable_textgrad
        self.enable_multi_judge = enable_multi_judge
        self.enable_novelty_verification = enable_novelty_verification

        self._llm_evaluator = None
        self._sectioned_evaluator = None
        self._textgrad_optimizer = None
        self._specialist_judge = None
        self._calibrated_scorer = None
        self._novelty_verifier = None

        self._semantic_scholar_api_key = semantic_scholar_api_key
        self._optimized_prompt_path = optimized_prompt_path

        self._optimized_prompts = None
        if optimized_prompt_path and os.path.exists(optimized_prompt_path):
            self._load_optimized_prompts(optimized_prompt_path)

    def _get_llm_evaluator(self):
        if self._llm_evaluator is None:
            from src.evaluation.llm_evaluator import LLMEvaluator
            self._llm_evaluator = LLMEvaluator()
        return self._llm_evaluator

    def _get_sectioned_evaluator(self):
        if self._sectioned_evaluator is None:
            from src.evaluation.sectioned_evaluator import SectionedEvaluator
            self._sectioned_evaluator = SectionedEvaluator(self._get_llm_evaluator())
        return self._sectioned_evaluator

    def _get_textgrad_optimizer(self):
        if self._textgrad_optimizer is None:
            from src.evaluation.textgrad_optimizer import TextGradOptimizer
            self._textgrad_optimizer = TextGradOptimizer(
                llm_evaluator=self._get_llm_evaluator()
            )
        return self._textgrad_optimizer

    def _get_specialist_judge(self):
        if self._specialist_judge is None:
            from src.evaluation.specialist_judge import SpecialistJudge, CalibratedScorer
            self._specialist_judge = SpecialistJudge()
            self._calibrated_scorer = CalibratedScorer()
        return self._specialist_judge

    def _get_calibrated_scorer(self):
        if self._calibrated_scorer is None:
            from src.evaluation.specialist_judge import CalibratedScorer
            self._calibrated_scorer = CalibratedScorer()
        return self._calibrated_scorer

    def _get_novelty_verifier(self):
        if self._novelty_verifier is None:
            from src.evaluation.citation_novelty_verifier import NoveltyVerifier
            self._novelty_verifier = NoveltyVerifier(
                semantic_scholar_api_key=self._semantic_scholar_api_key,
            )
        return self._novelty_verifier

    def _load_optimized_prompts(self, path: str):
        try:
            from src.evaluation.textgrad_optimizer import TextGradOptimizer
            optimizer = TextGradOptimizer()
            self._optimized_prompts = optimizer.load_optimized_prompt(path)
            logger.info(f"已加载优化提示词: {path}")
        except Exception as e:
            logger.warning(f"加载优化提示词失败: {str(e)}")
            self._optimized_prompts = None

    def evaluate(
        self,
        content: str,
        student_info: Dict = None,
        indicators: Dict = None,
        dimension_weights: Dict = None,
        calibration_set: List[Dict] = None,
        extra_judge_models: List[Dict] = None,
    ) -> Dict:
        """
        增强评估 - 完整流程

        Args:
            content: 论文全文
            student_info: 学生信息
            indicators: 评价指标
            dimension_weights: 维度权重
            calibration_set: 校准集（用于TextGrad优化和评分校准）
            extra_judge_models: 额外评审模型配置列表
                [{"name": "model_a", "api_key": "...", "base_url": "...", "model_name": "...", "weight": 0.8}]

        Returns:
            增强评估结果
        """
        logger.info("=" * 60)
        logger.info("开始增强评估流程")
        logger.info(f"TextGrad: {'启用' if self.enable_textgrad else '禁用'}")
        logger.info(f"多模型评审: {'启用' if self.enable_multi_judge else '禁用'}")
        logger.info(f"新颖度验证: {'启用' if self.enable_novelty_verification else '禁用'}")
        logger.info("=" * 60)

        base_result = self._run_base_evaluation(
            content, student_info, indicators, dimension_weights
        )

        enhanced_result = {
            "base_evaluation": base_result,
            "enhancement_modules": {},
        }

        if self.enable_novelty_verification:
            novelty_result = self._run_novelty_verification(content)
            enhanced_result["enhancement_modules"]["novelty_verification"] = novelty_result

            enhanced_result = self._integrate_novelty_into_base(
                enhanced_result, novelty_result
            )

        if self.enable_multi_judge:
            multi_judge_result = self._run_multi_judge_evaluation(
                content, extra_judge_models
            )
            enhanced_result["enhancement_modules"]["multi_judge"] = multi_judge_result

            enhanced_result = self._integrate_multi_judge_into_base(
                enhanced_result, multi_judge_result
            )

        if self.enable_textgrad and calibration_set:
            textgrad_result = self._run_textgrad_optimization(
                calibration_set, indicators
            )
            enhanced_result["enhancement_modules"]["textgrad_optimization"] = textgrad_result

        enhanced_result = self._compute_final_enhanced_score(enhanced_result)

        logger.info("=" * 60)
        logger.info(f"增强评估完成: 最终分数 {enhanced_result.get('final_enhanced_score', 'N/A')}")
        logger.info("=" * 60)

        return enhanced_result

    def _run_base_evaluation(
        self,
        content: str,
        student_info: Dict,
        indicators: Dict,
        dimension_weights: Dict,
    ) -> Dict:
        """运行基础评估流程"""
        logger.info("Step 1: 运行基础分段评估...")

        try:
            evaluator = self._get_sectioned_evaluator()
            result = evaluator.evaluate_thesis_sectioned(
                content=content,
                indicators=indicators,
                student_info=student_info,
                dimension_weights=dimension_weights,
            )
            overall = result.get("overall_score", 0)
            if overall is not None and overall > 0:
                logger.info(f"基础分段评估完成: {overall}分")
                return result
            else:
                logger.warning(f"基础分段评估返回0分，尝试检查子分数...")
                section_evals = result.get("section_evaluations", [])
                if section_evals:
                    scores = [e.get("section_score", 0) for e in section_evals if e.get("section_score")]
                    if scores:
                        avg = sum(scores) / len(scores)
                        logger.info(f"从章节评分中恢复: 平均{avg:.1f}分")
                        result["overall_score"] = round(avg, 1)
                        return result
                logger.warning("基础分段评估无有效分数，尝试LLM确定性评分...")
        except Exception as e:
            logger.error(f"基础分段评估失败: {str(e)}")
            import traceback
            traceback.print_exc()

        try:
            llm = self._get_llm_evaluator()
            result = llm.evaluate_with_deterministic_standards(
                submission_content=content,
                project_type="thesis",
                student_info=student_info,
            )
            overall = result.get("overall_score", 0)
            if overall and overall > 0:
                logger.info(f"LLM确定性评分完成: {overall}分")
                return result
            else:
                logger.error(f"LLM确定性评分也返回0分")
                return {"overall_score": 0, "error": "所有评估方式均返回0分，请检查API配置"}
        except Exception as e2:
            logger.error(f"LLM评估也失败: {str(e2)}")
            import traceback
            traceback.print_exc()
            return {"overall_score": 0, "error": f"评估失败: {str(e2)}"}

    def _run_novelty_verification(self, content: str) -> Dict:
        """运行引用网络新颖度验证"""
        logger.info("Step 2: 运行引用网络新颖度验证...")

        try:
            verifier = self._get_novelty_verifier()
            result = verifier.verify_thesis_novelty(content)
            return result
        except Exception as e:
            logger.error(f"新颖度验证失败: {str(e)}")
            return {
                "novelty_score": None,
                "error": str(e),
            }

    def _run_multi_judge_evaluation(
        self,
        content: str,
        extra_judge_models: List[Dict] = None,
    ) -> Dict:
        """运行多模型共识评审"""
        logger.info("Step 3: 运行多模型共识评审...")

        try:
            judge = self._get_specialist_judge()

            if extra_judge_models:
                from src.evaluation.specialist_judge import JudgeModelConfig
                for model_cfg in extra_judge_models:
                    judge.add_openai_compatible_model(
                        name=model_cfg.get("name", "extra_model"),
                        api_key=model_cfg.get("api_key", ""),
                        base_url=model_cfg.get("base_url", ""),
                        model_name=model_cfg.get("model_name", ""),
                        weight=model_cfg.get("weight", 1.0),
                        temperature=model_cfg.get("temperature", 0.1),
                    )

            result = judge.multi_judge_evaluate(content)
            return result
        except Exception as e:
            logger.error(f"多模型评审失败: {str(e)}")
            return {
                "overall_consensus_score": None,
                "error": str(e),
            }

    def _run_textgrad_optimization(
        self,
        calibration_set: List[Dict],
        indicators: Dict,
    ) -> Dict:
        """运行TextGrad提示词优化"""
        logger.info("Step 4: 运行TextGrad提示词优化...")

        try:
            optimizer = self._get_textgrad_optimizer()

            from src.prompts.thesis_prompts import ENHANCED_INSTITUTIONAL_SYSTEM_PROMPT

            user_template = """请对以下毕业设计论文进行校方固有评价体系维度评分。

## 论文内容

{content}

请返回JSON格式的评分结果。"""

            result = optimizer.optimize_prompt(
                initial_system_prompt=ENHANCED_INSTITUTIONAL_SYSTEM_PROMPT,
                initial_user_prompt_template=user_template,
                calibration_set=calibration_set,
                n_iterations=2,
            )

            if self._optimized_prompt_path:
                optimizer.save_optimized_prompt(result, self._optimized_prompt_path)

            return {
                "best_loss": result.get("best_loss"),
                "improvement": result.get("improvement"),
                "n_iterations": result.get("n_iterations_completed"),
                "optimization_history": result.get("optimization_history", []),
            }
        except Exception as e:
            logger.error(f"TextGrad优化失败: {str(e)}")
            return {"error": str(e)}

    def _integrate_novelty_into_base(
        self, enhanced_result: Dict, novelty_result: Dict
    ) -> Dict:
        """将新颖度验证结果整合到基础评估中"""
        base = enhanced_result.get("base_evaluation", {})

        novelty_score = novelty_result.get("novelty_score")
        if novelty_score is not None:
            if "novelty_verification" not in base:
                base["novelty_verification"] = {}

            base["novelty_verification"]["citation_based_novelty_score"] = novelty_score
            base["novelty_verification"]["novelty_grade"] = novelty_result.get("novelty_grade")
            base["novelty_verification"]["reference_verification_rate"] = novelty_result.get(
                "reference_statistics", {}
            ).get("verification_rate")
            base["novelty_verification"]["recency_score"] = novelty_result.get(
                "recency_analysis", {}
            ).get("recency_score")
            base["novelty_verification"]["self_citation_assessment"] = novelty_result.get(
                "self_citation_analysis", {}
            ).get("assessment")
            base["novelty_verification"]["innovation_verification"] = novelty_result.get(
                "innovation_verification", []
            )

            dim_scores = base.get("dimension_scores") or base.get("quantitative_table", {})
            innovation_score = None
            if isinstance(dim_scores, list):
                for ds in dim_scores:
                    name = ds.get("indicator_name", ds.get("dimension_name", ""))
                    if "创新" in name:
                        innovation_score = ds.get("score")
                        break
            elif isinstance(dim_scores, dict):
                inn = dim_scores.get("innovation", {})
                innovation_score = inn.get("score") if isinstance(inn, dict) else None

            if innovation_score is not None and novelty_score is not None:
                novelty_weight = 0.3
                adjusted_innovation = innovation_score * (1 - novelty_weight) + novelty_score * novelty_weight

                if isinstance(dim_scores, list):
                    for ds in dim_scores:
                        name = ds.get("indicator_name", ds.get("dimension_name", ""))
                        if "创新" in name:
                            ds["original_score"] = ds.get("score")
                            ds["score"] = round(adjusted_innovation, 1)
                            ds["novelty_adjustment"] = round(adjusted_innovation - innovation_score, 1)
                            ds["adjustment_reason"] = f"基于引用网络验证的新颖度评分({novelty_score})进行了校准"
                            break
                elif isinstance(dim_scores, dict):
                    inn = dim_scores.get("innovation", {})
                    if isinstance(inn, dict):
                        inn["original_score"] = inn.get("score")
                        inn["score"] = round(adjusted_innovation, 1)
                        inn["novelty_adjustment"] = round(adjusted_innovation - innovation_score, 1)

            enhanced_result["base_evaluation"] = base

        return enhanced_result

    def _integrate_multi_judge_into_base(
        self, enhanced_result: Dict, multi_judge_result: Dict
    ) -> Dict:
        """将多模型评审结果整合到基础评估中"""
        base = enhanced_result.get("base_evaluation", {})

        consensus_score = multi_judge_result.get("overall_consensus_score")
        if consensus_score is not None:
            base["multi_judge_consensus"] = {
                "consensus_score": consensus_score,
                "n_judges": multi_judge_result.get("n_judges", 1),
                "agreement_analysis": multi_judge_result.get("agreement_analysis", {}),
                "consensus_method": multi_judge_result.get("consensus_method", "weighted_average"),
            }

            calibrated_scorer = self._get_calibrated_scorer()
            base_score = base.get("overall_score", 0)
            if base_score and calibrated_scorer.is_calibrated:
                calibration = calibrated_scorer.bias_corrected_score(base_score)
                base["calibration_result"] = calibration

            consensus_scores = multi_judge_result.get("consensus_scores", {})
            if consensus_scores:
                base["multi_judge_dimension_consensus"] = {}
                for dim, info in consensus_scores.items():
                    if isinstance(info, dict) and info.get("score") is not None:
                        base["multi_judge_dimension_consensus"][dim] = info["score"]

            enhanced_result["base_evaluation"] = base

        return enhanced_result

    def _compute_final_enhanced_score(self, enhanced_result: Dict) -> Dict:
        """计算最终增强评分"""
        base = enhanced_result.get("base_evaluation", {})
        raw_base_score = base.get("overall_score", 0)
        try:
            base_score = float(raw_base_score) if raw_base_score is not None else 0
        except (ValueError, TypeError):
            base_score = 0

        if base_score <= 0:
            avg_section = base.get("avg_section_score", 0)
            if avg_section and avg_section > 0:
                base_score = avg_section
                logger.info(f"overall_score为0，使用章节平均分{avg_section}作为基础分")
            else:
                dim_scores = base.get("dimension_scores") or base.get("quantitative_table", {})
                if isinstance(dim_scores, list) and dim_scores:
                    scores = [d.get("score", 0) for d in dim_scores if isinstance(d, dict) and d.get("score")]
                    if scores:
                        base_score = sum(scores) / len(scores)
                        logger.info(f"overall_score为0，使用维度平均分{base_score}作为基础分")

        if base_score <= 0:
            enhanced_result["final_enhanced_score"] = 0
            enhanced_result["final_enhanced_grade"] = "不及格"
            enhanced_result["base_score"] = 0
            enhanced_result["score_adjustments"] = {}
            enhanced_result["total_adjustment"] = 0
            return enhanced_result

        adjustments = {}

        novelty_data = enhanced_result.get("enhancement_modules", {}).get("novelty_verification", {})
        novelty_score = novelty_data.get("novelty_score")
        if novelty_score is not None:
            innovation_dim = None
            dim_scores = base.get("dimension_scores") or base.get("quantitative_table", {})
            if isinstance(dim_scores, list):
                for ds in dim_scores:
                    if "创新" in ds.get("indicator_name", ds.get("dimension_name", "")):
                        innovation_dim = ds
                        break

            if innovation_dim:
                llm_innovation = innovation_dim.get("score", base_score)
                novelty_gap = novelty_score - llm_innovation
                if novelty_gap < -10:
                    novelty_adjustment = novelty_gap * 0.15
                    adjustments["novelty_correction"] = {
                        "value": round(novelty_adjustment, 1),
                        "reason": f"引用网络验证的新颖度({novelty_score})显著低于LLM评分({llm_innovation})，进行向下校准",
                    }
                elif novelty_gap > 10:
                    novelty_adjustment = novelty_gap * 0.05
                    adjustments["novelty_bonus"] = {
                        "value": round(novelty_adjustment, 1),
                        "reason": f"引用网络验证的新颖度({novelty_score})高于LLM评分({llm_innovation})，给予小幅加分",
                    }

        multi_judge_data = enhanced_result.get("enhancement_modules", {}).get("multi_judge", {})
        consensus_score = multi_judge_data.get("overall_consensus_score")
        if consensus_score is not None:
            judge_gap = consensus_score - base_score
            agreement = multi_judge_data.get("agreement_analysis", {})

            high_agreement = all(
                v.get("agreement_level") in ("high", "moderate")
                for v in agreement.values()
                if isinstance(v, dict)
            )

            if high_agreement and abs(judge_gap) > 5:
                judge_adjustment = judge_gap * 0.2
                adjustments["multi_judge_correction"] = {
                    "value": round(judge_adjustment, 1),
                    "reason": f"多模型共识评分({consensus_score})与基础评分({base_score})偏差{judge_gap:.1f}分，且评审一致性高，进行校准",
                }

        self_cite = novelty_data.get("self_citation_analysis", {})
        if self_cite.get("self_citation_ratio", 0) > 0.3:
            self_cite_penalty = -3.0
            adjustments["self_citation_penalty"] = {
                "value": self_cite_penalty,
                "reason": f"自引比例过高({self_cite['self_citation_ratio']:.1%})，扣减分数",
            }

        ref_verification = novelty_data.get("reference_statistics", {})
        if ref_verification.get("verification_rate", 1.0) < 0.5:
            ref_penalty = -2.0
            adjustments["reference_integrity_penalty"] = {
                "value": ref_penalty,
                "reason": f"参考文献验证率过低({ref_verification['verification_rate']:.1%})，可能存在虚假引用",
            }

        fake_analysis = novelty_data.get("fake_reference_analysis", {})
        if fake_analysis:
            fake_prob = fake_analysis.get("fake_probability", 0)
            risk_level = fake_analysis.get("risk_level", "minimal")
            topic_mismatch_count = fake_analysis.get("topic_mismatch_count", 0)
            if topic_mismatch_count > 0:
                topic_penalty = -3.0 * topic_mismatch_count
                adjustments["topic_mismatch_penalty"] = {
                    "value": max(topic_penalty, -10.0),
                    "reason": f"发现{topic_mismatch_count}条引用与论文主题严重不匹配，极可能是虚假引用或AI编造",
                }
            if risk_level == "high":
                fake_penalty = -5.0
                adjustments["fake_reference_penalty"] = {
                    "value": fake_penalty,
                    "reason": f"虚假引用风险高(概率{fake_prob:.0f}%)，存在大量无法验证或可疑的参考文献",
                }
            elif risk_level == "medium":
                fake_penalty = -2.0
                adjustments["fake_reference_penalty"] = {
                    "value": fake_penalty,
                    "reason": f"虚假引用风险中等(概率{fake_prob:.0f}%)，部分参考文献无法验证",
                }

        total_adjustment = sum(a["value"] for a in adjustments.values())
        final_score = max(0, min(100, base_score + total_adjustment))

        if final_score >= 90:
            final_grade = "优秀"
        elif final_score >= 80:
            final_grade = "良好"
        elif final_score >= 70:
            final_grade = "中等"
        elif final_score >= 60:
            final_grade = "及格"
        else:
            final_grade = "不及格"

        enhanced_result["final_enhanced_score"] = round(final_score, 1)
        enhanced_result["final_enhanced_grade"] = final_grade
        enhanced_result["score_adjustments"] = adjustments
        enhanced_result["total_adjustment"] = round(total_adjustment, 1)
        enhanced_result["base_score"] = base_score

        return enhanced_result

    def calibrate_with_dataset(
        self,
        calibration_set: List[Dict],
        threshold_excellent: float = 85.0,
        threshold_poor: float = 65.0,
    ) -> Dict:
        """
        使用校准集校准评审模型

        Args:
            calibration_set: 校准集，每项包含 {"content": str, "human_score": float, "human_scores": Dict}
            threshold_excellent: 优秀阈值
            threshold_poor: 较差阈值

        Returns:
            校准结果
        """
        judge = self._get_specialist_judge()
        scorer = self._get_calibrated_scorer()

        calibration_result = scorer.calibrate(
            calibration_set=calibration_set,
            judge=judge,
            threshold_excellent=threshold_excellent,
            threshold_poor=threshold_poor,
        )

        return calibration_result

    def add_judge_model(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model_name: str,
        weight: float = 1.0,
        temperature: float = 0.1,
    ):
        """添加评审模型"""
        judge = self._get_specialist_judge()
        judge.add_openai_compatible_model(
            name=name,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            weight=weight,
            temperature=temperature,
        )
        logger.info(f"已添加评审模型: {name} ({model_name})")

    def add_compassjudger(
        self,
        model_path: str = "opencompass/CompassJudger-2-7B-Instruct",
        weight: float = 0.8,
    ):
        """添加CompassJudger本地评审模型"""
        judge = self._get_specialist_judge()
        judge.add_compassjudger_model(model_path=model_path, weight=weight)
        logger.info(f"已添加CompassJudger模型: {model_path}")

    def optimize_prompts(
        self,
        calibration_set: List[Dict],
        n_iterations: int = 3,
        save_path: str = None,
    ) -> Dict:
        """
        单独运行TextGrad提示词优化

        Args:
            calibration_set: 校准集
            n_iterations: 迭代次数
            save_path: 优化结果保存路径

        Returns:
            优化结果
        """
        optimizer = self._get_textgrad_optimizer()

        from src.prompts.thesis_prompts import ENHANCED_INSTITUTIONAL_SYSTEM_PROMPT

        user_template = """请对以下毕业设计论文进行校方固有评价体系维度评分。

## 论文内容

{content}

请返回JSON格式的评分结果。"""

        result = optimizer.optimize_prompt(
            initial_system_prompt=ENHANCED_INSTITUTIONAL_SYSTEM_PROMPT,
            initial_user_prompt_template=user_template,
            calibration_set=calibration_set,
            n_iterations=n_iterations,
        )

        if save_path:
            optimizer.save_optimized_prompt(result, save_path)

        return result

    def verify_novelty(self, content: str) -> Dict:
        """
        单独运行新颖度验证

        Args:
            content: 论文全文

        Returns:
            新颖度验证结果
        """
        verifier = self._get_novelty_verifier()
        return verifier.verify_thesis_novelty(content)
