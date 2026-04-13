import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from ..models.schemas import EvaluationResult, DimensionScore

class InteractiveVisualizer:
    def __init__(self, output_dir: str = "data/output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_dimension_scores_chart(self, evaluation_result: EvaluationResult,
                                      save_path: Optional[str] = None) -> str:
        dimensions = [ds.dimension.value.replace('_', ' ').title() 
                    for ds in evaluation_result.dimension_scores]
        scores = [ds.score for ds in evaluation_result.dimension_scores]
        confidences = [ds.confidence for ds in evaluation_result.dimension_scores]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=dimensions,
            y=scores,
            name='评分',
            text=[f'{s:.1f}<br>(c:{c:.2f})' for s, c in zip(scores, confidences)],
            textposition='outside',
            marker=dict(
                color=scores,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="评分")
            )
        ))
        
        fig.update_layout(
            title=f'学生 {evaluation_result.student_id} 多维度评估结果',
            xaxis_title='评估维度',
            yaxis_title='评分 (0-10)',
            yaxis=dict(range=[0, 10]),
            hovermode='x unified',
            template='plotly_white',
            height=600
        )
        
        if save_path is None:
            save_path = self.output_dir / f"interactive_dimension_scores_{evaluation_result.student_id}.html"
        
        fig.write_html(str(save_path))
        return str(save_path)
    
    def create_radar_chart(self, evaluation_result: EvaluationResult,
                          save_path: Optional[str] = None) -> str:
        dimensions = [ds.dimension.value.replace('_', ' ').title() 
                    for ds in evaluation_result.dimension_scores]
        scores = [ds.score for ds in evaluation_result.dimension_scores]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=scores + [scores[0]],
            theta=dimensions + [dimensions[0]],
            fill='toself',
            name='评分',
            line_color='rgb(99, 110, 250)',
            fillcolor='rgba(99, 110, 250, 0.3)'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 10]
                )
            ),
            showlegend=True,
            title=f'学生 {evaluation_result.student_id} 能力雷达图',
            template='plotly_white',
            height=700
        )
        
        if save_path is None:
            save_path = self.output_dir / f"interactive_radar_{evaluation_result.student_id}.html"
        
        fig.write_html(str(save_path))
        return str(save_path)
    
    def create_comparison_chart(self, evaluation_results: List[EvaluationResult],
                               save_path: Optional[str] = None) -> str:
        fig = go.Figure()
        
        all_dimensions = set()
        for result in evaluation_results:
            all_dimensions.update([ds.dimension.value for ds in result.dimension_scores])
        
        all_dimensions = sorted(list(all_dimensions))
        
        colors = px.colors.qualitative.Set3
        
        for i, result in enumerate(evaluation_results):
            scores = []
            for dim in all_dimensions:
                dim_score = next((ds.score for ds in result.dimension_scores 
                                 if ds.dimension.value == dim), 0)
                scores.append(dim_score)
            
            fig.add_trace(go.Bar(
                name=f'学生 {result.student_id}',
                x=all_dimensions,
                y=scores,
                marker_color=colors[i % len(colors)]
            ))
        
        fig.update_layout(
            title='多学生评估结果对比',
            xaxis_title='评估维度',
            yaxis_title='评分 (0-10)',
            barmode='group',
            yaxis=dict(range=[0, 10]),
            template='plotly_white',
            height=600
        )
        
        if save_path is None:
            save_path = self.output_dir / "interactive_comparison.html"
        
        fig.write_html(str(save_path))
        return str(save_path)
    
    def create_overall_scores_chart(self, evaluation_results: List[EvaluationResult],
                                    save_path: Optional[str] = None) -> str:
        student_ids = [result.student_id for result in evaluation_results]
        overall_scores = [result.overall_score for result in evaluation_results]
        
        colors = ['rgb(255, 0, 0)' if score < 4 else 
                 'rgb(255, 165, 0)' if score < 7 else 
                 'rgb(0, 128, 0)' for score in overall_scores]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=student_ids,
            y=overall_scores,
            marker_color=colors,
            text=[f'{score:.2f}' for score in overall_scores],
            textposition='outside'
        ))
        
        fig.update_layout(
            title='学生综合评分对比',
            xaxis_title='学生ID',
            yaxis_title='综合评分 (0-10)',
            yaxis=dict(range=[0, 10]),
            template='plotly_white',
            height=500
        )
        
        if save_path is None:
            save_path = self.output_dir / "interactive_overall_scores.html"
        
        fig.write_html(str(save_path))
        return str(save_path)
    
    def create_dashboard(self, evaluation_results: List[EvaluationResult],
                         save_path: Optional[str] = None) -> str:
        from plotly.subplots import make_subplots
        
        if len(evaluation_results) == 1:
            result = evaluation_results[0]
            
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('维度评分', '能力雷达图', '置信度分布', '综合评分'),
                specs=[[{'type': 'bar'}, {'type': 'polar'}],
                       [{'type': 'bar'}, {'type': 'indicator'}]]
            )
            
            dimensions = [ds.dimension.value.replace('_', ' ').title() 
                        for ds in result.dimension_scores]
            scores = [ds.score for ds in result.dimension_scores]
            confidences = [ds.confidence for ds in result.dimension_scores]
            
            fig.add_trace(
                go.Bar(x=dimensions, y=scores, name='评分'),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatterpolar(r=scores + [scores[0]], 
                               theta=dimensions + [dimensions[0]],
                               fill='toself', name='能力'),
                row=1, col=2
            )
            
            fig.add_trace(
                go.Bar(x=dimensions, y=confidences, name='置信度'),
                row=2, col=1
            )
            
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=result.overall_score,
                    title={'text': "综合评分"},
                    gauge={'axis': {'range': [0, 10]},
                          'bar': {'color': "darkblue"},
                          'steps': [
                              {'range': [0, 4], 'color': "lightgray"},
                              {'range': [4, 7], 'color': "gray"},
                              {'range': [7, 10], 'color': "lightgreen"}],
                          'threshold': {'line': {'color': "red", 'width': 4},
                                      'thickness': 0.75,
                                      'value': 8}}
                ),
                row=2, col=2
            )
            
            fig.update_layout(
                title_text=f'学生 {result.student_id} 评估仪表板',
                height=800,
                showlegend=False
            )
            
        else:
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('综合评分对比', '维度评分对比', '评分分布', '置信度对比'),
                specs=[[{'type': 'bar'}, {'type': 'bar'}],
                       [{'type': 'box'}, {'type': 'bar'}]]
            )
            
            student_ids = [result.student_id for result in evaluation_results]
            overall_scores = [result.overall_score for result in evaluation_results]
            
            fig.add_trace(
                go.Bar(x=student_ids, y=overall_scores, name='综合评分'),
                row=1, col=1
            )
            
            all_dimensions = set()
            for result in evaluation_results:
                all_dimensions.update([ds.dimension.value for ds in result.dimension_scores])
            all_dimensions = sorted(list(all_dimensions))
            
            colors = px.colors.qualitative.Set3
            for i, result in enumerate(evaluation_results):
                scores = []
                for dim in all_dimensions:
                    dim_score = next((ds.score for ds in result.dimension_scores 
                                     if ds.dimension.value == dim), 0)
                    scores.append(dim_score)
                
                fig.add_trace(
                    go.Bar(name=f'学生 {result.student_id}',
                          x=all_dimensions, y=scores,
                          marker_color=colors[i % len(colors)]),
                    row=1, col=2
                )
            
            all_scores = []
            for result in evaluation_results:
                all_scores.extend([ds.score for ds in result.dimension_scores])
            
            fig.add_trace(
                go.Box(y=all_scores, name='评分分布'),
                row=2, col=1
            )
            
            avg_confidences = []
            for result in evaluation_results:
                avg_conf = sum(ds.confidence for ds in result.dimension_scores) / len(result.dimension_scores)
                avg_confidences.append(avg_conf)
            
            fig.add_trace(
                go.Bar(x=student_ids, y=avg_confidences, name='平均置信度'),
                row=2, col=2
            )
            
            fig.update_layout(
                title_text='多学生评估仪表板',
                height=800,
                barmode='group'
            )
        
        if save_path is None:
            save_path = self.output_dir / "interactive_dashboard.html"
        
        fig.write_html(str(save_path))
        return str(save_path)
    
    def export_to_json(self, evaluation_results: List[EvaluationResult],
                      save_path: Optional[str] = None) -> str:
        data = []
        for result in evaluation_results:
            result_dict = {
                "student_id": result.student_id,
                "evaluation_id": result.evaluation_id,
                "overall_score": result.overall_score,
                "dimension_scores": [
                    {
                        "dimension": ds.dimension.value,
                        "score": ds.score,
                        "confidence": ds.confidence,
                        "evidence": ds.evidence,
                        "reasoning": ds.reasoning
                    }
                    for ds in result.dimension_scores
                ],
                "strengths": result.strengths,
                "areas_for_improvement": result.areas_for_improvement,
                "recommendations": result.recommendations,
                "evaluated_at": result.evaluated_at.isoformat(),
                "evaluator_agent": result.evaluator_agent
            }
            data.append(result_dict)
        
        if save_path is None:
            save_path = self.output_dir / "evaluation_results.json"
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(save_path)