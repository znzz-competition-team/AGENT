from enum import Enum
from typing import Dict, List, Optional
import json

class ProjectType(Enum):
    ALGORITHM = "algorithm"
    SIMULATION = "simulation"
    PHYSICAL = "physical"
    TRADITIONAL_MECHANICAL = "traditional_mechanical"
    MIXED = "mixed"
    UNKNOWN = "unknown"

PROJECT_TYPE_NAMES = {
    ProjectType.ALGORITHM: "算法类",
    ProjectType.SIMULATION: "仿真类",
    ProjectType.PHYSICAL: "实物类",
    ProjectType.TRADITIONAL_MECHANICAL: "传统机械类",
    ProjectType.MIXED: "混合类",
    ProjectType.UNKNOWN: "未知类型"
}

EVALUATION_STANDARDS = {
    "algorithm": {
        "name": "算法类项目评价标准",
        "description": "适用于算法设计、模型开发、数据分析等项目，无实物模型和实验验证",
        "indicators": [
            {
                "id": "ALG_01",
                "name": "算法设计",
                "description": "算法原理、设计思路、创新性",
                "weight": 30,
                "grade_levels": {
                    "excellent": "算法原理清晰，设计思路新颖，有明显的创新点，能够解决复杂问题",
                    "good": "算法原理正确，设计思路合理，有一定创新性，能够解决问题",
                    "medium": "算法原理基本正确，设计思路一般，创新性不足",
                    "pass": "算法原理存在小问题，设计思路不够清晰",
                    "fail": "算法原理错误或设计思路混乱"
                }
            },
            {
                "id": "ALG_02",
                "name": "代码实现",
                "description": "代码质量、规范性、可读性",
                "weight": 25,
                "grade_levels": {
                    "excellent": "代码结构清晰，注释完整，符合规范，可读性强，模块化设计优秀",
                    "good": "代码结构较好，注释较完整，基本符合规范，可读性较好",
                    "medium": "代码结构一般，注释不够完整，规范性有待提高",
                    "pass": "代码结构较乱，注释缺失，规范性差",
                    "fail": "代码混乱，无法理解，严重违反规范"
                }
            },
            {
                "id": "ALG_03",
                "name": "性能优化",
                "description": "算法效率、资源占用、优化程度",
                "weight": 20,
                "grade_levels": {
                    "excellent": "算法效率高，资源占用合理，进行了充分的优化，性能指标优秀",
                    "good": "算法效率较高，资源占用较合理，有一定优化，性能指标良好",
                    "medium": "算法效率一般，资源占用偏高，优化不够充分",
                    "pass": "算法效率较低，资源占用过高，缺乏优化",
                    "fail": "算法效率极低，资源占用严重超标"
                }
            },
            {
                "id": "ALG_04",
                "name": "测试验证",
                "description": "测试用例、验证方法、结果分析",
                "weight": 15,
                "grade_levels": {
                    "excellent": "测试用例全面，验证方法科学，结果分析深入，结论可靠",
                    "good": "测试用例较全面，验证方法合理，结果分析较好",
                    "medium": "测试用例不够全面，验证方法一般，结果分析不够深入",
                    "pass": "测试用例较少，验证方法简单，结果分析浅显",
                    "fail": "缺乏测试验证或验证方法错误"
                }
            },
            {
                "id": "ALG_05",
                "name": "文档撰写",
                "description": "论文结构、表达清晰度、图表质量",
                "weight": 10,
                "grade_levels": {
                    "excellent": "论文结构严谨，表达清晰流畅，图表规范美观，格式完全符合要求",
                    "good": "论文结构合理，表达清晰，图表较规范，格式符合要求",
                    "medium": "论文结构基本合理，表达一般，图表质量有待提高",
                    "pass": "论文结构不够合理，表达不够清晰，图表质量较差",
                    "fail": "论文结构混乱，表达不清，图表质量极差"
                }
            }
        ],
        "excluded_indicators": ["实物模型", "实验验证", "硬件制作", "样机调试"],
        "keywords": ["算法", "模型", "深度学习", "机器学习", "神经网络", "优化", "数据分析", "人工智能", "AI", "算法设计"]
    },
    
    "simulation": {
        "name": "仿真类项目评价标准",
        "description": "适用于仿真分析、数值模拟、虚拟实验等项目，无实物模型和实际实验",
        "indicators": [
            {
                "id": "SIM_01",
                "name": "仿真建模",
                "description": "模型建立、参数设置、边界条件",
                "weight": 35,
                "grade_levels": {
                    "excellent": "模型建立准确，参数设置合理，边界条件完整，充分反映实际问题",
                    "good": "模型建立较准确，参数设置较合理，边界条件较完整",
                    "medium": "模型建立基本正确，参数设置一般，边界条件不够完整",
                    "pass": "模型建立存在偏差，参数设置不够合理，边界条件缺失",
                    "fail": "模型建立错误或参数设置严重不合理"
                }
            },
            {
                "id": "SIM_02",
                "name": "仿真分析",
                "description": "仿真过程、结果分析、数据解读",
                "weight": 30,
                "grade_levels": {
                    "excellent": "仿真过程详细，结果分析深入，数据解读准确，结论可靠",
                    "good": "仿真过程较详细，结果分析较好，数据解读较准确",
                    "medium": "仿真过程一般，结果分析不够深入，数据解读有待提高",
                    "pass": "仿真过程简单，结果分析浅显，数据解读存在问题",
                    "fail": "仿真过程混乱或结果分析错误"
                }
            },
            {
                "id": "SIM_03",
                "name": "参数优化",
                "description": "参数敏感性分析、优化设计",
                "weight": 20,
                "grade_levels": {
                    "excellent": "参数敏感性分析全面，优化设计合理，效果显著",
                    "good": "参数敏感性分析较全面，优化设计较合理，效果较好",
                    "medium": "参数敏感性分析一般，优化设计不够充分",
                    "pass": "参数敏感性分析缺失，优化设计简单",
                    "fail": "缺乏参数分析或优化设计错误"
                }
            },
            {
                "id": "SIM_04",
                "name": "文档撰写",
                "description": "论文结构、表达清晰度、图表质量",
                "weight": 15,
                "grade_levels": {
                    "excellent": "论文结构严谨，表达清晰流畅，图表规范美观，格式完全符合要求",
                    "good": "论文结构合理，表达清晰，图表较规范，格式符合要求",
                    "medium": "论文结构基本合理，表达一般，图表质量有待提高",
                    "pass": "论文结构不够合理，表达不够清晰，图表质量较差",
                    "fail": "论文结构混乱，表达不清，图表质量极差"
                }
            }
        ],
        "excluded_indicators": ["实物模型", "实验验证", "硬件制作", "样机调试"],
        "keywords": ["仿真", "模拟", "有限元", "ANSYS", "COMSOL", "MATLAB", "数值分析", "流体", "力学仿真", "热仿真", "电磁仿真"]
    },
    
    "physical": {
        "name": "实物类项目评价标准",
        "description": "适用于实物制作、样机开发、硬件设计等项目，包含实物模型和实验验证",
        "indicators": [
            {
                "id": "PHY_01",
                "name": "方案设计",
                "description": "设计方案、技术路线、可行性分析",
                "weight": 20,
                "grade_levels": {
                    "excellent": "设计方案创新，技术路线清晰，可行性分析充分",
                    "good": "设计方案合理，技术路线较清晰，可行性分析较好",
                    "medium": "设计方案一般，技术路线基本清晰，可行性分析不够充分",
                    "pass": "设计方案存在不足，技术路线不够清晰",
                    "fail": "设计方案错误或不可行"
                }
            },
            {
                "id": "PHY_02",
                "name": "实物制作",
                "description": "制作工艺、加工质量、装配精度",
                "weight": 25,
                "grade_levels": {
                    "excellent": "制作工艺精良，加工质量优秀，装配精度高",
                    "good": "制作工艺较好，加工质量良好，装配精度较高",
                    "medium": "制作工艺一般，加工质量一般，装配精度一般",
                    "pass": "制作工艺粗糙，加工质量较差，装配精度低",
                    "fail": "制作工艺极差或无法正常工作"
                }
            },
            {
                "id": "PHY_03",
                "name": "实验验证",
                "description": "实验设计、测试方法、数据分析",
                "weight": 25,
                "grade_levels": {
                    "excellent": "实验设计科学，测试方法合理，数据分析深入，结论可靠",
                    "good": "实验设计较科学，测试方法较合理，数据分析较好",
                    "medium": "实验设计一般，测试方法基本合理，数据分析不够深入",
                    "pass": "实验设计简单，测试方法单一，数据分析浅显",
                    "fail": "缺乏实验验证或实验设计错误"
                }
            },
            {
                "id": "PHY_04",
                "name": "功能实现",
                "description": "功能完整性、性能指标、稳定性",
                "weight": 20,
                "grade_levels": {
                    "excellent": "功能完整，性能指标优秀，运行稳定可靠",
                    "good": "功能较完整，性能指标良好，运行较稳定",
                    "medium": "功能基本完整，性能指标一般，稳定性有待提高",
                    "pass": "功能不完整，性能指标较低，稳定性差",
                    "fail": "功能严重缺失或无法正常运行"
                }
            },
            {
                "id": "PHY_05",
                "name": "文档撰写",
                "description": "论文结构、表达清晰度、图表质量",
                "weight": 10,
                "grade_levels": {
                    "excellent": "论文结构严谨，表达清晰流畅，图表规范美观，格式完全符合要求",
                    "good": "论文结构合理，表达清晰，图表较规范，格式符合要求",
                    "medium": "论文结构基本合理，表达一般，图表质量有待提高",
                    "pass": "论文结构不够合理，表达不够清晰，图表质量较差",
                    "fail": "论文结构混乱，表达不清，图表质量极差"
                }
            }
        ],
        "excluded_indicators": [],
        "keywords": ["实物", "样机", "硬件", "制作", "装配", "调试", "电路", "机械结构", "原型", "产品"]
    },
    
    "traditional_mechanical": {
        "name": "传统机械类项目评价标准",
        "description": "适用于传统机械设计、结构设计、工艺设计等项目",
        "indicators": [
            {
                "id": "MEC_01",
                "name": "结构设计",
                "description": "结构方案、设计计算、强度校核",
                "weight": 30,
                "grade_levels": {
                    "excellent": "结构方案合理，设计计算准确，强度校核完整",
                    "good": "结构方案较合理，设计计算较准确，强度校核较完整",
                    "medium": "结构方案一般，设计计算基本正确，强度校核不够完整",
                    "pass": "结构方案存在不足，设计计算有小错误，强度校核缺失",
                    "fail": "结构方案错误或设计计算严重错误"
                }
            },
            {
                "id": "MEC_02",
                "name": "图纸绘制",
                "description": "图纸规范性、完整性、准确性",
                "weight": 25,
                "grade_levels": {
                    "excellent": "图纸规范完整，表达准确清晰，符合国家标准",
                    "good": "图纸较规范完整，表达较准确，基本符合国家标准",
                    "medium": "图纸基本规范，表达一般，部分不符合国家标准",
                    "pass": "图纸不够规范，表达不够准确，多处不符合国家标准",
                    "fail": "图纸混乱或严重不符合标准"
                }
            },
            {
                "id": "MEC_03",
                "name": "工艺设计",
                "description": "加工工艺、装配工艺、工艺文件",
                "weight": 20,
                "grade_levels": {
                    "excellent": "加工工艺合理，装配工艺清晰，工艺文件完整",
                    "good": "加工工艺较合理，装配工艺较清晰，工艺文件较完整",
                    "medium": "加工工艺一般，装配工艺基本清晰，工艺文件不够完整",
                    "pass": "加工工艺简单，装配工艺不够清晰，工艺文件缺失",
                    "fail": "工艺设计错误或缺失"
                }
            },
            {
                "id": "MEC_04",
                "name": "计算分析",
                "description": "理论计算、有限元分析、优化设计",
                "weight": 15,
                "grade_levels": {
                    "excellent": "理论计算准确，有限元分析合理，优化设计有效",
                    "good": "理论计算较准确，有限元分析较合理，有优化设计",
                    "medium": "理论计算基本正确，有限元分析一般，优化设计不足",
                    "pass": "理论计算有小错误，有限元分析简单，缺乏优化设计",
                    "fail": "计算分析错误或缺失"
                }
            },
            {
                "id": "MEC_05",
                "name": "文档撰写",
                "description": "论文结构、表达清晰度、图表质量",
                "weight": 10,
                "grade_levels": {
                    "excellent": "论文结构严谨，表达清晰流畅，图表规范美观，格式完全符合要求",
                    "good": "论文结构合理，表达清晰，图表较规范，格式符合要求",
                    "medium": "论文结构基本合理，表达一般，图表质量有待提高",
                    "pass": "论文结构不够合理，表达不够清晰，图表质量较差",
                    "fail": "论文结构混乱，表达不清，图表质量极差"
                }
            }
        ],
        "excluded_indicators": [],
        "keywords": ["机械设计", "结构设计", "传动", "齿轮", "轴承", "轴", "箱体", "减速器", "机构", "工艺"]
    },
    
    "mixed": {
        "name": "混合类项目评价标准",
        "description": "适用于包含多种技术手段的综合性项目",
        "indicators": [
            {
                "id": "MIX_01",
                "name": "方案设计",
                "description": "总体方案、技术路线、系统集成",
                "weight": 25,
                "grade_levels": {
                    "excellent": "总体方案创新，技术路线清晰，系统集成合理",
                    "good": "总体方案合理，技术路线较清晰，系统集成较合理",
                    "medium": "总体方案一般，技术路线基本清晰，系统集成一般",
                    "pass": "总体方案存在不足，技术路线不够清晰",
                    "fail": "方案设计错误或不可行"
                }
            },
            {
                "id": "MIX_02",
                "name": "技术实现",
                "description": "关键技术、实现方法、技术难点",
                "weight": 30,
                "grade_levels": {
                    "excellent": "关键技术先进，实现方法科学，技术难点突破",
                    "good": "关键技术较好，实现方法合理，技术难点有进展",
                    "medium": "关键技术一般，实现方法基本可行，技术难点部分解决",
                    "pass": "关键技术简单，实现方法单一，技术难点未解决",
                    "fail": "技术实现失败或方法错误"
                }
            },
            {
                "id": "MIX_03",
                "name": "验证测试",
                "description": "测试方法、验证结果、性能评估",
                "weight": 25,
                "grade_levels": {
                    "excellent": "测试方法科学，验证结果可靠，性能评估全面",
                    "good": "测试方法较科学，验证结果较可靠，性能评估较好",
                    "medium": "测试方法一般，验证结果基本可靠，性能评估不够全面",
                    "pass": "测试方法简单，验证结果不够可靠，性能评估缺失",
                    "fail": "缺乏验证测试或测试方法错误"
                }
            },
            {
                "id": "MIX_04",
                "name": "文档撰写",
                "description": "论文结构、表达清晰度、图表质量",
                "weight": 20,
                "grade_levels": {
                    "excellent": "论文结构严谨，表达清晰流畅，图表规范美观，格式完全符合要求",
                    "good": "论文结构合理，表达清晰，图表较规范，格式符合要求",
                    "medium": "论文结构基本合理，表达一般，图表质量有待提高",
                    "pass": "论文结构不够合理，表达不够清晰，图表质量较差",
                    "fail": "论文结构混乱，表达不清，图表质量极差"
                }
            }
        ],
        "excluded_indicators": [],
        "keywords": ["综合", "集成", "系统", "平台", "智能", "自动化", "机器人", "物联网"]
    }
}

def detect_project_type(title: str, content: str) -> ProjectType:
    """
    根据项目标题和内容检测项目类型
    
    Args:
        title: 项目标题
        content: 项目内容
        
    Returns:
        项目类型
    """
    combined_text = f"{title} {content}".lower()
    
    type_scores = {}
    for type_key, type_config in EVALUATION_STANDARDS.items():
        keywords = type_config.get("keywords", [])
        score = sum(1 for keyword in keywords if keyword.lower() in combined_text)
        type_scores[type_key] = score
    
    max_score = max(type_scores.values())
    if max_score == 0:
        return ProjectType.UNKNOWN
    
    best_type = max(type_scores, key=type_scores.get)
    return ProjectType(best_type)

def get_evaluation_standards(project_type: ProjectType) -> Dict:
    """
    获取指定项目类型的评价标准
    
    Args:
        project_type: 项目类型
        
    Returns:
        评价标准配置
    """
    type_key = project_type.value
    return EVALUATION_STANDARDS.get(type_key, EVALUATION_STANDARDS["mixed"])

def build_deterministic_evaluation_prompt(
    submission_content: str,
    project_type: ProjectType,
    student_info: Dict = None,
    guidance_content: str = None
) -> str:
    """
    构建确定性评价提示词
    
    Args:
        submission_content: 提交内容
        project_type: 项目类型
        student_info: 学生信息
        guidance_content: 评价指导文件内容
        
    Returns:
        评价提示词
    """
    standards = get_evaluation_standards(project_type)
    type_name = PROJECT_TYPE_NAMES.get(project_type, "未知类型")
    
    indicators_text = ""
    for indicator in standards["indicators"]:
        indicators_text += f"""
**{indicator['id']}: {indicator['name']}** (权重: {indicator['weight']}%)
- 描述: {indicator['description']}
- 优秀(90-100分): {indicator['grade_levels']['excellent']}
- 良好(80-89分): {indicator['grade_levels']['good']}
- 中等(70-79分): {indicator['grade_levels']['medium']}
- 及格(60-69分): {indicator['grade_levels']['pass']}
- 不及格(<60分): {indicator['grade_levels']['fail']}

"""
    
    excluded_text = ""
    if standards.get("excluded_indicators"):
        excluded_text = f"""
**注意**: 本项目类型({type_name})不评价以下内容: {', '.join(standards['excluded_indicators'])}
如果学生提交内容中包含这些内容，请在评分时说明这些内容不在评价范围内。

"""
    
    student_info_text = ""
    if student_info:
        student_info_text = f"学生信息: {json.dumps(student_info, ensure_ascii=False)}\n"
    
    guidance_text = ""
    if guidance_content:
        guidance_text = f"""
## 评价指导文件

以下是评价指导文件的内容，请在评价时参考：

{guidance_content}

"""
    
    prompt = f"""# 毕业设计评价任务

## 项目类型
{type_name}

{student_info_text}
{guidance_text}
## 评价标准（必须严格按此标准评分）

{indicators_text}

{excluded_text}
## 学生提交内容

{submission_content}

## 评分要求

1. **严格按标准评分**: 必须严格按照上述评价标准进行评分，不得随意发挥
2. **引用证据**: 每个评分必须引用学生提交内容中的具体证据
3. **等级对应**: 根据学生表现确定等级，然后给出对应分数区间内的具体分数
4. **一致性**: 同一质量的作品应得到相近的分数
5. **排除项**: 对于不在评价范围内的内容，不得扣分
6. **参考指导文件**: 如果提供了评价指导文件，请参考其中的要求和标准进行评价

## 输出格式

请以JSON格式返回评价结果，结构如下：
{{
    "project_type": "{project_type.value}",
    "overall_score": 85,
    "dimension_scores": [
        {{
            "indicator_id": "指标编号",
            "indicator_name": "指标名称",
            "score": 85,
            "grade_level": "良好",
            "evidence": ["具体证据1", "具体证据2"],
            "reasoning": "评分理由（必须引用具体内容）"
        }}
    ],
    "strengths": ["优势1", "优势2"],
    "weaknesses": ["劣势1", "劣势2"],
    "overall_evaluation": "总体评价（200字以上）"
}}
"""
    return prompt

def get_grade_level(score: float) -> str:
    """
    根据分数获取等级
    
    Args:
        score: 分数
        
    Returns:
        等级名称
    """
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
