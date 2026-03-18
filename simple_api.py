#!/usr/bin/env python3
"""直接运行FastAPI应用，跳过视频处理器的导入"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath('.'))

# 导入必要的模块
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn

# 导入数据库相关模块
from src.database.database import SessionLocal, engine, Base
from src.database.database_service import DatabaseService
from src.models.schemas import StudentCreate, StudentResponse, StudentUpdate, EvaluationRequest, EvaluationResponse, DimensionScoreResponse
from datetime import datetime
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 创建FastAPI应用
app = FastAPI(
    title="学生多维度能力评估系统API",
    description="用于学生能力评估的API服务",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 依赖项，用于获取数据库会话
def get_database_service():
    db = SessionLocal()
    try:
        yield DatabaseService(db)
    finally:
        db.close()

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# 学生相关路由
@app.post("/students", response_model=StudentResponse)
async def create_student(
    student: StudentCreate,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 检查学生是否已存在
    existing_student = db_service.get_student_by_id(student.student_id)
    if existing_student:
        raise HTTPException(status_code=400, detail="学号已存在")
    
    # 创建学生
    new_student = db_service.create_student(
        student_id=student.student_id,
        name=student.name,
        age=student.age,
        grade=student.grade,
        major=student.major
    )
    
    return StudentResponse(
        id=new_student.id,
        student_id=new_student.student_id,
        name=new_student.name,
        age=new_student.age,
        grade=new_student.grade,
        major=new_student.major,
        created_at=new_student.created_at,
        updated_at=new_student.updated_at
    )

@app.get("/students", response_model=list[StudentResponse])
async def get_students(
    skip: int = 0,
    limit: int = 100,
    db_service: DatabaseService = Depends(get_database_service)
):
    students = db_service.get_all_students(skip=skip, limit=limit)
    return [
        StudentResponse(
            id=student.id,
            student_id=student.student_id,
            name=student.name,
            age=student.age,
            grade=student.grade,
            major=student.major,
            created_at=student.created_at,
            updated_at=student.updated_at
        )
        for student in students
    ]

@app.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    student = db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    return StudentResponse(
        id=student.id,
        student_id=student.student_id,
        name=student.name,
        age=student.age,
        grade=student.grade,
        major=student.major,
        created_at=student.created_at,
        updated_at=student.updated_at
    )

@app.put("/students/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: str,
    student_update: StudentUpdate,
    db_service: DatabaseService = Depends(get_database_service)
):
    student = db_service.update_student(
        student_id=student_id,
        **student_update.dict(exclude_unset=True)
    )
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    return StudentResponse(
        id=student.id,
        student_id=student.student_id,
        name=student.name,
        age=student.age,
        grade=student.grade,
        major=student.major,
        created_at=student.created_at,
        updated_at=student.updated_at
    )

@app.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    deleted = db_service.delete_student(student_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="学生不存在")
    
    return {"message": "学生删除成功"}

# 评估相关路由
@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_submission(
    request: EvaluationRequest,
    db_service: DatabaseService = Depends(get_database_service)
):
    logger.info(f"开始评估提交: {request.submission_id}, 阶段: {request.stage}")
    
    try:
        # 导入阶段评估器
        from src.evaluation.stage_evaluator import stage_evaluator
        
        # 确定评估阶段（默认为中期）
        stage = request.stage or "middle"
        
        # 生成基础评估结果
        import uuid
        evaluation_id = f"EVAL_{uuid.uuid4().hex[:8].upper()}"
        
        # 基础评分和反馈
        base_scores = {
            "学术表现": 8.2,
            "沟通能力": 7.8,
            "领导力": 7.5,
            "团队协作": 8.0,
            "创新能力": 7.0,
            "问题解决": 8.3,
            "时间管理": 7.9,
            "适应能力": 8.1,
            "技术能力": 8.4,
            "批判性思维": 7.7
        }
        
        base_feedback = {
            "strengths": ["学习态度积极", "基础知识扎实", "执行力强"],
            "areas_for_improvement": ["创新能力需要加强", "团队协作能力有待提高", "细节关注度不足"],
            "recommendations": ["多参与团队项目", "培养创新思维", "加强时间规划"]
        }
        
        # 根据阶段调整评分和反馈
        adjusted_scores = stage_evaluator.adjust_scores_by_stage(stage, base_scores)
        stage_feedback = stage_evaluator.generate_stage_specific_feedback(stage, base_feedback)
        
        # 计算综合评分
        overall_score = sum(adjusted_scores.values()) / len(adjusted_scores)
        overall_score = round(overall_score, 1)
        
        # 构建维度评分响应
        dimension_scores_response = []
        
        # 构建响应
        response = EvaluationResponse(
            evaluation_id=evaluation_id,
            student_id="TEST_STUDENT",  # 简化版本，使用固定学生ID
            overall_score=overall_score,
            strengths=stage_feedback["strengths"],
            areas_for_improvement=stage_feedback["areas_for_improvement"],
            recommendations=stage_feedback["recommendations"],
            dimension_scores=dimension_scores_response,
            evaluated_at=datetime.utcnow().isoformat(),
            evaluator_agent=f"stage_evaluator_{stage}",
            stage=stage
        )
        
        logger.info(f"评估完成: 阶段={stage}, 综合评分={overall_score}")
        
        return response
    except Exception as e:
        logger.error(f"评估过程中出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("simple_api:app", host="0.0.0.0", port=8000, reload=True)