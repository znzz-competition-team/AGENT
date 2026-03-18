import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import seaborn as sns
from typing import Dict, Any, List, Optional
from pathlib import Path
import numpy as np
from ..models.schemas import EvaluationResult, DimensionScore

class StaticVisualizer:
    def __init__(self, output_dir: str = "data/output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")
    
    def plot_dimension_scores(self, evaluation_result: EvaluationResult, 
                             save_path: Optional[str] = None) -> str:
        fig, ax = plt.subplots(figsize=(12, 6))
        
        dimensions = [ds.dimension.value.replace('_', ' ').title() 
                    for ds in evaluation_result.dimension_scores]
        scores = [ds.score for ds in evaluation_result.dimension_scores]
        confidences = [ds.confidence for ds in evaluation_result.dimension_scores]
        
        x_pos = np.arange(len(dimensions))
        
        bars = ax.bar(x_pos, scores, alpha=0.8, capsize=5)
        
        for i, (bar, conf) in enumerate(zip(bars, confidences)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}\n({conf:.2f})',
                   ha='center', va='bottom', fontsize=9)
        
        ax.set_xlabel('评估维度', fontsize=12, fontweight='bold')
        ax.set_ylabel('评分 (0-10)', fontsize=12, fontweight='bold')
        ax.set_title(f'学生 {evaluation_result.student_id} 多维度评估结果', 
                    fontsize=14, fontweight='bold', pad=20)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(dimensions, rotation=45, ha='right')
        ax.set_ylim(0, 10)
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        if save_path is None:
            save_path = self.output_dir / f"dimension_scores_{evaluation_result.student_id}.png"
        
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(save_path)
    
    def plot_radar_chart(self, evaluation_result: EvaluationResult,
                        save_path: Optional[str] = None) -> str:
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
        
        dimensions = [ds.dimension.value.replace('_', ' ').title() 
                    for ds in evaluation_result.dimension_scores]
        scores = [ds.score for ds in evaluation_result.dimension_scores]
        
        angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False).tolist()
        scores_plot = scores + [scores[0]]
        angles_plot = angles + [angles[0]]
        
        ax.plot(angles_plot, scores_plot, 'o-', linewidth=2, label='评分')
        ax.fill(angles_plot, scores_plot, alpha=0.25)
        
        ax.set_xticks(angles)
        ax.set_xticklabels(dimensions, size=10)
        ax.set_ylim(0, 10)
        ax.set_yticks([2, 4, 6, 8, 10])
        ax.set_yticklabels(['2', '4', '6', '8', '10'], size=8)
        ax.grid(True)
        
        ax.set_title(f'学生 {evaluation_result.student_id} 能力雷达图', 
                    size=14, weight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        
        plt.tight_layout()
        
        if save_path is None:
            save_path = self.output_dir / f"radar_chart_{evaluation_result.student_id}.png"
        
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(save_path)
    
    def plot_comparison(self, evaluation_results: List[EvaluationResult],
                       save_path: Optional[str] = None) -> str:
        fig, ax = plt.subplots(figsize=(14, 8))
        
        student_ids = [result.student_id for result in evaluation_results]
        
        all_dimensions = set()
        for result in evaluation_results:
            all_dimensions.update([ds.dimension.value for ds in result.dimension_scores])
        
        all_dimensions = sorted(list(all_dimensions))
        
        dimension_map = {dim: i for i, dim in enumerate(all_dimensions)}
        
        x = np.arange(len(all_dimensions))
        width = 0.8 / len(evaluation_results)
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(evaluation_results)))
        
        for i, result in enumerate(evaluation_results):
            scores = []
            for dim in all_dimensions:
                dim_score = next((ds.score for ds in result.dimension_scores 
                                 if ds.dimension.value == dim), 0)
                scores.append(dim_score)
            
            offset = (i - len(evaluation_results) / 2 + 0.5) * width
            bars = ax.bar(x + offset, scores, width, 
                         label=f'学生 {result.student_id}', 
                         color=colors[i], alpha=0.8)
        
        ax.set_xlabel('评估维度', fontsize=12, fontweight='bold')
        ax.set_ylabel('评分 (0-10)', fontsize=12, fontweight='bold')
        ax.set_title('多学生评估结果对比', fontsize=14, fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels([dim.replace('_', ' ').title() for dim in all_dimensions], 
                          rotation=45, ha='right')
        ax.set_ylim(0, 10)
        ax.legend(loc='upper right')
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        if save_path is None:
            save_path = self.output_dir / "comparison_chart.png"
        
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(save_path)
    
    def plot_overall_scores(self, evaluation_results: List[EvaluationResult],
                           save_path: Optional[str] = None) -> str:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        student_ids = [result.student_id for result in evaluation_results]
        overall_scores = [result.overall_score for result in evaluation_results]
        
        colors = plt.cm.RdYlGn(np.array(overall_scores) / 10)
        
        bars = ax.bar(student_ids, overall_scores, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        
        for bar, score in zip(bars, overall_scores):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{score:.2f}',
                   ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        ax.set_xlabel('学生ID', fontsize=12, fontweight='bold')
        ax.set_ylabel('综合评分 (0-10)', fontsize=12, fontweight='bold')
        ax.set_title('学生综合评分对比', fontsize=14, fontweight='bold', pad=20)
        ax.set_ylim(0, 10)
        ax.grid(axis='y', alpha=0.3)
        
        sm = plt.cm.ScalarMappable(cmap=plt.cm.RdYlGn, norm=plt.Normalize(vmin=0, vmax=10))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax)
        cbar.set_label('评分等级', rotation=270, labelpad=20, fontsize=10)
        
        plt.tight_layout()
        
        if save_path is None:
            save_path = self.output_dir / "overall_scores.png"
        
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(save_path)
    
    def plot_confidence_distribution(self, evaluation_result: EvaluationResult,
                                     save_path: Optional[str] = None) -> str:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        dimensions = [ds.dimension.value.replace('_', ' ').title() 
                    for ds in evaluation_result.dimension_scores]
        confidences = [ds.confidence for ds in evaluation_result.dimension_scores]
        
        colors = plt.cm.Blues(np.array(confidences))
        
        bars = ax.barh(dimensions, confidences, color=colors, alpha=0.8, edgecolor='black', linewidth=1)
        
        for bar, conf in zip(bars, confidences):
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2.,
                   f'{conf:.2f}',
                   ha='left', va='center', fontsize=10, fontweight='bold')
        
        ax.set_xlabel('置信度', fontsize=12, fontweight='bold')
        ax.set_ylabel('评估维度', fontsize=12, fontweight='bold')
        ax.set_title(f'学生 {evaluation_result.student_id} 评估置信度分布', 
                    fontsize=14, fontweight='bold', pad=20)
        ax.set_xlim(0, 1)
        ax.grid(axis='x', alpha=0.3)
        
        plt.tight_layout()
        
        if save_path is None:
            save_path = self.output_dir / f"confidence_{evaluation_result.student_id}.png"
        
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(save_path)