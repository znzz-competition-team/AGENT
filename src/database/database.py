from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config import settings
import os

def ensure_sqlite_schema_compatibility():
    """
    对历史 SQLite 库做最小兼容迁移，避免因缺列导致接口 500。
    """
    if not database_url.startswith("sqlite"):
        return

    required_columns = {
        "submissions": {
            "submission_purpose": "VARCHAR(20) DEFAULT 'normal'",
            "course_type": "VARCHAR(50) DEFAULT '理论课'",
            "syllabus_name": "VARCHAR(255)"
        }
    }

    with engine.begin() as conn:
        for table_name, columns in required_columns.items():
            table_info = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
            if not table_info:
                continue

            existing_columns = {row[1] for row in table_info}
            for column_name, column_def in columns.items():
                if column_name not in existing_columns:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
                    )

# 使用绝对路径创建数据库引擎，确保所有地方都使用同一个数据库文件
database_url = settings.database_absolute_path

# 检查是否是 SQLite
if database_url.startswith('sqlite'):
    # 添加UTF-8编码支持
    engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread": False,
            "isolation_level": None
        },
        pool_pre_ping=True
    )
    
    # 设置SQLite使用UTF-8编码
    from sqlalchemy import event
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA encoding = 'UTF-8'")
        cursor.close()
else:
    engine = create_engine(
        database_url,
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
    from .models import Student, Submission, MediaFile, EvaluationResult, DimensionScore, HandwritingRecord, ProgressReport
    
    # 只创建表，不删除现有表
    # 注意：如果需要更新表结构，应该使用数据库迁移工具
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema_compatibility()