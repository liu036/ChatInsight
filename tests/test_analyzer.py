"""分组分析测试：三级降级解析、重试、脏数据丢弃、时间回填。"""
from dataclasses import replace

from core.analyzer import analyze_group, parse_items
from core.models import MessageType

from .conftest import ScriptedLLMClient

VALID = (
    '{"items": [{"type": "progress", "task": "原型图", "assignee": "张伟",'
    ' "status": "doing", "detail": "完成 70%", "raw_text": "原型图完成 70%",'
    ' "msg_time": "2026-10-20 11:40"}]}'
)


def test_parse_direct_json():
    items, error = parse_items(VALID)
    assert not error
    assert len(items) == 1


def test_parse_fenced_json():
    items, error = parse_items(f"好的，结果如下：\n```json\n{VALID}\n```")
    assert not error
    assert len(items) == 1


def test_parse_failure_returns_error_flag():
    items, error = parse_items("这不是 JSON")
    assert error
    assert items == []


def test_analyze_group_success(project_groups, settings):
    result = analyze_group(ScriptedLLMClient([VALID]), project_groups[1], settings)

    assert not result.parse_error
    assert result.error is None
    assert result.llm_calls == 1
    assert len(result.items) == 1
    assert result.items[0].type == MessageType.PROGRESS


def test_retry_then_success(project_groups, settings):
    settings = replace(settings, max_retries=1)
    client = ScriptedLLMClient(["输出坏了", VALID])

    result = analyze_group(client, project_groups[1], settings)

    assert client.calls == 2  # 第一次失败，带提示重试后成功
    assert not result.parse_error


def test_persistent_failure_degrades(project_groups, settings):
    settings = replace(settings, max_retries=2)
    client = ScriptedLLMClient(["坏", "坏", "坏"])

    result = analyze_group(client, project_groups[1], settings)

    assert client.calls == 3  # 1 + 2 次重试
    assert result.parse_error is True
    assert result.items == []  # 降级：不丢组，但没有条目


def test_invalid_item_dropped_not_whole_group(project_groups, settings):
    raw = '{"items": [{"type": "progress"}, {"type": "progress", "task": "原型图", "raw_text": "x"}]}'
    result = analyze_group(ScriptedLLMClient([raw]), project_groups[1], settings)

    # 第一条缺 raw_text（必填）被丢弃，第二条保留
    assert len(result.items) == 1
    assert not result.parse_error


def test_msg_time_backfilled_from_group(project_groups, settings):
    """LLM 不给时间时，编排层按 raw_text 匹配回填。"""
    raw = (
        '{"items": [{"type": "progress", "task": "原型图", "assignee": "张伟",'
        ' "raw_text": "[2026-10-20 11:40] 张伟：原型图整体框架完成 70% 了，还差追溯页面。"}]}'
    )
    result = analyze_group(ScriptedLLMClient([raw]), project_groups[1], settings)

    assert result.items[0].msg_time == "2026-10-20 11:40"
