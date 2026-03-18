"""
学生多维度评估系统 - 批量评估示例

本示例展示如何批量评估多个学生
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_input_dir, get_output_dir
from src.processors.processor_factory import ProcessorFactory
from src.agents.crew_manager import StudentEvaluationCrew
from src.visualization.static_visualizer import StaticVisualizer
from src.visualization.interactive_visualizer import InteractiveVisualizer
from src.utils.logger import setup_logger

def example_batch_evaluation():
    print("=" * 60)
    print("学生多维度评估系统 - 批量评估示例")
    print("=" * 60)
    
    logger = setup_logger("batch_example", "data/output/batch_example.log")
    
    students_data = [
        {
            "student_id": "STU001",
            "name": "张三",
            "grade": "大三",
            "major": "计算机科学",
            "video": "presentation_stu001.mp4",
            "audio": "interview_stu001.wav",
            "document": "report_stu001.pdf"
        },
        {
            "student_id": "STU002",
            "name": "李四",
            "grade": "大四",
            "major": "软件工程",
            "video": "presentation_stu002.mp4",
            "audio": "interview_stu002.wav",
            "document": "report_stu002.pdf"
        },
        {
            "student_id": "STU003",
            "name": "王五",
            "grade": "大三",
            "major": "数据科学",
            "video": "presentation_stu003.mp4",
            "audio": "interview_stu003.wav",
            "document": "report_stu003.pdf"
        }
    ]
    
    print(f"\n准备评估 {len(students_data)} 名学生")
    
    processor_factory = ProcessorFactory()
    evaluation_crew = StudentEvaluationCrew()
    static_visualizer = StaticVisualizer(str(get_output_dir()))
    interactive_visualizer = InteractiveVisualizer(str(get_output_dir()))
    
    evaluation_results = []
    media_data_dict = {}
    
    input_dir = get_input_dir()
    
    for student in students_data:
        student_id = student["student_id"]
        print(f"\n{'=' * 40}")
        print(f"处理学生: {student['name']} ({student_id})")
        print(f"{'=' * 40}")
        
        media_files = []
        
        if "video" in student:
            video_path = input_dir / student["video"]
            if video_path.exists():
                media_files.append(str(video_path))
                print(f"  找到视频: {video_path.name}")
        
        if "audio" in student:
            audio_path = input_dir / student["audio"]
            if audio_path.exists():
                media_files.append(str(audio_path))
                print(f"  找到音频: {audio_path.name}")
        
        if "document" in student:
            doc_path = input_dir / student["document"]
            if doc_path.exists():
                media_files.append(str(doc_path))
                print(f"  找到文档: {doc_path.name}")
        
        if not media_files:
            print(f"  警告: 未找到 {student_id} 的媒体文件，跳过")
            continue
        
        print(f"\n  处理媒体文件...")
        processing_results = processor_factory.batch_process(media_files)
        
        media_data = {}
        for result in processing_results["results"]:
            if result.get("status") == "success":
                file_path = result.get("file_path", "")
                media_type = processor_factory.detect_media_type(file_path)
                media_data[media_type] = result
                print(f"    {media_type} 处理成功")
        
        media_data_dict[student_id] = media_data
        
        print(f"\n  评估学生...")
        try:
            evaluation_result = evaluation_crew.evaluate_student(
                student_id, student, media_data
            )
            evaluation_results.append(evaluation_result)
            
            print(f"  综合评分: {evaluation_result.overall_score:.2f}/10")
        except Exception as e:
            print(f"  评估失败: {str(e)}")
            continue
    
    if not evaluation_results:
        print("\n没有成功评估的学生")
        return
    
    print(f"\n{'=' * 60}")
    print(f"批量评估完成！共评估 {len(evaluation_results)} 名学生")
    print(f"{'=' * 60}")
    
    print(f"\n评估结果汇总:")
    for result in evaluation_results:
        print(f"  {result.student_id}: {result.overall_score:.2f}/10")
    
    print(f"\n生成对比图表...")
    
    comparison_chart = static_visualizer.plot_comparison(evaluation_results)
    print(f"  对比图表: {comparison_chart}")
    
    overall_chart = static_visualizer.plot_overall_scores(evaluation_results)
    print(f"  综合评分: {overall_chart}")
    
    dashboard = interactive_visualizer.create_dashboard(evaluation_results)
    print(f"  交互式仪表板: {dashboard}")
    
    json_path = interactive_visualizer.export_to_json(evaluation_results)
    print(f"  JSON数据: {json_path}")
    
    print(f"\n完成！所有结果已保存到: {get_output_dir()}")
    
    print(f"\n提示: 使用以下命令启动交互式仪表板:")
    print(f"  python main.py --mode dashboard --json-input {json_path}")

if __name__ == "__main__":
    example_batch_evaluation()