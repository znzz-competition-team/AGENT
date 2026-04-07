"""
规则引擎评分模块 - 实现确定性评价
将评价指标转化为可计算的规则，确保相同输入产生相同输出
"""

from typing import Dict, List, Optional, Tuple
import re
import json
from dataclasses import dataclass
from enum import Enum


class RuleType(Enum):
    KEYWORD_MATCH = "keyword_match"
    STRUCTURE_CHECK = "structure_check"
    COUNT_STATISTICS = "count_statistics"
    CONTENT_COMPLETENESS = "content_completeness"
    LENGTH_CHECK = "length_check"
    PATTERN_MATCH = "pattern_match"


@dataclass
class ScoringRule:
    rule_id: str
    rule_type: RuleType
    description: str
    weight: float
    parameters: Dict
    grade_thresholds: Dict[str, float]


@dataclass
class RuleResult:
    rule_id: str
    matched: bool
    score: float
    evidence: List[str]
    details: str


class RuleEngine:
    """规则引擎 - 确定性评分系统"""
    
    GRADE_SCORES = {
        "excellent": (90, 100),
        "good": (80, 89),
        "medium": (70, 79),
        "pass": (60, 69),
        "fail": (0, 59)
    }
    
    def __init__(self):
        self.rules: List[ScoringRule] = []
    
    def load_rules_from_indicators(self, indicators: Dict) -> None:
        """
        从评价指标加载规则
        
        Args:
            indicators: 提炼后的评价指标字典
        """
        self.rules = []
        
        indicator_list = indicators.get("indicators", [])
        for idx, indicator in enumerate(indicator_list):
            indicator_id = indicator.get("id", f"IND_{idx:02d}")
            indicator_name = indicator.get("name", f"指标{idx+1}")
            weight = indicator.get("weight", 10)
            
            rules = self._generate_rules_for_indicator(
                indicator_id, indicator_name, indicator, weight
            )
            self.rules.extend(rules)
    
    def _generate_rules_for_indicator(
        self, 
        indicator_id: str, 
        indicator_name: str, 
        indicator: Dict, 
        weight: float
    ) -> List[ScoringRule]:
        """
        为单个指标生成评分规则
        
        根据指标名称和描述自动生成规则
        """
        rules = []
        name_lower = indicator_name.lower()
        description = indicator.get("description", "").lower()
        
        if any(kw in name_lower for kw in ["算法", "algorithm", "设计"]):
            rules.extend(self._generate_algorithm_rules(indicator_id, indicator, weight))
        
        elif any(kw in name_lower for kw in ["代码", "code", "实现", "编程"]):
            rules.extend(self._generate_code_rules(indicator_id, indicator, weight))
        
        elif any(kw in name_lower for kw in ["仿真", "simulation", "模拟"]):
            rules.extend(self._generate_simulation_rules(indicator_id, indicator, weight))
        
        elif any(kw in name_lower for kw in ["实验", "experiment", "测试", "test"]):
            rules.extend(self._generate_experiment_rules(indicator_id, indicator, weight))
        
        elif any(kw in name_lower for kw in ["文档", "论文", "撰写", "写作"]):
            rules.extend(self._generate_document_rules(indicator_id, indicator, weight))
        
        elif any(kw in name_lower for kw in ["模型", "model", "建模"]):
            rules.extend(self._generate_model_rules(indicator_id, indicator, weight))
        
        elif any(kw in name_lower for kw in ["分析", "analysis", "数据处理"]):
            rules.extend(self._generate_analysis_rules(indicator_id, indicator, weight))
        
        elif any(kw in name_lower for kw in ["创新", "innovation", "新颖"]):
            rules.extend(self._generate_innovation_rules(indicator_id, indicator, weight))
        
        else:
            rules.extend(self._generate_generic_rules(indicator_id, indicator, weight))
        
        return rules
    
    def _generate_algorithm_rules(self, indicator_id: str, indicator: Dict, weight: float) -> List[ScoringRule]:
        """生成算法相关规则"""
        rules = []
        
        algorithm_keywords = [
            "算法", "algorithm", "深度学习", "机器学习", "神经网络", 
            "CNN", "RNN", "LSTM", "Transformer", "GAN", "优化",
            "模型", "训练", "预测", "分类", "回归", "聚类"
        ]
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R01",
            rule_type=RuleType.KEYWORD_MATCH,
            description="算法关键词覆盖度",
            weight=weight * 0.3,
            parameters={
                "keywords": algorithm_keywords,
                "min_matches": 3,
                "excellent_threshold": 0.7,
                "good_threshold": 0.5,
                "medium_threshold": 0.3,
                "pass_threshold": 0.1
            },
            grade_thresholds={
                "excellent": 0.7,
                "good": 0.5,
                "medium": 0.3,
                "pass": 0.1
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R02",
            rule_type=RuleType.STRUCTURE_CHECK,
            description="算法设计章节完整性",
            weight=weight * 0.3,
            parameters={
                "required_sections": [
                    "算法原理", "算法设计", "算法流程", "算法实现",
                    "模型结构", "网络结构", "算法步骤"
                ],
                "min_sections": 2
            },
            grade_thresholds={
                "excellent": 0.8,
                "good": 0.6,
                "medium": 0.4,
                "pass": 0.2
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R03",
            rule_type=RuleType.PATTERN_MATCH,
            description="算法公式和流程图",
            weight=weight * 0.4,
            parameters={
                "patterns": [
                    r"公式\s*\d+",
                    r"图\s*\d+.*流程",
                    r"图\s*\d+.*结构",
                    r"图\s*\d+.*框架",
                    r"Algorithm\s*\d+",
                    r"算法\s*\d+"
                ],
                "min_matches": 2
            },
            grade_thresholds={
                "excellent": 0.8,
                "good": 0.6,
                "medium": 0.4,
                "pass": 0.2
            }
        ))
        
        return rules
    
    def _generate_code_rules(self, indicator_id: str, indicator: Dict, weight: float) -> List[ScoringRule]:
        """生成代码相关规则"""
        rules = []
        
        code_keywords = [
            "代码", "code", "程序", "program", "函数", "function",
            "类", "class", "模块", "module", "接口", "interface",
            "API", "库", "library", "框架", "framework"
        ]
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R01",
            rule_type=RuleType.KEYWORD_MATCH,
            description="代码实现关键词",
            weight=weight * 0.3,
            parameters={
                "keywords": code_keywords,
                "min_matches": 2
            },
            grade_thresholds={
                "excellent": 0.7,
                "good": 0.5,
                "medium": 0.3,
                "pass": 0.1
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R02",
            rule_type=RuleType.PATTERN_MATCH,
            description="代码块和实现细节",
            weight=weight * 0.4,
            parameters={
                "patterns": [
                    r"```[\s\S]*?```",
                    r"def\s+\w+\s*\(",
                    r"class\s+\w+",
                    r"import\s+\w+",
                    r"from\s+\w+\s+import"
                ],
                "min_matches": 3
            },
            grade_thresholds={
                "excellent": 0.7,
                "good": 0.5,
                "medium": 0.3,
                "pass": 0.1
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R03",
            rule_type=RuleType.STRUCTURE_CHECK,
            description="实现章节完整性",
            weight=weight * 0.3,
            parameters={
                "required_sections": [
                    "系统设计", "系统实现", "代码实现", "程序设计",
                    "功能实现", "模块设计", "详细设计"
                ],
                "min_sections": 1
            },
            grade_thresholds={
                "excellent": 0.8,
                "good": 0.6,
                "medium": 0.4,
                "pass": 0.2
            }
        ))
        
        return rules
    
    def _generate_simulation_rules(self, indicator_id: str, indicator: Dict, weight: float) -> List[ScoringRule]:
        """生成仿真相关规则"""
        rules = []
        
        sim_keywords = [
            "仿真", "simulation", "模拟", "ANSYS", "MATLAB", "Simulink",
            "有限元", "FEM", "CFD", "数值模拟", "边界条件", "网格"
        ]
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R01",
            rule_type=RuleType.KEYWORD_MATCH,
            description="仿真关键词覆盖",
            weight=weight * 0.4,
            parameters={
                "keywords": sim_keywords,
                "min_matches": 3
            },
            grade_thresholds={
                "excellent": 0.7,
                "good": 0.5,
                "medium": 0.3,
                "pass": 0.1
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R02",
            rule_type=RuleType.STRUCTURE_CHECK,
            description="仿真分析章节",
            weight=weight * 0.3,
            parameters={
                "required_sections": [
                    "仿真模型", "仿真设置", "边界条件", "仿真结果",
                    "参数设置", "网格划分", "仿真分析"
                ],
                "min_sections": 2
            },
            grade_thresholds={
                "excellent": 0.8,
                "good": 0.6,
                "medium": 0.4,
                "pass": 0.2
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R03",
            rule_type=RuleType.COUNT_STATISTICS,
            description="仿真图表数量",
            weight=weight * 0.3,
            parameters={
                "pattern": r"图\s*\d+",
                "min_count": 3,
                "excellent_count": 8,
                "good_count": 5
            },
            grade_thresholds={
                "excellent": 8,
                "good": 5,
                "medium": 3,
                "pass": 1
            }
        ))
        
        return rules
    
    def _generate_experiment_rules(self, indicator_id: str, indicator: Dict, weight: float) -> List[ScoringRule]:
        """生成实验/测试相关规则"""
        rules = []
        
        exp_keywords = [
            "实验", "experiment", "测试", "test", "验证", "verification",
            "数据集", "dataset", "样本", "sample", "准确率", "accuracy",
            "精确率", "precision", "召回率", "recall", "F1"
        ]
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R01",
            rule_type=RuleType.KEYWORD_MATCH,
            description="实验测试关键词",
            weight=weight * 0.3,
            parameters={
                "keywords": exp_keywords,
                "min_matches": 3
            },
            grade_thresholds={
                "excellent": 0.7,
                "good": 0.5,
                "medium": 0.3,
                "pass": 0.1
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R02",
            rule_type=RuleType.STRUCTURE_CHECK,
            description="实验章节完整性",
            weight=weight * 0.4,
            parameters={
                "required_sections": [
                    "实验设计", "实验设置", "实验方法", "实验结果",
                    "结果分析", "性能评估", "对比实验"
                ],
                "min_sections": 2
            },
            grade_thresholds={
                "excellent": 0.8,
                "good": 0.6,
                "medium": 0.4,
                "pass": 0.2
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R03",
            rule_type=RuleType.PATTERN_MATCH,
            description="数据表格和结果展示",
            weight=weight * 0.3,
            parameters={
                "patterns": [
                    r"表\s*\d+",
                    r"准确率[：:]\s*\d+",
                    r"精确率[：:]\s*\d+",
                    r"\d+\.?\d*\s*%",
                    r"对比|比较"
                ],
                "min_matches": 2
            },
            grade_thresholds={
                "excellent": 0.7,
                "good": 0.5,
                "medium": 0.3,
                "pass": 0.1
            }
        ))
        
        return rules
    
    def _generate_document_rules(self, indicator_id: str, indicator: Dict, weight: float) -> List[ScoringRule]:
        """生成文档/论文相关规则"""
        rules = []
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R01",
            rule_type=RuleType.STRUCTURE_CHECK,
            description="论文结构完整性",
            weight=weight * 0.4,
            parameters={
                "required_sections": [
                    "摘要", "引言", "绪论", "背景", "相关工作",
                    "方法", "设计", "实现", "实验", "结果",
                    "讨论", "结论", "总结", "参考文献", "致谢"
                ],
                "min_sections": 5
            },
            grade_thresholds={
                "excellent": 0.8,
                "good": 0.6,
                "medium": 0.4,
                "pass": 0.3
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R02",
            rule_type=RuleType.LENGTH_CHECK,
            description="论文篇幅",
            weight=weight * 0.3,
            parameters={
                "min_length": 5000,
                "excellent_length": 20000,
                "good_length": 15000,
                "medium_length": 10000
            },
            grade_thresholds={
                "excellent": 20000,
                "good": 15000,
                "medium": 10000,
                "pass": 5000
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R03",
            rule_type=RuleType.COUNT_STATISTICS,
            description="图表数量",
            weight=weight * 0.15,
            parameters={
                "pattern": r"图\s*\d+|表\s*\d+",
                "min_count": 5,
                "excellent_count": 15,
                "good_count": 10
            },
            grade_thresholds={
                "excellent": 15,
                "good": 10,
                "medium": 5,
                "pass": 2
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R04",
            rule_type=RuleType.COUNT_STATISTICS,
            description="参考文献数量",
            weight=weight * 0.15,
            parameters={
                "pattern": r"\[\d+\]|\（\d+\）",
                "min_count": 5,
                "excellent_count": 20,
                "good_count": 10
            },
            grade_thresholds={
                "excellent": 20,
                "good": 10,
                "medium": 5,
                "pass": 3
            }
        ))
        
        return rules
    
    def _generate_model_rules(self, indicator_id: str, indicator: Dict, weight: float) -> List[ScoringRule]:
        """生成模型相关规则"""
        rules = []
        
        model_keywords = [
            "模型", "model", "结构", "structure", "参数", "parameter",
            "网络", "network", "层", "layer", "输入", "input", "输出", "output"
        ]
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R01",
            rule_type=RuleType.KEYWORD_MATCH,
            description="模型关键词",
            weight=weight * 0.4,
            parameters={
                "keywords": model_keywords,
                "min_matches": 3
            },
            grade_thresholds={
                "excellent": 0.7,
                "good": 0.5,
                "medium": 0.3,
                "pass": 0.1
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R02",
            rule_type=RuleType.PATTERN_MATCH,
            description="模型结构图和参数说明",
            weight=weight * 0.3,
            parameters={
                "patterns": [
                    r"图\s*\d+.*结构",
                    r"图\s*\d+.*模型",
                    r"参数[量个数]",
                    r"层[数结构]",
                    r"输入输出"
                ],
                "min_matches": 2
            },
            grade_thresholds={
                "excellent": 0.7,
                "good": 0.5,
                "medium": 0.3,
                "pass": 0.1
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R03",
            rule_type=RuleType.STRUCTURE_CHECK,
            description="模型设计章节",
            weight=weight * 0.3,
            parameters={
                "required_sections": [
                    "模型设计", "模型结构", "网络结构", "模型构建",
                    "模型训练", "参数设置", "模型优化"
                ],
                "min_sections": 2
            },
            grade_thresholds={
                "excellent": 0.8,
                "good": 0.6,
                "medium": 0.4,
                "pass": 0.2
            }
        ))
        
        return rules
    
    def _generate_analysis_rules(self, indicator_id: str, indicator: Dict, weight: float) -> List[ScoringRule]:
        """生成分析相关规则"""
        rules = []
        
        analysis_keywords = [
            "分析", "analysis", "结果", "result", "数据", "data",
            "统计", "statistics", "对比", "comparison", "趋势", "trend"
        ]
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R01",
            rule_type=RuleType.KEYWORD_MATCH,
            description="分析关键词",
            weight=weight * 0.4,
            parameters={
                "keywords": analysis_keywords,
                "min_matches": 3
            },
            grade_thresholds={
                "excellent": 0.7,
                "good": 0.5,
                "medium": 0.3,
                "pass": 0.1
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R02",
            rule_type=RuleType.STRUCTURE_CHECK,
            description="分析章节完整性",
            weight=weight * 0.3,
            parameters={
                "required_sections": [
                    "结果分析", "数据分析", "性能分析", "对比分析",
                    "讨论", "分析讨论", "实验分析"
                ],
                "min_sections": 1
            },
            grade_thresholds={
                "excellent": 0.8,
                "good": 0.6,
                "medium": 0.4,
                "pass": 0.2
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R03",
            rule_type=RuleType.PATTERN_MATCH,
            description="数据展示和分析图表",
            weight=weight * 0.3,
            parameters={
                "patterns": [
                    r"图\s*\d+.*结果",
                    r"图\s*\d+.*分析",
                    r"图\s*\d+.*对比",
                    r"表\s*\d+.*结果",
                    r"表\s*\d+.*对比"
                ],
                "min_matches": 2
            },
            grade_thresholds={
                "excellent": 0.7,
                "good": 0.5,
                "medium": 0.3,
                "pass": 0.1
            }
        ))
        
        return rules
    
    def _generate_innovation_rules(self, indicator_id: str, indicator: Dict, weight: float) -> List[ScoringRule]:
        """生成创新相关规则"""
        rules = []
        
        innovation_keywords = [
            "创新", "innovation", "新颖", "novel", "改进", "improve",
            "提出", "propose", "首次", "first", "原创", "original"
        ]
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R01",
            rule_type=RuleType.KEYWORD_MATCH,
            description="创新关键词",
            weight=weight * 0.5,
            parameters={
                "keywords": innovation_keywords,
                "min_matches": 2
            },
            grade_thresholds={
                "excellent": 0.6,
                "good": 0.4,
                "medium": 0.2,
                "pass": 0.1
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R02",
            rule_type=RuleType.STRUCTURE_CHECK,
            description="创新点阐述",
            weight=weight * 0.5,
            parameters={
                "required_sections": [
                    "创新点", "主要贡献", "研究贡献", "创新性",
                    "本文贡献", "主要创新"
                ],
                "min_sections": 1
            },
            grade_thresholds={
                "excellent": 0.8,
                "good": 0.6,
                "medium": 0.4,
                "pass": 0.2
            }
        ))
        
        return rules
    
    def _generate_generic_rules(self, indicator_id: str, indicator: Dict, weight: float) -> List[ScoringRule]:
        """生成通用规则"""
        rules = []
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R01",
            rule_type=RuleType.CONTENT_COMPLETENESS,
            description="内容完整性",
            weight=weight * 0.5,
            parameters={
                "min_paragraphs": 3,
                "min_sentences": 10
            },
            grade_thresholds={
                "excellent": 0.8,
                "good": 0.6,
                "medium": 0.4,
                "pass": 0.2
            }
        ))
        
        rules.append(ScoringRule(
            rule_id=f"{indicator_id}_R02",
            rule_type=RuleType.LENGTH_CHECK,
            description="内容篇幅",
            weight=weight * 0.5,
            parameters={
                "min_length": 500,
                "excellent_length": 2000,
                "good_length": 1000,
                "medium_length": 500
            },
            grade_thresholds={
                "excellent": 2000,
                "good": 1000,
                "medium": 500,
                "pass": 200
            }
        ))
        
        return rules
    
    def evaluate(self, content: str) -> Dict:
        """
        执行规则引擎评分
        
        Args:
            content: 待评价的内容
            
        Returns:
            评分结果字典
        """
        if not self.rules:
            return {
                "overall_score": 0,
                "grade_level": "无法评价",
                "dimension_scores": [],
                "error": "未加载评价规则"
            }
        
        total_weight = sum(rule.weight for rule in self.rules)
        weighted_score = 0
        rule_results = []
        
        for rule in self.rules:
            result = self._evaluate_single_rule(rule, content)
            rule_results.append(result)
            weighted_score += result.score * rule.weight
        
        overall_score = weighted_score / total_weight if total_weight > 0 else 0
        grade_level = self._get_grade_level(overall_score)
        
        dimension_scores = self._aggregate_rule_results(rule_results)
        
        return {
            "overall_score": round(overall_score, 1),
            "grade_level": grade_level,
            "dimension_scores": dimension_scores,
            "rule_results": [
                {
                    "rule_id": r.rule_id,
                    "score": rr.score,
                    "grade_level": self._get_grade_level(rr.score),
                    "evidence": rr.evidence[:3],
                    "details": rr.details
                }
                for r, rr in zip(self.rules, rule_results)
            ]
        }
    
    def _evaluate_single_rule(self, rule: ScoringRule, content: str) -> RuleResult:
        """评估单条规则"""
        if rule.rule_type == RuleType.KEYWORD_MATCH:
            return self._eval_keyword_match(rule, content)
        elif rule.rule_type == RuleType.STRUCTURE_CHECK:
            return self._eval_structure_check(rule, content)
        elif rule.rule_type == RuleType.COUNT_STATISTICS:
            return self._eval_count_statistics(rule, content)
        elif rule.rule_type == RuleType.CONTENT_COMPLETENESS:
            return self._eval_content_completeness(rule, content)
        elif rule.rule_type == RuleType.LENGTH_CHECK:
            return self._eval_length_check(rule, content)
        elif rule.rule_type == RuleType.PATTERN_MATCH:
            return self._eval_pattern_match(rule, content)
        else:
            return RuleResult(
                rule_id=rule.rule_id,
                matched=False,
                score=0,
                evidence=[],
                details="未知规则类型"
            )
    
    def _eval_keyword_match(self, rule: ScoringRule, content: str) -> RuleResult:
        """关键词匹配评估"""
        keywords = rule.parameters.get("keywords", [])
        content_lower = content.lower()
        
        matched_keywords = []
        for kw in keywords:
            if kw.lower() in content_lower:
                matched_keywords.append(kw)
        
        match_ratio = len(matched_keywords) / len(keywords) if keywords else 0
        
        thresholds = rule.grade_thresholds
        if match_ratio >= thresholds.get("excellent", 0.7):
            score = 95
        elif match_ratio >= thresholds.get("good", 0.5):
            score = 85
        elif match_ratio >= thresholds.get("medium", 0.3):
            score = 75
        elif match_ratio >= thresholds.get("pass", 0.1):
            score = 65
        else:
            score = 50
        
        return RuleResult(
            rule_id=rule.rule_id,
            matched=len(matched_keywords) > 0,
            score=score,
            evidence=matched_keywords[:5],
            details=f"匹配关键词 {len(matched_keywords)}/{len(keywords)} 个，覆盖率 {match_ratio:.1%}"
        )
    
    def _eval_structure_check(self, rule: ScoringRule, content: str) -> RuleResult:
        """结构检查评估"""
        required_sections = rule.parameters.get("required_sections", [])
        min_sections = rule.parameters.get("min_sections", 1)
        
        found_sections = []
        for section in required_sections:
            if section in content:
                found_sections.append(section)
        
        section_ratio = len(found_sections) / len(required_sections) if required_sections else 0
        
        thresholds = rule.grade_thresholds
        if section_ratio >= thresholds.get("excellent", 0.8):
            score = 95
        elif section_ratio >= thresholds.get("good", 0.6):
            score = 85
        elif section_ratio >= thresholds.get("medium", 0.4):
            score = 75
        elif section_ratio >= thresholds.get("pass", 0.2):
            score = 65
        else:
            score = 50
        
        return RuleResult(
            rule_id=rule.rule_id,
            matched=len(found_sections) >= min_sections,
            score=score,
            evidence=found_sections,
            details=f"找到章节 {len(found_sections)}/{len(required_sections)} 个"
        )
    
    def _eval_count_statistics(self, rule: ScoringRule, content: str) -> RuleResult:
        """数量统计评估"""
        pattern = rule.parameters.get("pattern", r"图\s*\d+")
        
        matches = re.findall(pattern, content)
        count = len(matches)
        
        thresholds = rule.grade_thresholds
        if count >= thresholds.get("excellent", 10):
            score = 95
        elif count >= thresholds.get("good", 6):
            score = 85
        elif count >= thresholds.get("medium", 3):
            score = 75
        elif count >= thresholds.get("pass", 1):
            score = 65
        else:
            score = 40
        
        return RuleResult(
            rule_id=rule.rule_id,
            matched=count > 0,
            score=score,
            evidence=matches[:5],
            details=f"找到 {count} 处匹配"
        )
    
    def _eval_content_completeness(self, rule: ScoringRule, content: str) -> RuleResult:
        """内容完整性评估"""
        min_paragraphs = rule.parameters.get("min_paragraphs", 3)
        min_sentences = rule.parameters.get("min_sentences", 10)
        
        paragraphs = [p for p in content.split("\n\n") if p.strip()]
        sentences = re.split(r"[。！？.!?]", content)
        sentences = [s for s in sentences if s.strip()]
        
        para_score = min(len(paragraphs) / min_paragraphs, 1.0) if min_paragraphs > 0 else 1.0
        sent_score = min(len(sentences) / min_sentences, 1.0) if min_sentences > 0 else 1.0
        
        completeness = (para_score + sent_score) / 2
        
        thresholds = rule.grade_thresholds
        if completeness >= thresholds.get("excellent", 0.8):
            score = 95
        elif completeness >= thresholds.get("good", 0.6):
            score = 85
        elif completeness >= thresholds.get("medium", 0.4):
            score = 75
        elif completeness >= thresholds.get("pass", 0.2):
            score = 65
        else:
            score = 40
        
        return RuleResult(
            rule_id=rule.rule_id,
            matched=completeness > 0.5,
            score=score,
            evidence=[f"段落数: {len(paragraphs)}", f"句子数: {len(sentences)}"],
            details=f"完整性: {completeness:.1%}"
        )
    
    def _eval_length_check(self, rule: ScoringRule, content: str) -> RuleResult:
        """篇幅检查评估"""
        length = len(content)
        
        thresholds = rule.grade_thresholds
        if length >= thresholds.get("excellent", 20000):
            score = 95
        elif length >= thresholds.get("good", 15000):
            score = 85
        elif length >= thresholds.get("medium", 10000):
            score = 75
        elif length >= thresholds.get("pass", 5000):
            score = 65
        else:
            score = 40
        
        return RuleResult(
            rule_id=rule.rule_id,
            matched=length >= rule.parameters.get("min_length", 5000),
            score=score,
            evidence=[f"总字数: {length}"],
            details=f"内容长度: {length} 字符"
        )
    
    def _eval_pattern_match(self, rule: ScoringRule, content: str) -> RuleResult:
        """模式匹配评估"""
        patterns = rule.parameters.get("patterns", [])
        min_matches = rule.parameters.get("min_matches", 1)
        
        all_matches = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            all_matches.extend(matches)
        
        unique_matches = list(set(all_matches))
        match_ratio = len(unique_matches) / len(patterns) if patterns else 0
        
        thresholds = rule.grade_thresholds
        if match_ratio >= thresholds.get("excellent", 0.7):
            score = 95
        elif match_ratio >= thresholds.get("good", 0.5):
            score = 85
        elif match_ratio >= thresholds.get("medium", 0.3):
            score = 75
        elif match_ratio >= thresholds.get("pass", 0.1):
            score = 65
        else:
            score = 40
        
        return RuleResult(
            rule_id=rule.rule_id,
            matched=len(unique_matches) >= min_matches,
            score=score,
            evidence=unique_matches[:5],
            details=f"模式匹配 {len(unique_matches)}/{len(patterns)} 个"
        )
    
    def _get_grade_level(self, score: float) -> str:
        """根据分数获取等级"""
        if score >= 90:
            return "优秀"
        elif score >= 80:
            return "良好"
        elif score >= 70:
            return "中等"
        elif score >= 60:
            return "及格"
        else:
            return "不及格"
    
    def _aggregate_rule_results(self, rule_results: List[RuleResult]) -> List[Dict]:
        """聚合规则结果为维度评分"""
        indicator_scores = {}
        
        for rule, result in zip(self.rules, rule_results):
            indicator_id = rule.rule_id.rsplit("_R", 1)[0]
            
            if indicator_id not in indicator_scores:
                indicator_scores[indicator_id] = {
                    "scores": [],
                    "weights": [],
                    "evidence": []
                }
            
            indicator_scores[indicator_id]["scores"].append(result.score)
            indicator_scores[indicator_id]["weights"].append(rule.weight)
            indicator_scores[indicator_id]["evidence"].extend(result.evidence)
        
        dimension_scores = []
        for indicator_id, data in indicator_scores.items():
            total_weight = sum(data["weights"])
            weighted_score = sum(s * w for s, w in zip(data["scores"], data["weights"])) / total_weight if total_weight > 0 else 0
            
            dimension_scores.append({
                "indicator_id": indicator_id,
                "score": round(weighted_score, 1),
                "grade_level": self._get_grade_level(weighted_score),
                "evidence": data["evidence"][:5]
            })
        
        return dimension_scores


rule_engine = RuleEngine()
