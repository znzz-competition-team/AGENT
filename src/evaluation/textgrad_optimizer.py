"""
TextGrad提示词自动优化模块

基于TextGrad思想，通过文本梯度（自然语言反馈）自动优化评估提示词。
核心流程：
1. 用当前提示词评估校准集（已有人工评分的论文）
2. 对比预测分数与人工分数，计算损失
3. 生成文本梯度（改进建议）
4. 根据梯度更新提示词
5. 迭代优化直到收敛
"""

from typing import Dict, List, Optional, Tuple
import json
import logging
import os
import copy
import time

logger = logging.getLogger(__name__)


class TextGradOptimizer:
    """TextGrad提示词自动优化器"""

    def __init__(self, llm_evaluator=None):
        self.llm_evaluator = llm_evaluator
        self.ai_config = None
        self.client = None
        self.optimization_history = []

    def _ensure_client(self):
        if self.client is None:
            from src.config import get_ai_config
            self.ai_config = get_ai_config()
            if self.llm_evaluator:
                self.client = self.llm_evaluator._initialize_client(self.ai_config)
            else:
                import openai
                self.client = openai.OpenAI(
                    api_key=self.ai_config["api_key"],
                    base_url=self.ai_config["base_url"]
                )

    def optimize_prompt(
        self,
        initial_system_prompt: str,
        initial_user_prompt_template: str,
        calibration_set: List[Dict],
        n_iterations: int = 3,
        evaluation_dimensions: List[str] = None,
        loss_function: str = "mse",
        early_stop_threshold: float = 0.02,
    ) -> Dict:
        """
        通过TextGrad方法优化评估提示词

        Args:
            initial_system_prompt: 初始系统提示词
            initial_user_prompt_template: 初始用户提示词模板，需包含{content}占位符
            calibration_set: 校准集，每项包含 {"content": str, "human_scores": Dict}
                human_scores示例: {"overall": 85, "innovation": 80, "research_depth": 85, "structure": 90, "method_experiment": 82}
            n_iterations: 优化迭代次数
            evaluation_dimensions: 评估维度列表
            loss_function: 损失函数类型 (mse/mae/weighted)
            early_stop_threshold: 早停阈值，相邻迭代损失差小于此值则停止

        Returns:
            优化结果字典
        """
        self._ensure_client()

        if evaluation_dimensions is None:
            evaluation_dimensions = ["innovation", "research_depth", "structure", "method_experiment"]

        current_system_prompt = initial_system_prompt
        current_user_template = initial_user_prompt_template

        best_loss = float("inf")
        best_system_prompt = current_system_prompt
        best_user_template = current_user_template
        history = []

        logger.info(f"TextGrad优化开始: {n_iterations}轮迭代, 校准集{len(calibration_set)}篇")

        for iteration in range(n_iterations):
            logger.info(f"--- TextGrad迭代 {iteration + 1}/{n_iterations} ---")

            predictions = []
            for idx, sample in enumerate(calibration_set):
                try:
                    pred = self._evaluate_with_prompt(
                        current_system_prompt,
                        current_user_template,
                        sample["content"],
                        evaluation_dimensions,
                    )
                    predictions.append({
                        "content_preview": sample["content"][:200],
                        "human_scores": sample["human_scores"],
                        "predicted_scores": pred,
                    })
                except Exception as e:
                    logger.warning(f"校准集样本{idx}评估失败: {str(e)}")
                    continue

            if not predictions:
                logger.error("所有校准集样本评估失败，终止优化")
                break

            loss = self._compute_loss(predictions, loss_function)

            dimension_errors = self._compute_dimension_errors(predictions)

            history.append({
                "iteration": iteration + 1,
                "loss": loss,
                "dimension_errors": dimension_errors,
                "n_samples": len(predictions),
                "system_prompt_length": len(current_system_prompt),
            })

            logger.info(
                f"迭代{iteration + 1}损失: {loss:.4f}, 维度误差: {dimension_errors}"
            )

            if loss < best_loss:
                best_loss = loss
                best_system_prompt = current_system_prompt
                best_user_template = current_user_template

            if iteration > 0 and abs(history[-2]["loss"] - loss) < early_stop_threshold:
                logger.info(f"损失变化小于{early_stop_threshold}，提前停止")
                break

            if iteration < n_iterations - 1:
                gradient = self._compute_text_gradient(
                    current_system_prompt,
                    current_user_template,
                    predictions,
                    loss,
                    dimension_errors,
                    evaluation_dimensions,
                )

                updated = self._update_prompt_with_gradient(
                    current_system_prompt,
                    current_user_template,
                    gradient,
                )

                current_system_prompt = updated["system_prompt"]
                current_user_template = updated["user_prompt_template"]

                logger.info(f"文本梯度: {gradient.get('summary', '')[:200]}")

        result = {
            "optimized_system_prompt": best_system_prompt,
            "optimized_user_prompt_template": best_user_template,
            "original_system_prompt": initial_system_prompt,
            "original_user_prompt_template": initial_user_prompt_template,
            "best_loss": best_loss,
            "optimization_history": history,
            "improvement": history[0]["loss"] - best_loss if len(history) > 0 else 0,
            "n_iterations_completed": len(history),
        }

        self.optimization_history.append(result)

        logger.info(
            f"TextGrad优化完成: 损失从{history[0]['loss']:.4f}降至{best_loss:.4f}, "
            f"改善{result['improvement']:.4f}"
        )

        return result

    def _evaluate_with_prompt(
        self,
        system_prompt: str,
        user_prompt_template: str,
        content: str,
        dimensions: List[str],
    ) -> Dict:
        """使用指定提示词评估单篇论文"""

        user_prompt = user_prompt_template.replace("{content}", content[:12000])

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end != -1:
                result = json.loads(raw[start:end])
            else:
                result = {"overall_score": 75}

        scores = {}
        if "overall_score" in result:
            scores["overall"] = float(result["overall_score"])
        if "quantitative_table" in result:
            qt = result["quantitative_table"]
            for dim in ["innovation", "research_depth", "structure", "method_experiment"]:
                if dim in qt and "score" in qt[dim]:
                    scores[dim] = float(qt[dim]["score"])
        if "institutional_scores" in result:
            for item in result["institutional_scores"]:
                dim_id = item.get("dimension_id", "")
                if dim_id in dimensions and "score" in item:
                    scores[dim_id] = float(item["score"])
        if "dimension_scores" in result:
            for item in result["dimension_scores"]:
                name = item.get("indicator_name", "")
                for dim in dimensions:
                    dim_cn = {
                        "innovation": "创新",
                        "research_depth": "研究",
                        "structure": "结构",
                        "method_experiment": "方法",
                    }.get(dim, dim)
                    if dim_cn in name and "score" in item:
                        scores[dim] = float(item["score"])

        if "overall" not in scores and scores:
            scores["overall"] = sum(scores.values()) / len(scores)

        return scores

    def _compute_loss(
        self, predictions: List[Dict], loss_function: str = "mse"
    ) -> float:
        """计算预测分数与人工分数之间的损失"""
        total_loss = 0.0
        count = 0

        for pred in predictions:
            human = pred["human_scores"]
            predicted = pred["predicted_scores"]

            for key in human:
                if key in predicted:
                    diff = float(human[key]) - float(predicted[key])
                    if loss_function == "mse":
                        total_loss += diff ** 2
                    elif loss_function == "mae":
                        total_loss += abs(diff)
                    elif loss_function == "weighted":
                        weight = 2.0 if key == "overall" else 1.0
                        total_loss += weight * (diff ** 2)
                    count += 1

        return total_loss / max(count, 1)

    def _compute_dimension_errors(self, predictions: List[Dict]) -> Dict[str, float]:
        """计算各维度的平均绝对误差"""
        dim_errors = {}
        dim_counts = {}

        for pred in predictions:
            human = pred["human_scores"]
            predicted = pred["predicted_scores"]

            for key in human:
                if key in predicted:
                    diff = abs(float(human[key]) - float(predicted[key]))
                    dim_errors[key] = dim_errors.get(key, 0) + diff
                    dim_counts[key] = dim_counts.get(key, 0) + 1

        return {
            k: round(dim_errors[k] / dim_counts[k], 2)
            for k in dim_errors
            if dim_counts[k] > 0
        }

    def _compute_text_gradient(
        self,
        system_prompt: str,
        user_prompt_template: str,
        predictions: List[Dict],
        loss: float,
        dimension_errors: Dict[str, float],
        dimensions: List[str],
    ) -> Dict:
        """
        计算文本梯度 - 生成自然语言改进建议

        类比于神经网络中的梯度，文本梯度是关于提示词改进方向的自然语言描述
        """
        self._ensure_client()

        error_cases = []
        for pred in predictions[:5]:
            human = pred["human_scores"]
            predicted = pred["predicted_scores"]
            diffs = {}
            for key in human:
                if key in predicted:
                    diffs[key] = round(float(predicted[key]) - float(human[key]), 1)
            error_cases.append({
                "content_preview": pred["content_preview"][:100],
                "human_scores": human,
                "predicted_scores": predicted,
                "differences": diffs,
            })

        dim_cn = {
            "innovation": "创新度",
            "research_depth": "研究分析深度",
            "structure": "文章结构",
            "method_experiment": "研究方法与实验",
            "overall": "总分",
        }
        error_desc = "\n".join(
            f"样本{i+1}: 人工评分={e['human_scores']}, 预测评分={e['predicted_scores']}, 偏差={e['differences']}"
            for i, e in enumerate(error_cases)
        )
        dim_error_desc = "\n".join(
            f"- {dim_cn.get(k, k)}: 平均绝对误差 {v}分"
            for k, v in dimension_errors.items()
        )
        gradient_prompt = f"""你是一位提示词工程专家。你需要分析当前评估提示词的问题，并生成"文本梯度"
        ——即具体的改进建议。

## 当前评估提示词

### System Prompt（前500字）:
{system_prompt[:500]}...

### User Prompt Template（前500字）:
{user_prompt_template[:500]}...

## 评估偏差分析
当前损失值: {loss:.4f}
各维度平均绝对误差:
{dim_error_desc}
具体偏差案例:
{error_desc}
## 任务
请分析提示词存在的问题，并生成文本梯度（改进建议）。重点关注：
1. **系统性偏差**：LLM是否在某个维度上系统性地给高分或低分？
   - 如果预测分数普遍高于人工分数 → 提示词可能过于宽松
   - 如果预测分数普遍低于人工分数 → 提示词可能过于严格
2. **区分度不足**：LLM是否对不同质量的论文给出了过于接近的分数？
   - 如果所有预测分数都集中在75-85之间 → 提示词缺乏区分度
3. **维度权重失衡**：某些维度的误差是否显著高于其他维度？
   - 如果创新度误差最大 → 提示词对创新度评估的指导不够明确
4. **证据要求不足**：LLM是否在没有充分证据的情况下给出评分？
   - 需要在提示词中强化"必须引用原文"的要求

请返回JSON格式:
{{
    "summary": "改进建议总结（一句话）",
    "systematic_bias": "系统性偏差描述",
    "discrimination_issue": "区分度问题描述",
    "dimension_imbalance": "维度失衡描述",
    "gradient_system_prompt": "对System Prompt的具体修改建议（3-5条）",
    "gradient_user_prompt": "对User Prompt的具体修改建议（3-5条）",
    "priority_fixes": ["最优先修复的问题1", "最优先修复的问题2"]
}}"""

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {
                    "role": "system",
                    "content": "你是一位提示词工程专家，擅长分析LLM评估提示词的偏差并生成改进建议。",
                },
                {"role": "user", "content": gradient_prompt},
            ],
            temperature=0.3,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        try:
            gradient = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end != -1:
                gradient = json.loads(raw[start:end])
            else:
                gradient = {
                    "summary": "无法解析梯度",
                    "gradient_system_prompt": ["增加评分校准说明"],
                    "gradient_user_prompt": ["强化证据引用要求"],
                }

        return gradient

    def _update_prompt_with_gradient(
        self,
        current_system_prompt: str,
        current_user_template: str,
        gradient: Dict,
    ) -> Dict:
        """根据文本梯度更新提示词"""
        self._ensure_client()

        system_gradient = gradient.get("gradient_system_prompt", [])
        user_gradient = gradient.get("gradient_user_prompt", [])

        if isinstance(system_gradient, list):
            system_gradient = "\n".join(f"- {g}" for g in system_gradient)
        if isinstance(user_gradient, list):
            user_gradient = "\n".join(f"- {g}" for g in user_gradient)

        update_prompt = f"""请根据以下改进建议（文本梯度），更新评估提示词。

## 当前System Prompt
{current_system_prompt}

## 对System Prompt的改进建议
{system_gradient}

## 当前User Prompt Template
{current_user_template}

## 对User Prompt的改进建议
{user_gradient}

## 要求
1. 保留原提示词的核心结构和评分标准
2. 将改进建议融入提示词，而非简单追加
3. 确保更新后的提示词更加精确、可操作
4. 不要删除原有的重要约束条件
5. User Prompt Template中必须保留{{content}}占位符

请返回JSON格式:
{{
    "system_prompt": "更新后的System Prompt",
    "user_prompt_template": "更新后的User Prompt Template"
}}"""

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {
                    "role": "system",
                    "content": "你是一位提示词工程专家，负责根据改进建议更新评估提示词。",
                },
                {"role": "user", "content": update_prompt},
            ],
            temperature=0.2,
            max_tokens=8000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        try:
            updated = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end != -1:
                updated = json.loads(raw[start:end])
            else:
                updated = {
                    "system_prompt": current_system_prompt,
                    "user_prompt_template": current_user_template,
                }

        if "{content}" not in updated.get("user_prompt_template", ""):
            updated["user_prompt_template"] = current_user_template

        return updated

    def optimize_prompt_bootstrap(
        self,
        initial_system_prompt: str,
        initial_user_prompt_template: str,
        thesis_samples: List[str],
        n_iterations: int = 2,
        evaluation_dimensions: List[str] = None,
    ) -> Dict:
        """
        自举模式优化提示词（无需人工评分）

        原理：在没有人工评分的情况下，通过以下策略优化提示词：
        1. 一致性检验：同一论文用同一提示词评估两次，检测评分波动
        2. 区分度检验：不同质量论文的评分差距是否足够大
        3. 自我批评：让LLM审视自己的评分是否合理
        4. 结构化改进：基于以上分析生成文本梯度

        Args:
            initial_system_prompt: 初始系统提示词
            initial_user_prompt_template: 初始用户提示词模板
            thesis_samples: 论文样本列表（只需论文文本，无需人工评分）
            n_iterations: 迭代次数
            evaluation_dimensions: 评估维度

        Returns:
            优化结果
        """
        self._ensure_client()

        if evaluation_dimensions is None:
            evaluation_dimensions = ["innovation", "research_depth", "structure", "method_experiment"]

        current_system_prompt = initial_system_prompt
        current_user_template = initial_user_prompt_template

        best_consistency = -1
        best_system_prompt = current_system_prompt
        best_user_template = current_user_template
        history = []

        logger.info(f"TextGrad自举优化开始: {n_iterations}轮迭代, {len(thesis_samples)}篇样本")

        for iteration in range(n_iterations):
            logger.info(f"--- 自举迭代 {iteration + 1}/{n_iterations} ---")

            round1_scores = []
            round2_scores = []

            for idx, content in enumerate(thesis_samples[:5]):
                try:
                    s1 = self._evaluate_with_prompt(
                        current_system_prompt, current_user_template, content, evaluation_dimensions
                    )
                    s2 = self._evaluate_with_prompt(
                        current_system_prompt, current_user_template, content, evaluation_dimensions
                    )
                    round1_scores.append(s1)
                    round2_scores.append(s2)
                except Exception as e:
                    logger.warning(f"样本{idx}评估失败: {str(e)}")
                    continue

            if not round1_scores:
                logger.error("所有样本评估失败")
                break

            consistency = self._compute_consistency(round1_scores, round2_scores)
            discrimination = self._compute_discrimination(round1_scores)

            overall_metric = consistency * 0.6 + discrimination * 0.4

            history.append({
                "iteration": iteration + 1,
                "consistency": round(consistency, 4),
                "discrimination": round(discrimination, 4),
                "overall_metric": round(overall_metric, 4),
                "n_samples": len(round1_scores),
            })

            logger.info(
                f"迭代{iteration + 1}: 一致性={consistency:.4f}, 区分度={discrimination:.4f}, 综合={overall_metric:.4f}"
            )

            if overall_metric > best_consistency:
                best_consistency = overall_metric
                best_system_prompt = current_system_prompt
                best_user_template = current_user_template

            if iteration < n_iterations - 1:
                gradient = self._compute_bootstrap_gradient(
                    current_system_prompt,
                    current_user_template,
                    round1_scores,
                    round2_scores,
                    consistency,
                    discrimination,
                    evaluation_dimensions,
                )

                updated = self._update_prompt_with_gradient(
                    current_system_prompt,
                    current_user_template,
                    gradient,
                )

                current_system_prompt = updated["system_prompt"]
                current_user_template = updated["user_prompt_template"]

        result = {
            "optimized_system_prompt": best_system_prompt,
            "optimized_user_prompt_template": best_user_template,
            "original_system_prompt": initial_system_prompt,
            "original_user_prompt_template": initial_user_prompt_template,
            "best_consistency": round(best_consistency, 4),
            "optimization_history": history,
            "mode": "bootstrap",
            "n_iterations_completed": len(history),
        }

        self.optimization_history.append(result)
        logger.info(f"TextGrad自举优化完成: 最佳综合指标={best_consistency:.4f}")
        return result

    def _compute_consistency(self, round1: List[Dict], round2: List[Dict]) -> float:
        """计算两次评估的一致性（1 - 平均相对偏差）"""
        total_diff = 0.0
        count = 0

        for s1, s2 in zip(round1, round2):
            for key in s1:
                if key in s2:
                    diff = abs(float(s1[key]) - float(s2[key]))
                    total_diff += diff
                    count += 1

        if count == 0:
            return 0.0

        avg_diff = total_diff / count
        return max(0, 1 - avg_diff / 50)

    def _compute_discrimination(self, scores: List[Dict]) -> float:
        """计算评分区分度（评分标准差越大，区分度越高）"""
        import numpy as np

        all_overall = []
        for s in scores:
            if "overall" in s:
                all_overall.append(float(s["overall"]))
            elif s:
                vals = [float(v) for v in s.values()]
                all_overall.append(sum(vals) / len(vals))

        if len(all_overall) < 2:
            return 0.0

        std = float(np.std(all_overall))
        return min(1.0, std / 15)

    def _compute_bootstrap_gradient(
        self,
        system_prompt: str,
        user_prompt_template: str,
        round1_scores: List[Dict],
        round2_scores: List[Dict],
        consistency: float,
        discrimination: float,
        dimensions: List[str],
    ) -> Dict:
        """自举模式下的文本梯度计算"""
        self._ensure_client()

        dim_cn = {
            "innovation": "创新度",
            "research_depth": "研究分析深度",
            "structure": "文章结构",
            "method_experiment": "研究方法与实验",
            "overall": "总分",
        }

        inconsistency_examples = []
        for i, (s1, s2) in enumerate(zip(round1_scores[:3], round2_scores[:3])):
            diffs = {}
            for key in s1:
                if key in s2:
                    diffs[key] = round(abs(float(s1[key]) - float(s2[key])), 1)
            inconsistency_examples.append({
                "sample": i + 1,
                "round1": s1,
                "round2": s2,
                "differences": diffs,
            })

        inconsistency_desc = "\n".join(
            f"样本{e['sample']}: 第1轮={e['round1']}, 第2轮={e['round2']}, 偏差={e['differences']}"
            for e in inconsistency_examples
        )

        prompt = f"""你是一位提示词工程专家。在没有人工评分的情况下，你需要通过分析LLM自评的一致性和区分度来优化评估提示词。

## 当前评估提示词

### System Prompt（前500字）:
{system_prompt[:500]}...

### User Prompt Template（前500字）:
{user_prompt_template[:500]}...

## 自评一致性分析

一致性得分: {consistency:.4f}（1.0=完全一致，0.0=完全不一致）
区分度得分: {discrimination:.4f}（1.0=区分度很高，0.0=所有论文得分相同）

两次评估的偏差案例:
{inconsistency_desc}

## 优化方向

1. **提升一致性**（当前{consistency:.2f}）：
   - 如果一致性低，说明提示词的评分标准不够明确，LLM每次理解不同
   - 需要增加更具体的评分锚点（如"引用3篇以上近5年文献=80分以上"）
   - 需要减少模糊表述（如"有一定创新"→"提出了至少1个新方法/新模型/新应用"）

2. **提升区分度**（当前{discrimination:.2f}）：
   - 如果区分度低，说明提示词让LLM倾向于给中间分数
   - 需要明确各等级的边界条件
   - 需要增加极端情况的评分指导

3. **强化证据约束**：
   - 确保提示词要求LLM必须引用论文原文作为评分依据
   - 如果没有找到证据，应该降低评分而非猜测

请返回JSON格式:
{{
    "summary": "改进建议总结（一句话）",
    "consistency_issue": "一致性问题分析",
    "discrimination_issue": "区分度问题分析",
    "gradient_system_prompt": "对System Prompt的具体修改建议（3-5条）",
    "gradient_user_prompt": "对User Prompt的具体修改建议（3-5条）",
    "priority_fixes": ["最优先修复的问题1", "最优先修复的问题2"]
}}"""

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {
                    "role": "system",
                    "content": "你是一位提示词工程专家，擅长通过一致性分析和区分度分析来优化LLM评估提示词。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        try:
            gradient = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end != -1:
                gradient = json.loads(raw[start:end])
            else:
                gradient = {
                    "summary": "无法解析梯度",
                    "gradient_system_prompt": ["增加评分校准锚点"],
                    "gradient_user_prompt": ["强化评分标准的具体性"],
                }

        return gradient

    def save_optimized_prompt(self, optimization_result: Dict, output_path: str):
        """保存优化后的提示词到文件"""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        save_data = {
            "optimized_system_prompt": optimization_result["optimized_system_prompt"],
            "optimized_user_prompt_template": optimization_result["optimized_user_prompt_template"],
            "best_loss": optimization_result["best_loss"],
            "improvement": optimization_result["improvement"],
            "n_iterations": optimization_result["n_iterations_completed"],
            "optimization_history": [
                {"iteration": h["iteration"], "loss": h["loss"], "dimension_errors": h["dimension_errors"]}
                for h in optimization_result.get("optimization_history", [])
            ],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        logger.info(f"优化提示词已保存至: {output_path}")

    def load_optimized_prompt(self, input_path: str) -> Dict:
        """加载已优化的提示词"""
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"已加载优化提示词: 损失{data.get('best_loss', 'N/A')}, 改善{data.get('improvement', 'N/A')}")
        return data
