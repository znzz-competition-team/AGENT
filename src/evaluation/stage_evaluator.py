"""
阶段评估系统 - 根据工作阶段调整评估标准
"""

from typing import Dict, List, Tuple
from enum import Enum


class WorkStage(Enum):
    """工作阶段枚举"""
    INITIAL = "initial"  # 初期阶段
    MIDDLE = "middle"    # 中期阶段
    FINAL = "final"      # 最终阶段


class StageEvaluator:
    """阶段评估器 - 根据工作阶段调整评估标准"""
    
    def __init__(self):
        self.stage_prompts = self._initialize_stage_prompts()
        self.scoring_adjustments = self._initialize_scoring_adjustments()
    
    def _initialize_stage_prompts(self) -> Dict[WorkStage, Dict[str, str]]:
        """初始化各阶段的评估提示词"""
        
        return {
            WorkStage.INITIAL: {
                "overall_guidance": """
                当前处于项目初期阶段，评估标准应相对宽松，重点考察：
                - 学习态度和积极性
                - 基础知识的掌握程度
                - 对项目目标的理解
                - 初步的规划能力
                
                评分标准：主要关注进步空间和潜力，而不是完美程度。
                """,
                "strength_focus": "学习热情、基础扎实、理解能力",
                "improvement_focus": "需要加强规划能力、提升细节关注度",
                "recommendation_template": "建议在后续阶段重点关注{area}，逐步提升{skill}"
            },
            
            WorkStage.MIDDLE: {
                "overall_guidance": """
                当前处于项目中期阶段，评估标准适中，重点考察：
                - 项目进展和执行力
                - 团队协作能力
                - 问题解决能力
                - 时间管理能力
                
                评分标准：平衡进步和成果，关注持续改进。
                """,
                "strength_focus": "执行力强、团队协作好、问题解决能力",
                "improvement_focus": "需要加强创新思维、提升效率",
                "recommendation_template": "建议在后续工作中加强{area}，优化{skill}"
            },
            
            WorkStage.FINAL: {
                "overall_guidance": """
                当前处于项目最终阶段，评估标准相对严格，重点考察：
                - 最终成果质量
                - 创新性和独特性
                - 综合能力体现
                - 成果的完整性和专业性
                
                评分标准：以专业标准要求，关注成果的完整性和质量。
                """,
                "strength_focus": "成果质量高、专业性强、创新突出",
                "improvement_focus": "需要提升综合能力、加强专业深度",
                "recommendation_template": "建议在未来的项目中继续提升{area}，深化{skill}"
            }
        }
    
    def _initialize_scoring_adjustments(self) -> Dict[WorkStage, Dict[str, float]]:
        """初始化各阶段的评分调整系数"""
        
        return {
            WorkStage.INITIAL: {
                "base_score_multiplier": 1.2,  # 初期评分宽松
                "leniency_bonus": 1.0,        # 宽容度奖励
                "strictness_penalty": 0.8     # 严格度惩罚（较低）
            },
            WorkStage.MIDDLE: {
                "base_score_multiplier": 1.0,  # 中期评分适中
                "leniency_bonus": 0.9,
                "strictness_penalty": 1.0
            },
            WorkStage.FINAL: {
                "base_score_multiplier": 0.9,  # 最终评分严格
                "leniency_bonus": 0.8,
                "strictness_penalty": 1.2
            }
        }
    
    def get_stage_prompt(self, stage: str, prompt_type: str) -> str:
        """获取指定阶段的提示词"""
        try:
            work_stage = WorkStage(stage)
            return self.stage_prompts[work_stage].get(prompt_type, "")
        except ValueError:
            # 如果阶段无效，使用中期标准
            return self.stage_prompts[WorkStage.MIDDLE].get(prompt_type, "")
    
    def adjust_scores_by_stage(self, stage: str, base_scores: Dict[str, float]) -> Dict[str, float]:
        """根据阶段调整评分"""
        try:
            work_stage = WorkStage(stage)
            adjustments = self.scoring_adjustments[work_stage]
            
            adjusted_scores = {}
            for dimension, score in base_scores.items():
                # 应用基础调整系数
                adjusted_score = score * adjustments["base_score_multiplier"]
                
                # 根据维度特性进一步调整
                if dimension in ["创新能力", "批判性思维", "技术能力"]:
                    # 这些维度在后期要求更高
                    if work_stage == WorkStage.FINAL:
                        adjusted_score *= 0.95  # 最终阶段更严格
                    elif work_stage == WorkStage.INITIAL:
                        adjusted_score *= 1.05  # 初期阶段更宽容
                
                elif dimension in ["学习态度", "基础掌握", "适应性"]:
                    # 这些维度在初期更重要
                    if work_stage == WorkStage.INITIAL:
                        adjusted_score *= 1.1   # 初期阶段更重视
                
                # 确保分数在合理范围内
                adjusted_score = max(0, min(10, adjusted_score))
                adjusted_scores[dimension] = round(adjusted_score, 1)
            
            return adjusted_scores
            
        except ValueError:
            # 如果阶段无效，返回原分数
            return base_scores
    
    def generate_stage_specific_feedback(self, stage: str, base_feedback: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """生成阶段特定的反馈"""
        try:
            work_stage = WorkStage(stage)
            
            stage_feedback = base_feedback.copy()
            
            # 根据阶段调整反馈语气和重点
            if work_stage == WorkStage.INITIAL:
                # 初期阶段：鼓励为主，关注潜力
                stage_feedback["strengths"] = [
                    f"在项目初期表现出{s}" for s in base_feedback.get("strengths", [])
                ]
                stage_feedback["areas_for_improvement"] = [
                    f"建议在后续阶段重点关注{i}" for i in base_feedback.get("areas_for_improvement", [])
                ]
                
            elif work_stage == WorkStage.FINAL:
                # 最终阶段：专业评价，关注成果
                stage_feedback["strengths"] = [
                    f"最终成果在{s}方面表现突出" for s in base_feedback.get("strengths", [])
                ]
                stage_feedback["areas_for_improvement"] = [
                    f"在{i}方面仍有提升空间" for i in base_feedback.get("areas_for_improvement", [])
                ]
            
            return stage_feedback
            
        except ValueError:
            return base_feedback
    
    def get_stage_description(self, stage: str) -> str:
        """获取阶段描述"""
        stage_descriptions = {
            "initial": "初期阶段 - 重点关注学习态度和基础掌握",
            "middle": "中期阶段 - 平衡考察进展和协作能力", 
            "final": "最终阶段 - 严格评估成果质量和专业性"
        }
        return stage_descriptions.get(stage, "标准评估模式")


# 全局评估器实例
stage_evaluator = StageEvaluator()