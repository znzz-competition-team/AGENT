import sqlite3
import os

# 检查数据库文件是否存在
db_path = 'student_profiler.db'

if not os.path.exists(db_path):
    print("数据库文件不存在，将创建新的数据库")
else:
    print("数据库文件存在，检查表结构")

# 连接数据库
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 检查submissions表结构
print("\n检查submissions表结构:")
try:
    c.execute('PRAGMA table_info(submissions);')
    columns = c.fetchall()
    column_names = [col[1] for col in columns]
    print("当前列:", column_names)
    
    # 检查是否需要添加新字段
    if 'submission_type' not in column_names:
        print("添加submission_type字段")
        c.execute('ALTER TABLE submissions ADD COLUMN submission_type TEXT DEFAULT "file";')
    
    if 'text_content' not in column_names:
        print("添加text_content字段")
        c.execute('ALTER TABLE submissions ADD COLUMN text_content TEXT;')
    
    conn.commit()
    print("数据库更新成功")
    
except Exception as e:
    print(f"错误: {e}")
finally:
    conn.close()

print("\n数据库检查完成")
