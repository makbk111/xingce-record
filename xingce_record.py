import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import base64
from github import Github
from github import GithubException
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import mm
from io import BytesIO

# ========== 配置区 ==========
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "makbk111/xingce-record")
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
CSV_PATH = st.secrets.get("CSV_PATH", "行测刷题记录.csv")
ERROR_CSV_PATH = "行测错题本.csv"

# 艾宾浩斯间隔（单位：天）
review_interval = [1, 2, 4, 7, 15, 30]

# 大模块 -> 细分小模块
module_sub_map = {
    "常识判断": ["时政", "法律", "文史", "科技", "地理", "经济", "其他常识"],
    "言语理解": ["逻辑填空", "片段阅读", "语句排序", "语句填空", "下文推断"],
    "判断推理": ["图形推理", "定义判断", "类比推理", "逻辑判断"],
    "数量关系": ["工程问题", "行程问题", "利润问题", "排列组合", "概率", "容斥", "极值", "其他数量"],
    "资料分析": ["增长", "比重", "平均数", "倍数", "比较大小", "综合分析"]
}
main_module_list = list(module_sub_map.keys())

# 错因列表
reason_list = ["知识点盲区","审题粗心","公式遗忘","踩出题陷阱","时间不够蒙错","不会速算"]

# 试卷模板
paper_templates = {
    "自定义": {},
    "河南省行测": {
        "常识判断": 15,
        "言语理解": 15,
        "判断推理": 10,
        "数量关系":10,
        "资料分析":15
    }
}

# Github读写函数
def get_github_repo():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
    return repo

def load_csv_from_github(file_path):
    repo = get_github_repo()
    try:
        content_file = repo.get_contents(file_path, ref=GITHUB_BRANCH)
        decoded = base64.b64decode(content_file.content).decode("utf-8")
        df = pd.read_csv(pd.StringIO(decoded))
        return df, content_file.sha
    except GithubException:
        if file_path == ERROR_CSV_PATH:
            columns = [
                "日期","主模块","子模块","考点","题干","选项","正确答案","你的答案",
                "错因","解析","review_stage","last_review_date","next_review_date"
            ]
        else:
            columns = ["日期","试卷名称","总题量","答对","耗时分钟","备注"]
        df = pd.DataFrame(columns=columns)
        return df, None

def save_csv_to_github(df, file_path, old_sha):
    repo = get_github_repo()
    csv_data = df.to_csv(index=False, encoding="utf-8-sig")
    if old_sha is None:
        repo.create_file(file_path, f"init {file_path}", csv_data, branch=GITHUB_BRANCH)
    else:
        repo.update_file(file_path, f"update {file_path}", csv_data, old_sha, branch=GITHUB_BRANCH)

# 生成自测PDF（无答案）
def generate_pdf_test(df_export):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="TitleStyle", parent=styles["Heading1"], fontSize=16, alignment=1)
    normal_style = styles["Normal"]
    story = []
    story.append(Paragraph("行测错题本【自测版】", title_style))
    story.append(Spacer(1, 10*mm))

    for idx, row in df_export.iterrows():
        text = f"""
<b>主模块</b>：{row['主模块']}｜<b>子模块</b>：{row['子模块']}｜<b>考点</b>：{row['考点']}｜<b>错因</b>：{row['错因']}<br/>
<b>题干</b>：{row['题干']}<br/>
<b>选项</b>：{row['选项']}<br/>
——————————
<br/>
"""
        p = Paragraph(text, normal_style)
        story.append(p)
        story.append(Spacer(1, 6*mm))
    doc.build(story)
    buffer.seek(0)
    return buffer

# 生成解析PDF（带完整答案）
def generate_pdf_answer(df_export):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="TitleStyle", parent=styles["Heading1"], fontSize=16, alignment=1)
    normal_style = styles["Normal"]
    story = []
    story.append(Paragraph("行测错题本【解析版】", title_style))
    story.append(Spacer(1, 10*mm))

    for idx, row in df_export.iterrows():
        text = f"""
<b>主模块</b>：{row['主模块']}｜<b>子模块</b>：{row['子模块']}｜<b>考点</b>：{row['考点']}｜<b>错因</b>：{row['错因']}<br/>
<b>题干</b>：{row['题干']}<br/>
<b>选项</b>：{row['选项']}<br/>
✅正确答案：{row['正确答案']} ｜ ❌你的答案：{row['你的答案']}<br/>
<b>复盘笔记</b>：{row['解析']}
"""
        p = Paragraph(text, normal_style)
        story.append(p)
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph("-"*60, normal_style))
        story.append(Spacer(1, 4*mm))
    doc.build(story)
    buffer.seek(0)
    return buffer

# ========== 页面主体 ==========
st.set_page_config(page_title="行测刷题&艾宾浩斯错题本｜细分小模块", layout="wide")
st.title("📚 行测刷题 + 艾宾浩斯错题复习｜细分小模块 + 双PDF")
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 模考记录录入",
    "❌ 错题录入",
    "⏰ 今日待复习",
    "📥 导出PDF（自测/解析）",
    "📊 复盘统计"
])

# -------- Tab1 模考记录 --------
with tab1:
    st.subheader("录入模考/套题记录")
    with st.form("record_form", clear_on_submit=True):
        select_paper = st.selectbox("选择试卷模板", list(paper_templates.keys()))
        total = st.number_input("总题量", min_value=1, max_value=200, value=120)
        right = st.number_input("答对题目数", min_value=0, max_value=200, value=70)
        time_use = st.number_input("用时（分钟）", min_value=1, max_value=300, value=110)
        note = st.text_area("备注（模考/专项、问题总结）", placeholder="例：资料分析速度慢")
        submit_record = st.form_submit_button("✅ 提交保存")
    if submit_record:
        df_record, sha_r = load_csv_from_github(CSV_PATH)
        new_row = {
            "日期": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "试卷名称": select_paper,
            "总题量": total,
            "答对": right,
            "耗时分钟": time_use,
            "备注": note
        }
        df_record = pd.concat([df_record, pd.DataFrame([new_row])], ignore_index=True)
        save_csv_to_github(df_record, CSV_PATH, sha_r)
        st.success("✅ 模考记录保存成功！")

# -------- Tab2 错题录入（支持子模块） --------
with tab2:
    st.subheader("添加错题（支持细分小模块）")
    with st.form("error_form", clear_on_submit=True):
        main_mod = st.selectbox("主模块", main_module_list)
        sub_mod = st.selectbox("细分小模块", module_sub_map[main_mod])
        err_point = st.text_input("考点（补充细化考点）", placeholder="填写细分考点")
        question_text = st.text_area("题干", placeholder="粘贴题目原文")
        option_text = st.text_area("选项", placeholder="A.xxx B.xxx C.xxx D.xxx")
        ans_right = st.text_input("正确答案")
        ans_my = st.text_input("你选的答案")
        err_reason = st.selectbox("错因", reason_list)
        explain = st.text_area("解析/复盘笔记", placeholder="写下自己的理解、避坑点")
        submit_err = st.form_submit_button("💾 保存错题")
    if submit_err:
        df_err, sha_e = load_csv_from_github(ERROR_CSV_PATH)
        now_str = datetime.now().strftime("%Y-%m-%d")
        next_dt = datetime.now() + timedelta(days=review_interval[0])
        err_row = {
            "日期": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "主模块": main_mod,
            "子模块": sub_mod,
            "考点": err_point,
            "题干": question_text,
            "选项": option_text,
            "正确答案": ans_right,
            "你的答案": ans_my,
            "错因": err_reason,
            "解析": explain,
            "review_stage": 0,
            "last_review_date": now_str,
            "next_review_date": next_dt.strftime("%Y-%m-%d")
        }
        df_err = pd.concat([df_err, pd.DataFrame([err_row])], ignore_index=True)
        save_csv_to_github(df_err, ERROR_CSV_PATH, sha_e)
        st.success("✅ 错题存入错题本，自动安排复习！")

    st.divider()
    st.subheader("🔍 全部错题检索")
    df_err_all, _ = load_csv_from_github(ERROR_CSV_PATH)
    filter_main = st.multiselect("筛选主模块", main_module_list, default=main_module_list)
    # 根据选中主模块动态加载子模块选项
    available_sub = []
    for m in filter_main:
        available_sub.extend(module_sub_map[m])
    filter_sub = st.multiselect("筛选细分小模块", available_sub, default=available_sub)
    filter_reason = st.multiselect("筛选错因", reason_list, default=reason_list)
    show_df = df_err_all[
        df_err_all["主模块"].isin(filter_main)
        & df_err_all["子模块"].isin(filter_sub)
        & df_err_all["错因"].isin(filter_reason)
    ]
    st.dataframe(show_df, use_container_width=True)

# -------- Tab3 今日待复习（核心艾宾浩斯） --------
with tab3:
    st.subheader("⏰ 今天需要复习的错题")
    df_err, sha_e = load_csv_from_github(ERROR_CSV_PATH)
    today = datetime.now().date()
    if len(df_err) > 0:
        df_err["next_review_date_dt"] = pd.to_datetime(df_err["next_review_date"]).dt.date
        todo = df_err[df_err["next_review_date_dt"] <= today].copy()
        st.write(f"待复习数量：{len(todo)} 条")
        if len(todo) > 0:
            for idx, row in todo.iterrows():
                with st.expander(f"【{row['主模块']}｜{row['子模块']}】{row['考点']} | 下次复习：{row['next_review_date']}"):
                    st.markdown(f"**题干**：{row['题干']}")
                    st.markdown(f"**选项**：{row['选项']}")
                    st.markdown(f"✅正确答案：{row['正确答案']} ｜ ❌你的答案：{row['你的答案']}")
                    st.markdown(f"错因：{row['错因']}")
                    st.markdown(f"复盘笔记：{row['解析']}")
                    stage = int(row["review_stage"])
                    if st.button(f"✅ 完成本轮复习（第{stage+1}轮）", key=f"rev_{idx}"):
                        new_stage = stage + 1
                        if new_stage >= len(review_interval):
                            new_next = "已完成全部复习轮次"
                        else:
                            add_days = review_interval[new_stage]
                            new_next_dt = datetime.now() + timedelta(days=add_days)
                            new_next = new_next_dt.strftime("%Y-%m-%d")
                        df_err.at[idx, "review_stage"] = new_stage
                        df_err.at[idx, "last_review_date"] = datetime.now().strftime("%Y-%m-%d")
                        df_err.at[idx, "next_review_date"] = new_next
                        save_csv_to_github(df_err, ERROR_CSV_PATH, sha_e)
                        st.rerun()
        else:
            st.success("🎉 今天没有待复习错题，安心刷新题！")
    else:
        st.info("错题本为空，先去【❌错题录入】添加错题吧")

# -------- Tab4 导出PDF（自测+解析） --------
with tab4:
    st.subheader("📥 筛选错题，导出PDF")
    st.info("💡 自测版：只给题干+选项，适合自己先做题；解析版：带答案和复盘笔记，做完对照批改")
    df_all, _ = load_csv_from_github(ERROR_CSV_PATH)

    # 主模块一键按钮
    col_btn1, col_btn2 = st.columns(2)
    if "selected_main" not in st.session_state:
        st.session_state["selected_main"] = main_module_list.copy()
    with col_btn1:
        if st.button("✅ 一键全选主模块"):
            st.session_state["selected_main"] = main_module_list.copy()
    with col_btn2:
        if st.button("❌ 一键清空主模块"):
            st.session_state["selected_main"] = []
    export_main = st.multiselect("选择主模块", main_module_list, default=st.session_state["selected_main"])
    st.session_state["selected_main"] = export_main

    # 子模块（动态）
    export_sub_options = []
    for m in export_main:
        export_sub_options.extend(module_sub_map[m])
    export_sub = st.multiselect("选择细分小模块", export_sub_options, default=export_sub_options)

    # 错因一键按钮
    col_r1, col_r2 = st.columns(2)
    if "selected_reason" not in st.session_state:
        st.session_state["selected_reason"] = reason_list.copy()
    with col_r1:
        if st.button("✅ 一键全选错因"):
            st.session_state["selected_reason"] = reason_list.copy()
    with col_r2:
        if st.button("❌ 一键清空错因"):
            st.session_state["selected_reason"] = []
    export_reason = st.multiselect("选择错因", reason_list, default=st.session_state["selected_reason"])
    st.session_state["selected_reason"] = export_reason

    export_df = df_all[
        df_all["主模块"].isin(export_main)
        & df_all["子模块"].isin(export_sub)
        & df_all["错因"].isin(export_reason)
    ].copy()
    st.write(f"本次选中导出数量：{len(export_df)} 条")
    st.dataframe(export_df, use_container_width=True)
    if len(export_df) > 0:
        pdf_test = generate_pdf_test(export_df)
        pdf_ans = generate_pdf_answer(export_df)
        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button(
                label="📄 下载【自测版PDF】",
                data=pdf_test,
                file_name="行测错题本_自测版.pdf",
                mime="application/pdf"
            )
        with col_b:
            st.download_button(
                label="📄 下载【解析版PDF】",
                data=pdf_ans,
                file_name="行测错题本_解析版.pdf",
                mime="application/pdf"
            )
    else:
        st.warning("没有符合筛选条件的错题，无法导出！")

# -------- Tab5 复盘统计 --------
with tab5:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📈 模考统计")
        df_rec, _ = load_csv_from_github(CSV_PATH)
        if len(df_rec) > 0:
            df_rec["正确率"] = df_rec["答对"] / df_rec["总题量"]
            st.dataframe(df_rec[["日期","试卷名称","总题量","答对","正确率","耗时分钟","备注"]], use_container_width=True)
            fig, ax = plt.subplots()
            ax.plot(df_rec["日期"], df_rec["正确率"] * 100, marker="o")
            ax.set_ylabel("正确率(%)")
            ax.set_title("正确率变化趋势")
            plt.xticks(rotation=45)
            st.pyplot(fig)
    with col2:
        st.subheader("⚠️ 错题统计")
        df_e, _ = load_csv_from_github(ERROR_CSV_PATH)
        if len(df_e) > 0:
            st.write(f"当前错题总数：{len(df_e)}")
            fig2, ax2 = plt.subplots()
            # 饼图：按子模块统计
            sub_cnt = df_e["子模块"].value_counts()
            ax2.pie(sub_cnt.values, labels=sub_cnt.index, autopct="%.1f%%")
            ax2.set_title("细分小模块错题分布")
            st.pyplot(fig2)
