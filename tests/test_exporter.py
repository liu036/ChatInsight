"""导出测试与示例数据黄金测试。"""
import json
from pathlib import Path

from core.exporter import to_json, to_markdown
from core.models import AnalysisResult, ExtractedItem, MessageType, Stats
from core.pipeline import run_analysis


def _sample_result() -> AnalysisResult:
    return AnalysisResult(
        items=[
            ExtractedItem(
                type=MessageType.TASK_ASSIGN,
                task="原型图",
                assignee="张伟",
                status="doing",
                deadline="下周三前",
                detail="完成 80%",
                raw_text="x",
                msg_time="2026-10-20 09:12",
                merged_count=3,
            ),
            ExtractedItem(
                type=MessageType.RISK,
                reporter="李娜",
                detail="条码图片偶尔生成失败",
                raw_text="y",
                msg_time="2026-10-21 10:02",
            ),
        ],
        stats=Stats(session_count=2, group_count=5, message_count=12, task_count=1, risk_count=1),
    )


def test_markdown_contains_all_sections():
    md = to_markdown(_sample_result())
    assert "## 任务分配" in md
    assert "## 进度" in md
    assert "## 风险" in md
    assert "## 待办" in md
    assert "原型图" in md
    assert "条码图片偶尔生成失败" in md


def test_json_roundtrip():
    data = json.loads(to_json(_sample_result()))
    assert data["stats"]["message_count"] == 12
    assert data["items"][0]["task"] == "原型图"


# ---------- 黄金测试：Mock 规则引擎输出必须与预期文件完全一致 ----------

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "data" / "samples"

SAMPLES = {
    "session_project": "session_project.txt",
    "session_meeting": "session_meeting.txt",
    "session_quality": "session_quality.txt",
}


def _run_golden(name: str) -> None:
    from core.mock_engine import extract

    text = (SAMPLES_DIR / SAMPLES[name]).read_text(encoding="utf-8")
    expected = json.loads((SAMPLES_DIR / "expected" / f"{name}.json").read_text(encoding="utf-8"))
    assert json.loads(extract(text)) == expected


def test_mock_matches_expected_project():
    _run_golden("session_project")


def test_mock_matches_expected_meeting():
    _run_golden("session_meeting")


def test_mock_matches_expected_quality():
    _run_golden("session_quality")


def test_full_pipeline_on_project_sample(sample_project_text, settings):
    """端到端：mock 模式跑完整流水线，验证归一化与统计。"""
    result = run_analysis(sample_project_text, settings=settings)

    assert result.stats.message_count == 12
    assert result.stats.session_count == 2
    assert result.stats.group_count == 5
    assert result.stats.failed_groups == 0
    assert result.stats.parse_errors == 0
    # 两条任务分配 + 两条进度汇报归一化为同一个任务
    assert result.stats.task_count == 1
    assert result.stats.risk_count == 3
    task = result.tasks[0]
    assert task.task == "原型图"
    assert task.assignee == "张伟"
    assert task.status == "doing"
