from typing import Dict, List, Optional, Any
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime
from models.schemas import EvaluationResult, DimensionScore, EvaluationDimension

class VisualizationService:
    """
    可视化服务，用于生成学生评估结果的各种图表
    """
    
    # 维度名称映射
    DIMENSION_NAMES = {
        EvaluationDimension.ACADEMIC_PERFORMANCE: "学术表现",
        EvaluationDimension.COMMUNICATION_SKILLS: "沟通能力",
        EvaluationDimension.LEADERSHIP: "领导力",
        EvaluationDimension.TEAMWORK: "团队协作",
        EvaluationDimension.CREATIVITY: "创新能力",
        EvaluationDimension.PROBLEM_SOLVING: "问题解决",
        EvaluationDimension.TIME_MANAGEMENT: "时间管理",
        EvaluationDimension.ADAPTABILITY: "适应能力",
        EvaluationDimension.TECHNICAL_SKILLS: "技术能力",
        EvaluationDimension.CRITICAL_THINKING: "批判性思维"
    }
    
    # 颜色配置
    COLORS = {
        "primary": "#4C78A8",
        "secondary": "#F58518",
        "success": "#72B7B2",
        "warning": "#E4572E",
        "info": "#54A24B",
        "light": "#ECEFF1",
        "dark": "#2C3E50"
    }
    
   def generate_radar_chart(self, dimension_scores: List[DimensionScore], avg_scores: List[float] = None) -> Dict[str, Any]:
        """
        生成高精度的多维度能力评估对比雷达图
        
        Args:
            dimension_scores: 当前学生的维度评分列表
            avg_scores: 全体/班级平均分列表（顺序需与维度一致）。若为 None 则只显示个人数据。
        """
        # 1. 准备和转换基础数据
        dimensions = []
        scores = []
        for score in dimension_scores:
            dimension_name = self.DIMENSION_NAMES.get(score.dimension, score.dimension.value)
            dimensions.append(dimension_name)
            scores.append(score.score)

        # 如果没有传入均值，这里模拟一组均值数据（或者你可以设为全 0/全 5）
        if avg_scores is None:
            avg_scores = [7.5, 7.0, 6.8, 7.2, 7.0, 6.5] # 假设总分是 10

        # --- 核心优化点：闭合数据环 ---
        # Plotly 雷达图如果不手动把第一个点加到末尾，线条不会首尾相连
        plot_dimensions = dimensions + [dimensions[0]]
        plot_scores = scores + [scores[0]]
        plot_avg = avg_scores + [avg_scores[0]]

        fig = go.Figure()

        # 2. 添加【班级平均】轨迹 (作为背景基准)
        fig.add_trace(go.Scatterpolar(
            r=plot_avg,
            theta=plot_dimensions,
            fill='toself',
            name='班级平均水平',
            fillcolor='rgba(200, 200, 200, 0.2)', # 浅灰色填充
            line=dict(color='gray', width=2, dash='dash'), # 灰色虚线
            marker=dict(size=4)
        ))

        # 3. 添加【个人表现】轨迹 (高亮突出)
        fig.add_trace(go.Scatterpolar(
            r=plot_scores,
            theta=plot_dimensions,
            fill='toself',
            name='学生个人表现',
            fillcolor='rgba(99, 110, 250, 0.35)', # 半透明主色
            line=dict(color='#636EFA', width=4),     # 加粗实线
            marker=dict(
                size=12, 
                symbol='circle-dot',
                color='#636EFA'
            )
        ))

        # 4. 深度布局优化 (大字体 & 清爽背景)
        fig.update_layout(
            polar=dict(
                bgcolor="white",
                radialaxis=dict(
                    visible=True,
                    range=[0, 10], # 假设分值范围 0-10
                    gridcolor="#F0F0F0",
                    tickfont=dict(size=14, color="#999999")
                ),
                angularaxis=dict(
                    # 关键：调大维度标签字体（3倍于默认，约18-20px）
                    tickfont=dict(size=20, color="black", weight="bold"),
                    gridcolor="#F0F0F0",
                    rotation=90,
                    direction="clockwise"
                )
            ),
            title=dict(
                text="<b>学生综合能力评估报告</b>",
                font=dict(size=30, color="#1A1A1A"), # 标题大字体
                x=0.5,
                y=0.98
            ),
            legend=dict(
                orientation="h", # 横向图例
                yanchor="bottom",
                y=-0.2,
                xanchor="center",
                x=0.5,
                font=dict(size=16)
            ),
            margin=dict(l=100, r=100, t=120, b=100),
            paper_bgcolor="rgba(0,0,0,0)"
        )

        # 转换为字典供前端解析
        return fig.to_dict()
    
    def generate_score_card(self, evaluation_result: EvaluationResult) -> Dict[str, Any]:
        """
        生成评分卡片
        
        Args:
            evaluation_result: 评估结果
        
        Returns:
            Dict[str, Any]: 评分卡片的配置数据
        """
        # 确定评分等级和颜色
        score = evaluation_result.overall_score
        if score >= 9.0:
            level = "优秀"
            color = self.COLORS["success"]
        elif score >= 7.5:
            level = "良好"
            color = self.COLORS["info"]
        elif score >= 6.0:
            level = "中等"
            color = self.COLORS["primary"]
        elif score >= 4.0:
            level = "待改进"
            color = self.COLORS["warning"]
        else:
            level = "较差"
            color = self.COLORS["secondary"]
        
        # 创建评分卡片
        fig = go.Figure()
        
        # 添加评分数字
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=score,
            title={'text': "综合评分"},
            gauge={
                'axis': {'range': [0, 10]},
                'bar': {'color': color},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, 4], 'color': self.COLORS["secondary"]},
                    {'range': [4, 6], 'color': self.COLORS["warning"]},
                    {'range': [6, 7.5], 'color': self.COLORS["primary"]},
                    {'range': [7.5, 9], 'color': self.COLORS["info"]},
                    {'range': [9, 10], 'color': self.COLORS["success"]}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': score
                }
            }
        ))
        
        # 配置图表
        fig.update_layout(
            title=f"评分等级: {level}",
            height=400
        )
        
        # 转换为JSON格式
        return fig.to_dict()
    
    def generate_trend_chart(self, evaluation_results: List[EvaluationResult]) -> Dict[str, Any]:
        """
        生成趋势图
        
        Args:
            evaluation_results: 评估结果列表（按时间顺序）
        
        Returns:
            Dict[str, Any]: 趋势图的配置数据
        """
        # 准备数据
        dates = []
        scores = []
        
        for result in evaluation_results:
            dates.append(result.evaluated_at)
            scores.append(result.overall_score)
        
        # 创建趋势图
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=scores,
            mode='lines+markers',
            name='综合评分',
            line=dict(color=self.COLORS["primary"], width=2),
            marker=dict(size=8, color=self.COLORS["primary"])
        ))
        
        # 添加趋势线
        if len(scores) > 1:
            # 计算趋势线
            df = pd.DataFrame({'date': dates, 'score': scores})
            df['date_num'] = pd.to_datetime(df['date']).astype(int) / 10**9
            
            # 线性回归
            from sklearn.linear_model import LinearRegression
            model = LinearRegression()
            model.fit(df[['date_num']], df['score'])
            df['trend'] = model.predict(df[['date_num']])
            
            # 添加趋势线
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=df['trend'],
                mode='lines',
                name='趋势线',
                line=dict(color=self.COLORS["secondary"], width=2, dash='dash')
            ))
        
        # 配置图表
        fig.update_layout(
            title="学生能力发展趋势图",
            xaxis_title="评估日期",
            yaxis_title="综合评分",
            yaxis_range=[0, 10],
            showlegend=True
        )
        
        # 转换为JSON格式
        return fig.to_dict()
    
    def generate_dimension_bar_chart(self, dimension_scores: List[DimensionScore]) -> Dict[str, Any]:
        """
        生成维度评分柱状图
        
        Args:
            dimension_scores: 各维度的评分列表
        
        Returns:
            Dict[str, Any]: 柱状图的配置数据
        """
        # 准备数据
        dimensions = []
        scores = []
        colors = []
        
        for score in dimension_scores:
            dimension_name = self.DIMENSION_NAMES.get(score.dimension, score.dimension.value)
            dimensions.append(dimension_name)
            scores.append(score.score)
            
            # 根据评分确定颜色
            if score.score >= 9.0:
                colors.append(self.COLORS["success"])
            elif score.score >= 7.5:
                colors.append(self.COLORS["info"])
            elif score.score >= 6.0:
                colors.append(self.COLORS["primary"])
            elif score.score >= 4.0:
                colors.append(self.COLORS["warning"])
            else:
                colors.append(self.COLORS["secondary"])
        
        # 创建柱状图
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=dimensions,
            y=scores,
            marker_color=colors,
            name='维度评分'
        ))
        
        # 配置图表
        fig.update_layout(
            title="各维度能力评分",
            xaxis_title="能力维度",
            yaxis_title="评分",
            yaxis_range=[0, 10],
            showlegend=False,
            xaxis_tickangle=-45
        )
        
        # 转换为JSON格式
        return fig.to_dict()
    
    def generate_heatmap(self, evaluation_results: List[EvaluationResult]) -> Dict[str, Any]:
        """
        生成热力图
        
        Args:
            evaluation_results: 评估结果列表
        
        Returns:
            Dict[str, Any]: 热力图的配置数据
        """
        # 准备数据
        data = []
        
        for result in evaluation_results:
            for score in result.dimension_scores:
                data.append({
                    'date': result.evaluated_at,
                    'dimension': self.DIMENSION_NAMES.get(score.dimension, score.dimension.value),
                    'score': score.score
                })
        
        # 创建DataFrame
        df = pd.DataFrame(data)
        
        #  pivot表
        pivot_df = df.pivot(index='dimension', columns='date', values='score')
        
        # 创建热力图
        fig = go.Figure(data=go.Heatmap(
            z=pivot_df.values,
            x=pivot_df.columns,
            y=pivot_df.index,
            colorscale=[
                [0, self.COLORS["secondary"]],
                [0.4, self.COLORS["warning"]],
                [0.6, self.COLORS["primary"]],
                [0.75, self.COLORS["info"]],
                [1, self.COLORS["success"]]
            ],
            colorbar=dict(title="评分")
        ))
        
        # 配置图表
        fig.update_layout(
            title="各维度能力发展热力图",
            xaxis_title="评估日期",
            yaxis_title="能力维度"
        )
        
        # 转换为JSON格式
        return fig.to_dict()
    
    def generate_comparison_chart(self, student_results: Dict[str, List[DimensionScore]]) -> Dict[str, Any]:
        """
        生成学生能力对比图
        
        Args:
            student_results: 学生ID到维度评分的映射
        
        Returns:
            Dict[str, Any]: 对比图的配置数据
        """
        # 准备数据
        data = []
        
        for student_id, dimension_scores in student_results.items():
            for score in dimension_scores:
                data.append({
                    'student': student_id,
                    'dimension': self.DIMENSION_NAMES.get(score.dimension, score.dimension.value),
                    'score': score.score
                })
        
        # 创建DataFrame
        df = pd.DataFrame(data)
        
        # 创建分组柱状图
        fig = px.bar(
            df,
            x='dimension',
            y='score',
            color='student',
            barmode='group',
            title='学生能力对比图',
            labels={'score': '评分', 'dimension': '能力维度'},
            color_discrete_sequence=[self.COLORS["primary"], self.COLORS["secondary"], self.COLORS["info"], self.COLORS["success"]]
        )
        
        # 配置图表
        fig.update_layout(
            yaxis_range=[0, 10],
            xaxis_tickangle=-45
        )
        
        # 转换为JSON格式
        return fig.to_dict()