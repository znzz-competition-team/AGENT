"""
数据库迁移脚本：为 submissions 表添加 submission_purpose 字段
"""
import sqlite3
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings

def migrate_database():
    # 获取数据库文件路径
    db_url = settings.database_absolute_path
    db_path = db_url.replace("sqlite:///", "")
    
    print(f"数据库路径: {db_path}")
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，将在应用启动时自动创建")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查列是否已存在
        cursor.execute("PRAGMA table_info(submissions)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'submission_purpose' not in columns:
            print("添加 submission_purpose 列...")
            cursor.execute("ALTER TABLE submissions ADD COLUMN submission_purpose VARCHAR(20) DEFAULT 'normal'")
            conn.commit()
            print("[OK] 成功添加 submission_purpose 列")
        else:
            print("[OK] submission_purpose 列已存在，无需迁移")
        
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] 迁移失败: {str(e)}")
        raise

if __name__ == "__main__":
    migrate_database()
