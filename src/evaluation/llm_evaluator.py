"""
大模型评估服务 - 使用AI模型进行评估
"""

from typing import Dict, List, Tuple
import openai
from src.config import get_ai_config
import json
import logging

logger = logging.getLogger(__name__)

class LLMEvaluator:
    """大模型评估器"""
    
    def __init__(self):
        # 初始化时不获取配置，每次评估时动态获取
        self.client = None
    
    def _initialize_client(self, ai_config):
        """初始化大模型客户端"""
        try:
            # 添加调试信息
            logger.info("AI配置: " + str(ai_config))
            logger.info("API密钥: " + str(ai_config.get('api_key')))
            
            if not ai_config["api_key"]:
                raise Exception("API密钥未设置，请在配置文件中设置API密钥")
            
            client = openai.OpenAI(
                api_key=ai_config["api_key"],
                base_url=ai_config["base_url"]
            )
            return client
        except Exception as e:
            logger.error("无法初始化大模型客户端: " + str(e))
            raise
    
    def evaluate_submission(self, submission_content: str, stage_progress: float, student_info: Dict = None) -> Dict:
        """
        使用大模型评估提交内容
        
        Args:
            submission_content: 提交的内容
            stage_progress: 阶段进度 (0.0-1.0)
            student_info: 学生信息
            
        Returns:
            评估结果字典
        """
        # 每次评估时都获取最新的配置
        self.ai_config = get_ai_config()
        self.client = self._initialize_client(self.ai_config)
        
        if not self.client:
            raise Exception("大模型客户端未初始化，请检查API配置")
        
        # 构建评估提示词
        prompt = self._build_evaluation_prompt(submission_content, stage_progress, student_info)
        
        # 调用大模型
        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": "你是一个专业的学生能力评估专家，需要对学生的提交内容进行全面、客观的评估。"},
                {"role": "user", "content": prompt}
            ],
            temperature=self.ai_config["temperature"],
            max_tokens=self.ai_config["max_tokens"],
            response_format={"type": "json_object"}
        )
        
        # 解析响应
        evaluation_result = json.loads(response.choices[0].message.content)
        
        # 记录原始评估结果的类型和内容
        print("=== 原始大模型返回结果 ===")
        print(f"类型: {type(evaluation_result)}")
        print(f"内容: {json.dumps(evaluation_result, ensure_ascii=False, indent=2)}")
        print(f"dimension_scores类型: {type(evaluation_result.get('dimension_scores'))}")
        if 'dimension_scores' in evaluation_result:
            print(f"dimension_scores内容: {evaluation_result['dimension_scores']}")
        
        normalized = self._normalize_evaluation_result(evaluation_result, stage_progress)
        
        # 记录标准化后的结果
        print("=== 标准化后的评估结果 ===")
        print(f"dimension_scores类型: {type(normalized.get('dimension_scores'))}")
        print(f"dimension_scores内容: {normalized['dimension_scores']}")
        
        return normalized
    
    def _build_evaluation_prompt(self, submission_content: str, stage_progress: float, student_info: Dict = None) -> str:
        """构建评估提示词"""
        
        # 阶段描述
        stage_description = self._get_stage_description(stage_progress)
        
        # 评分标准说明
        scoring_guidance = self._get_scoring_guidance(stage_progress)
        
        # 安全格式化
        student_info_str = json.dumps(student_info, ensure_ascii=False) if student_info else "无"
        stage_progress_str = str(round(stage_progress, 2))
        
        prompt = ("# 评估任务\n" +
                "请对以下学生提交的内容进行全面评估。\n\n" +
                "# 学生信息\n" +
                student_info_str + "\n\n" +
                "# 提交内容\n" +
                submission_content + "\n\n" +
                "# 评估阶段\n" +
                "当前处于项目" + stage_description + "，进度值: " + stage_progress_str + "\n\n" +
                "# 评分标准\n" +
                scoring_guidance + "\n\n" +
                "# 评估维度\n" +
                "请从以下10个维度进行评估：\n" +
                "1. 学术表现 (Academic Performance)\n" +
                "2. 沟通能力 (Communication Skills)\n" +
                "3. 领导力 (Leadership)\n" +
                "4. 团队协作 (Teamwork)\n" +
                "5. 创新能力 (Creativity)\n" +
                "6. 问题解决 (Problem Solving)\n" +
                "7. 时间管理 (Time Management)\n" +
                "8. 适应能力 (Adaptability)\n" +
                "9. 技术能力 (Technical Skills)\n" +
                "10. 批判性思维 (Critical Thinking)\n\n" +
                "# 评估要求\n" +
                "1. 每个维度评分范围：0-100分\n" +
                "2. 提供详细的优势分析\n" +
                "3. 提供具体的改进建议\n" +
                "4. 给出综合评分和整体建议\n" +
                "5. 评估结果必须以JSON格式返回，结构如下：\n\n" +
                '{"overall_score": 85,\n' +
                '    "dimension_scores": [\n' +
                '        {"dimension": "学术表现", "score": 80, "reasoning": "详细的评估理由"},\n' +
                '        {"dimension": "沟通能力", "score": 75, "reasoning": "详细的评估理由"},\n' +
                '        {"dimension": "领导力", "score": 70, "reasoning": "详细的评估理由"}\n' +
                '    ],\n' +
                '    "strengths": ["学习态度积极", "基础知识扎实"],\n' +
                '    "areas_for_improvement": ["创新能力需要加强", "团队协作能力有待提高"],\n' +
                '    "recommendations": ["多参与团队项目", "培养创新思维"]\n' +
                '}')
        
        return prompt
    
    def _get_stage_description(self, stage_progress: float) -> str:
        """根据进度获取阶段描述"""
        if stage_progress < 0.33:
            return "初期阶段"
        elif stage_progress < 0.66:
            return "中期阶段"
        else:
            return "最终阶段"
    
    def _get_scoring_guidance(self, stage_progress: float) -> str:
        """根据阶段进度获取评分指导"""
        if stage_progress < 0.33:
            return """
            评分标准（宽松）：
            - 重点关注学习态度和基础知识掌握
            - 鼓励为主，关注潜力和进步空间
            - 对创新能力和专业深度要求较低
            - 综合评分可适当偏高
            """
        elif stage_progress < 0.66:
            return """
            评分标准（适中）：
            - 平衡考察进展和能力发展
            - 关注执行能力和团队协作
            - 对各维度要求均衡
            - 综合评分应客观公正
            """
        else:
            return """
            评分标准（严格）：
            - 重点关注成果质量和专业性
            - 对创新能力和深度要求较高
            - 关注综合能力的全面发展
            - 评分应严格按照专业标准
            """
    
    def _normalize_evaluation_result(self, result: Dict, stage_progress: float) -> Dict:
        """标准化评估结果"""
        # 确保所有必要字段存在
        # 将0-100分转换为0-10分
        raw_overall_score = float(result.get("overall_score", 0.0))
        normalized = {
            "overall_score": min(10.0, max(0.0, raw_overall_score / 10.0)),
            "dimension_scores": result.get("dimension_scores", []),
            "strengths": result.get("strengths", []),
            "areas_for_improvement": result.get("areas_for_improvement", []),
            "recommendations": result.get("recommendations", []),
            "stage_progress": stage_progress
        }
        
        # 确保维度评分是列表格式，并且在0-10之间
        dimension_scores = normalized["dimension_scores"]
        normalized_dimension_scores = []
        
        if isinstance(dimension_scores, list):
            # 处理列表格式的维度评分
            for i, score_info in enumerate(dimension_scores):
                if isinstance(score_info, dict) and "score" in score_info:
                    # 新格式，包含dimension, score和reasoning
                    # 将0-100分转换为0-10分
                    raw_score = float(score_info.get("score", 0.0))
                    normalized_score = {
                        "dimension": score_info.get("dimension", "未知"),
                        "score": min(10.0, max(0.0, raw_score / 10.0)),
                        "reasoning": score_info.get("reasoning", "")
                    }
                    normalized_dimension_scores.append(normalized_score)
        elif isinstance(dimension_scores, dict):
            # 处理字典格式的维度评分，转换为列表格式
            for dimension_name, score_info in dimension_scores.items():
                if isinstance(score_info, dict) and "score" in score_info:
                    # 将0-100分转换为0-10分
                    raw_score = float(score_info.get("score", 0.0))
                    normalized_score = {
                        "dimension": dimension_name,
                        "score": min(10.0, max(0.0, raw_score / 10.0)),
                        "reasoning": score_info.get("reasoning", "")
                    }
                    normalized_dimension_scores.append(normalized_score)
                elif isinstance(score_info, (int, float)):
                    # 将0-100分转换为0-10分
                    raw_score = float(score_info)
                    normalized_score = {
                        "dimension": dimension_name,
                        "score": min(10.0, max(0.0, raw_score / 10.0)),
                        "reasoning": ""
                    }
                    normalized_dimension_scores.append(normalized_score)
        
        # 更新normalized中的dimension_scores为统一的列表格式
        normalized["dimension_scores"] = normalized_dimension_scores
        
        # 确保strengths、areas_for_improvement和recommendations是列表
        for field in ["strengths", "areas_for_improvement", "recommendations"]:
            if not isinstance(normalized[field], list):
                if normalized[field]:
                    normalized[field] = [str(normalized[field])]
                else:
                    normalized[field] = []
        
        return normalized
    
    def generate_report(self, prompt: str) -> str:
        """
        使用大模型生成报告
        
        Args:
            prompt: 报告生成提示词
            
        Returns:
            生成的报告内容
        """
        # 每次评估时都获取最新的配置
        self.ai_config = get_ai_config()
        self.client = self._initialize_client(self.ai_config)
        
        if not self.client:
            raise Exception("大模型客户端未初始化，请检查API配置")
        
        # 调用大模型
        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": "你是一位专业的教育评估专家，擅长分析学生在时间线上的能力进步。"},
                {"role": "user", "content": prompt}
            ],
            temperature=self.ai_config["temperature"],
            max_tokens=3000,  # 增加最大 tokens 以生成详细报告
            response_format={"type": "text"}
        )
        
        # 返回生成的报告
        return response.choices[0].message.content




# 全局评估器实例
llm_evaluator = LLMEvaluator()