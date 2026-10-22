"""数据模型：消息、抽取条目、分组结果与统计。

为什么用 Pydantic：LLM 输出是"不可信输入"，必须在边界上做严格校验——
脏数据丢弃单条、格式错误降级记录，而不是让异常扩散到 UI 层。
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """消息分类。chat 为闲聊，默认丢弃不计入结果。"""

    TASK_ASSIGN = "task_assign"  # 任务分配
    PROGRESS = "progress"  # 进度汇报
    RISK = "risk"  # 风险/阻塞
    CHAT = "chat"  # 闲聊（丢弃）


TaskStatus = Literal["todo", "doing", "done"]


class Message(BaseModel):
    """解析后的单条群消息。"""

    time: Optional[str] = None  # "YYYY-MM-DD HH:MM"，缺失时继承上一条
    speaker: str
    content: str
    session_id: str = ""
    raw_line: str = ""  # 原始行，用于 LLM 输入与结果追溯


class ExtractedItem(BaseModel):
    """LLM 抽取出的单条结构化信息。"""

    type: MessageType
    task: Optional[str] = None
    project: Optional[str] = None
    assignee: Optional[str] = None  # 执行人
    reporter: Optional[str] = None  # 布置/汇报人
    status: Optional[TaskStatus] = None
    deadline: Optional[str] = None  # 原文时间表达，严禁臆造
    detail: Optional[str] = None
    raw_text: str  # 消息原文（必填，保证可追溯）
    msg_time: Optional[str] = None  # 由编排层回填（LLM 不负责给时间）
    confidence: float = 1.0
    first_seen: Optional[str] = None  # 归一化合并时记录
    last_seen: Optional[str] = None
    merged_count: int = 1  # 被合并的消息条数


class GroupResult(BaseModel):
    """单个分组的分析结果（并发执行的基本单元）。"""

    session_id: str
    group_index: int
    message_count: int
    items: list[ExtractedItem] = Field(default_factory=list)
    error: Optional[str] = None  # 客户端异常信息（失败组不阻塞其他组）
    parse_error: bool = False  # JSON 三级降级后仍失败
    llm_calls: int = 0
    latency_ms: int = 0


class Stats(BaseModel):
    """整次分析的统计。"""

    session_count: int = 0
    group_count: int = 0
    message_count: int = 0
    llm_calls: int = 0
    failed_groups: int = 0
    parse_errors: int = 0
    total_latency_ms: int = 0
    task_count: int = 0  # 归一化后的任务数
    risk_count: int = 0


class AnalysisResult(BaseModel):
    """最终输出：归一化后的条目 + 统计。"""

    items: list[ExtractedItem] = Field(default_factory=list)
    stats: Stats = Field(default_factory=Stats)

    @property
    def tasks(self) -> list[ExtractedItem]:
        return [i for i in self.items if i.type != MessageType.RISK]

    @property
    def risks(self) -> list[ExtractedItem]:
        return [i for i in self.items if i.type == MessageType.RISK]

    @property
    def todos(self) -> list[ExtractedItem]:
        """待办：未完结的任务（状态不是 done）。"""
        return [i for i in self.tasks if i.status != "done"]
