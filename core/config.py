"""运行配置：统一从环境变量读取，支持 .env 文件（需 python-dotenv）。

设计取舍：用 dataclass 而不是 pydantic-settings——
配置项少且固定，dataclass 零依赖、可被测试直接构造；框架依赖留给真正需要它的地方。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:  # .env 支持是可选增强，缺失时静默降级到纯环境变量
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - 未安装 python-dotenv 时
    pass


@dataclass(frozen=True)
class Settings:
    """ChatInsight 全部运行参数。"""

    mode: str = "mock"  # mock = 内置规则引擎（无需 Key）；real = 调用真实 LLM
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_workers: int = 5
    timeout: int = 60
    max_retries: int = 2
    session_gap_minutes: int = 30  # 同一会话内超过该时长无消息则切分新组
    context_tail: int = 5  # 每组附带上一组末尾多少条消息作为上下文

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            mode=os.getenv("CHATINSIGHT_MODE", "mock"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("CHATINSIGHT_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("CHATINSIGHT_TEMPERATURE", "0.1")),
            max_workers=int(os.getenv("CHATINSIGHT_MAX_WORKERS", "5")),
            timeout=int(os.getenv("CHATINSIGHT_TIMEOUT", "60")),
            max_retries=int(os.getenv("CHATINSIGHT_MAX_RETRIES", "2")),
            session_gap_minutes=int(os.getenv("CHATINSIGHT_SESSION_GAP_MINUTES", "30")),
            context_tail=int(os.getenv("CHATINSIGHT_CONTEXT_TAIL", "5")),
        )
