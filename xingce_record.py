import streamlit as st

# ========== 访问密码 ==========
APP_PASSWORD = "020804"
# ======================================

if "is_login" not in st.session_state:
    st.session_state.is_login = False

if not st.session_state.is_login:
    st.title("🔐 访问验证")
    input_pwd = st.text_input("请输入访问密码", type="password")
    if st.button("确认登录"):
        if input_pwd == APP_PASSWORD:
            st.session_state.is_login = True
            st.rerun()
        else:
            st.error("❌ 密码错误，请重新输入")
    st.stop()

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
plt.rcParams['axes.unicode_minus'] = False
from datetime import datetime, timedelta
import base64
import io
from github import Github
from github import GithubException
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import mm

# ===================== 配置区 =====================
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
GITHUB_REPO = st.secrets.get("GITHUB_REPO")
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
CSV_PATH = st.secrets.get("CSV_PATH", "行测刷题记录.csv")
ERROR_CSV_PATH = "行测错题本.csv"
TAG_CSV_PATH = "标签配置.csv"

# 【新增字体配置】
FONT_LIST = [
    "系统默认",
    "Microsoft YaHei",
    "SimSun",
    "SimHei",
    "KaiTi",
    "Arial",
    "Times New Roman"
]

# 艾宾浩斯复习间隔
review_interval = [1, 2, 4, 7, 15, 30]

# ===================== 卷子模板 =====================
paper_templates = {
    "自定义": {},
    "江苏省A类": {
        "政治理论": 13,
        "常识判断": 7,
        "言语理解": {"逻辑填空":10, "片段阅读":13, "语句表达":2, "篇章阅读":5},
        "判断推理": {"图形推理":10, "定义判断":10, "类比推理":10, "逻辑判断":15},
        "数量关系": {"数字推理":5, "数学运算":15},
        "资料分析": 15
    },
    "河南省行测": {
        "政治理论": 15,
        "常识判断": 15,
        "言语理解": {"逻辑填空":15, "片段阅读":10, "语句表达":5, "篇章阅读":0},
        "判断推理": {"图形推理":10, "定义判断":5, "类比推理":5, "逻辑判断":10},
        "数量关系": {"数字推理":0, "数学运算":15},
        "资料分析": 10
    },
    "行测国考卷": {
        "政治理论": 20,
        "常识判断": 15,
        "言语理解": {"逻辑填空":15, "片段阅读":13, "语句表达":2, "篇章阅读":0},
        "判断推理": {"图形推理":10, "定义判断":10, "类比推理":5, "逻辑判断":10},
        "数量关系": {"数字推理":0, "数学运算":10},
        "资料分析": 20
    }
}

sections_info = [
    {"name": "政治理论", "sub": []},
    {"name": "常识判断", "sub": []},
    {"name": "言语理解", "sub": ["逻辑填空", "片段阅读", "语句表达", "篇章阅读"]},
    {"name": "判断推理", "sub": ["图形推理", "定义判断", "类比推理", "逻辑判断"]},
    {"name": "数量关系", "sub": ["数字推理", "数学运算"]},
    {"name": "资料分析", "sub": []},
]
sub_module_list = [
    "逻辑填空", "片段阅读", "语句表达", "篇章阅读",
    "图形推理", "定义判断", "类比推理", "逻辑判断",
    "数字推理", "数学运算"
]
TARGET_SCORE = 70

# 错题模块：大模块-子模块映射
module_sub_map = {
    "常识判断": ["时政", "法律", "文史", "科技", "地理", "经济", "其他常识"],
    "言语理解": ["逻辑填空", "片段阅读", "语句表达", "篇章阅读"],
    "判断推理": ["图形推理", "定义判断", "类比推理", "逻辑判断"],
    "数量关系": ["数字推理", "数学运算"],
    "资料分析": ["增长", "比重", "平均数", "倍数", "比较大小", "综合分析"]
}
main_module_list = list(module_sub_map.keys())

# ---------------- GitHub读写函数 ----------------
@st.cache_resource
def get_github_repo():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
    return repo

def load_csv_from_github(file_path):
    repo = get_github_repo()
    try:
        contents = repo.get_contents(file_path, ref=GITHUB_BRANCH)
        data = base64.b64decode(contents.content)
        df = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
        # ========= ✅ 错题本表强制文本列转为字符串，解决LossySetitemError =========
        if file_path == ERROR_CSV_PATH:
            text_cols = ["考点", "错因", "题干", "选项", "正确答案", "你的答案", "解析", "主模块", "子模块"]
            for c in text_cols:
                if c in df.columns:
                    df[c] = df[c].astype(str).replace("nan", "")
        # ======================================================================
        return df, contents.sha
    except GithubException as e:
        if e.status == 404:
            if file_path == ERROR_CSV_PATH:
                cols = [
                    "日期","主模块","子模块","考点","题干","选项","正确答案","你的答案",
                    "错因","解析","review_stage","last_review_date","next_review_date"
                ]
                df = pd.DataFrame(columns=cols)
            elif file_path == TAG_CSV_PATH:
                cols = ["标签名称"]
                init_tags = ["知识点盲区","审题粗心","公式遗忘","踩出题陷阱","时间不够蒙错","不会速算"]
                df = pd.DataFrame({"标签名称": init_tags})
                save_csv_to_github(df, TAG_CSV_PATH, None)
            else:
                df = pd.DataFrame(columns=get_header())
            return df, None
        else:
            raise e

def save_csv_to_github(df, file_path, old_sha=None):
    repo = get_github_repo()
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    content = buf.read()
    commit_msg = f"更新记录 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    if old_sha is None:
        repo.create_file(file_path, commit_msg, content, branch=GITHUB_BRANCH)
    else:
        repo.update_file(file_path, commit_msg, content, old_sha, branch=GITHUB_BRANCH)

def get_tag_list():
    df_tag, _ = load_csv_from_github(TAG_CSV_PATH)
    return df_tag["标签名称"].tolist()

def calc_rate(right, total):
    if total == 0:
        return 0.0
    return round(right / total * 100, 2)

def get_header():
    header = ["日期", "试卷名称", "卷子类型", "用时(分钟)", "备注"]
    for sec in sections_info:
        if sec["sub"]:
            for sub in sec["sub"]:
                header += [f"{sub}_对", f"{sub}_总", f"{sub}_正确率"]
            header += [f"{sec['name']}_合计对", f"{sec['name']}_合计总", f"{sec['name']}_合计正确率"]
        else:
            header += [f"{sec['name']}_对", f"{sec['name']}_总", f"{sec['name']}_正确率"]
    header += ["整套合计对", "整套合计总题", "整套正确率"]
    return header

# PDF生成函数
def generate_pdf_test(df_export):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="TitleStyle", parent=styles["Heading1"], fontSize=16, alignment=1)
    normal_style = styles["Normal"]
    story = []
    story.append(Paragraph("行测错题本【自测版】", title_style))
    story.append(Spacer(1, 10*mm))
    for _, row in df_export.iterrows():
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

def generate_pdf_answer(df_export):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="TitleStyle", parent=styles["Heading1"], fontSize=16, alignment=1)
    normal_style = styles["Normal"]
    story = []
    story.append(Paragraph("行测错题本【解析版】", title_style))
    story.append(Spacer(1, 10*mm))
    for _, row in df_export.iterrows():
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

# 加载数据
df, file_sha = load_csv_from_github(CSV_PATH)
df_err, err_sha = load_csv_from_github(ERROR_CSV_PATH)

st.set_page_config(page_title="行测刷题记录工具", layout="wide")

# ========== 【新增侧边栏字体设置】 ==========
if "font_choice" not in st.session_state:
    st.session_state["font_choice"] = "系统默认"
with st.sidebar.expander("🎨 全局字体设置"):
    selected_font = st.selectbox("选择字体", FONT_LIST, index=FONT_LIST.index(st.session_state["font_choice"]))
    st.session_state["font_choice"] = selected_font
    if selected_font != "系统默认":
        st.markdown(f"""
        <style>
        * {{
            font-family: "{selected_font}", sans-serif;
        }}
        </style>
        """, unsafe_allow_html=True)
    st.caption("提示：手机端没有该字体时自动回退默认字体")

st.title("📝 行测刷题记录 + 艾宾浩斯错题本")

# tab列表：试卷录入, 历史记录, 统计图表, 错题本, 薄弱排名, 复习计划, 导出PDF, 数据管理
tab_input, tab_history, tab_chart, tab_error, tab_rank, tab_review_plan, tab_export, tab_manage = st.tabs([
    "试卷录入", "历史记录", "统计图表", "错题本", "薄弱项排名", "复习计划", "导出PDF", "数据管理"
])


# 切换试卷类型回调
def on_paper_change():
    selected = st.session_state["paper_type_key"]
    temp = paper_templates[selected]
    for sec in sections_info:
        s_name = sec["name"]
        subs = sec["sub"]
        if subs:
            for sub in subs:
                k_t = f"{s_name}_{sub}_t"
                val = temp.get(s_name, {}).get(sub, 0) if isinstance(temp.get(s_name), dict) else 0
                st.session_state[k_t] = val
                k_r = f"{s_name}_{sub}_r"
                st.session_state[k_r] = 0
        else:
            k_t = f"{s_name}_t"
            val = temp.get(s_name,0)
            st.session_state[k_t] = val
            k_r = f"{s_name}_r"
            st.session_state[k_r] = 0

with tab_input:
    st.subheader("新增刷题记录")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        paper_type = st.selectbox("卷子类型", list(paper_templates.keys()), key="paper_type_key", on_change=on_paper_change)
    with col2:
        paper_name = st.text_input("试卷名称")
    with col3:
        use_time = st.text_input("用时(分钟)")
    with col4:
        note = st.text_input("备注")

    template = paper_templates[paper_type]
    input_data = {}
    total_right = 0
    total_all = 0

    for sec in sections_info:
        s_name = sec["name"]
        subs = sec["sub"]
        st.markdown(f"### 【{s_name}】")
        if subs:
            sec_r = 0
            sec_t = 0
            for sub in subs:
                c1, c2 = st.columns(2)
                k_r = f"{s_name}_{sub}_r"
                k_t = f"{s_name}_{sub}_t"
                if k_r not in st.session_state:
                    st.session_state[k_r] = 0
                if k_t not in st.session_state:
                    st.session_state[k_t] = template.get(s_name, {}).get(sub, 0) if isinstance(template.get(s_name), dict) else 0
                with c1:
                    r = st.number_input(f"{sub} 答对", min_value=0, key=k_r)
                with c2:
                    t = st.number_input(f"{sub} 总题", min_value=0, key=k_t)
                rt = calc_rate(r, t)
                st.caption(f"{sub} 正确率：{rt}%")
                input_data[f"{sub}_对"] = r
                input_data[f"{sub}_总"] = t
                input_data[f"{sub}_正确率"] = f"{rt}%"
                sec_r += r
                sec_t += t
            sec_rt = calc_rate(sec_r, sec_t)
            st.info(f"{s_name}合计：答对{sec_r}/{sec_t}，正确率 {sec_rt}%")
            input_data[f"{s_name}_合计对"] = sec_r
            input_data[f"{s_name}_合计总"] = sec_t
            input_data[f"{s_name}_合计正确率"] = f"{sec_rt}%"
            total_right += sec_r
            total_all += sec_t
        else:
            k_r = f"{s_name}_r"
            k_t = f"{s_name}_t"
            if k_r not in st.session_state:
                st.session_state[k_r] = 0
            if k_t not in st.session_state:
                st.session_state[k_t] = template.get(s_name,0)
            c1, c2 = st.columns(2)
            with c1:
                r = st.number_input(f"{s_name} 答对", min_value=0, key=k_r)
            with c2:
                t = st.number_input(f"{s_name} 总题", min_value=0, key=k_t)
            rt = calc_rate(r, t)
            st.caption(f"{s_name} 正确率：{rt}%")
            input_data[f"{s_name}_对"] = r
            input_data[f"{s_name}_总"] = t
            input_data[f"{s_name}_正确率"] = f"{rt}%"
            total_right += r
            total_all += t

    total_rt = calc_rate(total_right, total_all)
    st.success(f"✅ 整套合计：答对 {total_right}/{total_all}，整套正确率：{total_rt}%")

    if st.button("保存本条记录"):
        new_row = {
            "日期": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "试卷名称": paper_name,
            "卷子类型": paper_type,
            "用时(分钟)": use_time,
            "备注": note,
            "整套合计对": total_right,
            "整套合计总题": total_all,
            "整套正确率": f"{total_rt}%"
        }
        for k,v in input_data.items():
            new_row[k] = v
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_csv_to_github(df, CSV_PATH, file_sha)
        st.success("✅ 保存成功！数据已经写入GitHub仓库永久保存")
        st.rerun()

with tab_history:
    st.subheader("📋 历史刷题记录")
    st.dataframe(df, use_container_width=True)

with tab_chart:
    st.subheader("趋势统计图")
    if len(df) > 0:
        filter_paper = st.selectbox("筛选卷子类型", ["全部"] + list(df["卷子类型"].unique()))
        chart_type = st.radio("图表类型", ["大模块总图","细分小题图"])
        plot_df = df.copy()
        if filter_paper != "全部":
            plot_df = plot_df[plot_df["卷子类型"] == filter_paper]

        if len(plot_df) > 0:
            font = FontProperties()
            fig, ax = plt.subplots(figsize=(12,6))
            if chart_type == "大模块总图":
                ax.plot(plot_df["日期"], plot_df["政治理论_正确率"].str.replace("%","").astype(float), marker="o", label="政治理论")
                ax.plot(plot_df["日期"], plot_df["常识判断_正确率"].str.replace("%","").astype(float), marker="o", label="常识判断")
                ax.plot(plot_df["日期"], plot_df["言语理解_合计正确率"].str.replace("%","").astype(float), marker="o", label="言语理解")
                ax.plot(plot_df["日期"], plot_df["判断推理_合计正确率"].str.replace("%","").astype(float), marker="o", label="判断推理")
                ax.plot(plot_df["日期"], plot_df["数量关系_合计正确率"].str.replace("%","").astype(float), marker="o", label="数量关系")
                ax.plot(plot_df["日期"], plot_df["资料分析_正确率"].str.replace("%","").astype(float), marker="o", label="资料分析")
                ax.plot(plot_df["日期"], plot_df["整套正确率"].str.replace("%","").astype(float), marker="o", label="整套")
            else:
                for m in sub_module_list:
                    col = f"{m}_正确率"
                    ax.plot(plot_df["日期"], plot_df[col].str.replace("%","").astype(float), marker=".", label=m, linewidth=1.2)
            ax.axhline(y=TARGET_SCORE, color="#ff3333", linestyle="--", label=f"目标线 {TARGET_SCORE}%")

            ax.set_title(f"{chart_type} {'【'+filter_paper+'】' if filter_paper!='全部' else ''}", fontproperties=font, fontsize=14)
            ax.set_xlabel("时间", fontproperties=font, fontsize=12)
            ax.set_ylabel("正确率 %", fontproperties=font, fontsize=12)
            plt.xticks(rotation=30, ha="right", fontproperties=font)
            plt.yticks(fontproperties=font)
            ax.legend(prop=font, fontsize=8)
            ax.grid(alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)
        else:
            st.warning("筛选后暂无数据")
    else:
        st.info("暂无刷题记录，请先录入试卷")

with tab_error:
    st.subheader("❌ 错题本｜动态错因标签管理")
    err_tab1, err_tab2, err_tab3, err_tab4 = st.tabs(["录入错题", "标签管理", "全部错题检索", "✏️ 修改/删除错题"])
    tag_list = get_tag_list()

    with err_tab1:
        st.markdown("##### 添加错题")
        if "err_main_sel" not in st.session_state:
            st.session_state.err_main_sel = main_module_list[0]
        main_mod = st.selectbox("主模块", main_module_list, key="err_main_sel")
        sub_options = module_sub_map[main_mod]
        if "err_sub_sel" not in st.session_state or st.session_state.err_sub_sel not in sub_options:
            st.session_state.err_sub_sel = sub_options[0]

        with st.form("error_form", clear_on_submit=True):
            sub_mod = st.selectbox("细分小模块", sub_options, key="err_sub_sel")
            err_point = st.text_input("考点（补充细化考点）")
            question_text = st.text_area("题干")
            option_text = st.text_area("选项")
            ans_right = st.text_input("正确答案")
            ans_my = st.text_input("你选的答案")
            err_reason = st.selectbox("错因标签", tag_list)
            explain = st.text_area("解析/复盘笔记")
            submit_err = st.form_submit_button("💾 保存错题")
        if submit_err:
            df_err, err_sha = load_csv_from_github(ERROR_CSV_PATH)
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
            save_csv_to_github(df_err, ERROR_CSV_PATH, err_sha)
            st.success("✅ 错题保存成功，自动安排复习！")

    with err_tab2:
        st.markdown("##### 🏷️ 动态管理错因标签")
        new_tag = st.text_input("输入新增标签名称")
        if st.button("➕ 添加标签") and new_tag.strip():
            if new_tag.strip() not in tag_list:
                tag_list.append(new_tag.strip())
                df_tag = pd.DataFrame({"标签名称": tag_list})
                save_csv_to_github(df_tag, TAG_CSV_PATH, None)
                st.success(f"已添加标签：{new_tag.strip()}")
                st.rerun()
            else:
                st.warning("标签已存在！")
        del_tag = st.selectbox("选择要删除的标签", tag_list)
        if st.button("🗑️ 删除选中标签"):
            tag_list.remove(del_tag)
            df_tag = pd.DataFrame({"标签名称": tag_list})
            save_csv_to_github(df_tag, TAG_CSV_PATH, None)
            st.warning(f"已删除标签：{del_tag}（历史错题标签不会自动清除）")
            st.rerun()

    with err_tab3:
        st.markdown("##### 🔍 全部错题检索")
        df_err_all, _ = load_csv_from_github(ERROR_CSV_PATH)
        filter_main = st.multiselect("筛选主模块", main_module_list, default=main_module_list)
        available_sub = []
        for m in filter_main:
            available_sub.extend(module_sub_map[m])
        filter_sub = st.multiselect("筛选细分小模块", available_sub, default=available_sub)
        filter_reason = st.multiselect("筛选错因", tag_list, default=tag_list)
        show_df = df_err_all[
            df_err_all["主模块"].isin(filter_main)
            & df_err_all["子模块"].isin(filter_sub)
            & df_err_all["错因"].isin(filter_reason)
        ]
        st.dataframe(show_df, use_container_width=True)

    with err_tab4:
        st.markdown("##### ✏️ 修改 / 删除错题")
        df_edit_all, edit_sha = load_csv_from_github(ERROR_CSV_PATH)
        if len(df_edit_all) == 0:
            st.info("错题本暂无数据")
        else:
            select_idx = st.selectbox("选择错题序号", options=list(range(len(df_edit_all))))
            edit_row = df_edit_all.iloc[select_idx].copy()
            st.markdown(f"选中：【{edit_row['主模块']}｜{edit_row['子模块']}】{edit_row['考点']}")

            with st.form("edit_err_form", clear_on_submit=False):
                edit_main = st.selectbox("主模块", main_module_list, index=main_module_list.index(edit_row["主模块"]))
                edit_sub_opt = module_sub_map[edit_main]
                sub_index = edit_sub_opt.index(edit_row["子模块"]) if edit_row["子模块"] in edit_sub_opt else 0
                edit_sub = st.selectbox("细分小模块", edit_sub_opt, index=sub_index)
                edit_point = st.text_input("考点", value=edit_row["考点"])
                edit_q = st.text_area("题干", value=edit_row["题干"])
                edit_opt = st.text_area("选项", value=edit_row["选项"])
                edit_ans_r = st.text_input("正确答案", value=edit_row["正确答案"])
                edit_ans_m = st.text_input("你的答案", value=edit_row["你的答案"])
                reason_idx = tag_list.index(edit_row["错因"]) if edit_row["错因"] in tag_list else 0
                edit_reason = st.selectbox("错因标签", tag_list, index=reason_idx)
                edit_note = st.text_area("解析/复盘笔记", value=edit_row["解析"])

                st.markdown("##### 📅 复习计划（艾宾浩斯）")
                edit_stage = st.number_input("当前复习轮次 review_stage", min_value=0, max_value=len(review_interval), value=int(edit_row["review_stage"]))
                edit_last = st.text_input("上次复习日期", value=edit_row["last_review_date"])
                edit_next = st.text_input("下次复习日期", value=edit_row["next_review_date"])

                save_edit_btn = st.form_submit_button("💾 保存修改")

            if save_edit_btn:
                df_edit_all.at[select_idx, "主模块"] = str(edit_main) if edit_main not in [None, ""] else ""
                df_edit_all.at[select_idx, "子模块"] = str(edit_sub) if edit_sub not in [None, ""] else ""
                df_edit_all.at[select_idx, "考点"] = str(edit_point) if edit_point not in [None, ""] else ""
                df_edit_all.at[select_idx, "题干"] = str(edit_q) if edit_q not in [None, ""] else ""
                df_edit_all.at[select_idx, "选项"] = str(edit_opt) if edit_opt not in [None, ""] else ""
                df_edit_all.at[select_idx, "正确答案"] = str(edit_ans_r) if edit_ans_r not in [None, ""] else ""
                df_edit_all.at[select_idx, "你的答案"] = str(edit_ans_m) if edit_ans_m not in [None, ""] else ""
                df_edit_all.at[select_idx, "错因"] = str(edit_reason) if edit_reason not in [None, ""] else ""
                df_edit_all.at[select_idx, "解析"] = str(edit_note) if edit_note not in [None, ""] else ""
                df_edit_all.at[select_idx, "review_stage"] = edit_stage
                df_edit_all.at[select_idx, "last_review_date"] = edit_last
                df_edit_all.at[select_idx, "next_review_date"] = edit_next
                save_csv_to_github(df_edit_all, ERROR_CSV_PATH, edit_sha)
                st.success("✅ 错题修改已保存！")
                st.rerun()

            st.divider()
            st.markdown("##### 🗑️ 删除本条错题（不可恢复）")
            confirm_del_err = st.checkbox("确认删除这条错题")
            if confirm_del_err:
                if st.button("⚠️ 确认删除错题"):
                    df_edit_all = df_edit_all.drop(select_idx).reset_index(drop=True)
                    save_csv_to_github(df_edit_all, ERROR_CSV_PATH, edit_sha)
                    st.warning("✅ 错题已删除！")
                    st.rerun()

with tab_rank:
    st.subheader("📊 薄弱项排名")
    df_rank, _ = load_csv_from_github(ERROR_CSV_PATH)
    font = FontProperties()
    if len(df_rank) == 0:
        st.info("暂无错题记录，先录入错题")
    else:
        st.markdown("#### 🔹 各模块错题数量排行")
        rank_module = df_rank["主模块"].value_counts().reset_index()
        rank_module.columns = ["模块名称", "错题数量"]
        st.dataframe(rank_module, use_container_width=True)
        fig1, ax1 = plt.subplots(figsize=(10,4))
        ax1.barh(rank_module["模块名称"], rank_module["错题数量"], color="#ff6b6b")
        ax1.set_title("模块错题统计", fontproperties=font)
        ax1.set_xlabel("错题数量", fontproperties=font)
        ax1.set_yticklabels(rank_module["模块名称"], fontproperties=font)
        plt.tight_layout()
        st.pyplot(fig1)

        st.markdown("#### 🔹 错因标签频次排行")
        rank_tag = df_rank["错因"].value_counts().reset_index()
        rank_tag.columns = ["错因标签", "出现次数"]
        st.dataframe(rank_tag, use_container_width=True)
        fig2, ax2 = plt.subplots(figsize=(10,4))
        ax2.barh(rank_tag["错因标签"], rank_tag["出现次数"], color="#4285f4")
        ax2.set_title("错因分布统计", fontproperties=font)
        ax2.set_xlabel("次数", fontproperties=font)
        ax2.set_yticklabels(rank_tag["错因标签"], fontproperties=font)
        plt.tight_layout()
        st.pyplot(fig2)

with tab_review_plan:
    st.subheader("🎯 自动复习计划（薄弱模块优先）")
    df_rev, rev_sha = load_csv_from_github(ERROR_CSV_PATH)
    today = datetime.now().date()
    if len(df_rev) == 0:
        st.info("暂无错题，无法生成复习计划")
    else:
        df_rev["next_review_date_dt"] = pd.to_datetime(df_rev["next_review_date"], errors="coerce").dt.date
        module_count = df_rev["主模块"].value_counts().to_dict()
        df_rev["薄弱权重"] = df_rev["主模块"].map(module_count).fillna(0)

        df_today = df_rev[df_rev["next_review_date_dt"] <= today].copy()
        st.markdown(f"### ✅ 今日待复习（共 {len(df_today)} 道）")
        if len(df_today) > 0:
            df_today = df_today.sort_values("薄弱权重", ascending=False)
            for idx, row in df_today.iterrows():
                with st.expander(f"【{row['主模块']}｜{row['子模块']}】{row['考点']}"):
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
                        df_rev.at[idx, "review_stage"] = new_stage
                        df_rev.at[idx, "last_review_date"] = datetime.now().strftime("%Y-%m-%d")
                        df_rev.at[idx, "next_review_date"] = new_next
                        save_csv_to_github(df_rev, ERROR_CSV_PATH, rev_sha)
                        st.rerun()
        else:
            st.success("🎉 今天没有待复习错题！")

        st.markdown("---")
        st.markdown("### 📆 未来7天复习预览")
        df_future = df_rev.copy()
        df_future["next_review_date_dt"] = pd.to_datetime(df_future["next_review_date"], errors="coerce").dt.date
        df_future = df_future[
            (df_future["next_review_date_dt"] > today)
            & (df_future["next_review_date_dt"] <= today + timedelta(days=7))
        ].sort_values("next_review_date_dt")
        st.dataframe(df_future[["next_review_date","主模块","子模块","考点","错因"]], use_container_width=True)

with tab_export:
    st.markdown("##### 📥 筛选导出PDF")
    df_all, _ = load_csv_from_github(ERROR_CSV_PATH)
    tag_list = get_tag_list()
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

    export_sub_options = []
    for m in export_main:
        export_sub_options.extend(module_sub_map[m])
    export_sub = st.multiselect("选择细分小模块", export_sub_options, default=export_sub_options)

    col_r1, col_r2 = st.columns(2)
    if "selected_reason" not in st.session_state:
        st.session_state["selected_reason"] = tag_list.copy()
    with col_r1:
        if st.button("✅ 一键全选错因"):
            st.session_state["selected_reason"] = tag_list.copy()
    with col_r2:
        if st.button("❌ 一键清空错因"):
            st.session_state["selected_reason"] = []
    export_reason = st.multiselect("选择错因", tag_list, default=st.session_state["selected_reason"])
    st.session_state["selected_reason"] = export_reason

    export_df = df_all[
        df_all["主模块"].isin(export_main)
        & df_all["子模块"].isin(export_sub)
        & df_all["错因"].isin(export_reason)
    ].copy()
    st.write(f"选中导出数量：{len(export_df)}")
    st.dataframe(export_df, use_container_width=True)
    if len(export_df) > 0:
        pdf_test = generate_pdf_test(export_df)
        pdf_ans = generate_pdf_answer(export_df)
        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button("📄 下载自测版PDF", pdf_test, "行测错题本_自测版.pdf", "application/pdf")
        with col_b:
            st.download_button("📄 下载解析版PDF", pdf_ans, "行测错题本_解析版.pdf", "application/pdf")

with tab_manage:
    st.subheader("📂 刷题记录管理（单条删除，不会删同名全部）")
    df, file_sha = load_csv_from_github(CSV_PATH)
    if len(df) == 0:
        st.info("暂无刷题记录")
    else:
        st.dataframe(df, use_container_width=True)
        select_row_idx = st.selectbox("选择要删除的单条记录序号", options=list(range(len(df))))
        selected_row = df.iloc[select_row_idx]
        st.markdown(f"""
        📌 选中记录信息：
        - 日期：{selected_row['日期']}
        - 试卷名称：{selected_row['试卷名称']}
        - 卷子类型：{selected_row['卷子类型']}
        - 整套正确率：{selected_row['整套正确率']}
        """)

        col1, col2 = st.columns(2)
        with col1:
            confirm_del_one = st.checkbox("确认删除这一条记录（仅本条）")
            if confirm_del_one:
                if st.button("⚠️ 删除选中单条记录", type="secondary"):
                    df_new = df.drop(select_row_idx).reset_index(drop=True)
                    save_csv_to_github(df_new, CSV_PATH, file_sha)
                    st.success(f"✅ 单条记录删除成功！")
                    st.rerun()
        with col2:
            if st.button("⚠️ 清空全部刷题记录", type="primary"):
                confirm_clear_all = st.checkbox("确认清空【所有刷题记录】，不可恢复！")
                if confirm_clear_all:
                    df_empty = pd.DataFrame(columns=get_header())
                    save_csv_to_github(df_empty, CSV_PATH, file_sha)
                    st.success("✅ 全部刷题记录已清空！")
                    st.rerun()
