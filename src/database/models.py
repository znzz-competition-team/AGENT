from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Student(Base):
    __tablename__ = "students"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)
    grade = Column(String(50), nullable=True)
    major = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    submissions = relationship("Submission", back_populates="student")
    evaluation_results = relationship("EvaluationResult", back_populates="student")
    progress_reports = relationship("ProgressReport", back_populates="student")
    handwriting_records = relationship("HandwritingRecord", back_populates="student")

class MediaFile(Base):
    __tablename__ = "media_files"
    
    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String(255), nullable=False)
    file_name = Column(String(100), nullable=False)
    media_type = Column(String(20), nullable=False)  # video, audio, document
    size_bytes = Column(Integer, nullable=False)
    duration = Column(Float, nullable=True)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=True)
    submission = relationship("Submission", back_populates="media_files")

class Submission(Base):
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(String(50), unique=True, index=True, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    submission_type = Column(String(20), default="file")  # file, text
    text_content = Column(Text, nullable=True)  # 文字提交内容
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship("Student", back_populates="submissions")
    media_files = relationship("MediaFile", back_populates="submission")
    evaluation_result = relationship("EvaluationResult", back_populates="submission", uselist=False)

class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    
    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(String(50), unique=True, index=True, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    overall_score = Column(Float, nullable=False)
    strengths = Column(Text, nullable=True)
    areas_for_improvement = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    evaluator_agent = Column(String(100), nullable=False)
    stage_progress = Column(Float, nullable=True)  # 0.0-1.0
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship("Student", back_populates="evaluation_results")
    submission = relationship("Submission", back_populates="evaluation_result")
    dimension_scores = relationship("DimensionScore", back_populates="evaluation_result")

class DimensionScore(Base):
    __tablename__ = "dimension_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluation_results.id"), nullable=False)
    dimension = Column(String(50), nullable=False)
    score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    evidence = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    
    evaluation_result = relationship("EvaluationResult", back_populates="dimension_scores")

class ProgressReport(Base):
    __tablename__ = "progress_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String(50), unique=True, index=True, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    report = Column(Text, nullable=False)
    total_evaluations = Column(Integer, nullable=False)
    time_range = Column(Text, nullable=True)  # JSON 格式存储时间范围
    key_insights = Column(Text, nullable=True)  # JSON 格式存储关键洞察
    improvement_areas = Column(Text, nullable=True)  # JSON 格式存储改进领域
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship("Student", back_populates="progress_reports")

class HandwritingRecord(Base):
    __tablename__ = "handwriting_records"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    file_name = Column(String(100), nullable=False)
    recognized_text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    student = relationship("Student", back_populates="handwriting_records")