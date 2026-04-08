from pathlib import Path


INSERT_BLOCK = r'''
    st.markdown("---")
    st.subheader("🧠 手写试卷批改")
    st.warning("请先在 `AI设置` 页面配置支持图像输入的模型，例如 `gpt-4o` 或 `glm-4v`。")

    grading_student_options = {"": "不绑定学生"}
    try:
        response = requests.get(f"{API_BASE_URL}/students", timeout=10)
        if response.status_code == 200:
            students = response.json()
            grading_student_options.update({
                item["student_id"]: f'{item["student_id"]} - {item["name"]}'
                for item in students
            })
    except Exception:
        pass

    with st.form("grade_handwriting_exam_form"):
        selected_grading_student_id = st.selectbox(
            "关联学生",
            options=list(grading_student_options.keys()),
            format_func=lambda x: grading_student_options[x]
        )

        col1, col2 = st.columns(2)
        with col1:
            subject = st.text_input("科目", placeholder="如：数学、语文、英语")
        with col2:
            total_score = st.text_input("试卷总分", placeholder="如：100，可留空")

        exam_files = st.file_uploader(
            "上传试卷图片",
            type=["png", "jpg", "jpeg", "bmp", "webp"],
            accept_multiple_files=True,
            key="handwriting_exam_files",
            help="支持多页试卷，一次可上传多张图片"
        )

        answer_key = st.text_area(
            "参考答案",
            placeholder="按题号填写标准答案，例如：\n1. A\n2. x=2\n3. 论点包括 ...",
            height=220
        )
        rubric = st.text_area(
            "评分细则",
            placeholder="可选，例如：选择题每题 5 分；计算题按步骤给分；字迹模糊处酌情扣分。",
            height=140
        )
        extra_requirements = st.text_area(
            "额外要求",
            placeholder="可选，例如：重点检查单位是否正确；作文按立意、结构、语言三项评分。",
            height=100
        )

        grade_submit = st.form_submit_button("开始批改试卷", use_container_width=True)

        if grade_submit:
            if not exam_files:
                st.error("请至少上传一张试卷图片。")
            elif not answer_key.strip():
                st.error("请填写参考答案。")
            else:
                try:
                    data = {
                        "answer_key": answer_key,
                        "rubric": rubric,
                        "subject": subject,
                        "student_id": selected_grading_student_id,
                        "total_score": total_score,
                        "extra_requirements": extra_requirements,
                    }
                    files = [
                        ("files", (uploaded_file.name, uploaded_file, uploaded_file.type))
                        for uploaded_file in exam_files
                    ]

                    with st.spinner("正在识别试卷并批改，请稍候..."):
                        response = requests.post(
                            f"{API_BASE_URL}/agent/grade-handwriting-exam",
                            data=data,
                            files=files,
                            timeout=300
                        )

                    if response.status_code == 200:
                        result = response.json()
                        st.success("试卷批改完成。")

                        metric_col1, metric_col2, metric_col3 = st.columns(3)
                        with metric_col1:
                            st.metric("总得分", f"{result.get('total_score', 0)}")
                        with metric_col2:
                            st.metric("满分", f"{result.get('max_score', 0)}")
                        with metric_col3:
                            st.metric("模型", result.get("model", "N/A"))

                        if result.get("overall_comment"):
                            st.subheader("总体评语")
                            st.write(result["overall_comment"])

                        if result.get("course_achievement_comment"):
                            st.subheader("课程达成度评价")
                            st.write(result["course_achievement_comment"])

                        if result.get("strengths"):
                            st.subheader("亮点")
                            for item in result["strengths"]:
                                st.markdown(f"- {item}")

                        if result.get("areas_for_improvement"):
                            st.subheader("待改进")
                            for item in result["areas_for_improvement"]:
                                st.markdown(f"- {item}")

                        if result.get("recognized_text"):
                            with st.expander("查看识别出的试卷文本"):
                                st.text_area("识别文本", value=result.get("recognized_text", ""), height=320)

                        question_results = result.get("question_results", [])
                        if question_results:
                            st.subheader("逐题结果")
                            for question in question_results:
                                title = (
                                    f"第 {question.get('question_number', '?')} 题"
                                    f" | 得分 {question.get('score', 0)}/{question.get('max_score', 0)}"
                                )
                                with st.expander(title):
                                    st.markdown("**学生答案**")
                                    st.write(question.get("recognized_answer", ""))
                                    if question.get("reference_answer"):
                                        st.markdown("**参考答案**")
                                        st.write(question.get("reference_answer"))
                                    st.markdown("**评分理由**")
                                    st.write(question.get("reasoning", ""))
                                    if question.get("strengths"):
                                        st.markdown("**本题亮点**")
                                        for item in question["strengths"]:
                                            st.markdown(f"- {item}")
                                    if question.get("mistakes"):
                                        st.markdown("**本题失分点**")
                                        for item in question["mistakes"]:
                                            st.markdown(f"- {item}")
                    else:
                        try:
                            error_detail = response.json().get("detail", "未知错误")
                        except Exception:
                            error_detail = f"HTTP {response.status_code}: {response.text}"
                        st.error(f"批改失败: {error_detail}")
                except Exception as e:
                    st.error(f"批改失败: {str(e)}")

'''


def main() -> None:
    path = Path(r"d:\AGENT\AGENT\src\frontend\app.py")
    text = path.read_text(encoding="utf-8")
    needle = '# ==================== AI è®¾ç½® ===================='
    if needle not in text:
        raise SystemExit("needle not found")
    if 'grade_handwriting_exam_form' in text:
        raise SystemExit("grading form already inserted")
    path.write_text(text.replace(needle, INSERT_BLOCK + "\n" + needle, 1), encoding="utf-8")
    print("inserted grading form")


if __name__ == "__main__":
    main()
