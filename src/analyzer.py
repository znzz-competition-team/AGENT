import numpy as np
from collections import Counter
import re

class StudentToolAnalyzer:
    def __init__(self, stage="进阶期"):
        self.stage = stage
        # AI 常用转折词及句式指纹
        self.ai_signatures = ["总之", "综上所述", "不仅如此", "此外", "深入探讨"]

    def detect_ai_usage(self, text):
        """
        基于文本统计学检测 AI 使用率（无对话日志模式）
        """
        sentences = re.split(r'[。！？](?:\s|$)', text)
        sentences = [s for s in sentences if len(s) > 2]
        
        # 1. 计算句长突发性 (Burstiness)
        lengths = [len(s) for s in sentences]
        burstiness = np.std(lengths) / (np.mean(lengths) + 1e-6)
        
        # 2. 词汇丰富度 (TTR)
        words = list(text) # 简单中文字符处理
        ttr = len(set(words)) / len(words)
        
        # 3. AI 特征词频率
        signature_count = sum(1 for word in self.ai_signatures if word in text)
        
        # 综合判定得分 (0-100, 分数越高人工痕迹越多)
        # 人类写作通常 burstiness 高，TTR 高
        human_score = (burstiness * 40) + (ttr * 50) - (signature_count * 2)
        purity_score = np.clip(human_score, 0, 100)
        
        return {
            "ai_probability": 100 - purity_score,
            "burstiness": burstiness,
            "is_one_shot": True if burstiness < 0.5 and signature_count > 3 else False
        }

    def evaluate_math_formula(self, text):
        """
        检测 LaTeX 公式规范与深度
        """
        formulas = re.findall(r'\$\$(.*?)\$\$|\$(.*?)\$', text)
        formula_count = len(formulas)
        has_complex_symbol = any(re.search(r'\\int|\\sum|\\nabla|\\psi', str(f)) for f in formulas)
        
        math_score = min(formula_count * 10, 60) + (40 if has_complex_symbol else 0)
        return math_score, formulas