"""结果导出：Markdown（人读）与 JSON（机器读）。

四类视图与归一化结果的对应关系：
- 任务分配：所有任务条目（含已接进度汇报的），看谁在什么时候被布置了什么；
- 进度：状态为 doing/done 或有进度细节的任务；
- 风险：risk 条目；
- 待办：状态未到 done 的任务。
"""
from __future__ import annotations

import json

from .models import AnalysisResult, MessageType

_TYPE_LABELS = {
    MessageType.TASK_ASSIGN: "任务分配",
    MessageType.PROGRESS: "进度",
    MessageType.RISK: "风险",
}


def _task_row(item) -> str:
    return (
        f"| {item.task or '-'} | {item.assignee or '-'} | {item.status or '-'} "
        f"| {item.deadline or '-'} | {item.detail or '-'} | {item.last_seen or '-'} "
        f"| {item.merged_count} |"
    )


def to_markdown(result: AnalysisResult) -> str:
    """渲染为 Markdown 摘要报告。"""
    stats = result.stats
    lines = [
        "# 群聊 / 会议纪要智能摘要",
        "",
        f"- 消息数：{stats.message_count}（{stats.session_count} 个会话 / {stats.group_count} 个分组）",
        f"- LLM 调用：{stats.llm_calls} 次，失败分组 {stats.failed_groups} 个，"
        f"解析失败 {stats.parse_errors} 个",
        f"- 总耗时：{stats.total_latency_ms} ms",
        f"- 任务数：{stats.task_count}，风险数：{stats.risk_count}",
        "",
        "## 任务分配",
        "",
        "| 任务 | 执行人 | 状态 | 截止 | 详情 | 最近更新 | 合并条数 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in result.tasks:
        lines.append(_task_row(item))

    lines += ["", "## 进度", ""]
    in_progress = [i for i in result.tasks if i.status in ("doing", "done") or i.detail]
    if in_progress:
        for item in in_progress:
            lines.append(f"- **{item.task}**（{item.assignee}）：{item.detail or '无细节'}")
    else:
        lines.append("（无）")

    lines += ["", "## 风险", ""]
    if result.risks:
        for item in result.risks:
            lines.append(f"- {item.detail or item.raw_text}（记录人：{item.reporter or '-'}）")
    else:
        lines.append("（无）")

    lines += ["", "## 待办", ""]
    if result.todos:
        for item in result.todos:
            deadline = f"，截止：{item.deadline}" if item.deadline else ""
            lines.append(f"- [ ] {item.task}（{item.assignee or '未指定'}，状态：{item.status or 'todo'}{deadline}）")
    else:
        lines.append("（无）")

    lines += ["", "---", "*由 ChatInsight 自动生成；演示项目，数据均为虚构。*"]
    return "\n".join(lines)


def to_json(result: AnalysisResult) -> str:
    """序列化为 JSON（含统计）。"""
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
