"""任务归一化与状态机测试。"""
from core.models import ExtractedItem, MessageType
from core.normalizer import merge_items, normalize_task


def _item(**overrides) -> ExtractedItem:
    base = dict(type=MessageType.PROGRESS, raw_text="x", msg_time="2026-10-20 09:00")
    base.update(overrides)
    return ExtractedItem(**base)


def test_normalize_synonyms_and_leading_verbs():
    assert normalize_task("把标签打印系统的原型图出一版") == "原型图"
    assert normalize_task("原型图整体框架") == "原型图"
    assert normalize_task("原型图初稿") == "原型图"


def test_merge_same_task_across_groups():
    items = [
        _item(
            type=MessageType.TASK_ASSIGN,
            task="把标签打印系统的原型图出一版",
            assignee="张伟",
            reporter="王强",
            status="todo",
            deadline="下周三前",
            msg_time="2026-10-20 09:12",
        ),
        _item(
            task="原型图整体框架",
            assignee="张伟",
            status="doing",
            detail="完成 70%",
            msg_time="2026-10-20 11:40",
        ),
        _item(
            task="原型图初稿",
            assignee="张伟",
            status="doing",
            detail="完成 80%",
            msg_time="2026-10-21 16:30",
        ),
    ]
    merged = merge_items(items)

    assert len(merged) == 1
    task = merged[0]
    assert task.type == MessageType.TASK_ASSIGN  # 保留首次出现的类型
    assert task.task == "原型图"  # 收敛后的标准任务名
    assert task.status == "doing"  # 状态按时间线推进
    assert task.deadline == "下周三前"  # 截止来自任务分配
    assert task.detail == "完成 80%"  # 详情取最新进度
    assert task.merged_count == 3


def test_status_never_regresses():
    items = [
        _item(task="原型图", assignee="张伟", status="done", msg_time="2026-10-21 10:00"),
        _item(task="原型图", assignee="张伟", status="todo", msg_time="2026-10-21 11:00"),
    ]
    assert merge_items(items)[0].status == "done"


def test_different_assignees_not_merged():
    items = [
        _item(task="原型图", assignee="张伟", msg_time="2026-10-20 09:00"),
        _item(task="原型图", assignee="李娜", msg_time="2026-10-20 09:30"),
    ]
    assert len(merge_items(items)) == 2


def test_risks_pass_through_unchanged():
    items = [
        _item(type=MessageType.RISK, task=None, reporter="李娜", detail="有风险", msg_time="2026-10-20 09:16")
    ]
    merged = merge_items(items)
    assert len(merged) == 1
    assert merged[0].type == MessageType.RISK
