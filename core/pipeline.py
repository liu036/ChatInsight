"""分析流水线：把 10 步流程编排成一个可测试的函数。

流程：加载 → 会话分段 → 消息解析 → 时间窗分组 → 附加上下文
→ 线程池并发调用 → JSON 降级解析 → 跨组归一化 → 统计 → 展示/导出。

为什么并发放在 pipeline 而不是 UI：并发是业务行为不是界面行为，
放在这里才能被测试直接验证（见 tests/test_concurrency.py）。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from .analyzer import analyze_group
from .config import Settings
from .grouper import group_messages
from .llm import BaseLLMClient, get_llm_client
from .models import AnalysisResult, MessageType, Stats
from .normalizer import merge_items
from .parser import parse_chat


def run_analysis(
    text: str,
    settings: Settings | None = None,
    client: BaseLLMClient | None = None,
) -> AnalysisResult:
    """对一段对话文本执行完整分析，返回归一化结果。"""
    settings = settings or Settings.from_env()
    client = client or get_llm_client(settings)

    messages = parse_chat(text)
    groups = group_messages(messages, settings)

    results = []
    if groups:
        with ThreadPoolExecutor(max_workers=settings.max_workers) as pool:
            futures = [pool.submit(analyze_group, client, group, settings) for group in groups]
            for future in as_completed(futures):
                results.append(future.result())
    results.sort(key=lambda r: r.group_index)

    all_items = [item for result in results for item in result.items]
    merged = merge_items(all_items)

    return AnalysisResult(items=merged, stats=_build_stats(messages, results, merged))


def _build_stats(messages, results, merged) -> Stats:
    return Stats(
        session_count=len({m.session_id for m in messages}),
        group_count=len(results),
        message_count=len(messages),
        llm_calls=sum(r.llm_calls for r in results),
        failed_groups=sum(1 for r in results if r.error),
        parse_errors=sum(1 for r in results if r.parse_error),
        total_latency_ms=sum(r.latency_ms for r in results),
        task_count=sum(1 for i in merged if i.type != MessageType.RISK),
        risk_count=sum(1 for i in merged if i.type == MessageType.RISK),
    )
