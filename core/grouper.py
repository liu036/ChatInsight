"""分组与上下文拼接。

为什么按「会话 + 时间窗」分组，而不是整段一次性丢给 LLM：
1. 上下文长度可控，长对话不会溢出；
2. 天然形成并发单元（一组一次调用）；
3. 时间窗切分能对齐"一轮讨论"的语义边界。

为什么每组要附带上文末尾几条消息：
群聊里大量消息是"收到""已完成 80%"这类省略主语的回复，
没有上文就无法判断它在说哪个任务（上下文截断问题）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Settings
from .models import Message


@dataclass
class Group:
    """一个分析单元：同一会话、同一时间窗内的连续消息。"""

    session_id: str
    index: int
    messages: list[Message] = field(default_factory=list)
    context: list[Message] = field(default_factory=list)  # 上一组尾部消息


def group_messages(messages: list[Message], settings: Settings) -> list[Group]:
    """按会话 + 时间窗切分消息，并为每组附加上文上下文。"""
    groups: list[Group] = []
    current: Group | None = None
    last_time: str | None = None

    for msg in messages:
        need_new = (
            current is None
            or msg.session_id != current.session_id
            or _gap_exceeds(last_time, msg.time, settings.session_gap_minutes)
        )
        if need_new:
            current = Group(session_id=msg.session_id, index=len(groups))
            groups.append(current)
        current.messages.append(msg)
        if msg.time:
            last_time = msg.time

    for i in range(1, len(groups)):
        groups[i].context = groups[i - 1].messages[-settings.context_tail :]

    return groups


def _gap_exceeds(last_time: str | None, current_time: str | None, minutes: int) -> bool:
    """判断与上一条消息的时间差是否超过阈值；任一时间缺失则视为未超时。"""
    if not last_time or not current_time:
        return False
    from datetime import datetime

    fmt = "%Y-%m-%d %H:%M"
    try:
        delta = datetime.strptime(current_time, fmt) - datetime.strptime(last_time, fmt)
    except ValueError:
        return False
    return delta.total_seconds() > minutes * 60


def render_group(group: Group) -> str:
    """把分组渲染为 LLM 输入文本：上文（仅语境）+ 待分析新消息。"""
    lines: list[str] = []
    if group.context:
        lines.append("【上文末尾（仅用于理解语境，请勿抽取）】")
        lines.extend(m.raw_line for m in group.context)
        lines.append("")
    lines.append("【待分析的新消息】")
    lines.extend(m.raw_line for m in group.messages)
    return "\n".join(lines)
