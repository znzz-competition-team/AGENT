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
        student_info: Dict = None,
        use_enhanced_prompt: bool = True
    ) -> Dict:
        """
        根据评价指标使用大模型进行评分
        
        Args:
            submission_content: 提交内容（论文内容）
            indicators: 评价指标字典
            student_info: 学生信息
            use_enhanced_prompt: 是否使用增强版提示词
            
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
        
        if use_enhanced_prompt:
            from src.prompts.thesis_prompts import ENHANCED_THESIS_SYSTEM_PROMPT, FEW_SHOT_EXAMPLES, SELF_VERIFICATION_PROMPT, VERIFICATION_OUTPUT_FORMAT
            
            system_prompt = ENHANCED_THESIS_SYSTEM_PROMPT
            
            user_prompt = f"""请根据以下评价指标，对学生的毕业设计论文进行专业评审。

{student_info_str}

## 评价指标

{indicators_str}

## 论文内容

{submission_content[:15000]}

{FEW_SHOT_EXAMPLES}

## 评审要求

### 第一步：逐项分析
对每个指标，请按以下格式进行分析：
1. **标准理解**：这个指标要求什么？
2. **证据定位**：论文中哪些内容与该指标相关？
3. **质量评估**：这些内容的质量如何？有什么优点和不足？
4. **对比分析**：与优秀论文相比，差距在哪里？

### 第二步：评分
根据分析结果，给出0-100分的评分，并说明理由。

### 第三步：改进建议
针对每个不足之处，给出具体的改进建议。

{SELF_VERIFICATION_PROMPT}

{VERIFICATION_OUTPUT_FORMAT}

## 输出格式
请严格按照以下JSON格式返回：
{{
    "analysis_process": [
        {{
            "indicator_id": "指标编号",
            "indicator_name": "指标名称",
            "standard_understanding": "对评价标准的理解",
            "evidence_found": "论文中的相关内容（引用原文）",
            "quality_assessment": "质量评估（优点和不足）",
            "comparison_with_excellent": "与优秀标准的对比"
        }}
    ],
    "overall_score": 加权总分（保留1位小数）,
    "grade_level": "总体等级（优秀/良好/中等/及格/不及格）",
    "overall_comment": "总体评价（200-300字，需引用论文内容）",
    "dimension_scores": [
        {{
            "indicator_id": "指标编号",
            "indicator_name": "指标名称",
            "score": 分数（0-100）,
            "grade_level": "等级（优秀/良好/中等/及格/不及格）",
            "score_reason": "评分理由（必须引用论文具体内容）",
            "evidence": "支撑证据（原文引用）",
            "improvement_suggestions": ["具体改进建议"]
        }}
    ],
    "strengths": ["优势1（附证据）", "优势2（附证据）"],
    "weaknesses": ["不足1（附证据）", "不足2（附证据）"],
    "comparison_with_excellent_thesis": "与优秀论文的主要差距分析",
    "self_verification": {{
        "evidence_consistency": true/false,
        "evidence_consistency_note": "说明",
        "score_rationality": true/false,
        "score_rationality_note": "说明",
        "grade_consistency": true/false,
        "grade_consistency_note": "说明",
        "overall_consistent": true/false,
        "verification_passed": true/false
    }}
}}"""
        else:
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
        dimension_weights: dict = None,
        use_enhanced_prompt: bool = True
    ) -> Dict:
        """
        评估校方固有评价体系维度（创新度、研究分析深度、文章结构、研究方法与实验）
        
        Args:
            submission_content: 提交内容
            dimension_weights: 维度权重配置，如 {"innovation": 25, "research_depth": 25, ...}
            use_enhanced_prompt: 是否使用增强版提示词
            
        Returns:
            固有评价体系评分结果
        """
        from src.prompts.thesis_prompts import INSTITUTIONAL_SYSTEM_PROMPT, build_institutional_user_prompt, ENHANCED_INSTITUTIONAL_SYSTEM_PROMPT, FEW_SHOT_EXAMPLES, SELF_VERIFICATION_PROMPT, VERIFICATION_OUTPUT_FORMAT
        
        self.ai_config = get_ai_config()
        self.client = self._initialize_client(self.ai_config)
        
        if not self.client:
            raise Exception("大模型客户端未初始化，请检查API配置")
        
        system_prompt = ENHANCED_INSTITUTIONAL_SYSTEM_PROMPT if use_enhanced_prompt else INSTITUTIONAL_SYSTEM_PROMPT
        
        user_prompt = build_institutional_user_prompt(
            content=submission_content[:18000],
            dimension_weights=dimension_weights
        )
        
        if use_enhanced_prompt:
            user_prompt = f"""请对以下毕业设计论文进行校方固有评价体系维度评分。

## 论文内容

{submission_content[:18000]}

{FEW_SHOT_EXAMPLES}

## 评审思维链

在评分前，请按以下步骤思考：

### 创新度评估
1. 论文提出了什么新东西？（新方法/新模型/新应用/新发现）
2. 这个"新"是真正的创新还是简单的组合？
3. 创新是否有价值？解决了什么实际问题？
4. 与现有工作相比，改进有多大？

### 研究深度评估
1. 文献综述是否覆盖了主要相关工作？
2. 是否真正理解并分析了文献，而非简单罗列？
3. 现状分析是否有深度，能否归纳出关键问题？
4. 引用的文献是否新颖、权威？

### 文章结构评估
1. 章节安排是否符合学术规范？
2. 各章节之间是否有逻辑关联？
3. 论证是否连贯，有无跳跃或矛盾？
4. 语言表达是否规范、清晰？

### 方法与实验评估
1. 研究方法是否适合研究问题？
2. 方法描述是否详细、可复现？
3. 实验设计是否科学、完整？
4. 数据分析是否严谨、有说服力？

{SELF_VERIFICATION_PROMPT}

{VERIFICATION_OUTPUT_FORMAT}

## 输出格式
请严格按照以下JSON格式返回：
{{
    "institutional_scores": [
        {{
            "dimension_id": "innovation",
            "dimension_name": "创新度",
            "score": 分数（0-100）,
            "grade_level": "等级（优秀/良好/中等/及格/不及格）",
            "score_reason": "评分理由（必须引用论文具体内容）",
            "evidence": "论文中的具体证据",
            "analysis_details": {{
                "innovation_type": "创新类型（原创性/组合式/改进型）",
                "innovation_value": "创新价值说明",
                "comparison_with_existing": "与现有工作的对比"
            }}
        }},
        {{
            "dimension_id": "research_depth",
            "dimension_name": "研究分析深度",
            "score": 分数（0-100）,
            "grade_level": "等级",
            "score_reason": "评分理由（必须引用论文具体内容）",
            "evidence": "论文中的具体证据",
            "analysis_details": {{
                "literature_coverage": "文献覆盖情况",
                "analysis_depth": "分析深度评价",
                "problem_identification": "问题归纳能力"
            }}
        }},
        {{
            "dimension_id": "structure",
            "dimension_name": "文章结构",
            "score": 分数（0-100）,
            "grade_level": "等级",
            "score_reason": "评分理由（必须引用论文具体内容）",
            "evidence": "论文中的具体证据",
            "analysis_details": {{
                "chapter_arrangement": "章节安排评价",
                "logic_coherence": "逻辑连贯性评价",
                "expression_quality": "表达规范性评价"
            }}
        }},
        {{
            "dimension_id": "method_experiment",
            "dimension_name": "研究方法与实验",
            "score": 分数（0-100）,
            "grade_level": "等级",
            "score_reason": "评分理由（必须引用论文具体内容）",
            "evidence": "论文中的具体证据",
            "analysis_details": {{
                "method_appropriateness": "方法适合性评价",
                "method_detail": "方法详细度评价",
                "experiment_design": "实验设计评价"
            }}
        }}
    ],
    "overall_institutional_score": 加权总分（保留1位小数）,
    "overall_institutional_grade": "总体等级",
    "comparison_with_excellent_thesis": "与优秀论文的主要差距分析",
    "self_verification": {{
        "evidence_consistency": true/false,
        "evidence_consistency_note": "说明",
        "score_rationality": true/false,
        "score_rationality_note": "说明",
        "grade_consistency": true/false,
        "grade_consistency_note": "说明",
        "overall_consistent": true/false,
        "verification_passed": true/false
    }}
}}"""
        
        response = self.client.chat.completions.create(
            model=self.ai_config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=5000,
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