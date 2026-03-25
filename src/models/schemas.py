from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class MediaType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    TEXT = "text"

class StudentProfile(BaseModel):
    student_id: str
    name: str
    age: Optional[int] = None
    grade: Optional[str] = None
    major: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

class MediaFile(BaseModel):
    file_path: str
    media_type: MediaType
    duration: Optional[float] = None
    size_bytes: int
    uploaded_at: datetime = Field(default_factory=datetime.now)
    processed: bool = False

class EvaluationDimension(str, Enum):
    ACADEMIC_PERFORMANCE = "academic_performance"
    COMMUNICATION_SKILLS = "communication_skills"
    LEADERSHIP = "leadership"
    TEAMWORK = "teamwork"
    CREATIVITY = "creativity"
    PROBLEM_SOLVING = "problem_solving"
    TIME_MANAGEMENT = "time_management"
    ADAPTABILITY = "adaptability"
    TECHNICAL_SKILLS = "technical_skills"
    CRITICAL_THINKING = "critical_thinking"

class DimensionScore(BaseModel):
    dimension: EvaluationDimension
    score: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    evidence: List[str] = []
    reasoning: str

class EvaluationResult(BaseModel):
    student_id: str
    evaluation_id: str
    dimension_scores: List[DimensionScore]
    overall_score: float = Field(ge=0, le=10)
    strengths: List[str] = []
    areas_for_improvement: List[str] = []
    recommendations: List[str] = []
    evaluated_at: datetime = Field(default_factory=datetime.now)
    evaluator_agent: str

class AgentTask(BaseModel):
    task_id: str
    agent_name: str
    task_description: str
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class ProcessingLog(BaseModel):
    log_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    level: str
    message: str
    details: Optional[Dict[str, Any]] = None


# API 相关的 Schema 定义
class StudentCreate(BaseModel):
    student_id: str
    name: str
    age: Optional[int] = None
    grade: Optional[str] = None
    major: Optional[str] = None

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    grade: Optional[str] = None
    major: Optional[str] = None

class StudentResponse(BaseModel):
    id: int
    student_id: str
    name: str
    age: Optional[int] = None
    grade: Optional[str] = None
    major: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class SubmissionType(str, Enum):
    FILE = "file"
    TEXT = "text"

class SubmissionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class SubmissionCreate(BaseModel):
    student_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    submission_type: SubmissionType = SubmissionType.FILE
    text_content: Optional[str] = None

class SubmissionResponse(BaseModel):
    id: int
    submission_id: str
    student_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    submission_type: SubmissionType
    text_content: Optional[str] = None
    status: SubmissionStatus
    created_at: datetime
    updated_at: datetime

class MediaFileResponse(BaseModel):
    id: int
    submission_id: int
    file_path: str
    file_name: str
    media_type: MediaType
    duration: Optional[float] = None
    size_bytes: int
    processed: bool
    uploaded_at: datetime

class DimensionScoreResponse(BaseModel):
    dimension: EvaluationDimension
    score: float
    confidence: float
    evidence: List[str]
    reasoning: str

class EvaluationResultResponse(BaseModel):
    id: int
    student_id: str
    submission_id: int
    overall_score: float
    dimension_scores: List[DimensionScoreResponse]
    strengths: List[str]
    areas_for_improvement: List[str]
    recommendations: List[str]
    evaluated_at: datetime

class EvaluationRequest(BaseModel):
    submission_id: str
    stage: Optional[str] = None
    stage_progress: Optional[float] = None  # 0.0-1.0 之间的进度值

class EvaluationResponse(BaseModel):
    evaluation_id: str
    student_id: str
    overall_score: float
    dimension_scores: List[DimensionScoreResponse]
    strengths: List[str]
    areas_for_improvement: List[str]
    recommendations: List[str]
    evaluated_at: datetime
    evaluator_agent: str
    stage: Optional[str] = None
    stage_progress: Optional[float] = None  # 0.0-1.0 之间的进度值

class ProgressReportResponse(BaseModel):
    student_id: str
    report: str
    generated_at: datetime
    total_evaluations: int
    time_range: dict
    key_insights: List[str]
    improvement_areas: List[str]
    report_id: Optional[str] = None