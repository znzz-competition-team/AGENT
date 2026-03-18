# 数据库模块初始化
# 避免循环导入，不在这里导入具体类

__all__ = [
    "Base",
    "engine", 
    "get_db",
    "init_db",
    "Student",
    "Submission",
    "MediaFile",
    "EvaluationResult",
    "DimensionScore",
    "DatabaseService"
]

# 延迟导入
def __getattr__(name):
    if name in ['Base', 'engine', 'get_db', 'init_db']:
        from database.database import Base, engine, get_db, init_db
        return locals()[name]
    elif name in ['Student', 'Submission', 'MediaFile', 'EvaluationResult', 'DimensionScore']:
        from database.models import Student, Submission, MediaFile, EvaluationResult, DimensionScore
        return locals()[name]
    elif name == 'DatabaseService':
        from database.database_service import DatabaseService
        return DatabaseService
    raise AttributeError(f"module 'database' has no attribute '{name}'")
