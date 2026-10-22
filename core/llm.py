"""LLM 客户端：Mock（规则引擎）与 LangChain（真实 API）双实现。

为什么用协议而不是继承：analyzer 只依赖 analyze() 方法，
测试可以注入任意假客户端（脚本化响应、慢响应、必失败响应），
不需要 Mock 继承链条——组合优于继承的最小实践。

LangChain 的引入是轻量的：只用 ChatPromptTemplate 组织提示词、
ChatOpenAI 调用模型，不引入 Agent/LangGraph 那套重量级抽象。
"""
from __future__ import annotations

from typing import Protocol

from . import mock_engine
from .config import Settings
from .prompt import build_prompt


class BaseLLMClient(Protocol):
    """LLM 客户端协议：输入渲染后的对话文本，输出原始 JSON 字符串。"""

    def analyze(self, conversation: str, retry_hint: str = "") -> str:
        ...


class MockLLMClient:
    """内置规则引擎客户端：无需 API Key，输出确定性的合法 JSON。"""

    mode_name = "mock"

    def analyze(self, conversation: str, retry_hint: str = "") -> str:
        return mock_engine.extract(conversation)


class LangChainLLMClient:
    """基于 LangChain + ChatOpenAI 的客户端，指向任何 OpenAI 兼容端点。"""

    mode_name = "real"

    def __init__(self, settings: Settings):
        if not settings.api_key:
            raise ValueError("real 模式需要 OPENAI_API_KEY；或改用 mock 模式（CHATINSIGHT_MODE=mock）")

        # 延迟导入：mock 模式不安装 langchain 也能跑（演示/测试零依赖）
        from langchain_openai import ChatOpenAI

        self._chain = build_prompt() | ChatOpenAI(
            model=settings.model,
            temperature=settings.temperature,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            openai_api_key=settings.api_key,
            openai_api_base=settings.base_url,
        )

    def analyze(self, conversation: str, retry_hint: str = "") -> str:
        message = self._chain.invoke(
            {"conversation": conversation + retry_hint, "context": ""}
        )
        return message.content


def get_llm_client(settings: Settings) -> BaseLLMClient:
    """按配置返回客户端；real 模式缺少 Key 时给出明确错误。"""
    if settings.mode == "real":
        return LangChainLLMClient(settings)
    return MockLLMClient()
