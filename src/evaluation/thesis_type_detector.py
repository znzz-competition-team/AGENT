"""
论文类型检测器模块 - 多维度特征分析

支持检测类型：
1. algorithm - 算法类：算法设计、模型开发、数据分析、机器学习等
2. simulation - 仿真类：仿真分析、数值模拟、虚拟实验等
3. physical - 实物类：硬件制作、电路设计、嵌入式系统、样机开发等
4. traditional_mechanical - 传统机械类：机械结构设计、加工制造、传动机构等
5. mixed - 混合类：涉及以上多种类型的组合

检测维度：
1. 关键词特征分析（权重60%）
2. 章节结构分析（权重30%）
3. 技术术语分析（权重10%）
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TypeFeature:
    """类型特征定义"""
    keywords: Dict[str, int]
    required: List[str]
    excluded: List[str]
    chapter_patterns: List[str]


class ThesisTypeDetector:
    """论文类型检测器 - 多维度特征分析"""
    
    TYPE_FEATURES = {
        "algorithm": TypeFeature(
            keywords={
                "算法": 3, "深度学习": 3, "机器学习": 3, "神经网络": 3,
                "模型": 2, "训练": 2, "优化": 2, "分类": 2, "预测": 2,
                "卷积": 2, "循环": 2, "注意力": 2, "Transformer": 2,
                "数据集": 1, "准确率": 1, "损失函数": 2, "CNN": 2, "RNN": 2,
                "LSTM": 2, "GAN": 2, "强化学习": 3, "自然语言处理": 2, "NLP": 2,
                "图像识别": 2, "目标检测": 2, "语义分割": 2,
            },
            required=[],
            excluded=["实物", "样机", "硬件制作", "装配", "电路板", "PCB设计"],
            chapter_patterns=[r"算法设计", r"模型构建", r"实验分析", r"数据预处理", r"网络结构", r"模型训练"],
        ),
        "simulation": TypeFeature(
            keywords={
                "仿真": 3, "模拟": 3, "有限元": 3, "ANSYS": 3, "COMSOL": 3,
                "数值": 2, "网格": 2, "边界条件": 2, "收敛": 2,
                "流体": 2, "热": 2, "应力": 2, "变形": 2, "FLUENT": 3,
                "ABAQUS": 3, "MATLAB仿真": 2, "Simulink": 3, "多物理场": 2,
                "耦合": 2, "瞬态": 2, "稳态": 2, "网格划分": 2,
            },
            required=[],
            excluded=["实物", "样机", "硬件", "PCB"],
            chapter_patterns=[r"仿真分析", r"数值模拟", r"有限元分析", r"仿真结果", r"仿真模型", r"边界条件"],
        ),
        "physical": TypeFeature(
            keywords={
                "实物": 3, "样机": 3, "硬件": 3, "制作": 2, "调试": 2,
                "电路": 2, "PCB": 2, "嵌入式": 2, "单片机": 2, "STM32": 2,
                "传感器": 2, "执行器": 2, "测试": 1, "实验验证": 2,
                "Arduino": 2, "树莓派": 2, "FPGA": 2, "DSP": 2,
                "电路板": 2, "焊接": 2, "原型": 2, "系统集成": 2,
            },
            required=["实物", "样机", "硬件", "制作", "电路", "嵌入式", "单片机", "PCB"],
            excluded=[],
            chapter_patterns=[r"硬件设计", r"实物制作", r"系统调试", r"实验测试", r"电路设计", r"样机"],
        ),
        "traditional_mechanical": TypeFeature(
            keywords={
                "机械设计": 3, "结构设计": 3, "传动": 2, "齿轮": 2, "轴承": 2,
                "减速器": 3, "箱体": 2, "轴": 1, "强度": 2, "刚度": 2,
                "工艺": 2, "加工": 2, "公差": 2, "装配图": 2,
                "CAD": 2, "SolidWorks": 2, "Pro/E": 2, "UG": 2,
                "机械原理": 2, "机构": 2, "连杆": 2, "凸轮": 2,
            },
            required=[],
            excluded=["算法", "深度学习", "神经网络", "机器学习", "仿真"],
            chapter_patterns=[r"结构设计", r"传动设计", r"强度计算", r"工艺设计", r"机械设计", r"装配图"],
        ),
    }
    
    TYPE_NAMES = {
        "algorithm": "算法类",
        "simulation": "仿真类",
        "physical": "实物类",
        "traditional_mechanical": "传统机械类",
        "mixed": "混合类"
    }
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """预编译正则表达式"""
        self._chapter_pattern_cache = {}
        for type_key, features in self.TYPE_FEATURES.items():
            self._chapter_pattern_cache[type_key] = [
                re.compile(p, re.IGNORECASE) for p in features.chapter_patterns
            ]
    
    def detect(self, title: str, content: str, abstract: str = "") -> Dict:
        """
        多维度检测论文类型
        
        Args:
            title: 论文标题
            content: 论文全文内容
            abstract: 论文摘要
            
        Returns:
            {
                "type": "类型代码",
                "type_name": "类型名称",
                "confidence": 0.95,
                "reason": "判断理由",
                "features": {...}
            }
        """
        full_text = f"{title}\n{abstract}\n{content[:15000]}"
        
        keyword_scores = self._analyze_keywords(full_text)
        
        chapter_features = self._analyze_chapters(content)
        
        tech_terms = self._analyze_tech_terms(full_text)
        
        final_scores = self._calculate_final_scores(
            keyword_scores, chapter_features, tech_terms
        )
        
        best_type = max(final_scores, key=final_scores.get)
        confidence = final_scores[best_type]
        
        if confidence < 0.15:
            best_type = "mixed"
            confidence = 0.5
        
        reason = self._generate_reason(best_type, keyword_scores, chapter_features, tech_terms)
        
        return {
            "type": best_type,
            "type_name": self.TYPE_NAMES.get(best_type, "混合类"),
            "confidence": min(confidence, 1.0),
            "reason": reason,
            "features": {
                "keyword_scores": keyword_scores,
                "chapter_features": chapter_features,
                "tech_terms": tech_terms,
                "final_scores": final_scores,
                "matched_keywords": getattr(self, '_matched_keywords_detail', {}),
                "matched_chapters": getattr(self, '_matched_chapters_detail', {})
            }
        }
    
    def _analyze_keywords(self, text: str) -> Dict[str, float]:
        """分析关键词特征"""
        scores = {}
        matched_keywords_detail = {}
        text_lower = text.lower()
        
        for type_key, features in self.TYPE_FEATURES.items():
            score = 0
            matched_keywords = []
            
            for keyword, weight in features.keywords.items():
                if keyword.lower() in text_lower:
                    score += weight
                    matched_keywords.append((keyword, weight, text_lower.count(keyword.lower())))
            
            if features.required:
                required_match = any(
                    r.lower() in text_lower for r in features.required
                )
                if not required_match:
                    score *= 0.3
            
            for excluded in features.excluded:
                if excluded.lower() in text_lower:
                    score *= 0.5
                    break
            
            max_possible = sum(features.keywords.values())
            scores[type_key] = score / max_possible if max_possible > 0 else 0
            matched_keywords_detail[type_key] = sorted(matched_keywords, key=lambda x: -x[1])[:10]
        
        self._matched_keywords_detail = matched_keywords_detail
        return scores
    
    def _analyze_chapters(self, content: str) -> Dict[str, float]:
        """分析章节结构"""
        scores = {}
        matched_chapters_detail = {}
        
        for type_key, features in self.TYPE_FEATURES.items():
            score = 0
            matched_chapters = []
            patterns = self._chapter_pattern_cache.get(type_key, [])
            
            for pattern in patterns:
                matches = pattern.findall(content)
                if matches:
                    matched_chapters.extend(matches)
                score += len(matches)
            
            scores[type_key] = score / max(len(patterns), 1)
            matched_chapters_detail[type_key] = list(set(matched_chapters))
        
        self._matched_chapters_detail = matched_chapters_detail
        return scores
    
    def _analyze_tech_terms(self, text: str) -> Dict[str, List[str]]:
        """分析技术术语"""
        tech_terms = {}
        
        tech_patterns = {
            "algorithm": [
                r'\b(CNN|RNN|LSTM|GRU|GAN|Transformer|BERT|GPT|ResNet|VGG|YOLO)\b',
                r'(卷积神经网络|循环神经网络|生成对抗网络|注意力机制)',
            ],
            "simulation": [
                r'\b(ANSYS|COMSOL|FLUENT|ABAQUS|Simulink)\b',
                r'(有限元分析|计算流体力学|多物理场耦合)',
            ],
            "physical": [
                r'\b(STM32|Arduino|Raspberry|FPGA|DSP|PCB)\b',
                r'(嵌入式系统|微控制器|传感器|执行器)',
            ],
            "traditional_mechanical": [
                r'\b(SolidWorks|Pro/E|Creo|UG|AutoCAD)\b',
                r'(减速器|齿轮传动|连杆机构|凸轮机构)',
            ],
        }
        
        for type_key, patterns in tech_patterns.items():
            terms = []
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                terms.extend(matches)
            tech_terms[type_key] = list(set(terms))
        
        return tech_terms
    
    def _calculate_final_scores(
        self,
        keyword_scores: Dict,
        chapter_features: Dict,
        tech_terms: Dict
    ) -> Dict[str, float]:
        """计算最终评分"""
        final_scores = {}
        
        for type_key in self.TYPE_FEATURES.keys():
            keyword_score = keyword_scores.get(type_key, 0)
            chapter_score = chapter_features.get(type_key, 0)
            tech_term_count = len(tech_terms.get(type_key, []))
            
            score = (
                keyword_score * 0.6 +
                chapter_score * 0.3 +
                min(tech_term_count * 0.05, 0.1)
            )
            final_scores[type_key] = score
        
        total = sum(final_scores.values())
        if total > 0:
            for key in final_scores:
                final_scores[key] = final_scores[key] / total
        
        return final_scores
    
    def _generate_reason(
        self,
        best_type: str,
        keyword_scores: Dict,
        chapter_features: Dict,
        tech_terms: Dict
    ) -> str:
        """生成判断理由"""
        reasons = []
        
        type_name = self.TYPE_NAMES.get(best_type, "混合类")
        
        if keyword_scores.get(best_type, 0) > 0.2:
            reasons.append(f"检测到典型的{type_name}关键词特征")
        
        if chapter_features.get(best_type, 0) > 0.3:
            reasons.append(f"章节结构符合{type_name}项目特征")
        
        tech_term_list = tech_terms.get(best_type, [])
        if tech_term_list:
            terms_str = "、".join(tech_term_list[:3])
            reasons.append(f"检测到{type_name}相关技术术语：{terms_str}")
        
        if not reasons:
            reasons.append("根据综合特征分析判断")
        
        return "；".join(reasons)


def detect_thesis_type(title: str, content: str, abstract: str = "") -> Dict:
    """
    便捷函数：检测论文类型
    
    Args:
        title: 论文标题
        content: 论文内容
        abstract: 论文摘要
        
    Returns:
        检测结果字典
    """
    detector = ThesisTypeDetector()
    return detector.detect(title, content, abstract)
