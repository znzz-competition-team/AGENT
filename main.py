import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any
import sys

from src.config import settings, get_input_dir, get_output_dir
from src.processors.processor_factory import ProcessorFactory
from src.agents.crew_manager import StudentEvaluationCrew
from src.visualization.static_visualizer import StaticVisualizer
from src.visualization.interactive_visualizer import InteractiveVisualizer
from src.utils.logger import setup_logger, get_logger

logger = setup_logger("student_profiler", "data/output/app.log", level=logging.INFO)

class StudentProfilerSystem:
    def __init__(self):
        self.processor_factory = ProcessorFactory()
        self.evaluation_crew = StudentEvaluationCrew()
        self.static_visualizer = StaticVisualizer(str(get_output_dir()))
        self.interactive_visualizer = InteractiveVisualizer(str(get_output_dir()))
        
    def process_media_files(self, file_paths: List[str]) -> Dict[str, Any]:
        logger.info(f"开始处理 {len(file_paths)} 个媒体文件")
        
        results = self.processor_factory.batch_process(file_paths)
        
        logger.info(f"处理完成: 成功 {results['successful']}, 失败 {results['failed']}")
        return results
    
    def evaluate_student(self, student_id: str, student_data: Dict[str, Any], 
                        media_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"开始评估学生: {student_id}")
        
        try:
            evaluation_result = self.evaluation_crew.evaluate_student(
                student_id, student_data, media_data
            )
            
            logger.info(f"学生 {student_id} 评估完成，综合评分: {evaluation_result.overall_score}")
            return evaluation_result.dict()
            
        except Exception as e:
            logger.error(f"评估学生 {student_id} 时出错: {str(e)}")
            raise
    
    def generate_visualizations(self, evaluation_results: List[Dict[str, Any]]) -> Dict[str, str]:
        logger.info("开始生成可视化图表")
        
        from src.models.schemas import EvaluationResult
        
        evaluation_objects = [EvaluationResult(**result) for result in evaluation_results]
        
        visualization_paths = {}
        
        for result in evaluation_objects:
            try:
                bar_chart = self.static_visualizer.plot_dimension_scores(result)
                radar_chart = self.static_visualizer.plot_radar_chart(result)
                confidence_chart = self.static_visualizer.plot_confidence_distribution(result)
                
                visualization_paths[f"{result.student_id}_bar"] = bar_chart
                visualization_paths[f"{result.student_id}_radar"] = radar_chart
                visualization_paths[f"{result.student_id}_confidence"] = confidence_chart
                
            except Exception as e:
                logger.error(f"生成 {result.student_id} 的可视化时出错: {str(e)}")
        
        if len(evaluation_objects) > 1:
            try:
                comparison_chart = self.static_visualizer.plot_comparison(evaluation_objects)
                overall_chart = self.static_visualizer.plot_overall_scores(evaluation_objects)
                
                visualization_paths["comparison"] = comparison_chart
                visualization_paths["overall"] = overall_chart
                
            except Exception as e:
                logger.error(f"生成对比图表时出错: {str(e)}")
        
        try:
            dashboard_path = self.interactive_visualizer.create_dashboard(evaluation_objects)
            visualization_paths["dashboard"] = dashboard_path
            
            json_path = self.interactive_visualizer.export_to_json(evaluation_objects)
            visualization_paths["json"] = json_path
            
        except Exception as e:
            logger.error(f"生成交互式仪表板时出错: {str(e)}")
        
        logger.info(f"可视化生成完成，共 {len(visualization_paths)} 个文件")
        return visualization_paths

def main():
    parser = argparse.ArgumentParser(description="学生多维度评估系统")
    parser.add_argument("--mode", choices=["evaluate", "visualize", "dashboard"], 
                       default="evaluate", help="运行模式")
    parser.add_argument("--student-id", type=str, help="学生ID")
    parser.add_argument("--name", type=str, help="学生姓名")
    parser.add_argument("--grade", type=str, help="年级")
    parser.add_argument("--major", type=str, help="专业")
    parser.add_argument("--input-dir", type=str, default="data/input", help="输入文件目录")
    parser.add_argument("--output-dir", type=str, default="data/output", help="输出文件目录")
    parser.add_argument("--video", type=str, help="视频文件路径")
    parser.add_argument("--audio", type=str, help="音频文件路径")
    parser.add_argument("--document", type=str, help="文档文件路径")
    parser.add_argument("--json-input", type=str, help="JSON输入文件路径")
    
    args = parser.parse_args()
    
    try:
        system = StudentProfilerSystem()
        
        if args.mode == "evaluate":
            if not args.student_id:
                logger.error("评估模式需要提供学生ID")
                sys.exit(1)
            
            student_data = {
                "student_id": args.student_id,
                "name": args.name or "未知",
                "grade": args.grade or "未知",
                "major": args.major or "未知"
            }
            
            media_files = []
            if args.video:
                media_files.append(args.video)
            if args.audio:
                media_files.append(args.audio)
            if args.document:
                media_files.append(args.document)
            
            if not media_files:
                logger.error("至少需要提供一个媒体文件（视频/音频/文档）")
                sys.exit(1)
            
            logger.info("开始处理媒体文件...")
            processing_results = system.process_media_files(media_files)
            
            media_data = {}
            for result in processing_results["results"]:
                if result.get("status") == "success":
                    file_path = result.get("file_path", "")
                    media_type = ProcessorFactory.detect_media_type(file_path)
                    media_data[media_type] = result
            
            logger.info("开始评估学生...")
            evaluation_result = system.evaluate_student(args.student_id, student_data, media_data)
            
            logger.info("生成可视化图表...")
            visualizations = system.generate_visualizations([evaluation_result])
            
            logger.info(f"评估完成！综合评分: {evaluation_result['overall_score']:.2f}")
            logger.info(f"可视化文件已保存到: {get_output_dir()}")
            
        elif args.mode == "visualize":
            if not args.json_input:
                logger.error("可视化模式需要提供JSON输入文件")
                sys.exit(1)
            
            import json
            with open(args.json_input, 'r', encoding='utf-8') as f:
                evaluation_results = json.load(f)
            
            logger.info("生成可视化图表...")
            visualizations = system.generate_visualizations(evaluation_results)
            
            logger.info(f"可视化完成！文件已保存到: {get_output_dir()}")
            
        elif args.mode == "dashboard":
            if not args.json_input:
                logger.error("仪表板模式需要提供JSON输入文件")
                sys.exit(1)
            
            import json
            from src.visualization.dashboard import run_dashboard
            
            with open(args.json_input, 'r', encoding='utf-8') as f:
                evaluation_results = json.load(f)
            
            from src.models.schemas import EvaluationResult
            evaluation_objects = [EvaluationResult(**result) for result in evaluation_results]
            
            logger.info("启动Streamlit仪表板...")
            run_dashboard(evaluation_objects)
        
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()