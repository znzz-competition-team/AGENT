import streamlit as st
from typing import List, Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from ..models.schemas import EvaluationResult, DimensionScore
from ..visualization.interactive_visualizer import InteractiveVisualizer

class StreamlitDashboard:
    def __init__(self):
        self.visualizer = InteractiveVisualizer()
        
    def render_evaluation_results(self, evaluation_results: List[EvaluationResult]):
        st.set_page_config(
            page_title="学生多维度评估系统",
            page_icon="📊",
            layout="wide"
        )
        
        st.title("🎓 学生多维度评估系统")
        st.markdown("---")
        
        if not evaluation_results:
            st.warning("暂无评估结果")
            return
        
        st.sidebar.title("导航")
        page = st.sidebar.radio("选择页面", ["概览", "详细评估", "对比分析", "数据导出"])
        
        if page == "概览":
            self.render_overview(evaluation_results)
        elif page == "详细评估":
            self.render_detailed_evaluation(evaluation_results)
        elif page == "对比分析":
            self.render_comparison(evaluation_results)
        elif page == "数据导出":
            self.render_data_export(evaluation_results)
    
    def render_overview(self, evaluation_results: List[EvaluationResult]):
        st.header("📊 评估概览")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="评估学生总数",
                value=len(evaluation_results)
            )
        
        with col2:
            avg_score = sum(r.overall_score for r in evaluation_results) / len(evaluation_results)
            st.metric(
                label="平均综合评分",
                value=f"{avg_score:.2f}"
            )
        
        with col3:
            top_student = max(evaluation_results, key=lambda x: x.overall_score)
            st.metric(
                label="最高评分学生",
                value=f"{top_student.student_id} ({top_student.overall_score:.2f})"
            )
        
        st.markdown("---")
        
        st.subheader("综合评分排名")
        sorted_results = sorted(evaluation_results, key=lambda x: x.overall_score, reverse=True)
        
        df = pd.DataFrame([
            {
                "学生ID": r.student_id,
                "综合评分": r.overall_score,
                "评估时间": r.evaluated_at.strftime("%Y-%m-%d %H:%M")
            }
            for r in sorted_results
        ])
        
        fig = px.bar(
            df,
            x="学生ID",
            y="综合评分",
            color="综合评分",
            color_continuous_scale="RdYlGn",
            title="学生综合评分排名"
        )
        
        fig.update_yaxis(range=[0, 10])
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("评分分布")
        all_scores = []
        for result in evaluation_results:
            all_scores.extend([ds.score for ds in result.dimension_scores])
        
        fig = px.histogram(
            all_scores,
            nbins=20,
            title="评分分布直方图",
            labels={"value": "评分", "count": "频次"}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    def render_detailed_evaluation(self, evaluation_results: List[EvaluationResult]):
        st.header("📋 详细评估")
        
        selected_student = st.selectbox(
            "选择学生",
            options=[r.student_id for r in evaluation_results],
            index=0
        )
        
        result = next((r for r in evaluation_results if r.student_id == selected_student), None)
        
        if result:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader(f"学生 {result.student_id} - 综合评分: {result.overall_score:.2f}")
                
                dimensions = [ds.dimension.value.replace('_', ' ').title() 
                            for ds in result.dimension_scores]
                scores = [ds.score for ds in result.dimension_scores]
                confidences = [ds.confidence for ds in result.dimension_scores]
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=dimensions,
                    y=scores,
                    name='评分',
                    text=[f'{s:.1f}' for s in scores],
                    textposition='outside',
                    marker_color=scores,
                    marker_colorscale='Viridis'
                ))
                fig.update_yaxis(range=[0, 10])
                fig.update_layout(title="各维度评分")
                st.plotly_chart(fig, use_container_width=True)
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=scores + [scores[0]],
                    theta=dimensions + [dimensions[0]],
                    fill='toself',
                    name='能力'
                ))
                fig.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
                    showlegend=False,
                    title="能力雷达图"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("评估详情")
                
                for ds in result.dimension_scores:
                    with st.expander(f"{ds.dimension.value.replace('_', ' ').title()} - {ds.score:.1f}/10"):
                        st.write(f"**置信度**: {ds.confidence:.2f}")
                        st.write(f"**理由**: {ds.reasoning}")
                        
                        if ds.evidence:
                            st.write("**证据**:")
                            for evidence in ds.evidence:
                                st.write(f"- {evidence}")
                
                st.subheader("综合评价")
                
                if result.strengths:
                    st.write("**优势**:")
                    for strength in result.strengths:
                        st.success(strength)
                
                if result.areas_for_improvement:
                    st.write("**需要改进**:")
                    for area in result.areas_for_improvement:
                        st.warning(area)
                
                if result.recommendations:
                    st.write("**建议**:")
                    for i, rec in enumerate(result.recommendations, 1):
                        st.info(f"{i}. {rec}")
    
    def render_comparison(self, evaluation_results: List[EvaluationResult]):
        st.header("🔍 对比分析")
        
        if len(evaluation_results) < 2:
            st.info("需要至少2个学生才能进行对比分析")
            return
        
        selected_students = st.multiselect(
            "选择要对比的学生",
            options=[r.student_id for r in evaluation_results],
            default=[r.student_id for r in evaluation_results[:2]]
        )
        
        if len(selected_students) < 2:
            st.warning("请至少选择2个学生进行对比")
            return
        
        selected_results = [r for r in evaluation_results if r.student_id in selected_students]
        
        all_dimensions = set()
        for result in selected_results:
            all_dimensions.update([ds.dimension.value for ds in result.dimension_scores])
        all_dimensions = sorted(list(all_dimensions))
        
        fig = go.Figure()
        
        colors = px.colors.qualitative.Set3
        for i, result in enumerate(selected_results):
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
            barmode='group',
            yaxis=dict(range=[0, 10])
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("综合评分对比")
        
        comparison_data = []
        for result in selected_results:
            comparison_data.append({
                "学生ID": result.student_id,
                "综合评分": result.overall_score
            })
        
        df = pd.DataFrame(comparison_data)
        fig = px.bar(df, x="学生ID", y="综合评分", 
                    color="综合评分", color_continuous_scale="RdYlGn")
        fig.update_yaxis(range=[0, 10])
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("各维度详细对比")
        
        comparison_df = pd.DataFrame()
        for result in selected_results:
            row_data = {"学生ID": result.student_id}
            for ds in result.dimension_scores:
                row_data[ds.dimension.value.replace('_', ' ').title()] = ds.score
            comparison_df = pd.concat([comparison_df, pd.DataFrame([row_data])], ignore_index=True)
        
        st.dataframe(comparison_df, use_container_width=True)
    
    def render_data_export(self, evaluation_results: List[EvaluationResult]):
        st.header("💾 数据导出")
        
        st.subheader("导出格式选择")
        
        export_format = st.radio(
            "选择导出格式",
            ["JSON", "CSV", "Excel"]
        )
        
        if export_format == "JSON":
            import json
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
                    "evaluated_at": result.evaluated_at.isoformat()
                }
                data.append(result_dict)
            
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            st.download_button(
                label="下载 JSON 文件",
                data=json_str,
                file_name="evaluation_results.json",
                mime="application/json"
            )
        
        elif export_format == "CSV":
            csv_data = []
            for result in evaluation_results:
                row = {
                    "student_id": result.student_id,
                    "overall_score": result.overall_score,
                    "evaluated_at": result.evaluated_at.strftime("%Y-%m-%d %H:%M:%S")
                }
                for ds in result.dimension_scores:
                    row[f"{ds.dimension.value}_score"] = ds.score
                    row[f"{ds.dimension.value}_confidence"] = ds.confidence
                csv_data.append(row)
            
            df = pd.DataFrame(csv_data)
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            
            st.download_button(
                label="下载 CSV 文件",
                data=csv,
                file_name="evaluation_results.csv",
                mime="text/csv"
            )
        
        elif export_format == "Excel":
            excel_data = []
            for result in evaluation_results:
                row = {
                    "学生ID": result.student_id,
                    "综合评分": result.overall_score,
                    "评估时间": result.evaluated_at.strftime("%Y-%m-%d %H:%M:%S")
                }
                for ds in result.dimension_scores:
                    row[f"{ds.dimension.value}_评分"] = ds.score
                    row[f"{ds.dimension.value}_置信度"] = ds.confidence
                excel_data.append(row)
            
            df = pd.DataFrame(excel_data)
            
            output = pd.ExcelWriter("evaluation_results.xlsx", engine='openpyxl')
            df.to_excel(output, index=False, sheet_name='评估结果')
            output.close()
            
            with open("evaluation_results.xlsx", "rb") as f:
                st.download_button(
                    label="下载 Excel 文件",
                    data=f.read(),
                    file_name="evaluation_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        st.markdown("---")
        st.subheader("评估报告")
        
        for result in evaluation_results:
            with st.expander(f"学生 {result.student_id} 评估报告"):
                st.write(f"**综合评分**: {result.overall_score:.2f}/10")
                st.write(f"**评估时间**: {result.evaluated_at.strftime('%Y-%m-%d %H:%M:%S')}")
                
                st.write("**各维度评分**:")
                for ds in result.dimension_scores:
                    st.write(f"- {ds.dimension.value.replace('_', ' ').title()}: {ds.score:.1f}/10 (置信度: {ds.confidence:.2f})")
                
                if result.strengths:
                    st.write("**优势**:")
                    for strength in result.strengths:
                        st.write(f"- {strength}")
                
                if result.areas_for_improvement:
                    st.write("**需要改进**:")
                    for area in result.areas_for_improvement:
                        st.write(f"- {area}")
                
                if result.recommendations:
                    st.write("**建议**:")
                    for i, rec in enumerate(result.recommendations, 1):
                        st.write(f"{i}. {rec}")

def run_dashboard(evaluation_results: List[EvaluationResult]):
    dashboard = StreamlitDashboard()
    dashboard.render_evaluation_results(evaluation_results)