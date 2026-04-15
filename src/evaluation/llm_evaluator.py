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
    
    def evaluate_with_deterministic_standards(
        self,
        submission_content: str,
        project_type: str = None,
        student_info: Dict = None,
        syllabus_analysis: Dict = None,
        guidance_content: str = None
    ) -> Dict:
        """
        使用确定性评价标准进行评估
        
        Args:
            submission_content: 提交内容
            project_type: 项目类型（algorithm/simulation/physical/traditional_mechanical/mixed）
            student_info: 学生信息
            syllabus_analysis: 大纲分析结果
            guidance_content: 评价指导文件内容
            
        Returns:
            评估结果字典
        """
        from src.evaluation.evaluation_standards import (
            ProjectType, 
            detect_project_type, 
            get_evaluation_standards,
            build_deterministic_evaluation_prompt,
            get_grade_level
        )
        
        self.ai_config = get_ai_config()
        self.client = self._initialize_client(self.ai_config)
        
        if not self.client:
            raise Exception("大模型客户端未初始化，请检查API配置")
        
        title = student_info.get("title", "") if student_info else ""
        
        if project_type:
            try:
                detected_type = ProjectType(project_type)
            except ValueError:
                detected_type = detect_project_type(title, submission_content)
        else:
            detected_type = detect_project_type(title, submission_content)
        
        logger.info(f"检测到项目类型: {detected_type.value}")
        
        prompt = build_deterministic_evaluation_prompt(
            submission_content,
            detected_type,
            student_info,
            guidance_content
        )
        
        system_prompt = """你是一位资深的教育评估专家，专门负责毕业设计评价工作。
你的职责是严格按照给定的评价标准，客观、公正地评价学生的毕业设计。

重要规则：
1. **严格按标准评分**：必须严格按照提示词中给出的评价标准进行评分
2. **一致性原则**：相同质量的作品必须得到相近的分数
3. **证据支撑**：每个评分必须有学生提交内容中的具体证据支撑
4. **等级对应**：根据学生表现确定等级，然后给出对应分数区间内的具体分数
5. **排除项处理**：对于不在评价范围内的内容，不得扣分

请以专业、客观、严谨的态度进行评价，确保评价结果的一致性和可靠性。"""
        
        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=self.ai_config.get("max_tokens", 8000),
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        logger.info("=== 确定性评价原始响应 ===")
        logger.info(f"响应长度: {len(raw_content)}")
        
        try:
            evaluation_result = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            start_idx = raw_content.find('{')
            end_idx = raw_content.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = raw_content[start_idx:end_idx]
                evaluation_result = json.loads(json_str)
            else:
                raise Exception(f"解析大模型返回结果失败: {str(e)}")
        
        evaluation_result["project_type"] = detected_type.value
        
        if "overall_score" in evaluation_result:
            evaluation_result["grade_level"] = get_grade_level(evaluation_result["overall_score"])
        
        return evaluation_result
    
    def extract_guidance_content(self, file_content: str, file_name: str = "") -> Dict:
        """
        使用大模型提炼评价指导文件的内容
        
        Args:
            file_content: 文件内容
            file_name: 文件名
            
        Returns:
            提炼后的指导内容字典
        """
        self.ai_config = get_ai_config()
        self.client = self._initialize_client(self.ai_config)
        
        if not self.client:
            raise Exception("大模型客户端未初始化，请检查API配置")
        
        prompt = f"""请分析以下毕业设计评价指导文件，完成两个任务：

## 任务一：提取原始评价指标
从文件中完整提取所有评价指标，包括：
- 指标编号（如1.2、3.1等）
- 指标名称
- 对应的毕业要求指标点
- 指标描述
- 权重或分值

## 任务二：生成扩展评价指标
基于提取的原始指标，结合毕业设计评价的实际需要，生成更详细的评价细则，包括：
- 每个指标的具体评价要点（3-5个）
- 每个评价要点的评分标准（优秀/良好/中等/及格/不及格）
- 评价方式（指导教师评分/评阅教师评分/答辩评分等）

## 任务三：生成评价表格模板
生成一个可用于实际评分的评价表格结构，包含：
- 表格标题
- 表头（指标编号、指标名称、满分、得分、评价等级）
- 每行对应一个评价指标

请以JSON格式返回分析结果，结构如下：
{{
    "original_indicators": [
        {{
            "indicator_id": "指标编号（如1.2）",
            "name": "指标名称",
            "graduation_requirement": "对应毕业要求指标点",
            "description": "指标描述",
            "weight": 权重数值,
            "max_score": 满分值
        }}
    ],
    "indicators": [
        {{
            "indicator_id": "指标编号",
            "name": "指标名称",
            "weight": 权重,
            "max_score": 满分,
            "description": "指标描述",
            "evaluation_points": [
                {{
                    "point_name": "评价要点名称",
                    "weight": 要点权重,
                    "grade_criteria": {{
                        "excellent": "优秀标准（90-100分）",
                        "good": "良好标准（80-89分）",
                        "medium": "中等标准（70-79分）",
                        "pass": "及格标准（60-69分）",
                        "fail": "不及格标准（0-59分）"
                    }}
                }}
            ],
            "evaluation_method": "评价方式（指导教师评分/评阅教师评分/答辩评分）",
            "grading_criteria": "总体评分标准"
        }}
    ],
    "evaluation_table": {{
        "title": "毕业设计（论文）评价表",
        "columns": ["序号", "指标编号", "指标名称", "满分", "得分", "评价等级", "评价人"],
        "rows": [
            {{
                "序号": 1,
                "指标编号": "1.2",
                "指标名称": "文献分析",
                "满分": 100,
                "评价方式": "指导教师评分"
            }}
        ]
    }},
    "grading_levels": {{
        "excellent": {{"min": 90, "max": 100, "description": "优秀标准描述"}},
        "good": {{"min": 80, "max": 89, "description": "良好标准描述"}},
        "medium": {{"min": 70, "max": 79, "description": "中等标准描述"}},
        "pass": {{"min": 60, "max": 69, "description": "及格标准描述"}},
        "fail": {{"min": 0, "max": 59, "description": "不及格标准描述"}}
    }},
    "evaluation_flow": {{
        "steps": [
            {{"step": 1, "name": "指导教师评分", "weight": 0.4, "description": "指导教师根据学生平时表现和论文质量评分"}},
            {{"step": 2, "name": "评阅教师评分", "weight": 0.3, "description": "评阅教师独立评阅论文质量"}},
            {{"step": 3, "name": "答辩评分", "weight": 0.3, "description": "答辩委员会根据答辩表现评分"}}
        ],
        "final_score_formula": "总评成绩 = 指导教师评分×40% + 评阅教师评分×30% + 答辩评分×30%"
    }},
    "key_requirements": ["关键要求1", "关键要求2"],
    "summary": "整体内容总结（200字以内）"
}}

文件内容如下：
{file_content}
"""
        
        system_prompt = """你是一位资深的教育评估专家，擅长分析和提取教育评价相关的关键信息。
你的任务是从给定的毕业设计评价指导文件中：
1. 完整提取原始评价指标，不遗漏任何内容
2. 基于原始指标生成详细的评价细则，便于实际操作
3. 生成标准化的评价表格模板

请确保：
- 原始指标提取完整准确，保留文件中的所有信息
- 扩展指标具有可操作性，评价要点具体明确
- 评分标准客观公正，等级划分清晰
- 评价表格格式规范，便于实际使用"""
        
        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=8000,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        try:
            extracted_content = json.loads(raw_content)
            extracted_content["source_file"] = file_name
            
            if "original_indicators" in extracted_content and "indicators" not in extracted_content:
                extracted_content["indicators"] = extracted_content["original_indicators"]
            
            for indicator in extracted_content.get("indicators", []):
                if "weight" not in indicator or indicator["weight"] is None:
                    indicator["weight"] = 10
                if "max_score" not in indicator or indicator["max_score"] is None:
                    indicator["max_score"] = 100
            
            return extracted_content
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            start_idx = raw_content.find('{')
            end_idx = raw_content.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = raw_content[start_idx:end_idx]
                extracted_content = json.loads(json_str)
                extracted_content["source_file"] = file_name
                return extracted_content
            else:
                raise Exception(f"解析指导文件提取结果失败: {str(e)}")
    
    def generate_evaluation_standards(self, file_content: str, file_name: str, project_type: str = "mixed") -> Dict:
        """
        使用大模型生成项目评价指标
        
        Args:
            file_content: 指导文件内容
            file_name: 文件名
            project_type: 项目类型
            
        Returns:
            生成的标准字典
        """
        self.ai_config = get_ai_config()
        self.client = self._initialize_client(self.ai_config)
        
        if not self.client:
            raise Exception("大模型客户端未初始化，请检查API配置")
        
        project_type_names = {
            "algorithm": "算法类",
            "simulation": "仿真类",
            "physical": "实物类",
            "traditional_mechanical": "传统机械类",
            "mixed": "混合类"
        }
        
        project_type_descriptions = {
            "algorithm": "算法类项目主要涉及算法设计、模型开发、数据分析等，通常无实物模型和实验验证，重点评估算法原理、代码实现、性能优化等方面。",
            "simulation": "仿真类项目主要涉及数值模拟、虚拟实验等，通常无实物模型，重点评估仿真建模、参数设置、结果分析等方面。",
            "physical": "实物类项目主要涉及硬件制作、样机开发等，重点评估设计制作、调试测试、性能验证等方面。",
            "traditional_mechanical": "传统机械类项目主要涉及机械结构设计、机构分析等，重点评估结构设计、力学分析、工程制图等方面。",
            "mixed": "混合类项目综合多种类型特点，需要根据具体内容灵活评估。"
        }
        
        type_name = project_type_names.get(project_type, "混合类")
        type_desc = project_type_descriptions.get(project_type, "")
        
        prompt = f"""请根据以下原始评价指标文件，为{type_name}项目生成非常详细的衍生评价指标体系。

## 项目类型说明
- 类型名称：{type_name}
- 类型描述：{type_desc}

## 原始评价指标文件内容：
{file_content}

## 核心任务要求

### 【任务一：完整保留原始指标】
**这是最重要的任务！** 必须从原始文件中完整提取所有评价指标，包括：
- 指标编号（如1.2、3.1、3.2、3.3、10.1、10.2等）- 必须保留原始编号
- 指标名称（如"文献分析"、"设计方法"等）
- 对应毕业要求指标点（如"2.3"、"3.1"等）
- 指标完整描述（必须保留原文描述，如"能够借助文献分析了解所研究问题的影响因素和已有进展，以及寻求可替代的解决方案"）
- 权重或分值

**注意**：原始指标描述通常很长，必须完整保留，不能简化！

### 【任务二：生成详细评价要点】
为每个指标生成5-8个具体的评价要点（不是3个！），每个要点必须包含：
- 要点名称（具体明确）
- 要点权重（百分比，所有要点权重之和为100%）
- 要点详细描述（50字以上）
- 各等级评分标准（每个等级描述必须在50字以上）：
  - 优秀（90-100分）：详细描述达到优秀的具体表现和要求
  - 良好（80-89分）：详细描述达到良好的具体表现和要求
  - 中等（70-79分）：详细描述达到中等的具体表现和要求
  - 及格（60-69分）：详细描述达到及格的具体表现和要求
  - 不及格（0-59分）：详细描述不及格的具体情况

### 【任务三：生成评价表格】
生成一个完整的评价表格，包含所有评价指标。

### 【任务四：确定评价流程】
根据{type_name}项目特点，确定详细的评价流程和成绩计算方式。

## 输出格式要求

请以JSON格式返回，结构如下：
{{
    "name": "{type_name}项目评价标准",
    "description": "详细描述本评价标准的适用范围、评价目的和核心要求（必须300字以上，详细说明评价理念、适用对象、评价原则等）",
    "project_type": "{project_type}",
    "original_indicators": [
        {{
            "indicator_id": "1.2",
            "name": "文献分析",
            "graduation_requirement": "2.3",
            "description": "能够借助文献分析了解所研究问题的影响因素和已有进展，以及寻求可替代的解决方案。（完整保留原文描述）",
            "weight": 15,
            "max_score": 100
        }}
    ],
    "indicators": [
        {{
            "indicator_id": "1.2",
            "name": "文献分析",
            "weight": 15,
            "max_score": 100,
            "description": "详细描述该指标的评价范围和要求（必须200字以上，包括评价目的、评价内容、评价重点等）",
            "graduation_requirement": "2.3",
            "full_description": "能够借助文献分析了解所研究问题的影响因素和已有进展，以及寻求可替代的解决方案。",
            "evaluation_method": "指导教师评分",
            "evaluation_points": [
                {{
                    "point_name": "文献检索范围与数量",
                    "weight": 20,
                    "description": "评价学生检索文献的范围是否广泛，数量是否充足，是否涵盖国内外重要文献（50字以上）",
                    "grade_criteria": {{
                        "excellent": "优秀标准（90-100分）：检索文献数量超过30篇，涵盖国内外核心期刊、学位论文、会议论文等多种类型，文献来源权威可靠，时间跨度合理，能够全面反映研究领域的现状和发展趋势。（80字以上）",
                        "good": "良好标准（80-89分）：检索文献数量在20-30篇之间，涵盖国内外主要文献类型，文献来源较为权威，时间跨度较合理，能够较好地反映研究领域的现状。（60字以上）",
                        "medium": "中等标准（70-79分）：检索文献数量在15-20篇之间，文献类型相对单一，来源一般，能够基本反映研究领域的现状。（50字以上）",
                        "pass": "及格标准（60-69分）：检索文献数量在10-15篇之间，文献类型和来源较为有限，对研究领域现状的反映不够全面。（50字以上）",
                        "fail": "不及格标准（0-59分）：检索文献数量少于10篇，文献类型单一，来源不可靠，无法反映研究领域的现状，或存在严重抄袭行为。（50字以上）"
                    }}
                }},
                {{
                    "point_name": "文献分析深度",
                    "weight": 25,
                    "description": "评价学生对文献内容的理解和分析程度，是否能够提炼关键信息（50字以上）",
                    "grade_criteria": {{
                        "excellent": "优秀标准（90-100分）：能够深入分析文献内容，准确提炼研究方法、主要结论和创新点，能够识别文献之间的关联和差异，形成系统的文献综述框架，对研究问题有深刻见解。（80字以上）",
                        "good": "良好标准（80-89分）：能够较好地分析文献内容，提炼主要信息，识别文献之间的关联，形成较为系统的文献综述框架。（60字以上）",
                        "medium": "中等标准（70-79分）：能够基本分析文献内容，提炼部分关键信息，文献综述框架基本完整。（50字以上）",
                        "pass": "及格标准（60-69分）：对文献内容的分析较浅，仅能提炼表面信息，文献综述框架不够完整。（50字以上）",
                        "fail": "不及格标准（0-59分）：无法有效分析文献内容，仅简单罗列文献，缺乏提炼和总结。（50字以上）"
                    }}
                }}
            ],
            "grade_levels": {{
                "excellent": "优秀（90-100分）：全面完成文献调研任务，文献检索范围广泛、数量充足，分析深入透彻，能够准确识别研究问题的关键因素和前沿进展，系统提出多种替代方案并进行深入比较，文献综述质量高。（100字以上）",
                "good": "良好（80-89分）：较好完成文献调研任务，文献检索范围较广、数量较多，分析较为深入，能够识别研究问题的主要因素和进展，提出一些替代方案并进行比较，文献综述质量较好。（80字以上）",
                "medium": "中等（70-79分）：基本完成文献调研任务，文献检索范围一般、数量适中，分析深度一般，能够识别研究问题的部分因素和进展，提出基本替代方案，文献综述质量一般。（70字以上）",
                "pass": "及格（60-69分）：勉强完成文献调研任务，文献检索范围较窄、数量较少，分析较浅，仅能识别研究问题的部分因素，替代方案较少或分析较浅，文献综述质量较低。（60字以上）",
                "fail": "不及格（0-59分）：未完成文献调研任务，文献综述缺失、不准确或严重偏离主题，未能识别影响因素和进展，无替代方案，存在严重学术不端行为。（50字以上）"
            }}
        }}
    ],
    "evaluation_table": {{
        "title": "{type_name}毕业设计评价表",
        "description": "本表格用于{type_name}毕业设计的综合评价，包含所有评价指标",
        "columns": ["序号", "指标编号", "指标名称", "毕业要求指标点", "满分", "得分", "评价等级", "评价人", "备注"],
        "rows": [
            {{
                "序号": 1,
                "指标编号": "1.2",
                "指标名称": "文献分析",
                "毕业要求指标点": "2.3",
                "满分": 100,
                "评价方式": "指导教师评分"
            }}
        ]
    }},
    "evaluation_flow": {{
        "description": "评价流程说明（100字以上）",
        "steps": [
            {{"step": 1, "name": "指导教师评分", "weight": 0.4, "description": "指导教师根据学生平时表现和论文质量评分（50字以上）", "evaluation_focus": ["平时表现", "论文质量", "工作态度"]}},
            {{"step": 2, "name": "评阅教师评分", "weight": 0.3, "description": "评阅教师独立评阅论文质量（50字以上）", "evaluation_focus": ["论文结构", "研究方法", "创新性"]}},
            {{"step": 3, "name": "答辩评分", "weight": 0.3, "description": "答辩委员会根据答辩表现评分（50字以上）", "evaluation_focus": ["表达能力", "问题回答", "PPT质量"]}}
        ],
        "final_score_formula": "总评成绩 = 指导教师评分×40% + 评阅教师评分×30% + 答辩评分×30%",
        "grade_conversion": {{
            "excellent": "总评成绩≥90分",
            "good": "80分≤总评成绩<90分",
            "medium": "70分≤总评成绩<80分",
            "pass": "60分≤总评成绩<70分",
            "fail": "总评成绩<60分"
        }}
    }},
    "grading_levels": {{
        "excellent": {{"min": 90, "max": 100, "description": "优秀标准详细描述（100字以上）"}},
        "good": {{"min": 80, "max": 89, "description": "良好标准详细描述（100字以上）"}},
        "medium": {{"min": 70, "max": 79, "description": "中等标准详细描述（100字以上）"}},
        "pass": {{"min": 60, "max": 69, "description": "及格标准详细描述（100字以上）"}},
        "fail": {{"min": 0, "max": 59, "description": "不及格标准详细描述（100字以上）"}}
    }},
    "excluded_indicators": ["不适用于{type_name}项目的评价指标（说明原因）"],
    "project_specific_requirements": [
        "{type_name}项目的特殊评价要求1",
        "{type_name}项目的特殊评价要求2"
    ],
    "keywords": ["{type_name}", "关键词1", "关键词2", "关键词3"],
    "notes": "使用本评价标准的注意事项和说明（200字以上）",
    "references": ["参考的评价文件或标准"]
}}

## 【重要提示 - 必须严格遵守】

1. **完整性要求**：
   - 必须完整保留原始文件中的所有评价指标，不能遗漏
   - 原始指标描述必须完整保留，不能简化或改写
   - 指标编号必须保留原始编号（如1.2、3.1等）

2. **详细性要求**：
   - 每个指标描述必须在200字以上
   - 每个评价要点描述必须在50字以上
   - 每个评分等级描述必须在50字以上
   - 每个指标的grade_levels中每个等级描述必须在100字以上

3. **评价要点数量**：
   - 每个指标必须包含5-8个评价要点（不是3个！）
   - 每个评价要点的权重之和必须等于100%

4. **权重设置**：
   - 所有指标权重之和必须等于100%
   - 使用百分比表示（如15表示15%，不是0.15）

5. **项目特点调整**：
   - 算法类：强调算法原理、代码质量、性能优化、实验验证，排除实物制作相关指标
   - 仿真类：强调仿真建模、参数分析、结果验证，排除实验操作相关指标
   - 实物类：强调设计制作、调试测试、性能验证
   - 传统机械类：强调结构设计、力学分析、工程制图
   - 混合类：综合各类特点，灵活设置

6. **评分标准要求**：
   - 每个等级的评分标准要具体、可量化、可操作
   - 必须包含具体的数量指标（如文献数量、代码行数等）
   - 必须包含具体的行为描述

7. **描述风格**：
   - 使用专业、严谨的学术语言
   - 避免模糊表述（如"较好"、"一般"等）
   - 提供具体的判断标准
"""
        
        system_prompt = f"""你是一位资深的教育评估专家，专门负责{type_name}项目的评价标准制定，拥有20年以上的教学评估经验。
你的任务是根据原始评价指标文件，生成符合{type_name}项目特点的非常详细的评价标准。

【核心要求】
1. **完整性第一**：必须完整保留原始文件中的所有评价指标和描述，不能有任何遗漏
2. **详细性第二**：所有描述必须详细具体，字数要求必须满足
3. **可操作性第三**：评分标准必须具体、可量化、可操作

【输出质量标准】
- 原始指标描述：完整保留原文，不能简化
- 指标描述：200字以上
- 评价要点：每个指标5-8个，每个要点描述50字以上
- 评分标准：每个等级50字以上
- 总体评分等级：每个等级100字以上

请严格按照要求生成详细的评价标准，确保评价体系完整、科学、可操作。"""
        
        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=12000,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        try:
            generated_standards = json.loads(raw_content)
            generated_standards["source_file"] = file_name
            
            for indicator in generated_standards.get("indicators", []):
                if "weight" not in indicator or indicator["weight"] is None:
                    indicator["weight"] = 10
                if "max_score" not in indicator or indicator["max_score"] is None:
                    indicator["max_score"] = 100
                if isinstance(indicator.get("weight"), float) and indicator["weight"] < 1:
                    indicator["weight"] = int(indicator["weight"] * 100)
            
            return generated_standards
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            start_idx = raw_content.find('{')
            end_idx = raw_content.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = raw_content[start_idx:end_idx]
                generated_standards = json.loads(json_str)
                generated_standards["source_file"] = file_name
                return generated_standards
            else:
                raise Exception(f"解析生成的评价标准失败: {str(e)}")
    
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
        
        return response.choices[0].message.content
    
    def evaluate_with_indicators(
        self,
        submission_content: str,
        indicators: Dict,
        student_info: Dict = None
    ) -> Dict:
        """
        根据评价指标使用大模型进行评分
        
        Args:
            submission_content: 提交内容（论文内容）
            indicators: 评价指标字典
            student_info: 学生信息
            
        Returns:
            评分结果字典
        """
        self.ai_config = get_ai_config()
        self.client = self._initialize_client(self.ai_config)
        
        if not self.client:
            raise Exception("大模型客户端未初始化，请检查API配置")
        
        indicators_str = json.dumps(indicators, ensure_ascii=False, indent=2)
        
        student_info_str = ""
        if student_info:
            student_info_str = f"""
学生信息：
- 学号：{student_info.get('student_id', '未知')}
- 姓名：{student_info.get('name', '未知')}
- 题目：{student_info.get('title', '未知')}
"""
        
        system_prompt = """你是一位资深的教育评估专家，专门负责毕业设计评价工作。
你的职责是严格按照给定的评价指标，客观、公正地评价学生的毕业设计论文。

重要规则：
1. **严格按标准评分**：必须严格按照提示词中给出的评价指标进行评分
2. **一致性原则**：相同质量的作品必须得到相近的分数
3. **证据支撑**：每个评分必须有学生提交内容中的具体证据支撑
4. **等级对应**：根据学生表现确定等级，然后给出对应分数
5. **客观公正**：评分需基于论文实际内容，避免主观臆断

请以专业、客观、严谨的态度进行评价，确保评价结果的一致性和可靠性。"""

        user_prompt = f"""请根据以下评价指标，对学生的毕业设计论文进行评分。

{student_info_str}

## 评价指标

{indicators_str}

## 论文内容

{submission_content[:12000]}

## 评分要求

1. 对每个评价指标进行评分（0-100分）
2. 提供评分理由（为什么给这个分数）
3. 引用论文中的具体内容作为证据
4. 计算加权总分

请严格按照以下JSON格式返回评分结果：
{{
    "overall_score": 加权总分（保留1位小数）,
    "grade_level": "总体等级（优秀/良好/中等/及格/不及格）",
    "overall_comment": "总体评价（100-200字）",
    "dimension_scores": [
        {{
            "indicator_id": "指标编号",
            "indicator_name": "指标名称",
            "score": 分数（0-100）,
            "grade_level": "等级（优秀/良好/中等/及格/不及格）",
            "score_reason": "评分理由（100-200字）",
            "evidence": "论文中的具体证据",
            "improvement_suggestions": ["改进建议1", "改进建议2"]
        }}
    ]
}}"""

        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=6000,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        logger.info("=== 评价指标评分原始响应 ===")
        logger.info(f"响应长度: {len(raw_content)}")
        
        try:
            result = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            start_idx = raw_content.find('{')
            end_idx = raw_content.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = raw_content[start_idx:end_idx]
                result = json.loads(json_str)
            else:
                raise Exception(f"解析大模型返回结果失败: {str(e)}")
        
        result["evaluation_method"] = "llm_indicators"
        result["is_deterministic"] = True
        
        return result
    
    def evaluate_institutional_dimensions(
        self,
        submission_content: str,
        dimension_weights: Dict = None
    ) -> Dict:
        """
        评估校方固有评价体系维度（创新度、研究分析深度、文章结构、研究方法与实验）
        
        Args:
            submission_content: 提交内容
            dimension_weights: 维度权重配置，如 {"innovation": 25, "research_depth": 25, ...}
            
        Returns:
            固有评价体系评分结果
        """
        from src.prompts.thesis_prompts import INSTITUTIONAL_SYSTEM_PROMPT, build_institutional_user_prompt
        
        self.ai_config = get_ai_config()
        self.client = self._initialize_client(self.ai_config)
        
        if not self.client:
            raise Exception("大模型客户端未初始化，请检查API配置")
        
        user_prompt = build_institutional_user_prompt(
            content=submission_content[:15000],
            dimension_weights=dimension_weights
        )
        
        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": INSTITUTIONAL_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        try:
            result = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            start_idx = raw_content.find('{')
            end_idx = raw_content.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = raw_content[start_idx:end_idx]
                result = json.loads(json_str)
            else:
                raise Exception(f"解析固有评价体系结果失败: {str(e)}")
        
        if dimension_weights:
            total_weight = sum(dimension_weights.values())
            if total_weight > 0:
                weighted_score = 0
                for score_item in result.get("institutional_scores", []):
                    dim_id = score_item.get("dimension_id", "")
                    dim_score = score_item.get("score", 0)
                    weight = dimension_weights.get(dim_id, 25)
                    weighted_score += dim_score * (weight / total_weight)
                result["weighted_overall_score"] = round(weighted_score, 1)
        
        return result
    
    def calculate_fusion_score(
        self,
        rule_engine_score: float,
        institutional_result: Dict,
        coefficient_config: Dict = None
    ) -> Dict:
        """
        计算融合评分
        
        Args:
            rule_engine_score: 规则引擎评分
            institutional_result: 固有评价体系评分结果
            coefficient_config: 融合系数配置，如 {"excellent": 1.15, "good": 1.05, ...}
            
        Returns:
            融合结果字典
        """
        default_config = {
            "excellent": 1.15,
            "good": 1.05,
            "medium": 0.98,
            "pass": 0.90,
            "fail": 0.78
        }
        
        config = coefficient_config if coefficient_config else default_config
        
        institutional_scores = institutional_result.get("institutional_scores", [])
        
        dimension_coefficients = {}
        total_coefficient = 0
        count = 0
        
        for score_item in institutional_scores:
            dim_id = score_item.get("dimension_id", "")
            dim_score = score_item.get("score", 0)
            dim_grade = score_item.get("grade_level", "")
            
            if dim_score >= 90:
                coef = config.get("excellent", default_config["excellent"])
            elif dim_score >= 80:
                coef = config.get("good", default_config["good"])
            elif dim_score >= 70:
                coef = config.get("medium", default_config["medium"])
            elif dim_score >= 60:
                coef = config.get("pass", default_config["pass"])
            else:
                coef = config.get("fail", default_config["fail"])
            
            dimension_coefficients[dim_id] = {
                "coefficient": round(coef, 4),
                "score": dim_score,
                "grade_level": dim_grade
            }
            
            total_coefficient += coef
            count += 1
        
        if count > 0:
            avg_coefficient = total_coefficient / count
        else:
            avg_coefficient = 1.0
        
        adjustment = rule_engine_score * (avg_coefficient - 1)
        fusion_score = rule_engine_score + adjustment
        
        fusion_score = max(0, min(100, fusion_score))
        
        return {
            "original_score": round(rule_engine_score, 1),
            "fusion_coefficient": round(avg_coefficient, 4),
            "adjustment": round(adjustment, 1),
            "fusion_score": round(fusion_score, 1),
            "dimension_coefficients": dimension_coefficients,
            "coefficient_config_used": config
        }




# 全局评估器实例
llm_evaluator = LLMEvaluator()