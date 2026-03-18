from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class EvaluationAgent:
    def __init__(self, name: str, role: str, goal: str, backstory: str, 
                 llm_config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.llm_config = llm_config or {}
        self.agent = self._create_agent()
        
    def _create_agent(self) -> Agent:
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            allow_delegation=False,
            **self.llm_config
        )
    
    def create_task(self, description: str, expected_output: str, 
                   context: Optional[Dict[str, Any]] = None) -> Task:
        return Task(
            description=description,
            expected_output=expected_output,
            agent=self.agent,
            context=context
        )

class AcademicPerformanceAgent(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="academic_evaluator",
            role="学术表现评估专家",
            goal="基于学生的作业、考试、项目等材料，全面评估学生的学术表现",
            backstory="你是一位经验丰富的教育评估专家，拥有20年的学术评估经验。你擅长分析学生的学术成果，识别其学术优势和需要改进的领域。",
            llm_config=llm_config
        )

class CommunicationSkillsAgent(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="communication_evaluator",
            role="沟通能力评估专家",
            goal="通过分析学生的演讲、讨论、写作等表现，评估其沟通能力",
            backstory="你是一位专业的沟通能力评估师，擅长通过语言表达、非语言沟通、书面表达等多个维度评估学生的沟通技巧。",
            llm_config=llm_config
        )

class LeadershipAgent(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="leadership_evaluator",
            role="领导力评估专家",
            goal="评估学生在团队项目、组织活动中的领导力表现",
            backstory="你是一位领导力发展专家，曾在多个组织中担任领导力教练，擅长识别和培养领导力潜质。",
            llm_config=llm_config
        )

class TeamworkAgent(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="teamwork_evaluator",
            role="团队协作评估专家",
            goal="评估学生在团队合作中的表现，包括协作能力、团队贡献等",
            backstory="你是一位团队协作专家，拥有丰富的团队管理和团队建设经验，擅长评估团队协作效果。",
            llm_config=llm_config
        )

class CreativityAgent(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="creativity_evaluator",
            role="创新能力评估专家",
            goal="评估学生的创新思维、创意表达和问题解决能力",
            backstory="你是一位创新思维专家，曾在多个创新项目中担任顾问，擅长识别和培养创新潜质。",
            llm_config=llm_config
        )

class ProblemSolvingAgent(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="problem_solving_evaluator",
            role="问题解决能力评估专家",
            goal="评估学生分析问题、制定解决方案和执行方案的能力",
            backstory="你是一位问题解决专家，拥有丰富的咨询和培训经验，擅长评估和提升问题解决能力。",
            llm_config=llm_config
        )

class TimeManagementAgent(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="time_management_evaluator",
            role="时间管理评估专家",
            goal="评估学生的时间管理能力、任务规划和执行效率",
            backstory="你是一位时间管理专家，擅长通过任务完成情况、时间分配等维度评估时间管理能力。",
            llm_config=llm_config
        )

class AdaptabilityAgent(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="adaptability_evaluator",
            role="适应能力评估专家",
            goal="评估学生在面对新环境、新挑战时的适应和调整能力",
            backstory="你是一位适应能力评估专家，擅长通过学生在不同情境下的表现评估其适应能力。",
            llm_config=llm_config
        )

class TechnicalSkillsAgent(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="technical_skills_evaluator",
            role="技术能力评估专家",
            goal="评估学生的代码质量、算法设计和技术实现能力",
            backstory="你是一位技术能力评估专家，拥有丰富的编程和算法经验，擅长评估学生的技术能力水平。",
            llm_config=llm_config
        )

class CriticalThinkingAgent(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="critical_thinking_evaluator",
            role="批判性思维评估专家",
            goal="评估学生的论证能力、逻辑思维和批判性分析能力",
            backstory="你是一位批判性思维评估专家，擅长分析学生的论证结构、逻辑推理和批判性思考能力。",
            llm_config=llm_config
        )

class ComprehensiveEvaluator(EvaluationAgent):
    def __init__(self, llm_config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="comprehensive_evaluator",
            role="综合评估专家",
            goal="整合各维度的评估结果，提供全面的学生评估报告和改进建议",
            backstory="你是一位综合评估专家，擅长整合多维度信息，提供全面、客观、有建设性的评估报告。",
            llm_config=llm_config
        )