"""并发与容错测试。

验证两点：
1. 5 个分组的并发执行显著快于串行（线程池真的在并发）；
2. 单个分组失败只标记自己，不影响其他分组（fail-fast 的反面）。
"""
import time

from core.pipeline import run_analysis

from .conftest import SlowLLMClient


def test_groups_run_concurrently(sample_project_text, settings):
    client = SlowLLMClient(delay=0.1)
    started = time.perf_counter()
    result = run_analysis(sample_project_text, settings=settings, client=client)
    elapsed = time.perf_counter() - started

    assert result.stats.group_count == 5
    # 串行需要约 0.5s，并发应远低于此
    assert elapsed < 0.1 * 5 * 0.6


def test_single_group_failure_does_not_block_others(sample_project_text, settings):
    client = SlowLLMClient(delay=0.02, fail_for="16:30")  # 只让最后一个分组失败

    result = run_analysis(sample_project_text, settings=settings, client=client)

    assert result.stats.group_count == 5
    assert result.stats.failed_groups == 1
    assert result.stats.message_count == 12
