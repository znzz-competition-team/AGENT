from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config import settings

# 创建数据库引擎
# 检查是否是 SQLite
if settings.database_url.startswith('sqlite'):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()

# 依赖项，用于获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 初始化数据库
def init_db():
    # 导入所有模型，确保它们被注册到 Base.metadata
    from .models import Student, Submission, MediaFile, EvaluationResult, DimensionScore, HandwritingRecord
    
    # 创建所有表（如果不存在）
    Base.metadata.create_all(bind=engine)