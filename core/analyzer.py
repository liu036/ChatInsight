"""分组分析：调用 LLM → JSON 三级降级解析 → Pydantic 校验 → GroupResult。

三级降级解析（LLM 输出不可信的工程现实）：
1. 直接 json.loads；
2. 提取 ```json 代码块后再解析；
3. 仍失败 → 带重试提示再问一次；持续失败 → 标记 parse_error 降级记录，
   绝不静默丢整组消息。

为什么不用 LangChain 的 PydanticOutputParser：它会把格式说明追加进提示词，
但解析失败时直接抛异常，没有"代码块提取 / 修复重试 / 降级记录"的弹性。
这里选择手动解析 + 显式降级链，面试中可以展开这个取舍。
"""
from __future__ import annotations

import json
import re
import time

from pydantic import ValidationError

from .grouper import Group, render_group
from .llm import BaseLLMClient
from .models import ExtractedItem, GroupResult

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

RETRY_HINT = (
    "\n\n注意：上一次输出不是合法 JSON。请只输出一个 JSON 对象，"
    "不要输出解释文字，也不要输出代码块标记。"
)


def _strip_fence(text: str) -> str | None:
    matched = _FENCE_RE.search(text)
    return matched.group(1).strip() if matched else None


def parse_items(raw: str) -> tuple[list[dict], bool]:
    """三级降级解析，返回 (条目字典列表, 是否解析失败)。"""
    for candidate in (raw.strip(), _strip_fence(raw)):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        items = data.get("items") if isinstance(data, dict) else data
        if isinstance(items, list):
            return items, False
    return [], True


def _backfill_time(item: ExtractedItem, group: Group) -> ExtractedItem:
    """LLM 不负责给时间；由编排层按 raw_text 匹配回填消息时间。

    匹配策略：整行相等 → 内容互相包含，逐级放宽，保证归一化排序稳定。
    """
    if item.msg_time:
        return item
    for msg in group.messages:
        if (
            item.raw_text == msg.raw_line
            or (msg.content and msg.content in item.raw_text)
            or item.raw_text in msg.raw_line
        ):
            item.msg_time = msg.time
            break
    return item


def analyze_group(client: BaseLLMClient, group: Group, settings) -> GroupResult:
    """分析单个分组；客户端异常只标记本组失败，不向外抛。"""
    conversation = render_group(group)
    started = time.perf_counter()
    calls = 0
    raw = ""
    parse_error = False
    dicts: list[dict] = []

    try:
        for attempt in range(settings.max_retries + 1):
            calls += 1
            raw = client.analyze(conversation, retry_hint=RETRY_HINT if attempt else "")
            dicts, parse_error = parse_items(raw)
            if not parse_error:
                break
    except Exception as exc:  # 客户端异常：记录失败组，继续其他组
        return GroupResult(
            session_id=group.session_id,
            group_index=group.index,
            message_count=len(group.messages),
            items=[],
            error=f"{type(exc).__name__}: {exc}",
            llm_calls=calls,
            latency_ms=_elapsed_ms(started),
        )

    items: list[ExtractedItem] = []
    for data in dicts:
        try:
            items.append(_backfill_time(ExtractedItem(**data), group))
        except ValidationError:
            continue  # 丢弃单条脏数据，不丢整组

    return GroupResult(
        session_id=group.session_id,
        group_index=group.index,
        message_count=len(group.messages),
        items=items,
        parse_error=parse_error,
        llm_calls=calls,
        latency_ms=_elapsed_ms(started),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
