import os
import json
from typing import Dict, List, Any
import requests
import logging

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 尝试导入docx库
try:
    import docx
    logger.info("docx库导入成功")
except Exception as e:
    logger.error(f"docx库导入失败: {e}")
    docx = None

class SyllabusAnalyzer:
    """
    课程大纲分析器，用于提取能力点和评价标准，构建能力矩阵
    """
    
    def __init__(self, syllabus_folder: str):
        """
        初始化分析器
        
        Args:
            syllabus_folder: 课程大纲文件夹路径
        """
        self.syllabus_folder = syllabus_folder
        self.syllabi = {}
        self.ability_matrix = {}
        
    def load_syllabi(self):
        """
        加载所有课程大纲文件
        """
        try:
            if docx is None:
                raise Exception("docx库未导入，无法加载课程大纲文件")
            
            if not os.path.exists(self.syllabus_folder):
                raise Exception(f"课程大纲文件夹不存在: {self.syllabus_folder}")
            
            files = os.listdir(self.syllabus_folder)
            if not files:
                raise Exception(f"课程大纲文件夹为空: {self.syllabus_folder}")
            
            for file in files:
                if file.endswith('.docx'):
                    file_path = os.path.join(self.syllabus_folder, file)
                    try:
                        doc = docx.Document(file_path)
                        content = []
                        for para in doc.paragraphs:
                            text = para.text.strip()
                            if text:
                                content.append(text)
                        self.syllabi[file] = content
                        logger.info(f"成功加载课程大纲文件: {file}")
                    except Exception as e:
                        logger.error(f"加载课程大纲文件 {file} 失败: {e}")
                        raise
            
            if not self.syllabi:
                raise Exception("未找到有效的课程大纲文件")
        except Exception as e:
            logger.error(f"加载课程大纲文件失败: {e}")
            raise
        
    def extract_ability_points(self):
        """
        从课程大纲中提取能力点
        """
        for syllabus_name, content in self.syllabi.items():
            if syllabus_name in self.ability_matrix:
                ability_points = []
                for line in content:
                    # 提取能力点相关内容
                    if any(keyword in line for keyword in ['能力', '目标', '要求', '掌握', '了解', '理解']):
                        ability_points.append(line)
                # 只更新能力点，不覆盖评价标准
                self.ability_matrix[syllabus_name]['ability_points'] = ability_points
    
    def extract_evaluation_criteria(self):
        """
        从课程大纲中提取评价标准
        """
        for syllabus_name, content in self.syllabi.items():
            if syllabus_name in self.ability_matrix:
                evaluation_criteria = []
                for line in content:
                    # 提取评价标准相关内容
                    if any(keyword in line for keyword in ['评分', '评价', '标准', '考核', '达成度']):
                        evaluation_criteria.append(line)
                self.ability_matrix[syllabus_name]['evaluation_criteria'] = evaluation_criteria
    
    def build_ability_matrix(self):
        """
        构建能力矩阵
        """
        # 合并所有能力点
        all_ability_points = []
        for syllabus_name, data in self.ability_matrix.items():
            all_ability_points.extend(data.get('ability_points', []))
        
        # 去重并整理
        unique_ability_points = []
        seen = set()
        for point in all_ability_points:
            if point not in seen:
                seen.add(point)
                unique_ability_points.append(point)
        
        # 构建能力矩阵
        for syllabus_name in self.ability_matrix:
            self.ability_matrix[syllabus_name]['matrix'] = {}
            for point in unique_ability_points:
                # 简单判断能力点是否在该课程中
                ability_points = self.ability_matrix[syllabus_name].get('ability_points', [])
                if any(point in line for line in ability_points):
                    self.ability_matrix[syllabus_name]['matrix'][point] = '相关'
                else:
                    self.ability_matrix[syllabus_name]['matrix'][point] = '不相关'
    
    def analyze_with_llm(self, syllabus_content: str, syllabus_name: str) -> Dict:
        """
        使用后端API分析课程大纲
        
        Args:
            syllabus_content: 课程大纲内容
            syllabus_name: 课程大纲名称
            
        Returns:
            分析结果，包含能力点、评价标准等
        """
        try:
            # 构建API请求
            api_url = "http://localhost:8000/analyze_syllabus"
            payload = {
                "syllabus_content": syllabus_content,
                "syllabus_name": syllabus_name
            }
            
            response = requests.post(api_url, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                print(f"API分析成功: {result}")
                return result
            else:
                print(f"API分析失败: {response.status_code}")
                return {}
        except Exception as e:
            print(f"调用API时出错: {str(e)}")
            return {}
    
    def check_local_analysis(self, syllabus_name: str) -> Dict:
        """
        检查本地是否已有分析结果
        
        Args:
            syllabus_name: 课程大纲名称
            
        Returns:
            本地分析结果，如果不存在返回{}
        """
        analysis_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "analysis_results")
        os.makedirs(analysis_dir, exist_ok=True)
        
        analysis_file = os.path.join(analysis_dir, f"{syllabus_name.replace('.docx', '')}.json")
        
        if os.path.exists(analysis_file):
            try:
                with open(analysis_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"读取本地分析结果时出错: {str(e)}")
                return {}
        return {}
    
    def save_analysis_result(self, syllabus_name: str, analysis_result: Dict):
        """
        保存分析结果到本地
        
        Args:
            syllabus_name: 课程大纲名称
            analysis_result: 分析结果
        """
        analysis_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "analysis_results")
        os.makedirs(analysis_dir, exist_ok=True)
        
        analysis_file = os.path.join(analysis_dir, f"{syllabus_name.replace('.docx', '')}.json")
        
        try:
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            print(f"分析结果已保存到: {analysis_file}")
        except Exception as e:
            print(f"保存分析结果时出错: {str(e)}")
    
    def detect_document_type(self, content: str) -> str:
        """
        检测文档类型
        
        Args:
            content: 文档内容
            
        Returns:
            文档类型: 'graduation_requirements' 或 'course_evaluation' 或 'unknown'
        """
        graduation_keywords = ['毕业要求', '指标点', '支撑', '毕业指标', '达成度', '毕业要求指标点']
        evaluation_keywords = ['课程评价', '考核方式', '评分标准', '成绩评定', '课程目标', '评价方式', '考核标准']
        
        graduation_count = sum(1 for keyword in graduation_keywords if keyword in content)
        evaluation_count = sum(1 for keyword in evaluation_keywords if keyword in content)
        
        if graduation_count > evaluation_count:
            return 'graduation_requirements'
        elif evaluation_count > graduation_count:
            return 'course_evaluation'
        else:
            if graduation_count > 0:
                return 'graduation_requirements'
            return 'unknown'
    
    def build_course_evaluation_prompt(self, content: str) -> str:
        """
        构建课程评价标准分析提示词
        
        Args:
            content: 文档内容
            
        Returns:
            大模型提示词
        """
        prompt = f"""# 课程评价标准分析任务

请对以下课程评价相关文档进行详细、深入的分析，提取出：

1. **能力点**：课程要求学生掌握的具体知识和技能，每个能力点需要详细描述，包括具体的知识点、技能要求和掌握程度
2. **评价标准**：课程的详细评分标准和考核方式，包括各项考核的具体内容、评分权重、评分方法和标准

# 文档内容

{content}

# 输出要求

- 分析结果必须详细、具体，避免泛泛而谈
- 能力点需要具体到知识点和技能点，每个能力点应有详细描述
- 评价标准需要详细到具体的考核内容、评分标准和权重
- 如果文档中没有相关信息，对应字段返回空数组

# 输出格式

请以JSON格式返回分析结果，结构如下：
{{
    "ability_points": [
        {{
            "name": "能力点名称",
            "description": "详细描述",
            "level": "掌握程度（如：了解、理解、掌握、应用）"
        }}
    ],
    "evaluation_criteria": [
        {{
            "name": "评价项目",
            "weight": "权重（如：20%）",
            "description": "详细描述",
            "standard": "评分标准"
        }}
    ]
}}
"""
        return prompt
    
    def build_graduation_requirements_prompt(self, content: str) -> str:
        """
        构建毕业要求指标点分析提示词
        
        Args:
            content: 文档内容
            
        Returns:
            大模型提示词
        """
        prompt = f"""# 毕业要求指标点分析任务

请对以下毕业要求相关文档进行详细、深入的分析，提取出：

1. **毕业要求指标点**：课程支撑的具体毕业要求指标点，包括指标点编号、具体要求和支撑关系
2. **支撑强度**：每个指标点的支撑程度和支撑方式

# 文档内容

{content}

# 输出要求

- 分析结果必须详细、具体，避免泛泛而谈
- 毕业要求指标点需要具体到指标点编号和具体要求
- 支撑关系需要明确说明课程如何支撑该指标点
- 如果文档中没有相关信息，对应字段返回空数组

# 输出格式

请以JSON格式返回分析结果，结构如下：
{{
    "graduation_requirements": [
        {{
            "id": "指标点编号",
            "description": "详细描述",
            "support_level": "支撑程度（如：强支撑、中等支撑、弱支撑）",
            "support_method": "支撑方式（如：课程教学、实验实践、课程设计）"
        }}
    ]
}}
"""
        return prompt
    
    def build_syllabus_analysis_prompt(self, syllabus_content: str) -> str:
        """
        构建大纲分析提示词（通用版本，用于未知类型文档）
        
        Args:
            syllabus_content: 课程大纲内容
            
        Returns:
            大模型提示词
        """
        prompt = f"""# 课程大纲分析任务

请对以下课程大纲进行详细、深入的分析，提取出：

1. **能力点**：课程要求学生掌握的具体知识和技能，每个能力点需要详细描述，包括具体的知识点、技能要求和掌握程度
2. **评价标准**：课程的详细评分标准和考核方式，包括各项考核的具体内容、评分权重、评分方法和标准
3. **毕业要求指标点**：课程支撑的具体毕业要求指标点，包括指标点编号、具体要求和支撑关系

# 课程大纲内容

{syllabus_content}

# 输出要求

- 分析结果必须详细、具体，避免泛泛而谈
- 能力点需要具体到知识点和技能点，每个能力点应有详细描述
- 评价标准需要详细到具体的考核内容、评分标准和权重
- 毕业要求指标点需要具体到指标点编号和具体要求

# 输出格式

请以JSON格式返回分析结果，结构如下：
{{
    "ability_points": [
        {{
            "name": "能力点名称",
            "description": "详细描述",
            "level": "掌握程度（如：了解、理解、掌握、应用）"
        }}
    ],
    "evaluation_criteria": [
        {{
            "name": "评价项目",
            "weight": "权重（如：20%）",
            "description": "详细描述",
            "standard": "评分标准"
        }}
    ],
    "graduation_requirements": [
        {{
            "id": "指标点编号",
            "description": "详细描述",
            "support_level": "支撑程度（如：强支撑、中等支撑、弱支撑）"
        }}
    ]
}}
"""
        return prompt
    
    def build_graduation_project_initial_analysis_prompt(self, content: str) -> str:
        """
        第一轮：毕业设计大纲初步分析
        
        Args:
            content: 文档内容
            
        Returns:
            大模型提示词
        """
        prompt = f"""# 毕业设计大纲初步分析（第一轮）

请对以下毕业设计大纲进行初步分析，识别出：

1. **文档结构**：大纲的主要章节和内容组织方式
2. **核心要求**：毕业设计的主要任务和要求
3. **评价维度**：大纲中隐含或明确的评价维度
4. **关键指标**：需要重点关注的质量指标

# 文档内容

{content}

# 输出要求

- 简要概括文档的主要内容
- 识别出最重要的评价维度
- 为后续详细分析提供方向

# 输出格式

请以JSON格式返回分析结果，结构如下：
{{
    "document_structure": ["章节1", "章节2", "..."],
    "core_requirements": ["要求1", "要求2", "..."],
    "evaluation_dimensions": ["维度1", "维度2", "..."],
    "key_indicators": ["指标1", "指标2", "..."],
    "initial_summary": "对文档内容的简要概括（100-200字）"
}}
"""
        return prompt
    
    def build_graduation_project_detailed_analysis_prompt(self, content: str, initial_result: Dict) -> str:
        """
        第二轮：毕业设计大纲详细分析
        
        Args:
            content: 文档内容
            initial_result: 第一轮分析结果
            
        Returns:
            大模型提示词
        """
        initial_summary = initial_result.get('initial_summary', '')
        evaluation_dimensions = initial_result.get('evaluation_dimensions', [])
        key_indicators = initial_result.get('key_indicators', [])
        
        prompt = f"""# 毕业设计大纲详细分析（第二轮）

基于第一轮的初步分析，请对毕业设计大纲进行详细分析。

## 第一轮分析结果

- **文档概括**：{initial_summary}
- **评价维度**：{', '.join(evaluation_dimensions) if evaluation_dimensions else '无'}
- **关键指标**：{', '.join(key_indicators) if key_indicators else '无'}

## 原始文档内容

{content}

## 详细分析任务

请针对每个评价维度，提取具体的评价标准和评分要求：

1. **能力点**：毕业设计要求学生掌握的具体能力
2. **评价标准**：每个能力点的具体评分标准
3. **评分等级**：不同分数段的具体要求
4. **权重分配**：各部分的评分权重

# 输出格式

请以JSON格式返回分析结果，结构如下：
{{
    "ability_points": [
        {{
            "name": "能力点名称",
            "description": "详细描述",
            "level": "掌握程度",
            "indicators": ["具体指标1", "具体指标2"]
        }}
    ],
    "evaluation_criteria": [
        {{
            "name": "评价项目",
            "weight": "权重",
            "description": "详细描述",
            "standard": "评分标准",
            "grade_levels": {{
                "excellent": "优秀（90-100分）的具体要求",
                "good": "良好（80-89分）的具体要求",
                "medium": "中等（70-79分）的具体要求",
                "pass": "及格（60-69分）的具体要求",
                "fail": "不及格（60分以下）的具体要求"
            }}
        }}
    ],
    "scoring_rubric": "整体评分细则说明"
}}
"""
        return prompt
    
    def build_graduation_project_prompt_refinement_prompt(self, content: str, detailed_result: Dict) -> str:
        """
        第三轮：提示词优化与完善
        
        Args:
            content: 文档内容
            detailed_result: 第二轮详细分析结果
            
        Returns:
            大模型提示词
        """
        ability_points = detailed_result.get('ability_points', [])
        evaluation_criteria = detailed_result.get('evaluation_criteria', [])
        
        ability_points_str = json.dumps(ability_points, ensure_ascii=False, indent=2)
        evaluation_criteria_str = json.dumps(evaluation_criteria, ensure_ascii=False, indent=2)
        
        prompt = f"""# 毕业设计评价提示词优化（第三轮）

请对前两轮的分析结果进行审查和优化，生成最终的评价提示词模板。

## 已提取的能力点

{ability_points_str}

## 已提取的评价标准

{evaluation_criteria_str}

## 原始文档内容

{content}

## 优化任务

1. **完整性检查**：确保所有重要的评价维度都已覆盖
2. **一致性检查**：确保评价标准之间没有矛盾
3. **可操作性优化**：使评价标准更加具体、可量化
4. **提示词生成**：生成可直接用于学生作业评价的提示词

## 原始文档内容

{content}

## 第二轮分析结果

### 能力点
{ability_points_str}

### 评价标准
{evaluation_criteria_str}

## 优化任务

1. 审查分析结果是否完整、准确
2. 补充遗漏的评价维度
3. 优化评分标准的可操作性
4. 生成最终的评价提示词模板

# 输出格式

请以JSON格式返回优化后的结果，结构如下：
{{
    "optimized_ability_points": [
        {{
            "name": "能力点名称",
            "description": "详细描述",
            "level": "掌握程度",
            "indicators": ["具体指标1", "具体指标2"],
            "evaluation_hints": "评价提示"
        }}
    ],
    "optimized_evaluation_criteria": [
        {{
            "name": "评价项目",
            "weight": "权重",
            "description": "详细描述",
            "standard": "评分标准",
            "grade_levels": {{
                "excellent": "优秀的具体要求",
                "good": "良好的具体要求",
                "medium": "中等的具体要求",
                "pass": "及格的具体要求",
                "fail": "不及格的具体要求"
            }},
            "evaluation_hints": "评价提示"
        }}
    ],
    "evaluation_prompt_template": "可直接用于评价学生作业的提示词模板（包含所有评价维度和标准）",
    "optimization_notes": "优化说明，描述做了哪些改进"
}}
"""
        return prompt
    
    def analyze(self):
        """
        执行完整的分析流程
        """
        try:
            self.load_syllabi()
            
            # 对每个课程大纲进行分析
            for syllabus_name, content in self.syllabi.items():
                # 检查本地是否已有分析结果
                local_analysis = self.check_local_analysis(syllabus_name)
                if local_analysis:
                    print(f"使用本地分析结果: {syllabus_name}")
                    self.ability_matrix[syllabus_name] = local_analysis
                else:
                    print(f"使用后端API分析: {syllabus_name}")
                    # 使用后端API分析
                    syllabus_content = "\n".join(content)
                    api_result = self.analyze_with_llm(syllabus_content, syllabus_name)
                    
                    if api_result and (api_result.get('ability_points') or api_result.get('evaluation_criteria')):
                        # 保存API分析结果
                        # 确保结果包含必要的键
                        if 'ability_points' not in api_result:
                            api_result['ability_points'] = []
                        if 'evaluation_criteria' not in api_result:
                            api_result['evaluation_criteria'] = []
                        self.ability_matrix[syllabus_name] = api_result
                        self.save_analysis_result(syllabus_name, api_result)
                        print(f"API分析成功: {syllabus_name}")
                    else:
                        # 如果API分析失败或结果为空，直接报错
                        error_message = f"API分析失败或结果为空: {syllabus_name}"
                        print(error_message)
                        raise Exception(error_message)

            self.build_ability_matrix()
            return self.ability_matrix
        except Exception as e:
            print(f"分析课程大纲时出错: {e}")
            raise

if __name__ == "__main__":
    # 示例用法 - 使用相对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    syllabus_folder = os.path.join(project_root, "评价大纲")
    
    analyzer = SyllabusAnalyzer(syllabus_folder)
    ability_matrix = analyzer.analyze()
    
    # 保存能力矩阵到项目根目录
    ability_matrix_path = os.path.join(project_root, 'ability_matrix.json')
    with open(ability_matrix_path, 'w', encoding='utf-8') as f:
        json.dump(ability_matrix, f, ensure_ascii=False, indent=2)
    
    print(f"分析完成，能力矩阵已保存到 {ability_matrix_path}")
