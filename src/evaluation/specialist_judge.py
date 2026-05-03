"""
专用评审模型集成模块

支持多种评审模型的统一接口，包括：
1. 通用LLM评审（DeepSeek/GPT等，通过OpenAI兼容API）
2. 专用评审模型（CompassJudger等，通过Transformers本地部署或API）
3. 多模型共识机制（多评审交叉验证）
4. 偏置校正评分

核心思想：不同模型有不同的评审偏置，多模型共识可以降低单一模型的系统性偏差
"""

from typing import Dict, List, Optional, Tuple
import json
import logging
import os
import time
import numpy as np

logger = logging.getLogger(__name__)


class JudgeModelConfig:
    """评审模型配置"""

    def __init__(
        self,
        name: str,
        model_type: str,
        api_key: str = None,
        base_url: str = None,
        model_name: str = None,
        weight: float = 1.0,
        temperature: float = 0.1,
        max_tokens: int = 4000,
        enabled: bool = True,
    ):
        self.name = name
        self.model_type = model_type
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.weight = weight
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.enabled = enabled


class SpecialistJudge:
    """专用评审模型评估器"""

    JUDGE_PROMPT_TEMPLATE = """请作为一位专业的毕业设计论文评审专家，对以下论文进行独立评审。

## 评审维度
1. 创新度（0-100分）：论文的创新性，区分搭积木式创新与原创性创新
2. 研究分析深度（0-100分）：文献综述深度、问题归纳能力
3. 文章结构（0-100分）：章节安排合理性、逻辑连贯性
4. 研究方法与实验（0-100分）：方法适合性、实验设计完整性

## 论文内容
{content}

## 评审要求
1. 对每个维度给出0-100分的评分
2. 每个评分必须引用论文中的具体内容作为证据
3. 指出论文的主要优点和不足
4. 给出改进建议

请严格按照以下JSON格式返回评审结果：
{{
    "dimension_scores": {{
        "innovation": {{
            "score": 分数,
            "evidence": "论文中的具体证据",
            "reason": "评分理由"
        }},
        "research_depth": {{
            "score": 分数,
            "evidence": "论文中的具体证据",
            "reason": "评分理由"
        }},
        "structure": {{
            "score": 分数,
            "evidence": "论文中的具体证据",
            "reason": "评分理由"
        }},
        "method_experiment": {{
            "score": 分数,
            "evidence": "论文中的具体证据",
            "reason": "评分理由"
        }}
    }},
    "overall_score": 加权总分,
    "strengths": ["优点1", "优点2"],
    "weaknesses": ["不足1", "不足2"],
    "improvement_suggestions": ["建议1", "建议2"],
    "overall_comment": "总体评价（100-200字）"
}}"""

    def __init__(self, configs: List[JudgeModelConfig] = None):
        self.configs = configs or []
        self.clients = {}
        self._init_default_configs()

    def _init_default_configs(self):
        """初始化默认模型配置"""
        if not self.configs:
            from src.config import get_ai_config

            try:
                ai_config = get_ai_config()
                self.configs.append(
                    JudgeModelConfig(
                        name="primary_llm",
                        model_type="openai_compatible",
                        api_key=ai_config["api_key"],
                        base_url=ai_config["base_url"],
                        model_name=ai_config["model"],
                        weight=1.0,
                        temperature=0.1,
                    )
                )
            except Exception as e:
                logger.warning(f"初始化默认模型配置失败: {str(e)}")

    def add_judge_model(self, config: JudgeModelConfig):
        """添加评审模型"""
        self.configs.append(config)

    def add_openai_compatible_model(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model_name: str,
        weight: float = 1.0,
        temperature: float = 0.1,
    ):
        """添加OpenAI兼容API模型"""
        self.configs.append(
            JudgeModelConfig(
                name=name,
                model_type="openai_compatible",
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                weight=weight,
                temperature=temperature,
            )
        )

    def add_compassjudger_model(
        self,
        model_path: str = "opencompass/CompassJudger-2-7B-Instruct",
        weight: float = 0.8,
        device: str = "auto",
    ):
        """添加CompassJudger本地模型"""
        self.configs.append(
            JudgeModelConfig(
                name="compassjudger",
                model_type="compassjudger_local",
                model_name=model_path,
                weight=weight,
            )
        )
        self._compassjudger_device = device

    def _get_client(self, config: JudgeModelConfig):
        """获取模型客户端"""
        cache_key = f"{config.name}_{config.model_type}"
        if cache_key in self.clients:
            return self.clients[cache_key]

        if config.model_type == "openai_compatible":
            import openai

            client = openai.OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
            )
            self.clients[cache_key] = client
            return client

        elif config.model_type == "compassjudger_local":
            client = self._load_compassjudger(config.model_name)
            self.clients[cache_key] = client
            return client

        else:
            raise ValueError(f"不支持的模型类型: {config.model_type}")

    def _load_compassjudger(self, model_path: str):
        """加载CompassJudger本地模型"""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            device = getattr(self, "_compassjudger_device", "auto")
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype="auto",
                device_map=device,
            )
            logger.info(f"CompassJudger模型加载成功: {model_path}")
            return {"tokenizer": tokenizer, "model": model}
        except ImportError:
            logger.warning(
                "Transformers库未安装，CompassJudger本地模型不可用。"
                "请安装: pip install transformers torch"
            )
            return None
        except Exception as e:
            logger.warning(f"CompassJudger模型加载失败: {str(e)}")
            return None

    def evaluate_with_model(
        self,
        config: JudgeModelConfig,
        content: str,
        dimensions: List[str] = None,
    ) -> Dict:
        """使用指定模型评估论文"""
        if dimensions is None:
            dimensions = ["innovation", "research_depth", "structure", "method_experiment"]

        client = self._get_client(config)

        if config.model_type == "openai_compatible":
            return self._evaluate_openai_compatible(client, config, content, dimensions)
        elif config.model_type == "compassjudger_local":
            if client is None:
                return {"error": "CompassJudger模型不可用", "dimension_scores": {}}
            return self._evaluate_compassjudger(client, content, dimensions)
        else:
            raise ValueError(f"不支持的模型类型: {config.model_type}")

    def _evaluate_openai_compatible(
        self,
        client,
        config: JudgeModelConfig,
        content: str,
        dimensions: List[str],
    ) -> Dict:
        """使用OpenAI兼容API评估"""
        prompt = self.JUDGE_PROMPT_TEMPLATE.format(content=content[:15000])

        try:
            response = client.chat.completions.create(
                model=config.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位专业的毕业设计论文评审专家，请客观、公正地进行评审。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content
            result = self._parse_response(raw)
            result["model_name"] = config.name
            result["model_type"] = config.model_type
            return result

        except Exception as e:
            logger.error(f"模型{config.name}评估失败: {str(e)}")
            return {
                "error": str(e),
                "model_name": config.name,
                "dimension_scores": {},
                "overall_score": None,
            }

    def _evaluate_compassjudger(
        self, client: Dict, content: str, dimensions: List[str]
    ) -> Dict:
        """使用CompassJudger本地模型评估"""
        tokenizer = client["tokenizer"]
        model = client["model"]

        prompt = self.JUDGE_PROMPT_TEMPLATE.format(content=content[:12000])

        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

        generated_ids = model.generate(**model_inputs, max_new_tokens=2048)
        generated_ids = [
            output_ids[len(input_ids):]
            for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

        result = self._parse_response(response)
        result["model_name"] = "compassjudger"
        result["model_type"] = "compassjudger_local"
        return result

    def _parse_response(self, raw: str) -> Dict:
        """解析模型响应"""
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end != -1:
                try:
                    result = json.loads(raw[start:end])
                except json.JSONDecodeError:
                    result = {"dimension_scores": {}, "overall_score": None}
            else:
                result = {"dimension_scores": {}, "overall_score": None}

        if "dimension_scores" not in result and "institutional_scores" in result:
            dim_scores = {}
            for item in result["institutional_scores"]:
                dim_id = item.get("dimension_id", "")
                dim_scores[dim_id] = {
                    "score": item.get("score", 0),
                    "evidence": item.get("evidence", ""),
                    "reason": item.get("score_reason", ""),
                }
            result["dimension_scores"] = dim_scores

        return result

    def multi_judge_evaluate(
        self,
        content: str,
        dimensions: List[str] = None,
        consensus_method: str = "weighted_average",
        outlier_threshold: float = 15.0,
    ) -> Dict:
        """
        多模型共识评审

        Args:
            content: 论文内容
            dimensions: 评估维度
            consensus_method: 共识方法 (weighted_average/median/trimmed_mean)
            outlier_threshold: 异常值阈值（与中位数偏差超过此值的评分视为异常）

        Returns:
            共识评审结果
        """
        if dimensions is None:
            dimensions = ["innovation", "research_depth", "structure", "method_experiment"]

        enabled_configs = [c for c in self.configs if c.enabled]
        if not enabled_configs:
            logger.warning("没有可用的评审模型，使用默认配置")
            enabled_configs = self.configs[:1]

        individual_results = []
        for config in enabled_configs:
            logger.info(f"使用模型 {config.name} 进行评审...")
            try:
                result = self.evaluate_with_model(config, content, dimensions)
                individual_results.append(result)
            except Exception as e:
                logger.error(f"模型 {config.name} 评审失败: {str(e)}")
                continue

        if not individual_results:
            return {
                "error": "所有模型评审失败",
                "consensus_scores": {},
                "overall_consensus_score": None,
            }

        consensus = self._compute_consensus(
            individual_results,
            enabled_configs[: len(individual_results)],
            dimensions,
            consensus_method,
            outlier_threshold,
        )

        return consensus

    def _compute_consensus(
        self,
        results: List[Dict],
        configs: List[JudgeModelConfig],
        dimensions: List[str],
        method: str,
        outlier_threshold: float,
    ) -> Dict:
        """计算多模型共识"""
        dim_scores_collection = {dim: [] for dim in dimensions}
        overall_scores = []

        for i, result in enumerate(results):
            weight = configs[i].weight if i < len(configs) else 1.0
            model_name = result.get("model_name", f"model_{i}")

            dim_scores = result.get("dimension_scores", {})
            for dim in dimensions:
                if dim in dim_scores:
                    score = dim_scores[dim].get("score", dim_scores[dim]) if isinstance(dim_scores[dim], dict) else dim_scores[dim]
                    try:
                        score = float(score)
                    except (TypeError, ValueError):
                        continue
                    dim_scores_collection[dim].append({
                        "score": score,
                        "weight": weight,
                        "model": model_name,
                    })

            overall = result.get("overall_score")
            if overall is not None:
                try:
                    overall_scores.append({
                        "score": float(overall),
                        "weight": weight,
                        "model": model_name,
                    })
                except (TypeError, ValueError):
                    pass

        consensus_scores = {}
        for dim in dimensions:
            scores_list = dim_scores_collection.get(dim, [])
            if not scores_list:
                consensus_scores[dim] = {"score": None, "agreement": 0}
                continue

            consensus_scores[dim] = self._aggregate_scores(
                scores_list, method, outlier_threshold
            )

        overall_consensus = None
        if overall_scores:
            overall_result = self._aggregate_scores(
                overall_scores, method, outlier_threshold
            )
            overall_consensus = overall_result["score"]

        if overall_consensus is None and consensus_scores:
            valid_scores = [
                v["score"] for v in consensus_scores.values() if v.get("score") is not None
            ]
            if valid_scores:
                overall_consensus = round(sum(valid_scores) / len(valid_scores), 1)

        return {
            "consensus_scores": consensus_scores,
            "overall_consensus_score": overall_consensus,
            "individual_results": results,
            "consensus_method": method,
            "n_judges": len(results),
            "agreement_analysis": self._analyze_agreement(dim_scores_collection, dimensions),
        }

    def _aggregate_scores(
        self,
        scores_list: List[Dict],
        method: str,
        outlier_threshold: float,
    ) -> Dict:
        """聚合多个评分"""
        scores = [s["score"] for s in scores_list]
        weights = [s["weight"] for s in scores_list]
        models = [s["model"] for s in scores_list]

        if not scores:
            return {"score": None, "agreement": 0}

        if method == "weighted_average":
            filtered = self._remove_outliers(scores, weights, models, outlier_threshold)
            if filtered:
                f_scores, f_weights, f_models = filtered
                consensus = sum(
                    s * w for s, w in zip(f_scores, f_weights)
                ) / sum(f_weights)
            else:
                consensus = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

        elif method == "median":
            consensus = float(np.median(scores))

        elif method == "trimmed_mean":
            sorted_scores = sorted(scores)
            trim = max(1, len(sorted_scores) // 4)
            if len(sorted_scores) > trim * 2:
                trimmed = sorted_scores[trim:-trim]
            else:
                trimmed = sorted_scores
            consensus = sum(trimmed) / len(trimmed) if trimmed else sum(scores) / len(scores)

        else:
            consensus = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

        score_std = float(np.std(scores)) if len(scores) > 1 else 0.0

        return {
            "score": round(consensus, 1),
            "agreement": round(max(0, 100 - score_std * 5), 1),
            "std": round(score_std, 2),
            "individual_scores": [
                {"model": m, "score": s, "weight": w}
                for m, s, w in zip(models, scores, weights)
            ],
        }

    def _remove_outliers(
        self,
        scores: List[float],
        weights: List[float],
        models: List[str],
        threshold: float,
    ) -> Optional[Tuple]:
        """移除异常值评分"""
        if len(scores) <= 2:
            return None

        median = float(np.median(scores))
        filtered_scores = []
        filtered_weights = []
        filtered_models = []

        for s, w, m in zip(scores, weights, models):
            if abs(s - median) <= threshold:
                filtered_scores.append(s)
                filtered_weights.append(w)
                filtered_models.append(m)

        if len(filtered_scores) < 2:
            return None

        return filtered_scores, filtered_weights, filtered_models

    def _analyze_agreement(
        self,
        dim_scores_collection: Dict[str, List[Dict]],
        dimensions: List[str],
    ) -> Dict:
        """分析多模型评审一致性"""
        analysis = {}

        for dim in dimensions:
            scores_list = dim_scores_collection.get(dim, [])
            if len(scores_list) < 2:
                analysis[dim] = {
                    "agreement_level": "insufficient",
                    "max_disagreement": 0,
                }
                continue

            scores = [s["score"] for s in scores_list]
            max_diff = max(scores) - min(scores)
            std = float(np.std(scores))

            if std < 3:
                level = "high"
            elif std < 7:
                level = "moderate"
            else:
                level = "low"

            analysis[dim] = {
                "agreement_level": level,
                "max_disagreement": round(max_diff, 1),
                "std": round(std, 2),
            }

        return analysis


class CalibratedScorer:
    """校准评分器 - 消除LLM评审的系统性偏置"""

    def __init__(self):
        self.sensitivity = 0.85
        self.specificity = 0.75
        self.is_calibrated = False
        self.calibration_data = None

    def calibrate(
        self,
        calibration_set: List[Dict],
        judge: SpecialistJudge,
        threshold_excellent: float = 85.0,
        threshold_poor: float = 65.0,
    ) -> Dict:
        """
        校准评审模型

        Args:
            calibration_set: 校准集，每项包含 {"content": str, "human_score": float}
            judge: 评审模型
            threshold_excellent: 优秀阈值
            threshold_poor: 较差阈值

        Returns:
            校准结果
        """
        tp, fp, tn, fn = 0, 0, 0, 0

        for sample in calibration_set:
            human = sample["human_score"]
            try:
                result = judge.multi_judge_evaluate(sample["content"])
                predicted = result.get("overall_consensus_score", 75)
            except Exception:
                continue

            actually_good = human >= threshold_excellent
            predicted_good = predicted >= threshold_excellent
            actually_bad = human < threshold_poor
            predicted_bad = predicted < threshold_poor

            if actually_good and predicted_good:
                tp += 1
            elif not actually_good and predicted_good:
                fp += 1
            elif actually_bad and predicted_bad:
                tn += 1
            elif not actually_bad and predicted_bad:
                fn += 1

        self.sensitivity = tp / max(tp + fn, 1)
        self.specificity = tn / max(tn + fp, 1)
        self.is_calibrated = True
        self.calibration_data = {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "n_samples": len(calibration_set),
        }

        logger.info(
            f"校准完成: sensitivity={self.sensitivity:.3f}, specificity={self.specificity:.3f}"
        )

        return {
            "sensitivity": round(self.sensitivity, 4),
            "specificity": round(self.specificity, 4),
            "calibration_data": self.calibration_data,
            "is_reliable": (self.sensitivity + self.specificity) > 1.0,
        }

    def bias_corrected_score(self, raw_score: float) -> Dict:
        """
        偏置校正评分

        使用公式: θ = (p + q0 - 1) / (q0 + q1 - 1)
        其中 p = 原始比例, q0 = 特异度, q1 = 灵敏度
        """
        if not self.is_calibrated:
            return {
                "raw_score": raw_score,
                "corrected_score": raw_score,
                "confidence_interval": (raw_score - 5, raw_score + 5),
                "calibration_status": "not_calibrated",
            }

        if (self.sensitivity + self.specificity) <= 1.0:
            logger.warning("灵敏度+特异度<=1，校准不可靠，返回原始分数")
            return {
                "raw_score": raw_score,
                "corrected_score": raw_score,
                "confidence_interval": (raw_score - 8, raw_score + 8),
                "calibration_status": "unreliable",
            }

        p = raw_score / 100.0
        q0 = self.specificity
        q1 = self.sensitivity

        corrected_p = (p + q0 - 1) / (q0 + q1 - 1)
        corrected_score = max(0, min(100, corrected_p * 100))

        ci_margin = 1.96 * (corrected_p * (1 - corrected_p) / max(self.calibration_data.get("n_samples", 30), 1)) ** 0.5 * 100
        ci_lower = max(0, corrected_score - ci_margin)
        ci_upper = min(100, corrected_score + ci_margin)

        return {
            "raw_score": round(raw_score, 1),
            "corrected_score": round(corrected_score, 1),
            "adjustment": round(corrected_score - raw_score, 1),
            "confidence_interval": (round(ci_lower, 1), round(ci_upper, 1)),
            "calibration_status": "calibrated",
            "sensitivity": round(self.sensitivity, 4),
            "specificity": round(self.specificity, 4),
        }
