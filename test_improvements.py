"""
测试脚本 - 验证PDF提取和论文类型检测改进效果

测试内容：
1. PDF文本提取效果
2. 摘要提取效果
3. 论文类型检测效果
"""

import sys
import os
import logging

logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.pdf_extractor import PDFExtractor, extract_pdf_content
from src.evaluation.thesis_type_detector import ThesisTypeDetector, detect_thesis_type


def test_pdf_extraction():
    """测试PDF提取效果"""
    print("=" * 60)
    print("测试1: PDF文本提取效果")
    print("=" * 60)
    
    test_files = [
        "测试评价文件/基于无监督学习的工业数据故障检测系统研发与实现_王泽.pdf",
        "测试评价文件/一种可变形履带式巡检机器人的机构设计与运动学分析_马宏宇.pdf",
    ]
    
    extractor = PDFExtractor()
    
    for file_path in test_files:
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            continue
        
        print(f"\n文件: {os.path.basename(file_path)}")
        print("-" * 40)
        
        text, tables = extractor.extract(file_path)
        
        print(f"提取字符数: {len(text)}")
        print(f"提取表格数: {len(tables)}")
        
        print(f"\n前500字符预览:")
        print(text[:500])
        print("...")


def test_abstract_extraction():
    """测试摘要提取效果"""
    print("\n" + "=" * 60)
    print("测试2: 摘要提取效果")
    print("=" * 60)
    
    from src.api.main import extract_abstract
    
    test_files = [
        "测试评价文件/基于无监督学习的工业数据故障检测系统研发与实现_王泽.pdf",
        "测试评价文件/一种可变形履带式巡检机器人的机构设计与运动学分析_马宏宇.pdf",
    ]
    
    for file_path in test_files:
        if not os.path.exists(file_path):
            continue
        
        print(f"\n文件: {os.path.basename(file_path)}")
        print("-" * 40)
        
        text = extract_pdf_content(file_path)
        abstract = extract_abstract(text)
        
        print(f"摘要长度: {len(abstract)}")
        print(f"摘要内容:")
        print(abstract[:500] if len(abstract) > 500 else abstract)


def test_type_detection():
    """测试论文类型检测效果"""
    print("\n" + "=" * 60)
    print("测试3: 论文类型检测效果")
    print("=" * 60)
    
    test_cases = [
        {
            "file": "测试评价文件/基于无监督学习的工业数据故障检测系统研发与实现_王泽.pdf",
            "expected": "algorithm",
            "title": "基于无监督学习的工业数据故障检测系统研发与实现"
        },
        {
            "file": "测试评价文件/一种可变形履带式巡检机器人的机构设计与运动学分析_马宏宇.pdf",
            "expected": "physical",
            "title": "一种可变形履带式巡检机器人的机构设计与运动学分析"
        },
    ]
    
    detector = ThesisTypeDetector()
    
    for case in test_cases:
        file_path = case["file"]
        if not os.path.exists(file_path):
            continue
        
        print(f"\n文件: {os.path.basename(file_path)}")
        print(f"预期类型: {case['expected']}")
        print("-" * 40)
        
        text = extract_pdf_content(file_path)
        
        from src.api.main import extract_abstract
        abstract = extract_abstract(text)
        
        result = detector.detect(case["title"], text, abstract)
        
        print(f"检测类型: {result['type']} ({result['type_name']})")
        print(f"置信度: {result['confidence']:.2%}")
        print(f"判断理由: {result['reason']}")
        
        if result["features"]:
            print(f"\n关键词得分:")
            for k, v in result["features"]["keyword_scores"].items():
                print(f"  {k}: {v:.3f}")
            
            print(f"\n章节特征:")
            for k, v in result["features"]["chapter_features"].items():
                print(f"  {k}: {v:.3f}")
        
        is_correct = result["type"] == case["expected"]
        print(f"\n检测结果: {'✓ 正确' if is_correct else '✗ 错误'}")


def test_text_cleaning():
    """测试文本清理效果"""
    print("\n" + "=" * 60)
    print("测试4: 文本清理效果对比")
    print("=" * 60)
    
    test_text = """
    这是一段测试文本。
    
    它包含多个    连续空格和
    多个换行符。
    
    
    还有英文单词 test case 和中文混合。
    """
    
    print("原始文本:")
    print(repr(test_text))
    
    from src.frontend.pages.main import clean_pdf_text
    
    cleaned = clean_pdf_text(test_text)
    
    print("\n清理后文本:")
    print(repr(cleaned))
    
    print("\n清理后显示:")
    print(cleaned)


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("毕业设计评估系统改进测试")
    print("=" * 60)
    
    try:
        test_pdf_extraction()
    except Exception as e:
        print(f"PDF提取测试失败: {e}")
    
    try:
        test_abstract_extraction()
    except Exception as e:
        print(f"摘要提取测试失败: {e}")
    
    try:
        test_type_detection()
    except Exception as e:
        print(f"类型检测测试失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
