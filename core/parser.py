"""对话文本解析：原始文本 → 消息列表。

支持三种行格式：
1. 带时间戳与发言人：[2026-10-20 09:12] 王强：内容
2. 无时间戳：王强：内容（时间继承上一条，首条缺失则为 None）
3. 会话分隔：=== 会话标题 ===（也接受空行 + 时间跳变，见 grouper）

无法识别的行（公告、图片说明等）直接忽略——宁可漏一条，也不要把非消息
当消息抽取，否则会污染 LLM 的上下文。
"""
from __future__ import annotations

import re
from datetime import datetime

from .models import Message

SESSION_HEADER = re.compile(r"^===\s*(?P<title>.+?)\s*===$")
_SESSION_PREFIX = re.compile(r"^会话\s*\d+\s*[：:]\s*")

MESSAGE_LINE = re.compile(
    r"^(?:\[(?P<time>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)\]\s*)?"
    r"(?P<speaker>[^：:\[]{1,20})[：:]\s*(?P<content>.+)$"
)

TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
)

DEFAULT_SESSION = "未命名会话"


def parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_chat(text: str) -> list[Message]:
    """把一段对话文本解析为消息列表。"""
    messages: list[Message] = []
    session_id = DEFAULT_SESSION
    last_time: datetime | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        header = SESSION_HEADER.match(line)
        if header:
            title = _SESSION_PREFIX.sub("", header.group("title").strip())
            session_id = title or DEFAULT_SESSION
            continue

        matched = MESSAGE_LINE.match(line)
        if not matched:
            continue  # 非消息行（公告、系统提示等）

        parsed_time = parse_time(matched.group("time"))
        if parsed_time is not None:
            last_time = parsed_time
        time_str = last_time.strftime("%Y-%m-%d %H:%M") if last_time else None

        messages.append(
            Message(
                time=time_str,
                speaker=matched.group("speaker").strip(),
                content=matched.group("content").strip(),
                session_id=session_id,
                raw_line=line,
            )
        )

    return messages
