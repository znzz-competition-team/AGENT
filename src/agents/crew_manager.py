from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import uuid
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 尝试导入crewai和ChatOpenAI，如果不可用则使用模拟评估
try:
    from crewai import Crew, Process
    from langchain_openai import ChatOpenAI
    from agents.evaluation_agents import (
        EvaluationAgent,
        AcademicPerformanceAgent,
        CommunicationSkillsAgent,
        LeadershipAgent,
        TeamworkAgent,
        CreativityAgent,
        ProblemSolvingAgent,
        TimeManagementAgent,
        AdaptabilityAgent,
        TechnicalSkillsAgent,
        CriticalThinkingAgent,
        ComprehensiveEvaluator
    )
    CREWAI_AVAILABLE = True
except ImportError as e:
    CREWAI_AVAILABLE = False
    print(f"CrewAI not available, using mock evaluation: {str(e)}")

from models.schemas import EvaluationResult, DimensionScore, EvaluationDimension
from config import settings
from utils.data_fusion import DataFusionService

logger = logging.getLogger(__name__)

class StudentEvaluationCrew:
    def __init__(self, dimensions: Optional[List[EvaluationDimension]] = None, ai_config: Optional[Dict[str, Any]] = None):
        self.dimensions = dimensions or list(EvaluationDimension)
        self.ai_config = ai_config
        
        # 使用传入的AI配置或默认配置
        if CREWAI_AVAILABLE and ai_config:
            self.llm = ChatOpenAI(
                model=ai_config.get('model', settings.openai_model),
                temperature=ai_config.get('temperature', settings.openai_temperature),
                max_tokens=ai_config.get('max_tokens', settings.openai_max_tokens),
                api_key=ai_config.get('api_key', settings.openai_api_key),
                base_url=ai_config.get('base_url')
            )
            self.llm_config = {"llm": self.llm}
            self.agents = self._initialize_agents()
        else:
            self.llm = None
            self.llm_config = {}
            self.agents = {}
            print("Using mock evaluation mode")
        
    def _initialize_agents(self):
        agents = {}
        
        for dimension in self.dimensions:
            if dimension == EvaluationDimension.ACADEMIC_PERFORMANCE:
                agents["academic"] = AcademicPerformanceAgent(self.llm_config)
            elif dimension == EvaluationDimension.COMMUNICATION_SKILLS:
                agents["communication"] = CommunicationSkillsAgent(self.llm_config)
            elif dimension == EvaluationDimension.LEADERSHIP:
                agents["leadership"] = LeadershipAgent(self.llm_config)
            elif dimension == EvaluationDimension.TEAMWORK:
                agents["teamwork"] = TeamworkAgent(self.llm_config)
            elif dimension == EvaluationDimension.CREATIVITY:
                agents["creativity"] = CreativityAgent(self.llm_config)
            elif dimension == EvaluationDimension.PROBLEM_SOLVING:
                agents["problem_solving"] = ProblemSolvingAgent(self.llm_config)
            elif dimension == EvaluationDimension.TIME_MANAGEMENT:
                agents["time_management"] = TimeManagementAgent(self.llm_config)
            elif dimension == EvaluationDimension.ADAPTABILITY:
                agents["adaptability"] = AdaptabilityAgent(self.llm_config)
            elif dimension == EvaluationDimension.TECHNICAL_SKILLS:
                agents["technical_skills"] = TechnicalSkillsAgent(self.llm_config)
            elif dimension == EvaluationDimension.CRITICAL_THINKING:
                agents["critical_thinking"] = CriticalThinkingAgent(self.llm_config)
        
        agents["comprehensive"] = ComprehensiveEvaluator(self.llm_config)
        return agents
    
    def evaluate_student(self, student_id: str, student_data: Dict[str, Any], 
                        media_data: Any) -> EvaluationResult:
        evaluation_id = str(uuid.uuid4())
        
        # 确保输入参数是字典类型
        if not isinstance(student_data, dict):
            student_data = {}
        # 不再强制转换media_data为字典，保留原始类型
        
        # 如果CrewAI不可用，返回模拟评估结果
        if not CREWAI_AVAILABLE:
            print(f"Generating mock evaluation for student {student_id}")
            
            # 生成模拟的维度评分
            dimension_scores = []
            for dimension in self.dimensions:
                dimension_score = DimensionScore(
                    dimension=dimension,
                    score=7.5,  # 模拟评分
                    confidence=0.8,  # 模拟置信度
                    evidence=[f"模拟评估证据: {dimension.value}"],
                    reasoning=f"这是{dimension.value}维度的模拟评估理由"
                )
                dimension_scores.append(dimension_score)
            
            # 生成模拟的综合评估结果
            comprehensive_result = {
                "strengths": ["学习能力强", "团队协作能力好", "创新思维活跃"],
                "areas_for_improvement": ["时间管理需要加强", "沟通表达能力待提高"],
                "recommendations": ["制定合理的学习计划", "多参与团队项目", "提高语言表达能力"]
            }
            
            # 计算综合评分
            overall_score = 7.8
            
            result = EvaluationResult(
                student_id=student_id,
                evaluation_id=evaluation_id,
                dimension_scores=dimension_scores,
                overall_score=overall_score,
                strengths=comprehensive_result.get("strengths", []),
                areas_for_improvement=comprehensive_result.get("areas_for_improvement", []),
                recommendations=comprehensive_result.get("recommendations", []),
                evaluated_at=datetime.now(),
                evaluator_agent="mock_evaluator"
            )
            
            print(f"Mock evaluation generated for student {student_id}")
            return result
        
        try:
            dimension_scores = self._evaluate_dimensions(student_id, student_data, media_data)
            
            comprehensive_result = self._generate_comprehensive_evaluation(
                student_id, student_data, dimension_scores
            )
            
            overall_score = self._calculate_overall_score(dimension_scores)
            
            result = EvaluationResult(
                student_id=student_id,
                evaluation_id=evaluation_id,
                dimension_scores=dimension_scores,
                overall_score=overall_score,
                strengths=comprehensive_result.get("strengths", []),
                areas_for_improvement=comprehensive_result.get("areas_for_improvement", []),
                recommendations=comprehensive_result.get("recommendations", []),
                evaluated_at=datetime.now(),
                evaluator_agent="comprehensive_evaluator"
            )
            
            logger.info(f"Successfully evaluated student {student_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating student {student_id}: {str(e)}")
            raise

    def _evaluate_dimensions(self, student_id: str, student_data: Dict[str, Any], 
                           media_data: Any) -> List[DimensionScore]:
        dimension_scores = []
        
        for dimension in self.dimensions:
            try:
                # 修复agent_key匹配问题
                agent_key_mapping = {
                    EvaluationDimension.ACADEMIC_PERFORMANCE: "academic",
                    EvaluationDimension.COMMUNICATION_SKILLS: "communication",
                    EvaluationDimension.LEADERSHIP: "leadership",
                    EvaluationDimension.TEAMWORK: "teamwork",
                    EvaluationDimension.CREATIVITY: "creativity",
                    EvaluationDimension.PROBLEM_SOLVING: "problem_solving",
                    EvaluationDimension.TIME_MANAGEMENT: "time_management",
                    EvaluationDimension.ADAPTABILITY: "adaptability",
                    EvaluationDimension.TECHNICAL_SKILLS: "technical_skills",
                    EvaluationDimension.CRITICAL_THINKING: "critical_thinking"
                }
                
                agent_key = agent_key_mapping.get(dimension)
                if not agent_key or agent_key not in self.agents:
                    logger.warning(f"No agent found for dimension: {dimension.value}")
                    continue
                
                agent = self.agents[agent_key]
                score_data = self._evaluate_with_agent(
                    agent, dimension, student_data, media_data
                )
                
                dimension_score = DimensionScore(
                    dimension=dimension,
                    score=score_data.get("score", 5.0),
                    confidence=score_data.get("confidence", 0.7),
                    evidence=score_data.get("evidence", []),
                    reasoning=score_data.get("reasoning", "")
                )
                
                dimension_scores.append(dimension_score)
                
            except Exception as e:
                logger.error(f"Error evaluating dimension {dimension}: {str(e)}")
                continue
        
        return dimension_scores
    
    def _evaluate_with_agent(self, agent, dimension: EvaluationDimension,
                           student_data: Dict[str, Any], media_data: Any) -> Dict[str, Any]:
        # 准备格式化后的上下文信息用于任务描述
        context_info = {
            "student_info": student_data,
            "media_content": media_data,
            "dimension": dimension.value
        }
        
        # 根据不同的维度定制评估提示
        dimension_name = {
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
        }.get(dimension, dimension.value)
        
        # 获取媒体内容，不再强制转换为字典
        media_content = context_info['media_content']
        
        # 确保student_data是字典类型
        if not isinstance(student_data, dict):
            student_data = {}
        
        # 确保所有值都是字符串类型
        student_name = str(student_data.get('name', '未知'))
        student_grade = str(student_data.get('grade', '未知'))
        student_major = str(student_data.get('major', '未知'))
        
        # 针对技术能力的特殊评估提示
        if dimension == EvaluationDimension.TECHNICAL_SKILLS:
            description = ("请基于以下信息，评估学生在" + str(dimension_name) + "维度的表现：\n\n" +
                         "学生信息：\n" +
                         "- 姓名：" + student_name + "\n" +
                         "- 年级：" + student_grade + "\n" +
                         "- 专业：" + student_major + "\n\n" +
                         "媒体内容：\n" +
                         self._format_media_data(media_content) + "\n\n" +
                         "请从以下方面评估技术能力：\n" +
                         "1. 代码质量和规范性\n" +
                         "2. 算法设计和效率\n" +
                         "3. 技术实现的创新性\n" +
                         "4. 问题解决的技术方案\n" +
                         "5. 技术文档的完整性\n\n" +
                         "请给出：\n" +
                         "1. 0-10分的评分\n" +
                         "2. 评分的置信度（0-1）\n" +
                         "3. 支撑评分的证据\n" +
                         "4. 评分的详细理由")
        # 针对批判性思维的特殊评估提示
        elif dimension == EvaluationDimension.CRITICAL_THINKING:
            description = ("请基于以下信息，评估学生在" + str(dimension_name) + "维度的表现：\n\n" +
                         "学生信息：\n" +
                         "- 姓名：" + student_name + "\n" +
                         "- 年级：" + student_grade + "\n" +
                         "- 专业：" + student_major + "\n\n" +
                         "媒体内容：\n" +
                         self._format_media_data(media_content) + "\n\n" +
                         "请从以下方面评估批判性思维：\n" +
                         "1. 论证结构的逻辑性\n" +
                         "2. 证据的充分性和可靠性\n" +
                         "3. 对不同观点的考虑\n" +
                         "4. 分析问题的深度和广度\n" +
                         "5. 结论的合理性\n\n" +
                         "请给出：\n" +
                         "1. 0-10分的评分\n" +
                         "2. 评分的置信度（0-1）\n" +
                         "3. 支撑评分的证据\n" +
                         "4. 评分的详细理由")
        # 其他维度的通用评估提示
        else:
            description = ("请基于以下信息，评估学生在" + str(dimension_name) + "维度的表现：\n\n" +
                         "学生信息：\n" +
                         "- 姓名：" + student_name + "\n" +
                         "- 年级：" + student_grade + "\n" +
                         "- 专业：" + student_major + "\n\n" +
                         "媒体内容：\n" +
                         self._format_media_data(media_content) + "\n\n" +
                         "请从以下方面进行评估：\n" +
                         "1. 能力水平\n" +
                         "2. 表现一致性\n" +
                         "3. 发展潜力\n" +
                         "4. 实际应用能力\n\n" +
                         "请给出：\n" +
                         "1. 0-10分的评分\n" +
                         "2. 评分的置信度（0-1）\n" +
                         "3. 支撑评分的证据\n" +
                         "4. 评分的详细理由")
        
        expected_output = """
        请以JSON格式返回评估结果：
        {
            "score": 评分（0-10）,
            "confidence": 置信度（0-1）,
            "evidence": ["证据1", "证据2", ...],
            "reasoning": "评分理由"
        }
        """
        
        task = agent.create_task(description, expected_output)
        crew = Crew(
            agents=[agent.agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            
            import json
            try:
                score_data = json.loads(str(result))
            except json.JSONDecodeError:
                # 提取纯文本内容，移除代码格式
                reasoning_text = str(result)
                # 移除JSON代码块
                if '```json' in reasoning_text:
                    reasoning_text = reasoning_text.replace('```json', '').replace('```', '').strip()
                # 移除JSON格式标记
                if reasoning_text.strip().startswith('{') and reasoning_text.strip().endswith('}'):
                    try:
                        # 尝试解析JSON并提取reasoning字段
                        parsed = json.loads(reasoning_text)
                        if 'reasoning' in parsed:
                            reasoning_text = parsed['reasoning']
                    except:
                        pass
                score_data = {
                    "score": 5.0,
                    "confidence": 0.5,
                    "evidence": [],
                    "reasoning": reasoning_text
                }
            
            return score_data
            
        except Exception as e:
            logger.error(f"Error in agent evaluation: {str(e)}")
            return {
                "score": 5.0,
                "confidence": 0.3,
                "evidence": [],
                "reasoning": "评估过程中出现错误: " + str(e)
            }
    
    def _format_media_data(self, media_data: Any) -> str:
        formatted = []
        
        try:
            if isinstance(media_data, dict):
                # 处理字典类型的媒体数据
                for media_name, data in media_data.items():
                    # 确保media_name是字符串
                    media_name_str = str(media_name)
                    if isinstance(data, dict):
                        # 处理媒体处理结果字典
                        media_type = data.get("media_type", "unknown")
                        status = data.get("status", "unknown")
                        
                        if status == "processed" or status == "success":
                            if media_type == "video":
                                duration = data.get("duration", 0)
                                try:
                                    # 安全格式化
                                    formatted.append("视频文件: " + media_name_str + " (时长: " + str(round(float(duration), 2)) + "秒)")
                                except (ValueError, TypeError):
                                    formatted.append("视频文件: " + media_name_str)
                            elif media_type == "audio":
                                duration = data.get("duration", 0)
                                transcript = data.get("transcript", "")
                                try:
                                    # 安全格式化
                                    formatted.append("音频文件: " + media_name_str + " (时长: " + str(round(float(duration), 2)) + "秒)")
                                except (ValueError, TypeError):
                                    formatted.append("音频文件: " + media_name_str)
                                if transcript:
                                    try:
                                        # 安全格式化
                                        formatted.append("转录文本: " + str(transcript)[:200] + "...")
                                    except:
                                        formatted.append("转录文本: [无法显示]")
                            elif media_type == "document":
                                content = data.get("content", "")
                                pages = data.get("pages", 0)
                                try:
                                    # 安全格式化
                                    formatted.append("文档文件: " + media_name_str + " (页数: " + str(int(pages)) + ")")
                                except (ValueError, TypeError):
                                    formatted.append("文档文件: " + media_name_str)
                                if content:
                                    # 提取文档内容的前200个字符
                                    try:
                                        if isinstance(content, dict):
                                            full_text = content.get("full_text", "")
                                            if full_text:
                                                # 安全格式化
                                                formatted.append("文档内容: " + str(full_text)[:200] + "...")
                                        else:
                                            # 安全格式化
                                            formatted.append("文档内容: " + str(content)[:200] + "...")
                                    except:
                                        formatted.append("文档内容: [无法显示]")
                    else:
                        # 处理直接的文本内容（如文字提交）
                        try:
                            if str(media_name).startswith("text_"):
                                # 安全格式化
                                formatted.append("文字提交: " + str(media_name).replace('text_', ''))
                                if isinstance(data, str) and data:
                                    # 安全格式化
                                    formatted.append("内容: " + str(data)[:200] + "...")
                            else:
                                # 其他类型的内容
                                formatted.append("其他内容: " + media_name_str)
                                if isinstance(data, str) and data:
                                    # 安全格式化
                                    formatted.append("内容: " + str(data)[:200] + "...")
                        except:
                            formatted.append("其他内容: " + media_name_str)
            elif isinstance(media_data, list):
                # 处理列表类型的媒体数据
                for i, item in enumerate(media_data):
                    try:
                        if isinstance(item, dict):
                            # 处理列表中的字典项
                            file_name = item.get('file_name', f'文件{i+1}')
                            media_type = item.get('media_type', 'unknown')
                            formatted.append(f"{media_type}文件: {file_name}")
                        else:
                            # 处理其他类型的列表项
                            formatted.append(f"其他内容: {str(item)}")
                    except:
                        formatted.append(f"文件{i+1}: [无法显示]")
            else:
                # 处理其他类型的媒体数据
                formatted.append("媒体数据: " + str(media_data))
        except Exception as e:
            # 如果整个处理过程出错，返回错误信息
            return "媒体数据处理出错: " + str(e)
        
        return "\n".join(formatted) if formatted else "无媒体内容"
    
    def _generate_comprehensive_evaluation(self, student_id: str, student_data: Dict[str, Any],
                                          dimension_scores: List[DimensionScore]) -> Dict[str, Any]:
        agent = self.agents["comprehensive"]
        
        scores_summary = "\n".join([
            f"- {ds.dimension.value}: {ds.score}/10 (置信度: {ds.confidence})"
            for ds in dimension_scores
        ])
        
        # 确保student_data是字典类型
        if not isinstance(student_data, dict):
            student_data = {}
        
        # 确保所有值都是字符串类型
        student_name = str(student_data.get('name', '未知'))
        student_grade = str(student_data.get('grade', '未知'))
        student_major = str(student_data.get('major', '未知'))
        
        description = ("请基于以下各维度的评估结果，为学生" + student_name + "提供综合评估：\n\n" +
                     "学生信息：\n" +
                     "- 学号：" + str(student_id) + "\n" +
                     "- 姓名：" + student_name + "\n" +
                     "- 年级：" + student_grade + "\n" +
                     "- 专业：" + student_major + "\n\n" +
                     "各维度评分：\n" +
                     scores_summary + "\n\n" +
                     "请提供：\n" +
                     "1. 学生的主要优势（3-5条）\n" +
                     "2. 需要改进的方面（3-5条）\n" +
                     "3. 具体的改进建议（5-8条）")
        
        expected_output = """
        请以JSON格式返回综合评估结果：
        {
            "strengths": ["优势1", "优势2", ...],
            "areas_for_improvement": ["改进点1", "改进点2", ...],
            "recommendations": ["建议1", "建议2", ...]
        }
        """
        
        task = agent.create_task(description, expected_output)
        crew = Crew(
            agents=[agent.agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            
            import json
            try:
                comprehensive_data = json.loads(str(result))
            except json.JSONDecodeError:
                comprehensive_data = {
                    "strengths": ["需要更多信息"],
                    "areas_for_improvement": ["需要更多信息"],
                    "recommendations": ["需要更多信息"]
                }
            
            return comprehensive_data
            
        except Exception as e:
            logger.error(f"Error in comprehensive evaluation: {str(e)}")
            return {
                "strengths": [],
                "areas_for_improvement": [],
                "recommendations": []
            }
    
    def _calculate_overall_score(self, dimension_scores: List[DimensionScore]) -> float:
        if not dimension_scores:
            return 5.0
        
        # 使用数据融合服务计算加权平均分
        data_fusion_service = DataFusionService()
        return round(data_fusion_service.calculate_weighted_score(dimension_scores), 2)
    
    def batch_evaluate(self, students_data: List[Dict[str, Any]], 
                      media_data_dict: Dict[str, Dict[str, Any]]) -> List[EvaluationResult]:
        results = []
        
        for student_data in students_data:
            student_id = student_data.get("student_id")
            if not student_id:
                continue
            
            media_data = media_data_dict.get(student_id, {})
            
            try:
                result = self.evaluate_student(student_id, student_data, media_data)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to evaluate student {student_id}: {str(e)}")
                continue
        
        return results