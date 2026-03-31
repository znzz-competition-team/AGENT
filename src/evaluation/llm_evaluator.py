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
        self.ability_matrix = None
        self._load_ability_matrix()
    
    def _load_ability_matrix(self):
        """加载能力矩阵"""
        import json
        import os
        ability_matrix_path = os.path.join(os.path.dirname(__file__), '..', '..', 'ability_matrix.json')
        if os.path.exists(ability_matrix_path):
            with open(ability_matrix_path, 'r', encoding='utf-8') as f:
                self.ability_matrix = json.load(f)
    
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
    
    def evaluate_submission(self, submission_content: str, stage_progress: float, student_info: Dict = None, custom_prompts: Dict = None, syllabus_analysis: Dict = None) -> Dict:
        """
        使用大模型评估提交内容
        
        Args:
            submission_content: 提交的内容
            stage_progress: 阶段进度 (0.0-1.0)
            student_info: 学生信息
            custom_prompts: 自定义提示词
            syllabus_analysis: 大纲分析结果
            
        Returns:
            评估结果字典
        """
        # 每次评估时都获取最新的配置
        self.ai_config = get_ai_config()
        self.client = self._initialize_client(self.ai_config)
        
        if not self.client:
            raise Exception("大模型客户端未初始化，请检查API配置")
        
        # 构建评估提示词
        prompt = self._build_evaluation_prompt(submission_content, stage_progress, student_info, syllabus_analysis)
        
        # 使用自定义提示词或默认提示词
        system_prompt = custom_prompts.get("system_prompt") if custom_prompts else "你是一位资深的教育评估专家，拥有10年以上的学生能力评估经验。请以专业、客观、严谨的态度对学生提交的内容进行全面评估。评估过程中需注意：\n1. 严格按照给定的评分标准和评估维度进行评估\n2. 评估结果需基于提交内容的实际表现，避免主观臆断\n3. 优势分析和改进建议需具体、可操作，具有实际指导意义\n4. 综合评分需反映学生的整体表现，与各维度评分保持一致\n5. 评估结果需以JSON格式返回，确保格式正确、内容完整"
        user_prompt = custom_prompts.get("user_prompt") if custom_prompts else prompt
        
        # 替换用户提示词中的占位符
        if student_info:
            student_info_str = json.dumps(student_info, ensure_ascii=False)
        else:
            student_info_str = "无"
        
        user_prompt = user_prompt.replace("{student_info}", student_info_str)
        user_prompt = user_prompt.replace("{submission_content}", submission_content)
        
        # 调用大模型
        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=self.ai_config["temperature"],
            max_tokens=self.ai_config["max_tokens"],
            response_format={"type": "json_object"}
        )
        
        # 解析响应
        raw_content = response.choices[0].message.content
        
        # 记录原始响应
        logger.info("=== 大模型原始响应 ===")
        logger.info(f"响应长度: {len(raw_content)}")
        logger.info(f"响应内容前500字符: {raw_content[:500]}")
        
        try:
            evaluation_result = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            logger.error(f"原始响应内容: {raw_content}")
            
            # 尝试修复常见的JSON格式问题
            try:
                # 尝试提取JSON部分
                start_idx = raw_content.find('{')
                end_idx = raw_content.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = raw_content[start_idx:end_idx]
                    logger.info(f"尝试解析提取的JSON: {json_str[:200]}...")
                    evaluation_result = json.loads(json_str)
                else:
                    raise Exception(f"无法从响应中提取JSON: {str(e)}")
            except Exception as e2:
                logger.error(f"JSON修复失败: {str(e2)}")
                raise Exception(f"解析大模型返回结果失败: {str(e2)}\n原始响应: {raw_content[:500]}")
        
        # 记录原始评估结果的类型和内容
        logger.info("=== 原始大模型返回结果 ===")
        logger.info(f"类型: {type(evaluation_result)}")
        logger.info(f"内容: {json.dumps(evaluation_result, ensure_ascii=False, indent=2)}")
        logger.info(f"dimension_scores类型: {type(evaluation_result.get('dimension_scores'))}")
        if 'dimension_scores' in evaluation_result:
            logger.info(f"dimension_scores内容: {evaluation_result['dimension_scores']}")
        
        normalized = self._normalize_evaluation_result(evaluation_result, stage_progress)
        
        # 记录标准化后的结果
        logger.info("=== 标准化后的评估结果 ===")
        logger.info(f"dimension_scores类型: {type(normalized.get('dimension_scores'))}")
        logger.info(f"dimension_scores内容: {normalized['dimension_scores']}")
        
        return normalized
    
    def _build_evaluation_prompt(self, submission_content: str, stage_progress: float, student_info: Dict = None, syllabus_analysis: Dict = None) -> str:
        """构建评估提示词"""
        
        # 阶段描述
        stage_description = self._get_stage_description(stage_progress)
        
        # 评分标准说明
        scoring_guidance = self._get_scoring_guidance(stage_progress)
        
        # 安全格式化
        student_info_str = json.dumps(student_info, ensure_ascii=False) if student_info else "无"
        stage_progress_str = str(round(stage_progress, 2))
        
        # 从大纲分析结果中提取能力点
        ability_points = []
        evaluation_criteria = []
        
        if syllabus_analysis:
            # 使用大纲分析结果
            ability_points = syllabus_analysis.get('ability_points', [])
            evaluation_criteria = syllabus_analysis.get('evaluation_criteria', [])
        elif self.ability_matrix:
            # 使用能力矩阵
            for syllabus_name, data in self.ability_matrix.items():
                ability_points.extend(data.get('ability_points', []))
        
        # 如果没有能力点，使用默认维度
        if not ability_points:
            ability_points = [
                {"name": "表述与表达", "description": "文字表达能力、逻辑清晰度、专业术语使用"},
                {"name": "建模知识", "description": "对建模方法的理解和应用能力"},
                {"name": "分析知识", "description": "数据分析能力和问题分析能力"},
                {"name": "设计与开发", "description": "系统设计和开发实现能力"},
                {"name": "模因分析", "description": "对技术原理和机制的理解能力"}
            ]
        
        # 构建能力点评估指南
        ability_guidelines = "# 课程大纲能力点\n\n"
        ability_guidelines += "以下是课程大纲中规定的能力点，必须对每一项进行详细评估：\n\n"
        for i, ability in enumerate(ability_points, 1):
            if isinstance(ability, dict):
                name = ability.get('name', '未知能力点')
                description = ability.get('description', '')
                level = ability.get('level', '')
                ability_guidelines += f"**{i}. {name}**\n"
                if description:
                    ability_guidelines += f"   - 要求: {description}\n"
                if level:
                    ability_guidelines += f"   - 掌握程度: {level}\n"
                ability_guidelines += "\n"
            else:
                ability_guidelines += f"**{i}. {ability}**\n\n"
        
        # 构建评价标准指南
        criteria_guidelines = ""
        if evaluation_criteria:
            criteria_guidelines = "# 课程评价标准\n\n"
            criteria_guidelines += "以下是课程大纲中规定的评价标准，评估时必须参考：\n\n"
            for i, criterion in enumerate(evaluation_criteria, 1):
                if isinstance(criterion, dict):
                    name = criterion.get('name', '未知评价项目')
                    weight = criterion.get('weight', '')
                    description = criterion.get('description', '')
                    standard = criterion.get('standard', '')
                    criteria_guidelines += f"**{i}. {name}**"
                    if weight:
                        criteria_guidelines += f" (权重: {weight})"
                    criteria_guidelines += "\n"
                    if description:
                        criteria_guidelines += f"   - 内容: {description}\n"
                    if standard:
                        criteria_guidelines += f"   - 标准: {standard}\n"
                    criteria_guidelines += "\n"
                else:
                    criteria_guidelines += f"**{i}. {criterion}**\n\n"
        
        prompt = f"""# 角色定位

你是一位经验丰富的大学任课教师，拥有10年以上的教学经验。你的职责是客观、公正地评价学生的作业，给出符合学生实际表现的分数。
你必须像真正的老师一样严格评分，不能因为学生努力就给予高分，也不能因为同情而放宽标准。

# 评估任务

请对以下学生提交的作业进行**详细、客观、严格**的评价。你需要：
1. 仔细阅读学生的提交内容
2. 对照课程大纲的要求，评估学生在各个能力点上的表现
3. 给出客观的分数，分数必须反映学生的真实水平
4. 详细说明评分理由，指出优势和劣势
5. 评估大纲任务的完成情况

# 重要原则（必须严格遵守）

1. **客观公正**：评分必须基于作业的实际质量，严禁主观臆断、过度宽容或讨好学生
2. **标准严格**：严格按照大学课程评分标准，大多数学生的分数应该在60-85分之间
3. **实事求是**：优势要具体指出，劣势也要明确指出，不得回避问题
4. **证据充分**：每个评分都必须有具体的证据支撑，引用作业中的具体内容
5. **评分分布**：不要让所有学生都得优或良，要根据实际表现给出合理的分数分布

# 评分标准（大学课程标准）

**优秀（90-100分）**：极少数学生能达到，作业质量远超要求，有创新性见解，内容深入全面
**良好（80-89分）**：少数学生能达到，作业质量较好，完全达到要求，内容充实
**中等（70-79分）**：大多数学生应得的分数，作业质量一般，基本达到要求，有提升空间
**及格（60-69分）**：作业质量较差，勉强达到要求，有明显不足
**不及格（<60分）**：作业质量很差，未达到要求，存在严重问题

# 学生信息

{student_info_str}

# 提交内容

{submission_content}

# 评估阶段

当前处于项目{stage_description}，进度值: {stage_progress_str}

{scoring_guidance}

{ability_guidelines}

{criteria_guidelines}

# 输出要求

请以JSON格式返回评估结果，结构如下：

```json
{{
    "overall_score": 75,
    "dimension_scores": [
        {{
            "dimension": "能力点名称（必须来自大纲能力点列表）",
            "score": 75,
            "confidence": 0.85,
            "evidence": ["作业中支持该评分的具体证据1", "作业中支持该评分的具体证据2"],
            "reasoning": "详细解释为什么给出这个分数（至少200字），必须引用作业中的具体内容，详细分析学生的表现，指出优点和不足"
        }}
    ],
    "strengths": [
        "具体优势1（必须引用作业中的具体证据，详细说明为什么这是优势）",
        "具体优势2（必须引用作业中的具体证据，详细说明为什么这是优势）",
        "具体优势3（必须引用作业中的具体证据，详细说明为什么这是优势）"
    ],
    "weaknesses": [
        "具体劣势1（必须指出具体问题，详细说明为什么这是劣势）",
        "具体劣势2（必须指出具体问题，详细说明为什么这是劣势）",
        "具体劣势3（必须指出具体问题，详细说明为什么这是劣势）"
    ],
    "task_completion": {{
        "completed_tasks": ["已完成的大纲任务1", "已完成的大纲任务2"],
        "incomplete_tasks": ["未完成的大纲任务1", "未完成的大纲任务2"],
        "completion_rate": 0.75,
        "completion_details": "详细说明大纲任务的完成情况，哪些完成了，哪些没完成，完成质量如何（至少150字）"
    }},
    "overall_evaluation": "总体评价（至少200字），综合分析学生的作业质量，给出客观的评价，说明为什么给出这个总分"
}}
```
# 特别提醒

1. **必须对大纲中的每个能力点进行评估**，不得遗漏
2. **每个评分必须有具体证据支撑**，引用作业中的具体内容
3. **必须客观公正**，像真正的老师一样严格评分
4. **必须指出劣势**，不得只说优势不说劣势
5. **评估内容必须详细**，每个能力点的reasoning至少200字
6. **分数分布要合理**，不要让所有学生都得高分
7. **不需要改进建议**，只需要客观评价
8. **必须评估大纲任务完成情况**，说明哪些完成了，哪些没完成
"""
        
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
            - 综合评分需基于实际表现，客观反映学生的当前水平
            """
        elif stage_progress < 0.66:
            return """
            评分标准（适中）：
            - 平衡考察进展和能力发展
            - 关注执行能力和团队协作
            - 对各维度要求均衡
            - 综合评分应客观公正，反映学生的真实水平
            """
        else:
            return """
            评分标准（严格）：
            - 重点关注成果质量和专业性
            - 对创新能力和深度要求较高
            - 关注综合能力的全面发展
            - 评分应严格按照专业标准，客观反映学生的实际表现
            """
    
    def _normalize_evaluation_result(self, result: Dict, stage_progress: float) -> Dict:
        """标准化评估结果"""
        # 确保所有必要字段存在
        # 直接使用大模型返回的0-100分
        raw_overall_score = float(result.get("overall_score", 0.0))
        normalized = {
            "overall_score": min(100.0, max(0.0, raw_overall_score)),
            "dimension_scores": result.get("dimension_scores", []),
            "ability_scores": result.get("ability_scores", []),
            "strengths": result.get("strengths", []),
            "weaknesses": result.get("weaknesses", result.get("areas_for_improvement", [])),
            "task_completion": result.get("task_completion", {
                "completed_tasks": [],
                "incomplete_tasks": [],
                "completion_rate": 0.0,
                "completion_details": ""
            }),
            "overall_evaluation": result.get("overall_evaluation", ""),
            # 兼容旧格式
            "areas_for_improvement": result.get("weaknesses", result.get("areas_for_improvement", [])),
            "recommendations": result.get("recommendations", [])
        }
        
        # 确保维度评分是列表格式，并且在0-100之间
        dimension_scores = normalized["dimension_scores"]
        normalized_dimension_scores = []
        
        if isinstance(dimension_scores, list):
            # 处理列表格式的维度评分
            for i, score_info in enumerate(dimension_scores):
                if isinstance(score_info, dict) and "score" in score_info:
                    # 新格式，包含dimension, score, confidence, evidence和reasoning
                    # 直接使用大模型返回的0-100分
                    raw_score = float(score_info.get("score", 0.0))
                    normalized_score = {
                        "dimension": score_info.get("dimension", "未知"),
                        "score": min(100.0, max(0.0, raw_score)),
                        "confidence": score_info.get("confidence", 0.8),
                        "evidence": score_info.get("evidence", []),
                        "reasoning": score_info.get("reasoning", "")
                    }
                    normalized_dimension_scores.append(normalized_score)
        elif isinstance(dimension_scores, dict):
            # 处理字典格式的维度评分，转换为列表格式
            for dimension_name, score_info in dimension_scores.items():
                if isinstance(score_info, dict) and "score" in score_info:
                    # 直接使用大模型返回的0-100分
                    raw_score = float(score_info.get("score", 0.0))
                    normalized_score = {
                        "dimension": dimension_name,
                        "score": min(100.0, max(0.0, raw_score)),
                        "confidence": score_info.get("confidence", 0.8),
                        "evidence": score_info.get("evidence", []),
                        "reasoning": score_info.get("reasoning", "")
                    }
                    normalized_dimension_scores.append(normalized_score)
                elif isinstance(score_info, (int, float)):
                    # 直接使用大模型返回的0-100分
                    raw_score = float(score_info)
                    normalized_score = {
                        "dimension": dimension_name,
                        "score": min(100.0, max(0.0, raw_score)),
                        "confidence": 0.8,
                        "evidence": [],
                        "reasoning": ""
                    }
                    normalized_dimension_scores.append(normalized_score)
        
        # 确保能力评分是列表格式，并且在0-100之间
        ability_scores = normalized["ability_scores"]
        normalized_ability_scores = []
        
        if isinstance(ability_scores, list):
            # 处理列表格式的能力评分
            for i, score_info in enumerate(ability_scores):
                if isinstance(score_info, dict) and "score" in score_info:
                    # 新格式，包含ability, score和reasoning
                    # 直接使用大模型返回的0-100分
                    raw_score = float(score_info.get("score", 0.0))
                    normalized_score = {
                        "ability": score_info.get("ability", "未知"),
                        "score": min(100.0, max(0.0, raw_score)),
                        "reasoning": score_info.get("reasoning", "")
                    }
                    normalized_ability_scores.append(normalized_score)
        
        # 更新normalized中的dimension_scores和ability_scores为统一的列表格式
        normalized["dimension_scores"] = normalized_dimension_scores
        normalized["ability_scores"] = normalized_ability_scores
        
        # 确保strengths、areas_for_improvement和recommendations是列表
        for field in ["strengths", "areas_for_improvement", "recommendations"]:
            if not isinstance(normalized[field], list):
                if normalized[field]:
                    normalized[field] = [str(normalized[field])]
                else:
                    normalized[field] = []
        
        return normalized
    
    def generate_report(self, prompt: str, max_tokens: int = 3000) -> str:
        """
        使用大模型生成报告
        
        Args:
            prompt: 报告生成提示词
            max_tokens: 最大生成token数
            
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
            max_tokens=max_tokens,
            response_format={"type": "text"}
        )
        
        # 返回生成的报告
        return response.choices[0].message.content




# 全局评估器实例
llm_evaluator = LLMEvaluator()