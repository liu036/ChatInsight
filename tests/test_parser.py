"""消息解析测试。"""
from core.parser import parse_chat


def test_parse_project_sample(sample_project_text):
    messages = parse_chat(sample_project_text)

    assert len(messages) == 12
    assert messages[0].speaker == "王强"
    assert messages[0].content.startswith("张伟，下周三前")
    assert messages[0].time == "2026-10-20 09:12"
    # 两个会话标题生成两个 session_id
    assert {m.session_id for m in messages} == {
        "智能标签演示系统项目群（10-20）",
        "智能标签演示系统项目群（10-21）",
    }


def test_time_inheritance_and_non_message_lines():
    text = (
        "=== 会话 1：测试会话 ===\n"
        "[2026-10-20 09:00] 张三：第一句\n"
        "李四：第二句\n"
        "【公告】系统将于今晚维护\n"
    )
    messages = parse_chat(text)

    assert len(messages) == 2
    # 无时间戳的消息继承上一条时间
    assert messages[1].time == messages[0].time == "2026-10-20 09:00"
    # 非消息行（无“发言人：内容”结构）被忽略
    assert all("公告" not in m.content for m in messages)


def test_seconds_precision_and_iso_t():
    text = "[2026-10-20T09:30:05] 王五：带 T 和秒的时间格式\n"
    messages = parse_chat(text)
    assert messages[0].time == "2026-10-20 09:30"
