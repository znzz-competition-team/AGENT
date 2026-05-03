from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from .models import Student, Submission, MediaFile, EvaluationResult, DimensionScore, HandwritingRecord, ProgressReport
from datetime import datetime
import uuid

class DatabaseService:
    def __init__(self, db: Session):
        self.db = db
    
    # Student operations
    def create_student(self, student_id: str, name: str, age: Optional[int] = None, 
                      grade: Optional[str] = None, major: Optional[str] = None) -> Student:
        student = Student(
            student_id=student_id,
            name=name,
            age=age,
            grade=grade,
            major=major
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student
    
    def get_student_by_id(self, student_id: str) -> Optional[Student]:
        return self.db.query(Student).filter(Student.student_id == student_id).first()
    
    def get_student_by_internal_id(self, internal_id: int) -> Optional[Student]:
        return self.db.query(Student).filter(Student.id == internal_id).first()
    
    def get_all_students(self, skip: int = 0, limit: int = 100) -> List[Student]:
        return self.db.query(Student).offset(skip).limit(limit).all()
    
    def update_student(self, student_id: str, **kwargs) -> Optional[Student]:
        student = self.get_student_by_id(student_id)
        if student:
            for key, value in kwargs.items():
                setattr(student, key, value)
            student.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(student)
        return student
    
    def delete_student(self, student_id: str) -> bool:
        student = self.get_student_by_id(student_id)
        if student:
            # 先删除与该学生关联的所有相关记录
            from .models import HandwritingRecord, Submission, MediaFile, EvaluationResult, DimensionScore, ProgressReport
            
            # 1. 删除与学生关联的手写识别记录
            self.db.query(HandwritingRecord).filter(HandwritingRecord.student_id == student.id).delete()
            
            # 2. 删除与学生关联的进度报告
            self.db.query(ProgressReport).filter(ProgressReport.student_id == student.id).delete()
            
            # 3. 删除与学生关联的评估结果及其维度评分
            evaluation_results = self.db.query(EvaluationResult).filter(EvaluationResult.student_id == student.id).all()
            for evaluation_result in evaluation_results:
                # 删除维度评分
                self.db.query(DimensionScore).filter(DimensionScore.evaluation_id == evaluation_result.id).delete()
                # 删除评估结果
                self.db.delete(evaluation_result)
            
            # 4. 删除与学生关联的提交记录及其相关内容
            submissions = self.db.query(Submission).filter(Submission.student_id == student.id).all()
            for submission in submissions:
                # 删除与提交关联的媒体文件
                self.db.query(MediaFile).filter(MediaFile.submission_id == submission.id).delete()
                
                # 删除提交记录
                self.db.delete(submission)
            
            # 5. 最后删除学生
            self.db.delete(student)
            self.db.commit()
            return True
        return False
    
    # Submission operations
    def create_submission(self, title: str, description: Optional[str] = None, student_id: Optional[str] = None,
                         submission_type: str = "file", submission_purpose: str = "normal", 
                         text_content: Optional[str] = None) -> Submission:
        student_id_int = None
        if student_id:
            student = self.get_student_by_id(student_id)
            if not student:
                raise ValueError(f"Student with ID {student_id} not found")
            student_id_int = student.id
        
        submission = Submission(
            submission_id=f"SUB_{uuid.uuid4().hex[:8].upper()}",
            student_id=student_id_int,
            title=title,
            description=description,
            submission_type=submission_type,
            submission_purpose=submission_purpose,
            text_content=text_content
        )
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        return submission
    
    def get_submission_by_id(self, submission_id: str) -> Optional[Submission]:
        return self.db.query(Submission).filter(Submission.submission_id == submission_id).first()
    
    def get_submission_by_pk(self, pk: int) -> Optional[Submission]:
        return self.db.query(Submission).filter(Submission.id == pk).first()
    
    def get_submissions_by_student_id(self, student_id: str, skip: int = 0, limit: int = 100) -> List[Submission]:
        student = self.get_student_by_id(student_id)
        if not student:
            return []
        return self.db.query(Submission).filter(Submission.student_id == student.id).offset(skip).limit(limit).all()
    
    def update_submission_status(self, submission_id: str, status: str) -> Optional[Submission]:
        submission = self.get_submission_by_id(submission_id)
        if submission:
            submission.status = status
            submission.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(submission)
        return submission
    
    def get_all_submissions(self, skip: int = 0, limit: int = 100) -> List[Submission]:
        """获取所有提交记录"""
        return self.db.query(Submission).offset(skip).limit(limit).all()
    
    def delete_submission(self, submission_id: str) -> bool:
        """删除提交记录及其相关的媒体文件和评估结果"""
        submission = self.get_submission_by_id(submission_id)
        if not submission:
            return False
        
        # 1. 删除与提交关联的评估结果及其维度评分
        evaluation_results = self.db.query(EvaluationResult).filter(EvaluationResult.submission_id == submission.id).all()
        for evaluation_result in evaluation_results:
            # 删除维度评分
            self.db.query(DimensionScore).filter(DimensionScore.evaluation_id == evaluation_result.id).delete()
            # 删除评估结果
            self.db.delete(evaluation_result)
        
        # 2. 删除与提交关联的媒体文件
        media_files = self.db.query(MediaFile).filter(MediaFile.submission_id == submission.id).all()
        for media_file in media_files:
            # 删除文件
            import os
            if os.path.exists(media_file.file_path):
                try:
                    os.remove(media_file.file_path)
                except:
                    pass
            # 删除数据库记录
            self.db.delete(media_file)
        
        # 3. 删除提交记录
        self.db.delete(submission)
        self.db.commit()
        return True
    
    # MediaFile operations
    def create_media_file(self, submission_id, file_path: str, file_name: str, media_type: str,
                         size_bytes: int, duration: Optional[float] = None) -> MediaFile:
        if isinstance(submission_id, int):
            submission_id_int = submission_id
        else:
            submission = self.get_submission_by_id(submission_id)
            submission_id_int = submission.id if submission else None
        
        media_file = MediaFile(
            submission_id=submission_id_int,
            file_path=file_path,
            file_name=file_name,
            media_type=media_type,
            size_bytes=size_bytes,
            duration=duration
        )
        self.db.add(media_file)
        self.db.commit()
        self.db.refresh(media_file)
        return media_file
    
    def get_media_files_by_submission_id(self, submission_id: str) -> List[MediaFile]:
        submission = self.get_submission_by_id(submission_id)
        if not submission:
            return []
        return self.db.query(MediaFile).filter(MediaFile.submission_id == submission.id).all()
    
    def get_media_file_by_id(self, file_id: int) -> Optional[MediaFile]:
        return self.db.query(MediaFile).filter(MediaFile.id == file_id).first()
    
    def update_media_file(self, file_id: int, **kwargs) -> Optional[MediaFile]:
        media_file = self.get_media_file_by_id(file_id)
        if media_file:
            for key, value in kwargs.items():
                setattr(media_file, key, value)
            self.db.commit()
            self.db.refresh(media_file)
        return media_file
    
    def delete_media_file(self, file_id: int) -> bool:
        """删除媒体文件"""
        import logging
        logger = logging.getLogger(__name__)
        media_file = self.get_media_file_by_id(file_id)
        if not media_file:
            logger.error(f"文件ID {file_id} 不存在")
            return False
        
        # 删除文件
        file_deleted = False
        try:
            if os.path.exists(media_file.file_path):
                os.remove(media_file.file_path)
                file_deleted = True
                logger.info(f"成功删除文件: {media_file.file_path}")
            else:
                logger.warning(f"文件不存在: {media_file.file_path}")
        except Exception as e:
            logger.error(f"删除文件失败: {str(e)}", exc_info=True)
        
        # 无论文件是否删除成功，都删除数据库记录
        self.db.delete(media_file)
        self.db.commit()
        logger.info(f"成功删除数据库中的媒体文件记录: {file_id}")
        return True
    
    # EvaluationResult operations
    def create_evaluation_result(self, submission_id: str, overall_score: float, 
                                strengths: Optional[str] = None, 
                                areas_for_improvement: Optional[str] = None, 
                                recommendations: Optional[str] = None, 
                                evaluator_agent: str = "comprehensive_evaluator",
                                stage: Optional[str] = None,
                                stage_progress: Optional[float] = None) -> EvaluationResult:
        submission = self.get_submission_by_id(submission_id)
        if not submission:
            raise ValueError(f"Submission with ID {submission_id} not found")
        
        # 检查提交是否有关联学生
        if not submission.student_id:
            raise ValueError(f"Submission with ID {submission_id} has no associated student")
        
        # 处理列表类型的参数，转换为字符串
        strengths_str = strengths
        if isinstance(strengths, list):
            strengths_str = ", ".join(strengths) if strengths else None
        
        areas_for_improvement_str = areas_for_improvement
        if isinstance(areas_for_improvement, list):
            areas_for_improvement_str = ", ".join(areas_for_improvement) if areas_for_improvement else None
        
        recommendations_str = recommendations
        if isinstance(recommendations, list):
            recommendations_str = ", ".join(recommendations) if recommendations else None
        
        evaluation_result = EvaluationResult(
            evaluation_id=f"EVAL_{uuid.uuid4().hex[:8].upper()}",
            student_id=submission.student_id,
            submission_id=submission.id,
            overall_score=overall_score,
            strengths=strengths_str,
            areas_for_improvement=areas_for_improvement_str,
            recommendations=recommendations_str,
            evaluator_agent=evaluator_agent,
            stage=stage,
            stage_progress=stage_progress
        )
        self.db.add(evaluation_result)
        self.db.commit()
        self.db.refresh(evaluation_result)
        return evaluation_result
    
    def get_evaluation_result_by_id(self, evaluation_id: str) -> Optional[EvaluationResult]:
        return self.db.query(EvaluationResult).filter(EvaluationResult.evaluation_id == evaluation_id).first()
    
    def get_evaluation_result_by_submission_id(self, submission_id: str) -> Optional[EvaluationResult]:
        submission = self.get_submission_by_id(submission_id)
        if not submission:
            return None
        return self.db.query(EvaluationResult).filter(EvaluationResult.submission_id == submission.id).first()
    
    def get_evaluation_results_by_student_id(self, student_id: str, skip: int = 0, limit: int = 100) -> List[EvaluationResult]:
        student = self.get_student_by_id(student_id)
        if not student:
            return []
        return self.db.query(EvaluationResult).filter(EvaluationResult.student_id == student.id).offset(skip).limit(limit).all()
    
    def get_evaluation_results_by_student_id_sorted(self, student_id: str) -> List[EvaluationResult]:
        """获取学生的所有评估结果，按创建时间排序"""
        student = self.get_student_by_id(student_id)
        if not student:
            return []
        
        # 获取所有评估结果，按创建时间排序
        evaluations = self.db.query(EvaluationResult).filter(EvaluationResult.student_id == student.id).order_by(EvaluationResult.evaluated_at).all()
        
        return evaluations
    
    def delete_evaluation_result(self, evaluation_id: str) -> bool:
        """删除评估记录及其相关的维度评分"""
        evaluation = self.get_evaluation_result_by_id(evaluation_id)
        if not evaluation:
            return False
        
        # 删除相关的维度评分
        self.db.query(DimensionScore).filter(DimensionScore.evaluation_id == evaluation.id).delete()
        
        # 删除评估结果
        self.db.delete(evaluation)
        self.db.commit()
        return True
    
    def update_evaluation_result(self, evaluation_id: str, **kwargs) -> Optional[EvaluationResult]:
        """更新评估记录"""
        evaluation = self.get_evaluation_result_by_id(evaluation_id)
        if not evaluation:
            return None
        
        # 处理dimension_scores字段
        if 'dimension_scores' in kwargs:
            # 删除现有的维度评分
            self.db.query(DimensionScore).filter(DimensionScore.evaluation_id == evaluation.id).delete()
            
            # 添加新的维度评分
            for ds in kwargs['dimension_scores']:
                if isinstance(ds, dict) and 'dimension' in ds and 'score' in ds:
                    self.create_dimension_score(
                        evaluation_id=evaluation_id,
                        dimension=ds['dimension'],
                        score=ds['score'],
                        confidence=0.9,  # 默认置信度
                        reasoning=ds.get('reasoning', '')
                    )
            
            # 从kwargs中移除dimension_scores，避免后续处理
            del kwargs['dimension_scores']
        
        for key, value in kwargs.items():
            # 处理特殊字段
            if key in ['strengths', 'areas_for_improvement', 'recommendations']:
                if isinstance(value, list):
                    # 将列表转换为字符串
                    setattr(evaluation, key, ", ".join(value) if value else None)
                else:
                    setattr(evaluation, key, value)
            elif key == 'evaluated_at':
                # 处理评估时间
                if isinstance(value, str):
                    try:
                        # 尝试解析时间字符串
                        evaluated_at = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                        setattr(evaluation, key, evaluated_at)
                    except ValueError:
                        # 如果解析失败，保持原有值
                        pass
            else:
                setattr(evaluation, key, value)
        
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation
    
    # ProgressReport operations
    def create_progress_report(self, student_id: str, report: str, total_evaluations: int, 
                             time_range: dict, key_insights: list, improvement_areas: list) -> ProgressReport:
        """创建进度报告"""
        import uuid
        import json
        
        student = self.get_student_by_id(student_id)
        if not student:
            raise ValueError(f"Student with ID {student_id} not found")
        
        # 转换为 JSON 字符串
        time_range_str = json.dumps(time_range, ensure_ascii=False)
        key_insights_str = json.dumps(key_insights, ensure_ascii=False)
        improvement_areas_str = json.dumps(improvement_areas, ensure_ascii=False)
        
        progress_report = ProgressReport(
            report_id=f"REPORT_{uuid.uuid4().hex[:8].upper()}",
            student_id=student.id,
            report=report,
            total_evaluations=total_evaluations,
            time_range=time_range_str,
            key_insights=key_insights_str,
            improvement_areas=improvement_areas_str
        )
        self.db.add(progress_report)
        self.db.commit()
        self.db.refresh(progress_report)
        return progress_report
    
    def get_progress_reports_by_student_id(self, student_id: str) -> List[ProgressReport]:
        """获取学生的所有进度报告"""
        student = self.get_student_by_id(student_id)
        if not student:
            return []
        return self.db.query(ProgressReport).filter(ProgressReport.student_id == student.id).order_by(ProgressReport.generated_at.desc()).all()
    
    def get_progress_report_by_id(self, report_id: str) -> Optional[ProgressReport]:
        """根据报告ID获取进度报告"""
        return self.db.query(ProgressReport).filter(ProgressReport.report_id == report_id).first()
    
    def update_progress_report(self, report_id: str, **kwargs) -> Optional[ProgressReport]:
        """更新进度报告"""
        report = self.get_progress_report_by_id(report_id)
        if report:
            for key, value in kwargs.items():
                if key == 'time_range' or key == 'key_insights' or key == 'improvement_areas':
                    import json
                    setattr(report, key, json.dumps(value, ensure_ascii=False))
                else:
                    setattr(report, key, value)
            self.db.commit()
            self.db.refresh(report)
        return report
    
    def delete_progress_report(self, report_id: str) -> bool:
        """删除进度报告"""
        report = self.get_progress_report_by_id(report_id)
        if not report:
            return False
        
        # 删除进度报告
        self.db.delete(report)
        self.db.commit()
        return True
    
    # DimensionScore operations
    def create_dimension_score(self, evaluation_id: str, dimension: str, score: float, 
                              confidence: float, evidence: Optional[str] = None, 
                              reasoning: Optional[str] = None) -> DimensionScore:
        evaluation = self.db.query(EvaluationResult).filter(EvaluationResult.evaluation_id == evaluation_id).first()
        if not evaluation:
            raise ValueError(f"Evaluation result with ID {evaluation_id} not found")
        
        # 处理列表类型的evidence参数，转换为字符串
        evidence_str = evidence
        if isinstance(evidence, list):
            evidence_str = ", ".join(evidence) if evidence else None
        
        dimension_score = DimensionScore(
            evaluation_id=evaluation.id,
            dimension=dimension,
            score=score,
            confidence=confidence,
            evidence=evidence_str,
            reasoning=reasoning
        )
        self.db.add(dimension_score)
        self.db.commit()
        self.db.refresh(dimension_score)
        return dimension_score
    
    def get_dimension_scores_by_evaluation_id(self, evaluation_id: str) -> List[DimensionScore]:
        evaluation = self.get_evaluation_result_by_id(evaluation_id)
        if not evaluation:
            return []
        return self.db.query(DimensionScore).filter(DimensionScore.evaluation_id == evaluation.id).all()
    
    # HandwritingRecord operations
    def add_handwriting_record(self, student_id: str, file_name: str, 
                              recognized_text: str, confidence: float) -> HandwritingRecord:
        """添加手写识别记录"""
        student = self.get_student_by_id(student_id)
        if not student:
            raise ValueError(f"Student with ID {student_id} not found")
        
        record = HandwritingRecord(
            student_id=student.id,
            file_name=file_name,
            recognized_text=recognized_text,
            confidence=confidence
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
