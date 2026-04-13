import sqlite3
import os

# 获取项目根目录
project_root = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(project_root, 'syllabus_evaluation.db')

# 连接到SQLite数据库（使用绝对路径）
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查看evaluation_results表的结构
cursor.execute('PRAGMA table_info(evaluation_results)')
columns = cursor.fetchall()

print('evaluation_results表结构:')
for column in columns:
    print(f"列名: {column[1]}, 类型: {column[2]}, 非空: {column[3]}, 主键: {column[5]}")

# 关闭连接
conn.close()
