import sqlite3
import uuid
from datetime import datetime
import os

# 获取项目根目录
project_root = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(project_root, 'syllabus_evaluation.db')

# 连接到SQLite数据库（使用绝对路径）
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查evaluation_results表结构
cursor.execute('PRAGMA table_info(evaluation_results)')
columns = cursor.fetchall()

print('evaluation_results表结构:')
for column in columns:
    print(f"列名: {column[1]}, 类型: {column[2]}, 非空: {column[3]}, 主键: {column[5]}")

# 确保students表存在
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

# 确保submissions表存在
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

# 模拟大模型返回的评估结果
mock_evaluation_result = {
    "overall_score": 88.0,
    "dimension_scores": [
        {"dimension": "学术表现", "score": 85, "reasoning": "学术表现优秀"},
        {"dimension": "创新能力", "score": 80, "reasoning": "创新能力良好"}
    ],
    "ability_scores": [
        {"ability": "表述与表达", "score": 90, "reasoning": "表述清晰"},
        {"ability": "建模知识", "score": 85, "reasoning": "建模知识扎实"}
    ],
    "strengths": [
        "建模流程掌握扎实，从数据预处理到模型评估的各个环节都规范且详尽",
        "模型实现与对比分析能力突出，能熟练应用多种深度学习模型并进行性能量化比较"
    ],
    "areas_for_improvement": [
        "部分任务的结果分析可更深入，如任务4中SAM适配多类别分割的失败原因可进一步探讨理论局限",
        "工业AI应用场景的分析可加强，如更具体地讨论智能工厂中工件识别的实际挑战和解决方案"
    ],
    "recommendations": [
        "在未来的项目中，可尝试更复杂的工业场景模拟，如结合实时数据或硬件部署，以提升工程实战经验",
        "加强理论学习，深入理解模型背后的数学原理和最新研究进展，以支持更创新的算法改进"
    ]
}

# 模拟评估结果
evaluation_id = f"EVAL_{uuid.uuid4().hex[:8].upper()}"
overall_score = mock_evaluation_result["overall_score"]
strengths = ", ".join(mock_evaluation_result["strengths"])
areas_for_improvement = ", ".join(mock_evaluation_result["areas_for_improvement"])
recommendations = ", ".join(mock_evaluation_result["recommendations"])
evaluator_agent = "comprehensive_evaluator"
stage_progress = 1.0
evaluated_at = datetime.utcnow().isoformat()

# 检查evaluation_results表是否包含stage_progress列
has_stage_progress = False
for column in columns:
    if column[1] == 'stage_progress':
        has_stage_progress = True
        break

print(f"evaluation_results表是否包含stage_progress列: {has_stage_progress}")

# 插入评估结果
try:
    if has_stage_progress:
        # 表包含stage_progress列，插入所有字段
        cursor.execute('''
        INSERT INTO evaluation_results 
        (evaluation_id, student_id, submission_id, overall_score, strengths, areas_for_improvement, recommendations, evaluator_agent, stage_progress, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (evaluation_id, student_id, submission_id, overall_score, strengths, areas_for_improvement, recommendations, evaluator_agent, stage_progress, evaluated_at))
    else:
        # 表不包含stage_progress列，插入除stage_progress外的字段
        cursor.execute('''
        INSERT INTO evaluation_results 
        (evaluation_id, student_id, submission_id, overall_score, strengths, areas_for_improvement, recommendations, evaluator_agent, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (evaluation_id, student_id, submission_id, overall_score, strengths, areas_for_improvement, recommendations, evaluator_agent, evaluated_at))
    conn.commit()
    print('评估结果插入成功！')
    
    # 验证数据是否插入成功
    cursor.execute('SELECT * FROM evaluation_results WHERE evaluation_id = ?', (evaluation_id,))
    result = cursor.fetchone()
    print('插入的评估结果:', result)
    
except Exception as e:
    print(f'插入评估结果时出错: {e}')
    conn.rollback()

# 关闭连接
conn.close()

print('测试完成！')
