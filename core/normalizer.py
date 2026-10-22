"""任务归一化与跨组合并。

企业群聊里同一个任务有无数种说法：
"原型图出一版" / "原型图整体框架" / "原型图初稿"……
如果不归一化，看板会被同一个任务刷满好几遍。

归一化两步走：
1. 文本规范化：去标点、去首动词语气词（"把/将/完成"）；
2. 同义词映射：把已知变体收敛到标准任务名（SYNONYMS 可按团队扩展）。

合并规则：
- 键 = (执行人, 规范化任务名)；风险类不过键，原样保留；
- 状态机只进不退：todo → doing → done；
- deadline 取最早出现值，detail 取最新进度，merged_count 记录合并条数。
"""
from __future__ import annotations

import re

from .models import ExtractedItem, MessageType

# 同义词/变体映射：键会按长度从长到短替换，避免短键误伤
SYNONYMS: dict[str, str] = {
    "标签打印系统的原型图": "原型图",
    "标签打印系统原型图": "原型图",
    "原型图整体框架": "原型图",
    "原型图初稿": "原型图",
    "原型图出一版": "原型图",
    "批量导入已经": "批量导入",
}

_LEADING_VERBS = ("把", "将", "完成一下", "完成")
_PUNCT_RE = re.compile(r"[。，、！？!?,.\s]+")

_STATUS_ORDER = {"todo": 0, "doing": 1, "done": 2}


def normalize_task(task: str | None) -> str:
    """规范化任务名，使同一任务的不同表述收敛到同一键。"""
    if not task:
        return ""
    text = _PUNCT_RE.sub("", task)
    for prefix in _LEADING_VERBS:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    for key in sorted(SYNONYMS, key=len, reverse=True):
        text = text.replace(key, SYNONYMS[key])
    return text


def _advance_status(old: str | None, new: str | None) -> str | None:
    """状态机只进不退。"""
    if not new:
        return old
    if not old:
        return new
    return new if _STATUS_ORDER.get(new, 0) > _STATUS_ORDER.get(old, 0) else old


def merge_items(items: list[ExtractedItem]) -> list[ExtractedItem]:
    """跨分组归一化合并；按消息时间排序后依次归并。"""
    tasks: dict[tuple[str, str], ExtractedItem] = {}
    others: list[ExtractedItem] = []

    for item in sorted(items, key=lambda i: i.msg_time or ""):
        if item.type == MessageType.CHAT:
            continue
        if item.type == MessageType.RISK or not item.assignee or not item.task:
            others.append(item)
            continue

        key = (item.assignee, normalize_task(item.task))
        if key not in tasks:
            merged = item.model_copy(deep=True)
            merged.task = key[1]
            merged.first_seen = item.msg_time
            merged.last_seen = item.msg_time
            merged.merged_count = 1
            tasks[key] = merged
            continue

        merged = tasks[key]
        merged.merged_count += 1
        merged.status = _advance_status(merged.status, item.status)
        if item.deadline and not merged.deadline:
            merged.deadline = item.deadline
        if item.detail:
            merged.detail = item.detail
        merged.last_seen = item.msg_time or merged.last_seen

    return list(tasks.values()) + others
