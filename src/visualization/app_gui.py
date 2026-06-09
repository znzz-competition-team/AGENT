import streamlit as st
import pandas as pd

# 页面布局
st.set_page_config(page_title="AGENT 能力评估插件", layout="wide")

st.title("🛡️ AGENT: 学生工具能力智能评估")
st.sidebar.header("评估配置")
current_stage = st.sidebar.selectbox("当前评估阶段", ["感知期", "应用期", "内化期", "创新期"])

uploaded_file = st.file_uploader("上传学生报告 (Markdown/TXT)", type=['md', 'txt'])

if uploaded_file:
    content = uploaded_file.read().decode("utf-8")
    analyzer = StudentToolAnalyzer(stage=current_stage)
    
    # 执行分析
    ai_metrics = analyzer.detect_ai_usage(content)
    math_score, formulas = analyzer.evaluate_math_formula(content)
    
    # --- UI 展示 ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("AI 生成概率", f"{ai_metrics['ai_probability']:.1f}%")
        st.progress(ai_metrics['ai_probability'] / 100)
        
    with col2:
        st.metric("数学工具得分", f"{math_score}/100")
        st.progress(math_score / 100)

    with col3:
        usage_type = "一键生成 ⚠️" if ai_metrics['is_one_shot'] else "深度协同 ✅"
        st.metric("创作模式判定", usage_type)

    # 周期性对比图
    st.subheader("📈 周期性能力成长曲线")
    # 模拟历史数据
    history_df = pd.DataFrame({
        "阶段": ["感知期", "应用期"],
        "AI协同": [45, ai_metrics['ai_probability']],
        "数学建模": [30, math_score]
    })
    st.line_chart(history_df.set_index("阶段"))

    # LaTeX 公式展示区
    if formulas:
        st.subheader("📐 检测到的核心公式")
        for f in formulas[:3]: # 展示前三个
            st.latex(f[0] if f[0] else f[1])