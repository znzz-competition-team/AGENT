import sqlite3
import os

# 确保数据库文件所在目录存在
db_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(db_dir, 'syllabus_evaluation.db')

# 连接到SQLite数据库
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 创建students表
cursor.execute('''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    age INTEGER,
    grade TEXT,
    major TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
''')

# 创建submissions表
cursor.execute('''
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id TEXT UNIQUE NOT NULL,
    student_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    submission_type TEXT DEFAULT "file",
    text_content TEXT,
    status TEXT DEFAULT "pending",
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id)
)
''')

# 创建media_files表
cursor.execute('''
CREATE TABLE IF NOT EXISTS media_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    duration REAL,
    processed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (submission_id) REFERENCES submissions(id)
)
''')

# 创建evaluation_results表，包含stage和stage_progress列
cursor.execute('''
CREATE TABLE IF NOT EXISTS evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id TEXT UNIQUE NOT NULL,
    student_id INTEGER NOT NULL,
    submission_id INTEGER NOT NULL,
    overall_score REAL NOT NULL,
    strengths TEXT,
    areas_for_improvement TEXT,
    recommendations TEXT,
    evaluator_agent TEXT NOT NULL,
    stage TEXT,
    stage_progress REAL,
    evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (submission_id) REFERENCES submissions(id)
)
''')

# 创建dimension_scores表
cursor.execute('''
CREATE TABLE IF NOT EXISTS dimension_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER NOT NULL,
    dimension TEXT NOT NULL,
    score REAL NOT NULL,
    confidence REAL NOT NULL,
    evidence TEXT,
    reasoning TEXT,
    FOREIGN KEY (evaluation_id) REFERENCES evaluation_results(id)
)
''')

# 提交更改
conn.commit()

# 插入测试数据
# 插入学生数据
cursor.execute('''
INSERT OR IGNORE INTO students (student_id, name, grade, major)
VALUES (?, ?, ?, ?)
''', ('2022001', '张三', '2022级', '计算机科学与技术'))

# 提交更改
conn.commit()

# 获取学生ID
cursor.execute('SELECT id FROM students WHERE student_id = ?', ('2022001',))
student_id = cursor.fetchone()[0]

# 插入提交数据
cursor.execute('''
INSERT OR IGNORE INTO submissions (submission_id, student_id, title, description)
VALUES (?, ?, ?, ?)
''', ('SUB_123456', student_id, '人工智能课程作业', '基于深度学习的图像分类'))

# 提交更改
conn.commit()

# 获取提交ID
cursor.execute('SELECT id FROM submissions WHERE submission_id = ?', ('SUB_123456',))
submission_id = cursor.fetchone()[0]

# 插入评估结果数据
test_evaluation = (
    'EVAL_789012',
    student_id,
    submission_id,
    88.0,
    '实践能力强，能完整实现从数据预处理到模型评估的深度学习流程',
    '前沿技术原理理解深度不足，如注意力机制、Transformer和大模型的内部工作机制阐述较浅',
    '加强理论学习，深入阅读注意力机制、Transformer等前沿技术的原理论文，提升理论深度',
    'comprehensive_evaluator'
)

cursor.execute('''
INSERT OR IGNORE INTO evaluation_results 
(evaluation_id, student_id, submission_id, overall_score, strengths, areas_for_improvement, recommendations, evaluator_agent)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
''', test_evaluation)

# 提交更改
conn.commit()

# 验证数据是否插入成功
cursor.execute('SELECT * FROM evaluation_results WHERE evaluation_id = ?', ('EVAL_789012',))
evaluation_result = cursor.fetchone()
print('评估结果插入成功:', evaluation_result)

# 关闭连接
conn.close()

print('数据库创建和测试完成！')
print(f'数据库文件路径: {db_path}')
