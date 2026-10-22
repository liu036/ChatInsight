"""ChatInsight · Streamlit 入口。

布局：
- 侧边栏：运行模式（Mock / 真实 API）与 LLM 参数、示例加载；
- 主区域：输入 → 分析 → 四类结果（任务分配 / 进度 / 风险 / 待办）→ 导出。

Mock 模式下无需任何 API Key 即可完整演示全流程。
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.config import Settings
from core.exporter import to_json, to_markdown
from core.models import AnalysisResult
from core.pipeline import run_analysis

SAMPLES_DIR = Path(__file__).resolve().parent / "data" / "samples"

SAMPLE_FILES = {
    "项目群对话（含任务/进度/风险/闲聊）": "session_project.txt",
    "项目周会纪要": "session_meeting.txt",
    "面料质量群反馈": "session_quality.txt",
}


def _sidebar() -> Settings:
    """侧边栏：模式切换与 LLM 配置，返回当前 Settings。"""
    st.sidebar.title("ChatInsight")
    st.sidebar.caption("群聊 / 会议纪要智能摘要 · 演示项目")

    mode = st.sidebar.radio(
        "运行模式",
        options=["mock", "real"],
        format_func=lambda m: "Mock（内置规则引擎，无需 Key）" if m == "mock" else "真实 LLM（OpenAI 兼容 API）",
    )

    api_key = base_url = model = ""
    temperature, max_workers, max_retries = 0.1, 5, 2

    if mode == "real":
        with st.sidebar.expander("LLM 配置", expanded=True):
            api_key = st.text_input("API Key", type="password", value="")
            base_url = st.text_input("Base URL", value="https://api.openai.com/v1")
            model = st.text_input("模型", value="gpt-4o-mini")
            temperature = st.slider("Temperature", 0.0, 1.0, 0.1, 0.05)
        if not api_key:
            st.sidebar.warning("未填写 API Key，将回退到 Mock 模式")

    max_workers = st.sidebar.slider("并发线程数", 1, 10, 5)
    max_retries = st.sidebar.number_input("JSON 解析重试次数", 0, 5, 2)

    return Settings(
        mode="mock" if mode == "real" and not api_key else mode,
        api_key=api_key,
        base_url=base_url or "https://api.openai.com/v1",
        model=model or "gpt-4o-mini",
        temperature=temperature,
        max_workers=int(max_workers),
        max_retries=int(max_retries),
    )


def _render_result(result: AnalysisResult, settings: Settings) -> None:
    """主区域：统计指标 + 四类结果 + 导出。"""
    if settings.mode == "mock":
        st.info("当前为 Mock 模式：结果由内置规则引擎生成，用于无 Key 演示。", icon="🧪")

    stats = result.stats
    cols = st.columns(5)
    cols[0].metric("消息数", stats.message_count)
    cols[1].metric("分组数", f"{stats.group_count}（{stats.session_count} 会话）")
    cols[2].metric("任务数", stats.task_count)
    cols[3].metric("风险数", stats.risk_count)
    cols[4].metric("LLM 调用", f"{stats.llm_calls} 次 / 失败 {stats.failed_groups}")

    tab_assign, tab_progress, tab_risk, tab_todo = st.tabs(
        ["📋 任务分配", "📈 进度", "⚠️ 风险", "✅ 待办"]
    )

    with tab_assign:
        if result.tasks:
            st.dataframe(
                [
                    {
                        "任务": i.task,
                        "执行人": i.assignee,
                        "状态": i.status,
                        "截止": i.deadline,
                        "详情": i.detail,
                        "合并条数": i.merged_count,
                    }
                    for i in result.tasks
                ],
                use_container_width=True,
            )
        else:
            st.caption("（无）")

    with tab_progress:
        in_progress = [i for i in result.tasks if i.status in ("doing", "done") or i.detail]
        if in_progress:
            for item in in_progress:
                st.markdown(f"- **{item.task}**（{item.assignee}）：{item.detail or '无细节'}")
        else:
            st.caption("（无）")

    with tab_risk:
        if result.risks:
            for item in result.risks:
                st.markdown(f"- {item.detail or item.raw_text}（记录人：{item.reporter or '-'}）")
        else:
            st.caption("（无）")

    with tab_todo:
        if result.todos:
            for item in result.todos:
                deadline = f"，截止：{item.deadline}" if item.deadline else ""
                st.markdown(
                    f"- [ ] {item.task}（{item.assignee or '未指定'}，状态：{item.status or 'todo'}{deadline}）"
                )
        else:
            st.caption("（无）")

    st.divider()
    col_md, col_json = st.columns(2)
    with col_md:
        st.download_button(
            "导出 Markdown",
            data=to_markdown(result),
            file_name="chatinsight_summary.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col_json:
        st.download_button(
            "导出 JSON",
            data=to_json(result),
            file_name="chatinsight_result.json",
            mime="application/json",
            use_container_width=True,
        )

    with st.expander("原始 JSON 输出"):
        st.json(to_json(result))


def main() -> None:
    st.set_page_config(page_title="ChatInsight · 群聊纪要智能摘要", page_icon="🧭", layout="wide")
    settings = _sidebar()

    if "text" not in st.session_state:
        st.session_state.text = ""

    with st.form("input_form"):
        text = st.text_area(
            "粘贴群聊 / 会议纪要（支持 [时间] 发言人：内容 格式）",
            value=st.session_state.text,
            height=260,
            placeholder="[2026-10-20 09:12] 王强：张伟，下周三前把原型图出一版。\n...",
        )
        col_sample, col_submit = st.columns([1, 1])
        with col_sample:
            sample_name = st.selectbox("或加载示例对话", options=list(SAMPLE_FILES))
            if st.form_submit_button("加载示例"):
                st.session_state.text = (SAMPLES_DIR / SAMPLE_FILES[sample_name]).read_text(
                    encoding="utf-8"
                )
                st.rerun()
        with col_submit:
            submitted = st.form_submit_button("开始分析", type="primary", use_container_width=True)

    if submitted:
        if not text.strip():
            st.warning("请输入对话文本，或点击“加载示例”。")
            return
        with st.spinner("分析中……（按时间窗分组后并发调用）"):
            try:
                result = run_analysis(text, settings=settings)
            except Exception as exc:  # 配置错误等：明确展示，不崩溃
                st.error(f"分析失败：{type(exc).__name__}: {exc}")
                return
        _render_result(result, settings)


if __name__ == "__main__":
    main()
