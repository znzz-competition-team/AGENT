"""
简化测试脚本 - 快速验证核心改进
"""

import sys
import os
import logging

logging.basicConfig(level=logging.ERROR)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def quick_test():
    """快速测试"""
    print("=" * 50)
    print("快速测试 - 验证核心改进")
    print("=" * 50)
    
    print("\n1. 测试论文类型检测器...")
    from src.evaluation.thesis_type_detector import ThesisTypeDetector
    
    detector = ThesisTypeDetector()
    
    test_cases = [
        {
            "title": "基于深度学习的图像识别算法研究",
            "content": "本文研究了卷积神经网络CNN在图像识别中的应用，使用了ResNet和VGG模型进行训练和测试。",
            "expected": "algorithm"
        },
        {
            "title": "基于ANSYS的机械结构仿真分析",
            "content": "本文使用ANSYS软件对机械结构进行有限元分析，研究了应力分布和变形情况。",
            "expected": "simulation"
        },
        {
            "title": "智能巡检机器人设计与实现",
            "content": "本文设计了一款智能巡检机器人，包括硬件电路设计、STM32单片机控制、传感器集成等。",
            "expected": "physical"
        },
        {
            "title": "减速器传动机构设计",
            "content": "本文设计了齿轮减速器的传动机构，进行了强度计算和结构设计，绘制了装配图。",
            "expected": "traditional_mechanical"
        },
    ]
    
    correct = 0
    for case in test_cases:
        result = detector.detect(case["title"], case["content"], "")
        is_correct = result["type"] == case["expected"]
        correct += 1 if is_correct else 0
        status = "[OK]" if is_correct else "[FAIL]"
        print(f"  {status} {case['title'][:20]}... -> {result['type']} (expected: {case['expected']}, confidence: {result['confidence']:.2%})")
    
    print(f"\n类型检测准确率: {correct}/{len(test_cases)} ({correct/len(test_cases)*100:.0f}%)")
    
    print("\n2. 测试文本清理...")
    from src.frontend.pages.main import clean_pdf_text
    
    test_text = "这是  一段   测试文本。\n\n\n包含多个空格和换行。"
    cleaned = clean_pdf_text(test_text)
    print(f"  原始: {repr(test_text)}")
    print(f"  清理后: {repr(cleaned)}")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    quick_test()
