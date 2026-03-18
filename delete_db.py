import os

db_file = "student_profiler_new.db"

if os.path.exists(db_file):
    try:
        os.remove(db_file)
        print(f"成功删除数据库文件: {db_file}")
    except Exception as e:
        print(f"删除数据库文件失败: {str(e)}")
else:
    print(f"数据库文件不存在: {db_file}")
