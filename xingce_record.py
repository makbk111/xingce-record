import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import base64
from github import Github
from github import GithubException

# ===================== 配置区（从streamlit secrets读取，不要直接写在这里！） =====================
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
GITHUB_REPO = st.secrets.get("GITHUB_REPO")
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
CSV_PATH = st.secrets.get("CSV_PATH", "行测刷题记录.csv")

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
        "言语理解": {"逻辑填空":15, "片段阅读":11, "语句表达":2, "篇章阅读":2},
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

# ---------------- GitHub读写函数 ----------------
@st.cache_resource
def get_github_repo():
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
    return repo

def load_csv_from_github():
    repo = get_github_repo()
    try:
        contents = repo.get_contents(CSV_PATH, ref=GITHUB_BRANCH)
        data = base64.b64decode(contents.content)
        df = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
        return df, contents.sha
    except GithubException as e:
        if e.status == 404:
            # 文件不存在，返回空df
            df = pd.DataFrame(columns=get_header())
            return df, None
        else:
            raise e

def save_csv_to_github(df, old_sha=None):
    repo = get_github_repo()
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    content = buf.read()
    commit_msg = f"更新刷题记录 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    if old_sha is None:
        repo.create_file(CSV_PATH, commit_msg, content, branch=GITHUB_BRANCH)
    else:
        repo.update_file(CSV_PATH, commit_msg, content, old_sha, branch=GITHUB_BRANCH)

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

# 加载数据
import io
df, file_sha = load_csv_from_github()

st.set_page_config(page_title="行测刷题记录工具", layout="wide")
st.title("📝 行测刷题记录工具（云端持久保存版）")

tab_input, tab_history, tab_chart, tab_export = st.tabs(["录入记录", "历史记录", "趋势绘图", "导出MD"])

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
        save_csv_to_github(df, file_sha)
        st.success("✅ 保存成功！数据已经写入GitHub仓库永久保存")
        st.rerun()

with tab_history:
    st.subheader("历史刷题记录")
    st.dataframe(df, use_container_width=True)
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    st.download_button("下载全部CSV备份", buf.getvalue(), "行测刷题记录.csv", "text/csv")

with tab_chart:
    st.subheader("趋势图")
    if len(df) > 0:
        filter_paper = st.selectbox("筛选卷子类型绘图", ["全部"] + list(df["卷子类型"].unique()))
        chart_type = st.radio("图表类型", ["大模块总图","细分小题图"])
        plot_df = df.copy()
        if filter_paper != "全部":
            plot_df = plot_df[plot_df["卷子类型"] == filter_paper]

        if len(plot_df) > 0:
            plt.rcParams["font.sans-serif"] = ["SimHei"]
            plt.rcParams["axes.unicode_minus"] = False
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
            ax.set_title(f"{chart_type} {'【'+filter_paper+'】' if filter_paper!='全部' else ''}")
            ax.set_xlabel("时间")
            ax.set_ylabel("正确率 %")
            plt.xticks(rotation=30, ha="right")
            ax.legend(fontsize=8)
            ax.grid(alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)
        else:
            st.warning("筛选后暂无数据")
    else:
        st.info("暂无刷题记录，先去录入一条数据")

with tab_export:
    st.subheader("导出Markdown复盘表")
    header_md = [
        "日期", "试卷名称", "卷子类型", "用时", "备注",
        "政治理论", "常识判断",
        "逻辑填空", "片段阅读", "语句表达", "篇章阅读",
        "图形推理", "定义判断", "类比推理", "逻辑判断",
        "数字推理", "数学运算",
        "资料分析",
        "整套正确率"
    ]
    md_lines = []
    export_filter = st.selectbox("选择导出类型", ["全部记录"] + list(paper_templates.keys()))
    if export_filter == "全部记录":
        md_lines.append("# 刷题汇总复盘表【全部记录】\n")
        exp_df = df
    else:
        md_lines.append(f"# 刷题汇总复盘表【筛选：{export_filter}】\n")
        exp_df = df[df["卷子类型"] == export_filter]
    md_lines.append("| " + " | ".join(header_md) + " |")
    md_lines.append("| " + " | ".join(["---"]*len(header_md)) + " |")

    for _,row in exp_df.iterrows():
        def safe(v):
            if pd.isna(v) or str(v).strip() == "":
                return "-"
            return str(v)
        line = [
            safe(row["日期"]),
            safe(row["试卷名称"]),
            safe(row["卷子类型"]),
            safe(row["用时(分钟)"]),
            safe(row["备注"]),
            safe(row["政治理论_正确率"]),
            safe(row["常识判断_正确率"]),
            safe(row["逻辑填空_正确率"]),
            safe(row["片段阅读_正确率"]),
            safe(row["语句表达_正确率"]),
            safe(row["篇章阅读_正确率"]),
            safe(row["图形推理_正确率"]),
            safe(row["定义判断_正确率"]),
            safe(row["类比推理_正确率"]),
            safe(row["逻辑判断_正确率"]),
            safe(row["数字推理_正确率"]),
            safe(row["数学运算_正确率"]),
            safe(row["资料分析_正确率"]),
            safe(row["整套正确率"])
        ]
        md_lines.append("| " + " | ".join(line) + " |")
    md_text = "\n".join(md_lines)
    st.code(md_text, language="markdown")
    st.download_button("下载MD文件", md_text, f"刷题汇总【{export_filter}】.md")
