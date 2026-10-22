"""Mock 规则引擎（演示/测试专用）。

用少量确定性正则模拟 LLM 的结构化抽取能力，覆盖示例数据中的典型句式。
目的：
1. 没有 API Key 也能完整演示全流程（Streamlit 一键切换）；
2. 为 pytest 提供确定性依赖，测试不发起任何网络调用。

它不是产品功能，只理解本仓库示例数据的句式——
这正是"为什么要接真实 LLM"的对照，也是面试中"没有 Key 怎么演示"的答案。
"""
from __future__ import annotations

import json
import re

# 单行消息：[时间] 发言人：内容（时间可选）
LINE_RE = re.compile(
    r"^(?:\[(?P<time>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)\]\s*)?"
    r"(?P<speaker>[^：:\[]{1,20})[：:]\s*(?P<content>.+)$"
)

# 任务分配：张伟，下周三前把标签打印系统的原型图出一版，周四下午评审。
TASK_ASSIGN_RE = re.compile(
    r"^(?P<assignee>[^，。！!？?\s]{2,4})[，,]\s*"
    r"(?P<deadline>\S{1,8}前)(?P<task>[^，。！!？?]+)"
    r"(?:[，,](?P<detail>[^。！!？?]*))?"
)

# 进度汇报：原型图整体框架完成 70% 了，还差追溯页面。
PROGRESS_RE = re.compile(
    r"^(?P<task>[\u4e00-\u9fa5A-Za-z]{2,12})完成\s*(?P<pct>\d+)\s*%[的了]?[，,]?(?P<detail>.*)$"
)

# 风险：……，可能得回滚整笔录入。/ ……，有风险。
RISK_RE = re.compile(
    r"(?P<detail>[^。！!？?]+?)(?:可能得|可能需要|存在风险|有风险|需要注意|有问题|风险)"
    r"(?P<action>[^。！!？?]*)"
)

# 这些词开头的消息通常是寒暄/短回复，不作为任务（防止把"好的"当成人名）
CHAT_WORDS = {"收到", "好的", "好"}


def _clean(text: str | None) -> str | None:
    """去掉首尾空白与句读，统一输出风格。"""
    if not text:
        return None
    cleaned = text.strip().rstrip("。！!？?，,、 ")
    return cleaned or None


def extract(conversation: str) -> str:
    """对一段对话文本执行规则抽取，返回 JSON 字符串（与真实 LLM 同构）。"""
    if "【待分析的新消息】" in conversation:  # 只分析新消息，忽略附带的语境
        conversation = conversation.split("【待分析的新消息】", 1)[1]

    items: list[dict] = []
    for line in conversation.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("==="):
            continue
        matched = LINE_RE.match(line)
        if not matched:
            continue
        content = _clean(matched.group("content")) or ""
        item = _match_content(matched.group("time"), matched.group("speaker"), content, line)
        if item:
            items.append(item)

    return json.dumps({"items": items}, ensure_ascii=False, indent=2)


def _match_content(time_str: str | None, speaker: str, content: str, line: str) -> dict | None:
    base = {"raw_text": line, "msg_time": time_str, "confidence": 0.9}

    matched = TASK_ASSIGN_RE.match(content)
    if matched and matched.group("assignee") not in CHAT_WORDS:
        return {
            **base,
            "type": "task_assign",
            "task": _clean(matched.group("task")),
            "assignee": matched.group("assignee"),
            "reporter": speaker,
            "status": "todo",
            "deadline": _clean(matched.group("deadline")),
            "detail": _clean(matched.group("detail")),
        }

    matched = PROGRESS_RE.match(content)
    if matched:
        detail = f"完成 {matched.group('pct')}%"
        extra = _clean(matched.group("detail"))
        if extra:
            detail = f"{detail}，{extra}"
        return {
            **base,
            "type": "progress",
            "task": _clean(matched.group("task")),
            "assignee": speaker,
            "reporter": None,
            "status": "doing",
            "deadline": None,
            "detail": detail,
            "confidence": 0.85,
        }

    matched = RISK_RE.search(content)
    if matched:
        detail = _clean(matched.group("detail")) or ""
        action = _clean(matched.group("action"))
        if action:
            detail = f"{detail}，{action}"
        return {
            **base,
            "type": "risk",
            "task": None,
            "assignee": None,
            "reporter": speaker,
            "status": None,
            "deadline": None,
            "detail": detail or None,
            "confidence": 0.8,
        }

    return None  # 闲聊/无法识别的句式：不计入结果
