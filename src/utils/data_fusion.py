<<<<<<< HEAD
from typing import Dict, List, Optional, Tuple
=======
from typing import Dict, List, Optional, Tuple, Any
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
from models.schemas import DimensionScore, EvaluationResult, EvaluationDimension
import numpy as np

class DataFusionService:
    """
<<<<<<< HEAD
    数据融合服务，用于整合多个维度的评分并进行加权计算
    """
    
    # 默认权重配置
=======
    数据融合服务，用于整合多个维度的评分并进行加权计算。
    支持根据课程类型（如理论课、实践课）动态调整评价权重。
    """
    
    # 理论课权重配置 (侧重学术、思维、沟通)
    THEORY_WEIGHTS = {
        EvaluationDimension.ACADEMIC_PERFORMANCE: 0.20,
        EvaluationDimension.CRITICAL_THINKING: 0.20,
        EvaluationDimension.COMMUNICATION_SKILLS: 0.15,
        EvaluationDimension.PROBLEM_SOLVING: 0.10,
        EvaluationDimension.CREATIVITY: 0.10,
        EvaluationDimension.TECHNICAL_SKILLS: 0.05,
        EvaluationDimension.LEADERSHIP: 0.05,
        EvaluationDimension.TEAMWORK: 0.05,
        EvaluationDimension.TIME_MANAGEMENT: 0.05,
        EvaluationDimension.ADAPTABILITY: 0.05
    }

    # 实践课权重配置 (侧重技术、解决问题、团队协作)
    PRACTICE_WEIGHTS = {
        EvaluationDimension.TECHNICAL_SKILLS: 0.20,
        EvaluationDimension.PROBLEM_SOLVING: 0.20,
        EvaluationDimension.TEAMWORK: 0.15,
        EvaluationDimension.CREATIVITY: 0.10,
        EvaluationDimension.ADAPTABILITY: 0.10,
        EvaluationDimension.ACADEMIC_PERFORMANCE: 0.05,
        EvaluationDimension.COMMUNICATION_SKILLS: 0.05,
        EvaluationDimension.LEADERSHIP: 0.05,
        EvaluationDimension.TIME_MANAGEMENT: 0.05,
        EvaluationDimension.CRITICAL_THINKING: 0.05
    }

    # 默认/通用权重配置
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
    DEFAULT_WEIGHTS = {
        EvaluationDimension.ACADEMIC_PERFORMANCE: 0.15,
        EvaluationDimension.COMMUNICATION_SKILLS: 0.15,
        EvaluationDimension.LEADERSHIP: 0.1,
        EvaluationDimension.TEAMWORK: 0.1,
        EvaluationDimension.CREATIVITY: 0.1,
        EvaluationDimension.PROBLEM_SOLVING: 0.1,
        EvaluationDimension.TIME_MANAGEMENT: 0.05,
        EvaluationDimension.ADAPTABILITY: 0.05,
        EvaluationDimension.TECHNICAL_SKILLS: 0.1,
        EvaluationDimension.CRITICAL_THINKING: 0.1
    }
    
    # 评分等级和对应的描述
    SCORE_LEVELS = {
<<<<<<< HEAD
        (9.0, 10.0): {"level": "优秀", "description": "表现出色，远超预期"},
=======
        (9.0, 10.1): {"level": "优秀", "description": "表现出色，远超预期"}, # 上限改为10.1以包含满分10.0
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        (7.5, 9.0): {"level": "良好", "description": "表现良好，达到预期"},
        (6.0, 7.5): {"level": "中等", "description": "表现一般，基本达到要求"},
        (4.0, 6.0): {"level": "待改进", "description": "表现有待提高，需要努力"},
        (0.0, 4.0): {"level": "较差", "description": "表现较差，需要大幅改进"}
    }
    
<<<<<<< HEAD
    def __init__(self, weights: Optional[Dict[EvaluationDimension, float]] = None):
=======
    def __init__(self, custom_weights: Optional[Dict[EvaluationDimension, float]] = None):
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        """
        初始化数据融合服务
        
        Args:
<<<<<<< HEAD
            weights: 各维度的权重配置，如果为None则使用默认权重
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        # 验证权重总和是否为1
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.001:
            # 归一化权重
            self.weights = {k: v / total_weight for k, v in self.weights.items()}
    
    def calculate_weighted_score(self, dimension_scores: List[DimensionScore]) -> float:
        """
        计算加权平均分
        
        Args:
            dimension_scores: 各维度的评分列表
        
        Returns:
            float: 加权平均分
        """
=======
            custom_weights: 自定义各维度的权重配置。如果提供，将覆盖内置逻辑。
        """
        self._custom_weights = custom_weights
    
    def _get_weights(self, course_type: str = "理论课") -> Dict[EvaluationDimension, float]:
        """
        根据课程类型获取对应的权重配置，并确保权重总和为1
        """
        if self._custom_weights is not None:
            weights = self._custom_weights
        elif course_type == "实践课":
            weights = self.PRACTICE_WEIGHTS
        elif course_type == "理论课":
            weights = self.THEORY_WEIGHTS
        else:
            weights = self.DEFAULT_WEIGHTS

        # 验证权重总和是否为1，若不是则归一化
        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 0.001:
            weights = {k: v / total_weight for k, v in weights.items()}
            
        return weights

    def calculate_weighted_score(self, dimension_scores: List[DimensionScore], course_type: str = "理论课") -> float:
        """
        计算加权平均分
        """
        if not dimension_scores:
            return 0.0

        weights = self._get_weights(course_type)
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        total_score = 0.0
        total_weight = 0.0
        
        for score in dimension_scores:
<<<<<<< HEAD
            weight = self.weights.get(score.dimension, 0.1)  # 默认权重为0.1
=======
            weight = weights.get(score.dimension, 0.0) 
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
            total_score += score.score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return total_score / total_weight
    
<<<<<<< HEAD
    def calculate_confidence(self, dimension_scores: List[DimensionScore]) -> float:
        """
        计算整体评估的置信度
        
        Args:
            dimension_scores: 各维度的评分列表
        
        Returns:
            float: 整体置信度
=======
    def calculate_confidence(self, dimension_scores: List[DimensionScore], course_type: str = "理论课") -> float:
        """
        计算整体评估的置信度
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        """
        if not dimension_scores:
            return 0.0
        
<<<<<<< HEAD
        # 计算置信度的加权平均
=======
        weights = self._get_weights(course_type)
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        total_confidence = 0.0
        total_weight = 0.0
        
        for score in dimension_scores:
<<<<<<< HEAD
            weight = self.weights.get(score.dimension, 0.1)
=======
            weight = weights.get(score.dimension, 0.0)
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
            total_confidence += score.confidence * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return total_confidence / total_weight
    
    def get_score_level(self, score: float) -> Tuple[str, str]:
        """
        根据评分获取等级和描述
<<<<<<< HEAD
        
        Args:
            score: 评分
        
        Returns:
            Tuple[str, str]: 等级和描述
=======
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        """
        for (min_score, max_score), level_info in self.SCORE_LEVELS.items():
            if min_score <= score < max_score:
                return level_info["level"], level_info["description"]
<<<<<<< HEAD
        # 默认返回
        return "中等", "表现一般，基本达到要求"
    
    def generate_strengths(self, dimension_scores: List[DimensionScore], threshold: float = 7.5) -> List[str]:
        """
        生成优势列表
        
        Args:
            dimension_scores: 各维度的评分列表
            threshold: 优势阈值，默认7.5
        
        Returns:
            List[str]: 优势列表
        """
        strengths = []
        
        dimension_names = {
=======
        return "中等", "表现一般，基本达到要求"
    
    def _get_dimension_names(self) -> Dict[EvaluationDimension, str]:
        return {
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
            EvaluationDimension.ACADEMIC_PERFORMANCE: "学术表现",
            EvaluationDimension.COMMUNICATION_SKILLS: "沟通能力",
            EvaluationDimension.LEADERSHIP: "领导力",
            EvaluationDimension.TEAMWORK: "团队协作",
            EvaluationDimension.CREATIVITY: "创新能力",
            EvaluationDimension.PROBLEM_SOLVING: "问题解决",
            EvaluationDimension.TIME_MANAGEMENT: "时间管理",
            EvaluationDimension.ADAPTABILITY: "适应能力",
            EvaluationDimension.TECHNICAL_SKILLS: "技术能力",
            EvaluationDimension.CRITICAL_THINKING: "批判性思维"
        }
<<<<<<< HEAD
=======

    def generate_strengths(self, dimension_scores: List[DimensionScore], threshold: float = 7.5) -> List[str]:
        """生成优势列表"""
        strengths = []
        dimension_names = self._get_dimension_names()
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        
        for score in dimension_scores:
            if score.score >= threshold:
                dimension_name = dimension_names.get(score.dimension, score.dimension.value)
                strengths.append(f"{dimension_name}（评分：{score.score:.1f}）")
        
        return strengths
    
    def generate_areas_for_improvement(self, dimension_scores: List[DimensionScore], threshold: float = 6.0) -> List[str]:
<<<<<<< HEAD
        """
        生成待改进领域列表
        
        Args:
            dimension_scores: 各维度的评分列表
            threshold: 待改进阈值，默认6.0
        
        Returns:
            List[str]: 待改进领域列表
        """
        areas = []
        
        dimension_names = {
            EvaluationDimension.ACADEMIC_PERFORMANCE: "学术表现",
            EvaluationDimension.COMMUNICATION_SKILLS: "沟通能力",
            EvaluationDimension.LEADERSHIP: "领导力",
            EvaluationDimension.TEAMWORK: "团队协作",
            EvaluationDimension.CREATIVITY: "创新能力",
            EvaluationDimension.PROBLEM_SOLVING: "问题解决",
            EvaluationDimension.TIME_MANAGEMENT: "时间管理",
            EvaluationDimension.ADAPTABILITY: "适应能力",
            EvaluationDimension.TECHNICAL_SKILLS: "技术能力",
            EvaluationDimension.CRITICAL_THINKING: "批判性思维"
        }
=======
        """生成待改进领域列表"""
        areas = []
        dimension_names = self._get_dimension_names()
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        
        for score in dimension_scores:
            if score.score < threshold:
                dimension_name = dimension_names.get(score.dimension, score.dimension.value)
                areas.append(f"{dimension_name}（评分：{score.score:.1f}）")
        
        return areas
    
    def generate_recommendations(self, dimension_scores: List[DimensionScore]) -> List[str]:
<<<<<<< HEAD
        """
        生成改进建议
        
        Args:
            dimension_scores: 各维度的评分列表
        
        Returns:
            List[str]: 改进建议列表
        """
=======
        """生成改进建议"""
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        recommendations = []
        
        # 按评分排序，找出最低的几个维度
        sorted_scores = sorted(dimension_scores, key=lambda x: x.score)
        lowest_dimensions = sorted_scores[:3]  # 取最低的3个维度
        
<<<<<<< HEAD
        # 为每个低分维度生成建议
=======
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        for score in lowest_dimensions:
            if score.score < 6.0:
                recommendation = self._generate_specific_recommendation(score.dimension)
                if recommendation:
                    recommendations.append(recommendation)
        
<<<<<<< HEAD
        # 通用建议
=======
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        if not recommendations:
            recommendations.append("继续保持当前的良好表现，尝试在各维度上进一步提升")
        
        return recommendations
    
    def _generate_specific_recommendation(self, dimension: EvaluationDimension) -> str:
<<<<<<< HEAD
        """
        为特定维度生成改进建议
        
        Args:
            dimension: 评估维度
        
        Returns:
            str: 改进建议
        """
=======
        """为特定维度生成改进建议"""
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        recommendations = {
            EvaluationDimension.ACADEMIC_PERFORMANCE: "加强学习方法的改进，增加阅读量，积极参与课堂讨论，提高学术写作能力",
            EvaluationDimension.COMMUNICATION_SKILLS: "多参与演讲和小组讨论，练习表达能力，学习有效沟通技巧",
            EvaluationDimension.LEADERSHIP: "主动承担团队责任，学习领导力理论，实践团队管理技能",
            EvaluationDimension.TEAMWORK: "积极参与团队活动，学会倾听他人意见，培养合作精神",
            EvaluationDimension.CREATIVITY: "尝试新的思维方式，参与创意活动，培养创新意识",
            EvaluationDimension.PROBLEM_SOLVING: "多做实践练习，学习系统分析问题的方法，培养逻辑思维",
            EvaluationDimension.TIME_MANAGEMENT: "制定合理的时间计划，学习优先级管理，避免拖延",
            EvaluationDimension.ADAPTABILITY: "主动尝试新事物，学习应对变化的策略，培养灵活性",
            EvaluationDimension.TECHNICAL_SKILLS: "加强编程练习，学习新技术，参与项目实践",
            EvaluationDimension.CRITICAL_THINKING: "多阅读不同观点的材料，练习逻辑分析，培养独立思考能力"
        }
<<<<<<< HEAD
        
        return recommendations.get(dimension, "继续努力提升该维度的能力")
    
    def fuse_data(self, dimension_scores: List[DimensionScore]) -> Dict[str, any]:
=======
        return recommendations.get(dimension, "继续努力提升该维度的能力")
    
    def fuse_data(self, dimension_scores: List[DimensionScore], course_type: str = "理论课") -> Dict[str, Any]:
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        """
        融合数据，生成综合评估结果
        
        Args:
            dimension_scores: 各维度的评分列表
<<<<<<< HEAD
        
        Returns:
            Dict[str, any]: 综合评估结果
        """
        # 计算加权平均分
        overall_score = self.calculate_weighted_score(dimension_scores)
        
        # 计算整体置信度
        confidence = self.calculate_confidence(dimension_scores)
        
        # 获取评分等级和描述
        level, level_description = self.get_score_level(overall_score)
        
        # 生成优势列表
        strengths = self.generate_strengths(dimension_scores)
        
        # 生成待改进领域列表
        areas_for_improvement = self.generate_areas_for_improvement(dimension_scores)
        
        # 生成改进建议
        recommendations = self.generate_recommendations(dimension_scores)
        
        # 构建综合评估结果
=======
            course_type: 课程类型（用于动态权重计算）
        """
        # 传入课程类型计算分数和置信度
        overall_score = self.calculate_weighted_score(dimension_scores, course_type)
        confidence = self.calculate_confidence(dimension_scores, course_type)
        
        level, level_description = self.get_score_level(overall_score)
        
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        result = {
            "overall_score": overall_score,
            "confidence": confidence,
            "level": level,
            "level_description": level_description,
<<<<<<< HEAD
            "strengths": strengths,
            "areas_for_improvement": areas_for_improvement,
            "recommendations": recommendations
=======
            "strengths": self.generate_strengths(dimension_scores),
            "areas_for_improvement": self.generate_areas_for_improvement(dimension_scores),
            "recommendations": self.generate_recommendations(dimension_scores),
            "course_type_applied": course_type # 将应用的权重类型一并返回，方便前端展示
>>>>>>> 13733ce0a70eef683f89b9c58cf4bdf335da8e17
        }
        
        return result