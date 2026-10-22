"""pytest 公共 fixtures。

测试全程不发起真实网络调用：
- ScriptedLLMClient：按脚本返回原始输出，用于验证解析降级链；
- SlowLLMClient：可配置延迟/定向失败，用于验证并发与容错。
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from core.config import Settings

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "data" / "samples"


class ScriptedLLMClient:
    """按预设序列返回原始文本；序列用尽后重复最后一条。"""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0

    def analyze(self, conversation: str, retry_hint: str = "") -> str:
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


class SlowLLMClient:
    """模拟慢速 LLM；fail_for 命中的分组抛异常（模拟单组失败）。"""

    def __init__(self, delay: float = 0.1, fail_for: str | None = None):
        self.delay = delay
        self.fail_for = fail_for

    def analyze(self, conversation: str, retry_hint: str = "") -> str:
        time.sleep(self.delay)
        if self.fail_for and self.fail_for in conversation:
            raise RuntimeError("模拟 LLM 调用失败")
        return '{"items": []}'


@pytest.fixture
def settings() -> Settings:
    return Settings(mode="mock", max_workers=5, max_retries=0)


@pytest.fixture
def sample_project_text() -> str:
    return (SAMPLES_DIR / "session_project.txt").read_text(encoding="utf-8")


@pytest.fixture
def project_groups(sample_project_text, settings):
    from core.grouper import group_messages
    from core.parser import parse_chat

    return group_messages(parse_chat(sample_project_text), settings)
