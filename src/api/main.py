from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
import shutil
from datetime import datetime
import sys
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('api_debug.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 添加项目根目录到 Python 路径
current_file = os.path.abspath(__file__)
api_dir = os.path.dirname(current_file)
src_dir = os.path.dirname(api_dir)
project_root = os.path.dirname(src_dir)

# 确保 src 目录和项目根目录都在 Python 路径?
for path in [src_dir, project_root]:
    if path not in sys.path:
        sys.path.insert(0, path)

from src.config import settings, AI_PROVIDERS, get_ai_config
from src.database import get_db, DatabaseService, init_db
from src.database.models import Student, Submission, MediaFile, EvaluationResult, ProgressReport
from src.models.schemas import (
    StudentCreate, StudentUpdate, StudentResponse,
    SubmissionCreate, SubmissionResponse, SubmissionStatus, SubmissionType,
    MediaFileResponse,
    EvaluationResultResponse, DimensionScoreResponse,
    EvaluationRequest, EvaluationResponse, ProgressReportResponse,
    EvaluationDimension, HandwritingExamGradeResponse
)
from src.models.schemas import EvaluationResult as SchemaEvaluationResult
# 移除对CrewAI和MediaProcessor的依赖，避免CV2依赖
# from src.agents.crew_manager import StudentEvaluationCrew
# from src.utils.media_processor import MediaProcessor
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
import json
from typing import Union

# 增加文件大小限制
from starlette.middleware.base import BaseHTTPMiddleware

# 辅助函数：处理evidence字段，确保返回List[str]类型
def process_evidence(evidence: Union[str, list, None]) -> list:
    """处理evidence字段，确保返回List[str]类型"""
    if isinstance(evidence, str):
        # 如果是字符串，分割成列表
        return [item.strip() for item in evidence.split(",") if item.strip()]
    elif isinstance(evidence, list):
        # 如果已经是列表，直接返回
        return evidence
    else:
        # 如果是None或其他类型，返回空列?
        return []

def process_string_list(value: Union[str, list, None]) -> list:
    """处理字符串列表字段，确保返回List[str]类型"""
    if isinstance(value, str):
        # 如果是字符串，分割成列表
        return [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, list):
        # 如果已经是列表，直接返回
        return value
    else:
        # 如果是None或其他类型，返回空列?
        return []

# 文档内容提取函数
def extract_document_content(file_path: str) -> str:
    """提取文档内容"""
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == ".pdf":
            return extract_pdf_content(file_path)
        elif file_ext == ".docx":
            return extract_docx_content(file_path)
        elif file_ext == ".doc":
            return extract_doc_content(file_path)
        elif file_ext == ".txt":
            return extract_txt_content(file_path)
        else:
            return ""
    except Exception as e:
        logger.error(f"提取文件内容失败: {str(e)}")
        return ""

def extract_pdf_content(file_path: str) -> str:
    """提取PDF文件内容"""
    try:
        import PyPDF2
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text()
            return text
    except Exception as e:
        logger.error(f"提取PDF内容失败: {str(e)}")
        return ""

def extract_docx_content(file_path: str) -> str:
    """提取DOCX文件内容"""
    try:
        from docx import Document
        doc = Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        logger.error(f"提取DOCX内容失败: {str(e)}")
        return ""

def extract_doc_content(file_path: str) -> str:
    """提取DOC文件内容"""
    try:
        import docx2txt
        text = docx2txt.process(file_path)
        return text
    except Exception as e:
        logger.error(f"提取DOC内容失败: {str(e)}")
        return ""

def extract_txt_content(file_path: str) -> str:
    """提取TXT文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    except Exception as e:
        logger.error(f"提取TXT内容失败: {str(e)}")
        return ""


def parse_float_form(value: Optional[str]) -> Optional[float]:
    """?Form 中的可选数字安全转换为 float?"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"数值格式错? {value}") from exc


def parse_bool_form(value: Optional[str], default: bool = True) -> bool:
    """Parse optional bool string in form payload."""
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise HTTPException(status_code=400, detail=f"布尔值格式错? {value}")
def ensure_baidu_ocr_dependency() -> None:
    """检查百?OCR SDK 是否可用?"""
    try:
        import aip  # noqa: F401
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="当前环境未安装百度OCR依赖 `baidu-aip`，普通手写识别功能暂不可用。请先安装：pip install baidu-aip",
        ) from exc


def model_supports_vision(model_name: Optional[str]) -> bool:
    """粗略判断当前模型是否支持图像输入?"""
    if not model_name:
        return False
    model = model_name.lower()
    vision_markers = (
        "gpt-4o",
        "gpt-4.1",
        "gpt-4-turbo",
        "glm-4v",
        "qwen-vl-ocr",
        "qvq",
        "vl",
        "vision",
        "omni",
    )
    non_vision_markers = (
        "qwen-turbo",
        "qwen-plus",
        "qwen-max",
        "deepseek-chat",
        "deepseek-reasoner",
        "gpt-3.5",
    )
    if any(marker in model for marker in non_vision_markers):
        return False
    return any(marker in model for marker in vision_markers)


HANDWRITING_OCR_PROMPT = (
    "请识别图片中的手写文字内容?"
    "尽量保持原文顺序逐行输出，不要添加解释?"
    "若包含数学公式、上下标、分式、积分、根号、希腊字母、单位或编号，请尽量准确保留原样?"
    "看不清的字符用[不清]标记，不要臆造内容?"
)


def run_multimodal_handwriting_ocr(file_path: str, ai_config: Dict[str, Any]) -> Dict[str, Any]:
    """使用支持视觉的多模态模型进行手写识别?"""
    import base64
    import mimetypes
    from openai import OpenAI

    file_ext = os.path.splitext(file_path)[1].lower()
    client = OpenAI(
        api_key=ai_config["api_key"],
        base_url=ai_config.get("base_url"),
    )

    def image_bytes_to_content(image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{encoded}",
            },
        }

    def recognize_single_image(image_bytes: bytes, mime_type: str) -> str:
        response = client.chat.completions.create(
            model=ai_config["model"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        image_bytes_to_content(image_bytes, mime_type),
                        {"type": "text", "text": HANDWRITING_OCR_PROMPT},
                    ],
                }
            ],
            temperature=min(float(ai_config.get("temperature", 0.01)), 0.1),
            max_tokens=max(int(ai_config.get("max_tokens", 2000)), 2000),
        )
        content = response.choices[0].message.content
        if isinstance(content, list):
            text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            return "\n".join(part for part in text_parts if part).strip()
        return (content or "").strip()

    if file_ext == ".pdf":
        import fitz

        recognized_pages = []
        doc = fitz.open(file_path)
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                page_text = recognize_single_image(pix.tobytes("png"), "image/png")
                if page_text:
                    recognized_pages.append(f"第{page_num + 1}?\n{page_text}")
            recognized_text = "\n\n".join(recognized_pages).strip()
        finally:
            doc.close()
    else:
        mime_type, _ = mimetypes.guess_type(file_path)
        with open(file_path, "rb") as image_file:
            recognized_text = recognize_single_image(image_file.read(), mime_type or "image/png")

    if not recognized_text:
        raise HTTPException(status_code=400, detail="AI 视觉模型未识别到有效文字内容，请检查图片是否清晰?")

    return {
        "recognized_text": recognized_text,
        "confidence": 95.0,
        "engine": ai_config["model"],
    }


def run_baidu_handwriting_ocr(
    file_path: str,
    app_id: str,
    api_key: str,
    secret_key: str,
) -> Dict[str, Any]:
    """使用百度 OCR 进行手写识别?"""
    ensure_baidu_ocr_dependency()
    from aip import AipOcr

    file_ext = os.path.splitext(file_path)[1].lower()
    client = AipOcr(app_id, api_key, secret_key)

    if file_ext == ".pdf":
        import fitz

        recognized_pages = []
        doc = fitz.open(file_path)
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                result = client.handwriting(pix.tobytes("png"))
                if 'words_result' in result and result['words_result']:
                    page_text = '\n'.join([item['words'] for item in result['words_result']])
                    recognized_pages.append(f"第{page_num + 1}?\n{page_text}")
                else:
                    error_msg = result.get('error_msg', '未知错误')
                    error_code = result.get('error_code', '未知错误?')
                    logger.warning(f"第{page_num + 1}页识别失? {error_msg} (错误? {error_code})")
        finally:
            doc.close()

        recognized_text = "\n\n".join(recognized_pages).strip()
        if not recognized_text:
            raise HTTPException(status_code=400, detail="PDF文件中未提取到文字，请确保PDF包含可识别的文字内容")
        confidence = 90.0
    else:
        with open(file_path, 'rb') as f:
            image = f.read()
        result = client.handwriting(image)
        if 'words_result' in result:
            recognized_text = '\n'.join([item['words'] for item in result['words_result']]).strip()
            confidence = 95.0
        else:
            error_msg = result.get('error_msg', '未知错误')
            error_code = result.get('error_code', '未知错误?')
            raise HTTPException(status_code=400, detail=f"百度OCR识别失败：{error_msg} (错误? {error_code})")

    return {
        "recognized_text": recognized_text,
        "confidence": confidence,
        "engine": "baidu-ocr",
    }

# 初始化数据库
init_db()

app = FastAPI(
    title="学生多维度能力评估系?API",
    description="基于 OpenAI GPT-4o ?CrewAI 的学生能力评估系?",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域?
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置文件上传大小限制
app.max_request_size = 500 * 1024 * 1024  # 500MB

# 确保上传目录存在
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 创建数据库表
from database.database import Base, engine
Base.metadata.create_all(bind=engine)

# 依赖?
def get_database_service(db: Session = Depends(get_db)) -> DatabaseService:
    return DatabaseService(db)

# 根路?- API 欢迎页面
@app.get("/")
async def root():
    return {
        "message": "欢迎使用学生多维度能力评估系?API",
        "version": "1.0.0",
        "docs": "http://localhost:8000/docs",
        "health": "http://localhost:8000/health",
        "endpoints": {
            "students": "/students",
            "submissions": "/submissions",
            "evaluations": "/evaluate",
            "files": "/submissions/{submission_id}/files"
        }
    }

# 健康检?
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# 学生相关路由
@app.post("/students", response_model=StudentResponse)
async def create_student(
    student: StudentCreate,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 检查学生是否已存在
    existing_student = db_service.get_student_by_id(student.student_id)
    if existing_student:
        raise HTTPException(status_code=400, detail="学生已存?")
    
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

@app.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    student = db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存?")
    
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

@app.get("/students", response_model=List[StudentResponse])
async def get_all_students(
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
        raise HTTPException(status_code=404, detail="学生不存?")
    
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
        raise HTTPException(status_code=404, detail="学生不存?")
    
    return {"message": "学生删除成功"}

# 提交相关路由
@app.post("/submissions", response_model=SubmissionResponse)
async def create_submission(
    submission: SubmissionCreate,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 检查学生是否存在（如果提供?student_id?
    student = None
    if submission.student_id:
        student = db_service.get_student_by_id(submission.student_id)
        if not student:
            raise HTTPException(status_code=404, detail="学生不存?")
    
    # 验证提交类型
    if submission.submission_type == SubmissionType.TEXT and not submission.text_content:
        raise HTTPException(status_code=400, detail="文字提交必须提供内容")
    
    # 创建提交
    new_submission = db_service.create_submission(
        title=submission.title,
        description=submission.description,
        student_id=submission.student_id,
        submission_type=submission.submission_type.value,
        text_content=submission.text_content
    )
    
    return SubmissionResponse(
        id=new_submission.id,
        submission_id=new_submission.submission_id,
        student_id=student.student_id if student else None,
        title=new_submission.title,
        description=new_submission.description,
        submission_type=SubmissionType(new_submission.submission_type),
        text_content=new_submission.text_content,
        status=SubmissionStatus(new_submission.status),
        created_at=new_submission.created_at,
        updated_at=new_submission.updated_at
    )

@app.get("/submissions", response_model=List[SubmissionResponse])
async def get_all_submissions(
    skip: int = 0,
    limit: int = 100,
    db_service: DatabaseService = Depends(get_database_service)
):
    submissions = db_service.get_all_submissions(skip=skip, limit=limit)
    
    result = []
    for submission in submissions:
        student = None
        if submission.student_id:
            student = db_service.get_student_by_internal_id(submission.student_id)
        
        result.append(SubmissionResponse(
            id=submission.id,
            submission_id=submission.submission_id,
            student_id=student.student_id if student else None,
            title=submission.title,
            description=submission.description,
            submission_type=SubmissionType(submission.submission_type),
            text_content=submission.text_content,
            status=SubmissionStatus(submission.status),
            created_at=submission.created_at,
            updated_at=submission.updated_at
        ))
    
    return result

@app.get("/submissions/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    submission = db_service.get_submission_by_id(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存?")
    
    student = None
    if submission.student_id:
        student = db_service.get_student_by_internal_id(submission.student_id)
        if not student:
            raise HTTPException(status_code=404, detail="学生不存?")
    
    return SubmissionResponse(
        id=submission.id,
        submission_id=submission.submission_id,
        student_id=student.student_id if student else None,
        title=submission.title,
        description=submission.description,
        submission_type=SubmissionType(submission.submission_type),
        text_content=submission.text_content,
        status=SubmissionStatus(submission.status),
        created_at=submission.created_at,
        updated_at=submission.updated_at
    )

@app.get("/students/{student_id}/submissions", response_model=List[SubmissionResponse])
async def get_student_submissions(
    student_id: str,
    skip: int = 0,
    limit: int = 100,
    db_service: DatabaseService = Depends(get_database_service)
):
    submissions = db_service.get_submissions_by_student_id(student_id, skip=skip, limit=limit)
    
    return [
        SubmissionResponse(
            id=submission.id,
            submission_id=submission.submission_id,
            student_id=student_id,
            title=submission.title,
            description=submission.description,
            submission_type=SubmissionType(submission.submission_type),
            text_content=submission.text_content,
            status=SubmissionStatus(submission.status),
            created_at=submission.created_at,
            updated_at=submission.updated_at
        )
        for submission in submissions
    ]

# 手写文字识别路由
@app.post("/handwriting-recognize")
async def handwriting_recognize(
    student_id: str = Form(...),
    app_id: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    secret_key: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db_service: DatabaseService = Depends(get_database_service)
):
    """识别手写文字"""
    # 检查学生是否存?    student = db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存?")
    
    # 保存上传的图?
    file_path = os.path.join(UPLOAD_DIR, f"handwriting_{student_id}_{file.filename}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 检查文件类?        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".pdf"]:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        
        current_ai_config = get_current_ai_config()
        if model_supports_vision(current_ai_config.get("model")):
            logger.info("手写识别使用 AI 视觉模型: %s", current_ai_config.get("model"))
            ocr_result = run_multimodal_handwriting_ocr(file_path, current_ai_config)
        else:
            if not all([app_id, api_key, secret_key]):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "当前 AI 模型不支持图像识别，且未提供完整的百?OCR 配置?"
                        "请在 AI 设置中切换到支持视觉的模型（?qwen-vl-ocr-latest、gpt-4o、glm-4v），"
                        "或填写百?OCR ?APP ID / API Key / Secret Key?"
                    ),
                )
            logger.info("手写识别使用百度 OCR")
            ocr_result = run_baidu_handwriting_ocr(file_path, app_id, api_key, secret_key)
        
        # 保存识别记录
        db_service.add_handwriting_record(
            student_id=student_id,
            file_name=file.filename,
            recognized_text=ocr_result["recognized_text"],
            confidence=ocr_result["confidence"],
        )
        
        return {
            "student_id": student_id,
            "recognized_text": ocr_result["recognized_text"],
            "confidence": ocr_result["confidence"],
            "engine": ocr_result["engine"],
            "file_name": file.filename
        }
    except HTTPException:
        # 清理临时文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise
    except Exception as e:
        # 清理临时文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        # 记录详细错误信息
        import traceback
        error_detail = traceback.format_exc()
        print(f"识别失败: {error_detail}")
        raise HTTPException(status_code=500, detail=f"服务器内部错? {str(e)}")
    finally:
        # 清理临时文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass


@app.post("/agent/grade-handwriting-exam", response_model=HandwritingExamGradeResponse)
async def grade_handwriting_exam(
    answer_key: str = Form(...),
    rubric: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    student_id: Optional[str] = Form(None),
    total_score: Optional[str] = Form(None),
    extra_requirements: Optional[str] = Form(None),
    recognition_mode: str = Form("general"),
    context_text: Optional[str] = Form(None),
    system_functions: Optional[str] = Form(None),
    system_relationships: Optional[str] = Form(None),
    validate_derivation: Optional[str] = Form("true"),
    files: List[UploadFile] = File(...),
    db_service: DatabaseService = Depends(get_database_service)
):
    """使用多模?agent 识别并批改手写试卷?"""
    if student_id:
        student = db_service.get_student_by_id(student_id)
        if not student:
            raise HTTPException(status_code=404, detail="学生不存?")

    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一张试卷图?")

    parsed_total_score = parse_float_form(total_score)
    parsed_validate_derivation = parse_bool_form(validate_derivation, default=True)
    normalized_mode = (recognition_mode or "general").strip().lower()
    if normalized_mode not in {"general", "formula"}:
        raise HTTPException(status_code=400, detail="recognition_mode 仅支?general ?formula")
    allowed_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    temp_paths: List[str] = []

    try:
        current_ai_config = get_current_ai_config()
        current_model = current_ai_config.get("model")
        if not model_supports_vision(current_model):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"当前模型 `{current_model}` 不支持图片输入，无法进行试卷识别与批改?"
                    "请到 AI 设置中切换为支持视觉的模型，例如 `gpt-4o` ?`glm-4v`?"
                ),
            )

        for file in files:
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_exts:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的试卷图片类型: {file.filename}"
                )

            safe_name = f"exam_{int(time.time() * 1000)}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, safe_name)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            temp_paths.append(file_path)

        from src.agents.exam_grading_agent import HandwritingExamGradingAgent

        grading_agent = HandwritingExamGradingAgent(ai_config=current_ai_config)
        result = grading_agent.grade_exam(
            image_paths=temp_paths,
            answer_key=answer_key,
            rubric=rubric,
            subject=subject,
            total_score=parsed_total_score,
            extra_requirements=extra_requirements,
            recognition_mode=normalized_mode,
            context_text=context_text,
            system_functions=system_functions,
            system_relationships=system_relationships,
            validate_derivation=parsed_validate_derivation,
        )

        return HandwritingExamGradeResponse(
            success=True,
            recognition_mode=result.get("recognition_mode", normalized_mode),
            student_id=student_id,
            subject=subject,
            recognized_text=result["recognized_text"],
            total_score=result["total_score"],
            max_score=result["max_score"],
            overall_comment=result["overall_comment"],
            course_achievement_comment=result.get("course_achievement_comment", ""),
            strengths=result["strengths"],
            areas_for_improvement=result["areas_for_improvement"],
            question_results=result["question_results"],
            formula_boxes=result.get("formula_boxes", []),
            derivation_checks=result.get("derivation_checks", []),
            model=result["model"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"试卷批改失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"试卷批改失败: {str(e)}")
    finally:
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

# 文件上传路由
@app.post("/submissions/{submission_id}/files", response_model=MediaFileResponse)
async def upload_file(
    submission_id: str,
    file: UploadFile = File(...),
    db_service: DatabaseService = Depends(get_database_service)
):
    # 检查提交是否存?
    submission = db_service.get_submission_by_id(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="提交不存?")
    
    # 保存文件
    file_path = os.path.join(UPLOAD_DIR, f"{submission_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 确定文件类型
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext in [".pdf", ".docx", ".doc", ".txt"]:
        media_type = "document"
    elif file_ext in [".mp4", ".mov"]:
        media_type = "video"
    elif file_ext in [".mp3", ".wav"]:
        media_type = "audio"
    else:
        raise HTTPException(status_code=400, detail="不支持的文件类型")
    
    # 获取文件大小
    size_bytes = os.path.getsize(file_path)
    
    # 创建媒体文件记录
    media_file = db_service.create_media_file(
        submission_id=submission_id,
        file_path=file_path,
        file_name=file.filename,
        media_type=media_type,
        size_bytes=size_bytes
    )
    
    return MediaFileResponse(
        id=media_file.id,
        submission_id=media_file.submission_id,
        file_path=media_file.file_path,
        media_type=media_file.media_type,
        size_bytes=media_file.size_bytes,
        duration=media_file.duration,
        processed=media_file.processed,
        uploaded_at=media_file.created_at
    )

@app.get("/submissions/{submission_id}/files", response_model=List[MediaFileResponse])
async def get_submission_files(
    submission_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    media_files = db_service.get_media_files_by_submission_id(submission_id)
    
    return [
        MediaFileResponse(
            id=file.id,
            submission_id=file.submission_id,
            file_path=file.file_path,
            media_type=file.media_type,
            size_bytes=file.size_bytes,
            duration=file.duration,
            processed=file.processed,
            uploaded_at=file.created_at
        )
        for file in media_files
    ]

# 文件修改路由
@app.put("/files/{file_id}", response_model=MediaFileResponse)
async def update_file(
    file_id: int,
    file_name: str = Form(...),
    media_type: str = Form(...),
    db_service: DatabaseService = Depends(get_database_service)
):
    # 检查文件是否存?
    media_file = db_service.get_media_file_by_id(file_id)
    if not media_file:
        raise HTTPException(status_code=404, detail="文件不存?")
    
    # 更新文件信息
    updated_file = db_service.update_media_file(
        file_id=file_id,
        file_name=file_name,
        media_type=media_type
    )
    
    return MediaFileResponse(
        id=updated_file.id,
        submission_id=updated_file.submission_id,
        file_path=updated_file.file_path,
        media_type=updated_file.media_type,
        size_bytes=updated_file.size_bytes,
        duration=updated_file.duration,
        processed=updated_file.processed,
        uploaded_at=updated_file.created_at
    )

# 文件删除路由
@app.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    db_service: DatabaseService = Depends(get_database_service)
):
    deleted = db_service.delete_media_file(file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文件不存?")
    
    return {"message": "文件删除成功"}

# 评估相关路由
@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_submission(
    request: EvaluationRequest,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 使用大模型进行评?
    logger.info(f"开始评估提? {request.submission_id}, 阶段: {request.stage}, 进度: {request.stage_progress}")
    
    try:
        # 检查提交是否存?
        submission = db_service.get_submission_by_id(request.submission_id)
        if not submission:
            raise HTTPException(status_code=404, detail="提交不存?")
        
        # 检查学生是否存?
        student = db_service.get_student_by_internal_id(submission.student_id)
        if not student:
            raise HTTPException(status_code=404, detail="学生不存?")
        
        # 导入大模型评估器
        from evaluation.llm_evaluator import llm_evaluator
        
        # 确定阶段进度（默认为0.5，即中期?
        stage_progress = request.stage_progress or 0.5
        # 确保进度值在0-1之间
        stage_progress = max(0.0, min(1.0, stage_progress))
        
        # 准备评估内容
        submission_content = submission.text_content or ""
        
        # 提取上传文件的内?
        media_files = db_service.get_media_files_by_submission_id(request.submission_id)
        logger.info(f"找到 {len(media_files)} 个媒体文?")
        if media_files:
            file_contents = []
            for media_file in media_files:
                logger.info(f"处理媒体文件: {media_file.file_name}, 类型: {media_file.media_type}, 路径: {media_file.file_path}")
                if media_file.media_type == "document":
                    file_content = extract_document_content(media_file.file_path)
                    logger.info(f"提取文件内容长度: {len(file_content)}")
                    if file_content:
                        file_contents.append(f"文件 {media_file.file_name} 的内?\n{file_content}")
            
            if file_contents:
                logger.info(f"成功提取 {len(file_contents)} 个文件的内容")
                if submission_content:
                    submission_content += "\n\n" + "\n\n".join(file_contents)
                else:
                    submission_content = "\n\n".join(file_contents)
            else:
                logger.info("没有提取到文件内?")
        else:
            logger.info("没有找到媒体文件")
        
        # 如果仍然没有内容，设置为默认?
        if not submission_content:
            submission_content = "无内?"
        
        # 准备学生信息
        student_info = {
            "student_id": student.student_id,
            "name": student.name,
            "grade": student.grade,
            "major": student.major
        }
        
        # 使用大模型进行评?
        evaluation_result = llm_evaluator.evaluate_submission(
            submission_content=submission_content,
            stage_progress=stage_progress,
            student_info=student_info
        )
        
        # 生成评估ID
        import uuid
        evaluation_id = f"EVAL_{uuid.uuid4().hex[:8].upper()}"
        
        # 保存评估结果到数据库
        db_evaluation = db_service.create_evaluation_result(
            submission_id=request.submission_id,
            overall_score=evaluation_result["overall_score"],
            strengths=", ".join(evaluation_result["strengths"]),
            areas_for_improvement=", ".join(evaluation_result["areas_for_improvement"]),
            recommendations=", ".join(evaluation_result["recommendations"]),
            stage=f"progress_{stage_progress:.2f}"
        )
        
        # 保存维度评分
        from models.schemas import EvaluationDimension
        dimension_mapping = {
            "学术表现": EvaluationDimension.ACADEMIC_PERFORMANCE,
            "沟通能?": EvaluationDimension.COMMUNICATION_SKILLS,
            "领导?": EvaluationDimension.LEADERSHIP,
            "团队协作": EvaluationDimension.TEAMWORK,
            "创新能力": EvaluationDimension.CREATIVITY,
            "问题解决": EvaluationDimension.PROBLEM_SOLVING,
            "时间管理": EvaluationDimension.TIME_MANAGEMENT,
            "适应能力": EvaluationDimension.ADAPTABILITY,
            "技术能?": EvaluationDimension.TECHNICAL_SKILLS,
            "批判性思维": EvaluationDimension.CRITICAL_THINKING
        }
        
        # 构建维度评分响应
        dimension_scores_response = []
        for dimension_name, score_info in evaluation_result["dimension_scores"].items():
            dimension = dimension_mapping.get(dimension_name)
            if dimension:
                # 获取评分和推?
                if isinstance(score_info, dict):
                    score = score_info.get("score", 0.0)
                    reasoning = score_info.get("reasoning", "由大模型生成的评估结?")
                else:
                    score = score_info
                    reasoning = "由大模型生成的评估结?"
                
                # 保存维度评分到数据库
                db_service.create_dimension_score(
                    evaluation_id=db_evaluation.evaluation_id,
                    dimension=dimension.value,
                    score=score,
                    confidence=0.9,
                    evidence=f"基于大模型的评估，进度? {stage_progress:.2f}",
                    reasoning=reasoning
                )
                
                # 构建维度评分响应
                dimension_score_response = DimensionScoreResponse(
                    dimension=dimension,
                    score=score,
                    confidence=0.9,
                    evidence=[f"基于大模型的评估，进度? {stage_progress:.2f}"],
                    reasoning=reasoning
                )
                dimension_scores_response.append(dimension_score_response)
        
        # 更新提交状?
        db_service.update_submission_status(request.submission_id, SubmissionStatus.COMPLETED)
        
        # 构建响应
        response = EvaluationResponse(
            evaluation_id=evaluation_id,
            student_id=student.student_id,
            overall_score=evaluation_result["overall_score"],
            strengths=evaluation_result["strengths"],
            areas_for_improvement=evaluation_result["areas_for_improvement"],
            recommendations=evaluation_result["recommendations"],
            dimension_scores=dimension_scores_response,
            evaluated_at=datetime.utcnow().isoformat(),
            evaluator_agent="llm_evaluator",
            stage=f"progress_{stage_progress:.2f}",
            stage_progress=stage_progress
        )
        
        logger.info(f"评估完成: 进度={stage_progress:.2f}, 综合评分={evaluation_result['overall_score']}")
        
        return response
    except HTTPException as he:
        # 更新提交状态为失败
        try:
            db_service.update_submission_status(request.submission_id, SubmissionStatus.FAILED)
        except:
            pass
        raise
    except Exception as e:
        # 更新提交状态为失败
        try:
            db_service.update_submission_status(request.submission_id, SubmissionStatus.FAILED)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"评估过程中出? {str(e)}")

@app.get("/evaluations/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 获取评估结果
    evaluation = db_service.get_evaluation_result_by_id(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估结果不存?")
    
    # 获取学生信息
    student = db_service.get_student_by_internal_id(evaluation.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存?")
    
    # 获取维度评分
    dimension_scores = db_service.get_dimension_scores_by_evaluation_id(evaluation_id)
    
    # 构建维度评分响应
    dimension_scores_response = [
        DimensionScoreResponse(
            dimension=ds.dimension,
            score=ds.score,
            confidence=ds.confidence,
            evidence=process_evidence(ds.evidence),
            reasoning=ds.reasoning
        )
        for ds in dimension_scores
    ]
    
    # 检查evaluation对象是否有stage属?
    stage = None
    if hasattr(evaluation, 'stage'):
        stage = evaluation.stage
    
    return EvaluationResponse(
        evaluation_id=evaluation.evaluation_id,
        student_id=student.student_id,
        overall_score=evaluation.overall_score,
        strengths=process_string_list(evaluation.strengths),
        areas_for_improvement=process_string_list(evaluation.areas_for_improvement),
        recommendations=process_string_list(evaluation.recommendations),
        dimension_scores=dimension_scores_response,
        evaluated_at=evaluation.evaluated_at,
        evaluator_agent=evaluation.evaluator_agent,
        stage=stage
    )

@app.get("/students/{student_id}/evaluations", response_model=List[EvaluationResponse])
async def get_student_evaluations(
    student_id: str,
    skip: int = 0,
    limit: int = 100,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 获取学生的评估结?
    evaluations = db_service.get_evaluation_results_by_student_id(student_id, skip=skip, limit=limit)
    
    response = []
    for evaluation in evaluations:
        # 获取维度评分
        dimension_scores = db_service.get_dimension_scores_by_evaluation_id(evaluation.evaluation_id)
        
        # 构建维度评分响应
        dimension_scores_response = [
            DimensionScoreResponse(
                dimension=ds.dimension,
                score=ds.score,
                confidence=ds.confidence,
                evidence=process_evidence(ds.evidence),
                reasoning=ds.reasoning
            )
            for ds in dimension_scores
        ]
        
        # 从stage字段中提取进度?
        stage = None
        if hasattr(evaluation, 'stage'):
            stage = evaluation.stage
        
        # 获取学生信息
        student = db_service.get_student_by_internal_id(evaluation.student_id)
        if not student:
            continue
        
        response.append(EvaluationResponse(
            evaluation_id=evaluation.evaluation_id,
            student_id=student.student_id,
            overall_score=evaluation.overall_score,
            strengths=process_string_list(evaluation.strengths),
            areas_for_improvement=process_string_list(evaluation.areas_for_improvement),
            recommendations=process_string_list(evaluation.recommendations),
            dimension_scores=dimension_scores_response,
            evaluated_at=evaluation.evaluated_at,
            evaluator_agent=evaluation.evaluator_agent,
            stage=stage
        ))
    
    return response

@app.delete("/evaluations/{evaluation_id}")
async def delete_evaluation(
    evaluation_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """删除评估记录及其相关的维度评?"""
    success = db_service.delete_evaluation_result(evaluation_id)
    if not success:
        raise HTTPException(status_code=404, detail="评估记录不存?")
    
    return {"message": "评估记录已成功删?"}

@app.get("/students/{student_id}/progress-report", response_model=ProgressReportResponse)
async def generate_student_progress_report(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """
    生成学生的整体进度报告，根据之前的不同进度的作业评价?
    将其输入大模型后获得对该学生的，在时间线上的能力进步
    """
    # 获取学生的所有评估结果，按时间排?
    evaluations = db_service.get_evaluation_results_by_student_id_sorted(student_id)
    
    if not evaluations:
        raise HTTPException(status_code=404, detail="该学生没有评估记?")
    
    # 构建评估历史数据
    evaluation_history = []
    for eval in evaluations:
        dimension_scores = db_service.get_dimension_scores_by_evaluation_id(eval.evaluation_id)
        dimension_data = [
            {
                "dimension": ds.dimension,
                "score": ds.score,
                "confidence": ds.confidence,
                "reasoning": ds.reasoning
            }
            for ds in dimension_scores
        ]
        
        evaluation_history.append({
            "evaluation_id": eval.evaluation_id,
            "evaluated_at": eval.evaluated_at.isoformat(),
            "overall_score": eval.overall_score,
            "strengths": process_string_list(eval.strengths),
            "areas_for_improvement": process_string_list(eval.areas_for_improvement),
            "recommendations": process_string_list(eval.recommendations),
            "dimension_scores": dimension_data
        })
    
    # 构建提示?
    prompt = f"""你是一位专业的教育评估专家，擅长分析学生在时间线上的能力进步?

请根据以下学生的评估历史数据，生成一份详细的整体进度报告?

学生ID: {student_id}

评估历史（按时间顺序）：
{json.dumps(evaluation_history, ensure_ascii=False, indent=2)}

报告要求?
1. 分析学生在各个维度上的能力变化趋?
2. 识别学生的优势和持续改进的领?
3. 提供关于学生能力发展的关键洞?
4. 给出基于历史数据的未来发展建?
5. 报告应该结构清晰，语言专业但易于理?
6. 包含具体的数据支持和分析

请生成一份全面的进度报告，帮助教师和学生了解能力发展情况?"""
    
    try:
        # 调用大模型生成报?
        from src.evaluation.llm_evaluator import llm_evaluator
        report = llm_evaluator.generate_report(prompt)
        
        # 提取关键信息
        key_insights = ["学生能力发展趋势分析", "优势领域识别", "改进空间分析"]
        improvement_areas = ["需要持续关注的能力维度"]
        
        # 构建时间范围
        time_range = {
            "start": evaluations[0].evaluated_at.isoformat(),
            "end": evaluations[-1].evaluated_at.isoformat()
        }
        
        # 保存进度报告到数据库
        db_service.create_progress_report(
            student_id=student_id,
            report=report,
            total_evaluations=len(evaluations),
            time_range=time_range,
            key_insights=key_insights,
            improvement_areas=improvement_areas
        )
        
        return ProgressReportResponse(
            student_id=student_id,
            report=report,
            generated_at=datetime.utcnow(),
            total_evaluations=len(evaluations),
            time_range=time_range,
            key_insights=key_insights,
            improvement_areas=improvement_areas
        )
    except Exception as e:
        logger.error(f"生成进度报告失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成进度报告失败: {str(e)}")

@app.get("/students/{student_id}/progress-reports", response_model=List[ProgressReportResponse])
async def get_student_progress_reports(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """
    获取学生的历史进度报?
    """
    import json
    
    # 获取学生的所有进度报?
    reports = db_service.get_progress_reports_by_student_id(student_id)
    
    if not reports:
        return []
    
    # 构建响应
    response = []
    for report in reports:
        # 解析 JSON 字段
        time_range = {}
        key_insights = []
        improvement_areas = []
        
        try:
            if report.time_range:
                time_range = json.loads(report.time_range)
            if report.key_insights:
                key_insights = json.loads(report.key_insights)
            if report.improvement_areas:
                improvement_areas = json.loads(report.improvement_areas)
        except:
            pass
        
        response.append(ProgressReportResponse(
            student_id=student_id,
            report=report.report,
            generated_at=report.generated_at,
            total_evaluations=report.total_evaluations,
            time_range=time_range,
            key_insights=key_insights,
            improvement_areas=improvement_areas
        ))
    
    return response

@app.get("/submissions/{submission_id}/evaluation", response_model=EvaluationResponse)
async def get_submission_evaluation(
    submission_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    # 获取提交的评估结?
    evaluation = db_service.get_evaluation_result_by_submission_id(submission_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="评估结果不存?")
    
    # 获取学生信息
    student = db_service.get_student_by_internal_id(evaluation.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存?")
    
    # 获取维度评分
    dimension_scores = db_service.get_dimension_scores_by_evaluation_id(evaluation.evaluation_id)
    
    # 构建维度评分响应
    dimension_scores_response = [
        DimensionScoreResponse(
            dimension=ds.dimension,
            score=ds.score,
            confidence=ds.confidence,
            evidence=process_evidence(ds.evidence),
            reasoning=ds.reasoning
        )
        for ds in dimension_scores
    ]
    
    # 检查evaluation对象是否有stage属?
    stage = None
    if hasattr(evaluation, 'stage'):
        stage = evaluation.stage
    
    return EvaluationResponse(
            evaluation_id=evaluation.evaluation_id,
            student_id=student.student_id,
            overall_score=evaluation.overall_score,
            strengths=process_string_list(evaluation.strengths),
            areas_for_improvement=process_string_list(evaluation.areas_for_improvement),
            recommendations=process_string_list(evaluation.recommendations),
            dimension_scores=dimension_scores_response,
            evaluated_at=evaluation.evaluated_at,
            evaluator_agent=evaluation.evaluator_agent,
            stage=stage
        )

@app.get("/students/{student_id}/evaluations/comparison")
async def compare_student_evaluations(
    student_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """获取学生的评估结果对?"""
    # 获取学生信息
    student = db_service.get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存?")
    
    # 获取按阶段排序的评估结果
    evaluations = db_service.get_evaluation_results_by_student_id_sorted(student_id)
    
    if not evaluations:
        raise HTTPException(status_code=404, detail="暂无评估记录")
    
    # 构建对比响应
    comparison_data = {
        "student_id": student_id,
        "student_name": student.name,
        "evaluations": []
    }
    
    for evaluation in evaluations:
        # 获取维度评分
        dimension_scores = db_service.get_dimension_scores_by_evaluation_id(evaluation.evaluation_id)
        
        # 构建维度评分响应
        dimension_scores_response = [
            {
                "dimension": ds.dimension,
                "score": ds.score,
                "confidence": ds.confidence
            }
            for ds in dimension_scores
        ]
        
        evaluation_data = {
            "evaluation_id": evaluation.evaluation_id,
            "overall_score": evaluation.overall_score,
            "evaluated_at": evaluation.evaluated_at,
            "dimension_scores": dimension_scores_response,
            "strengths": process_string_list(evaluation.strengths),
            "areas_for_improvement": process_string_list(evaluation.areas_for_improvement),
            "recommendations": process_string_list(evaluation.recommendations)
        }
        
        comparison_data["evaluations"].append(evaluation_data)
    
    # 计算评分变化
    if len(evaluations) > 1:
        score_changes = []
        for i in range(1, len(evaluations)):
            prev_evaluation = evaluations[i-1]
            current_evaluation = evaluations[i]
            
            score_change = {
                "from_evaluation": prev_evaluation.evaluation_id,
                "to_evaluation": current_evaluation.evaluation_id,
                "overall_score_change": current_evaluation.overall_score - prev_evaluation.overall_score,
                "dimension_score_changes": []
            }
            
            # 计算维度评分变化
            prev_dimensions = {ds.dimension: ds.score for ds in db_service.get_dimension_scores_by_evaluation_id(prev_evaluation.evaluation_id)}
            current_dimensions = {ds.dimension: ds.score for ds in db_service.get_dimension_scores_by_evaluation_id(current_evaluation.evaluation_id)}
            
            for dimension in set(prev_dimensions.keys()) | set(current_dimensions.keys()):
                prev_score = prev_dimensions.get(dimension, 0)
                current_score = current_dimensions.get(dimension, 0)
                
                score_change["dimension_score_changes"].append({
                    "dimension": dimension,
                    "change": current_score - prev_score
                })
            
            score_changes.append(score_change)
        
        comparison_data["score_changes"] = score_changes
    
    return comparison_data

# AI 配置相关?Pydantic 模型
class AIConfigRequest(BaseModel):
    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000

class AIConfigResponse(BaseModel):
    provider: str
    model: str
    base_url: str
    temperature: float
    max_tokens: int
    has_api_key: bool

class TestAIResponse(BaseModel):
    success: bool
    message: str
    model: Optional[str] = None
    response_time: Optional[float] = None
    error: Optional[str] = None

# 内存中存储的 AI 配置（实际生产环境应该使用更安全的方式）
_current_ai_config: Dict[str, Any] = None

def get_current_ai_config():
    """获取当前 AI 配置"""
    global _current_ai_config
    if _current_ai_config is None:
        # 使用默认配置
        config = get_ai_config()
        _current_ai_config = {
            "provider": settings.ai_provider,
            "api_key": config.get("api_key", ""),
            "model": config.get("model", settings.ai_model),
            "base_url": config.get("base_url", ""),
            "temperature": config.get("temperature", settings.ai_temperature),
            "max_tokens": config.get("max_tokens", settings.ai_max_tokens)
        }
    return _current_ai_config

# AI 配置相关路由
@app.get("/ai-config")
async def get_ai_configuration():
    """获取当前 AI 配置"""
    config = get_current_ai_config()
    return {
        "provider": config["provider"],
        "model": config["model"],
        "base_url": config["base_url"],
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
        "api_key": config["api_key"],  # 返回 API Key 以便前端使用
        "has_api_key": bool(config["api_key"])
    }

@app.post("/ai-config")
async def update_ai_configuration(config: AIConfigRequest):
    """更新 AI 配置"""
    global _current_ai_config
    
    # 验证提供?
    if config.provider not in AI_PROVIDERS and config.provider != "custom":
        raise HTTPException(status_code=400, detail=f"不支持的 AI 提供? {config.provider}")
    
    # 获取提供商信?
    provider_info = AI_PROVIDERS.get(config.provider, {})
    
    # 确定 base_url
    if config.provider == "custom":
        if not config.base_url:
            raise HTTPException(status_code=400, detail="自定义提供商必须提供 base_url")
        base_url = config.base_url
    else:
        base_url = config.base_url or provider_info.get("base_url", "")
    
    # 保存配置
    _current_ai_config = {
        "provider": config.provider,
        "api_key": config.api_key,
        "model": config.model,
        "base_url": base_url,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens
    }
    
    # 更新环境变量（供其他模块使用?
    os.environ["AI_PROVIDER"] = config.provider
    os.environ["AI_API_KEY"] = config.api_key
    os.environ["AI_MODEL"] = config.model
    os.environ["AI_BASE_URL"] = base_url
    os.environ["AI_TEMPERATURE"] = str(config.temperature)
    os.environ["AI_MAX_TOKENS"] = str(config.max_tokens)
    
    # 同时设置OpenAI的环境变量，确保兼容?
    os.environ["OPENAI_API_KEY"] = config.api_key
    os.environ["OPENAI_MODEL"] = config.model
    if base_url:
        os.environ["OPENAI_BASE_URL"] = base_url
    
    return {"message": "AI 配置已更?", "provider": config.provider, "model": config.model}

@app.post("/ai-config/reset")
async def reset_ai_configuration():
    """重置 AI 配置为默认?"""
    global _current_ai_config
    _current_ai_config = None
    
    # 清除环境变量
    for key in ["AI_PROVIDER", "AI_API_KEY", "AI_MODEL", "AI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"]:
        if key in os.environ:
            del os.environ[key]
    
    return {"message": "AI 配置已重置为默认?"}

@app.post("/ai-config/test", response_model=TestAIResponse)
async def test_ai_connection():
    """测试 AI 连接"""
    config = get_current_ai_config()
    
    if not config["api_key"]:
        return TestAIResponse(
            success=False,
            message="",
            error="未配?API Key"
        )
    
    try:
        start_time = time.time()
        
        # 根据提供商使用不同的测试方式
        if config["provider"] in ["openai", "deepseek", "zhipu", "moonshot", "qwen", "custom"]:
            # 使用 OpenAI 兼容格式测试
            from openai import OpenAI
            
            client = OpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"]
            )
            
            response = client.chat.completions.create(
                model=config["model"],
                messages=[
                    {"role": "system", "content": "你是一?helpful assistant."},
                    {"role": "user", "content": "你好，请回复'连接测试成功'"}
                ],
                temperature=config["temperature"],
                max_tokens=config["max_tokens"]
            )
            
            response_time = time.time() - start_time
            message = response.choices[0].message.content
            
            return TestAIResponse(
                success=True,
                message=message,
                model=config["model"],
                response_time=round(response_time, 2)
            )
        else:
            return TestAIResponse(
                success=False,
                message="",
                error=f"不支持的提供? {config['provider']}"
            )
            
    except Exception as e:
        return TestAIResponse(
            success=False,
            message="",
            error=f"连接测试失败: {str(e)}"
        )

# 主入?
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
        reload_dirs=[os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    )



