# src/course_classifier.py
import re

def classify_course_type(text_content: str) -> str:
    if not text_content:
        return "理论课"

    nature_match = re.search(r'课程性质[：:\s]*([^\n\r]+)', text_content)
    if nature_match:
        nature = nature_match.group(1)
        if any(k in nature for k in ['实践', '实验', '竞赛', '课程设计', '实训']):
            return "实践课"
        if any(k in nature for k in ['理论', '基础']):
            return "理论课"

    practice_keywords = ['实践', '实验', '设计', '竞赛', '实训', '操作', '动手']
    theory_keywords = ['理论', '原理', '基础', '概念', '推导']

    practice_score = sum(text_content.count(k) for k in practice_keywords)
    theory_score = sum(text_content.count(k) for k in theory_keywords)

    return "实践课" if practice_score > theory_score else "理论课"