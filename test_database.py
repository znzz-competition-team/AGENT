import sqlite3

# 连接到SQLite数据库（使用与主配置相同的数据库文件）
conn = sqlite3.connect('syllabus_evaluation.db')
cursor = conn.cursor()

# 删除现有的evaluation_results表（如果存在）
cursor.execute('DROP TABLE IF EXISTS evaluation_results')

# 创建新的evaluation_results表，不包含stage_progress列
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
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (submission_id) REFERENCES submissions(id)
)
''')

# 提交更改
conn.commit()

# 插入测试数据
test_data = (
    'EVAL_TEST123',
    1,
    11,
    88.0,
    '测试优势1, 测试优势2',
    '测试改进点1, 测试改进点2',
    '测试建议1, 测试建议2',
    'comprehensive_evaluator',
    '2026-03-28 08:00:00'
)

cursor.execute('''
INSERT INTO evaluation_results 
(evaluation_id, student_id, submission_id, overall_score, strengths, areas_for_improvement, recommendations, evaluator_agent, evaluated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
''', test_data)

# 提交更改
conn.commit()

# 验证数据是否插入成功
cursor.execute('SELECT * FROM evaluation_results WHERE evaluation_id = ?', ('EVAL_TEST123',))
result = cursor.fetchone()
print('测试数据插入结果:', result)

# 关闭连接
conn.close()

print('数据库测试完成！')
