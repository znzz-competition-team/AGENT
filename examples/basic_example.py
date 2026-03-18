"""
学生多维度评估系统 - 基础示例

本示例展示如何使用系统进行基本的学生评估
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings, get_input_dir, get_output_dir
from src.processors.processor_factory import ProcessorFactory
from src.agents.crew_manager import StudentEvaluationCrew
from src.visualization.static_visualizer import StaticVisualizer
from src.visualization.interactive_visualizer import InteractiveVisualizer
from src.utils.logger import setup_logger

def example_basic_evaluation():
    print("=" * 60)
    print("学生多维度评估系统 - 基础示例")
    print("=" * 60)
    
    logger = setup_logger("example", "data/output/example.log")
    
    student_id = "STU001"
    student_data = {
        "student_id": student_id,
        "name": "张三",
        "grade": "大三",
        "major": "计算机科学"
    }
    
    print(f"\n学生信息:")
    print(f"  学号: {student_data['student_id']}")
    print(f"  姓名: {student_data['name']}")
    print(f"  年级: {student_data['grade']}")
    print(f"  专业: {student_data['major']}")
    
    print(f"\n处理媒体文件...")
    
    input_dir = get_input_dir()
    
    video_file = input_dir / "presentation.mp4"
    audio_file = input_dir / "interview.wav"
    document_file = input_dir / "report.pdf"
    
    media_files = []
    if video_file.exists():
        media_files.append(str(video_file))
        print(f"  找到视频文件: {video_file.name}")
    if audio_file.exists():
        media_files.append(str(audio_file))
        print(f"  找到音频文件: {audio_file.name}")
    if document_file.exists():
        media_files.append(str(document_file))
        print(f"  找到文档文件: {document_file.name}")
    
    if not media_files:
        print("\n提示: 请将媒体文件放入 data/input/ 目录")
        print("支持的文件格式:")
        print("  视频: .mp4, .avi, .mov, .mkv")
        print("  音频: .wav, .mp3, .flac, .aac")
        print("  文档: .pdf, .docx, .doc, .xlsx, .xls, .txt")
        return
    
    processor_factory = ProcessorFactory()
    processing_results = processor_factory.batch_process(media_files)
    
    print(f"\n处理结果:")
    print(f"  成功: {processing_results['successful']}")
    print(f"  失败: {processing_results['failed']}")
    
    media_data = {}
    for result in processing_results["results"]:
        if result.get("status") == "success":
            file_path = result.get("file_path", "")
            media_type = processor_factory.detect_media_type(file_path)
            media_data[media_type] = result
            print(f"  {media_type} 处理成功")
    
    print(f"\n开始评估...")
    evaluation_crew = StudentEvaluationCrew()
    evaluation_result = evaluation_crew.evaluate_student(
        student_id, student_data, media_data
    )
    
    print(f"\n评估结果:")
    print(f"  综合评分: {evaluation_result.overall_score:.2f}/10")
    print(f"  评估时间: {evaluation_result.evaluated_at}")
    
    print(f"\n各维度评分:")
    for ds in evaluation_result.dimension_scores:
        print(f"  {ds.dimension.value.replace('_', ' ').title()}: "
              f"{ds.score:.1f}/10 (置信度: {ds.confidence:.2f})")
    
    if evaluation_result.strengths:
        print(f"\n优势:")
        for strength in evaluation_result.strengths:
            print(f"  - {strength}")
    
    if evaluation_result.areas_for_improvement:
        print(f"\n需要改进:")
        for area in evaluation_result.areas_for_improvement:
            print(f"  - {area}")
    
    if evaluation_result.recommendations:
        print(f"\n建议:")
        for i, rec in enumerate(evaluation_result.recommendations, 1):
            print(f"  {i}. {rec}")
    
    print(f"\n生成可视化图表...")
    
    static_visualizer = StaticVisualizer(str(get_output_dir()))
    interactive_visualizer = InteractiveVisualizer(str(get_output_dir()))
    
    bar_chart = static_visualizer.plot_dimension_scores(evaluation_result)
    print(f"  条形图: {bar_chart}")
    
    radar_chart = static_visualizer.plot_radar_chart(evaluation_result)
    print(f"  雷达图: {radar_chart}")
    
    dashboard = interactive_visualizer.create_dashboard([evaluation_result])
    print(f"  交互式仪表板: {dashboard}")
    
    json_path = interactive_visualizer.export_to_json([evaluation_result])
    print(f"  JSON数据: {json_path}")
    
    print(f"\n完成！所有结果已保存到: {get_output_dir()}")

if __name__ == "__main__":
    example_basic_evaluation()