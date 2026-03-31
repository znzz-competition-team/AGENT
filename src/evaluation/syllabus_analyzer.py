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
    
    def generate_evaluation_prompt(self):
        """
        生成大模型评估提示词
        """
        # 构建能力点列表
        ability_points = []
        for syllabus_name, data in self.ability_matrix.items():
            ability_points.extend(data.get('ability_points', []))
        
        # 去重
        unique_ability_points = list(set(ability_points))
        
        # 构建评价标准列表
        evaluation_criteria = []
        for syllabus_name, data in self.ability_matrix.items():
            evaluation_criteria.extend(data.get('evaluation_criteria', []))
        
        # 生成提示词
        prompt = f"""
        # 评估任务
       请根据以下课程大纲中的能力点和评价标准，对学生的表现进行全面、客观的评估。
        
        # 课程大纲能力点
        {chr(10).join([f"- {point}" for point in unique_ability_points])}
        
        # 评价标准
        {chr(10).join([f"- {criterion}" for criterion in evaluation_criteria])}
        
        # 评估要求
        1. 对每个能力点进行评分，评分范围为0-100分
        2. 提供详细的评分理由，基于学生的实际表现
        3. 给出综合评分和整体建议
        4. 评估结果必须以JSON格式返回，结构如下：
        {{
            "overall_score": 85,
            "ability_scores": [
                {{"ability": "表述与表达", "score": 80, "reasoning": "详细的评分理由"}},
                {{"ability": "建模知识", "score": 75, "reasoning": "详细的评分理由"}},
                {{"ability": "分析知识", "score": 90, "reasoning": "详细的评分理由"}},
                {{"ability": "设计与开发", "score": 85, "reasoning": "详细的评分理由"}},
                {{"ability": "模因分析", "score": 70, "reasoning": "详细的评分理由"}}
            ],
            "strengths": ["学习态度积极", "基础知识扎实"],
            "areas_for_improvement": ["创新能力需要加强", "团队协作能力有待提高"],
            "recommendations": ["多参与团队项目", "培养创新思维"]
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
    
    # 生成评估提示词
    prompt = analyzer.generate_evaluation_prompt()
    prompt_path = os.path.join(project_root, 'evaluation_prompt.txt')
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    print(f"分析完成，能力矩阵已保存到 {ability_matrix_path}")
    print(f"评估提示词已保存到 {prompt_path}")
