"""Few-shot 提示词工程。

设计取舍（面试可展开）：
1. 示例固定且量小（3 条），直接内联进系统提示，而不用 LangChain 的
   FewShotPromptTemplate + 示例选择器——后者在示例库大、需要按输入检索时
   才有收益，此处只会增加一层间接性。
2. 分类边界、输出 schema、"禁止臆造"等约束写在系统提示里，示例只负责
   "示范"：一个任务分配、一个进度汇报（含同一任务的另一种表述）、一段闲聊。
3. 花括号转义：ChatPromptTemplate 用 str.format 语法解析模板，提示词里的
   JSON 花括号必须双写转义，否则会被当作输入变量而报错。
"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

SYSTEM_TEMPLATE = """你是企业沟通记录的结构化抽取引擎。输入是一段群聊或会议纪要片段，请逐条判断并抽取。

分类定义：
- task_assign：布置了任务（有明确执行人或明确动作）
- progress：汇报某项任务的进展或完成情况
- risk：指出阻塞、延期、缺料、异常等风险
- chat：寒暄、闲聊、与工作无关（输出空 items，不计入结果）

抽取规则：
1. 只抽取原文明确信息；截止时间、执行人不明确时留空，禁止臆造。
2. 同一任务被多人多次提及只输出一条，状态按时间线推进（todo → doing → done）。
3. 人员使用群内昵称原样输出，不要猜测真实姓名。
4. “收到”“好的”这类回复若能归属到上文任务则作为 progress 合并，否则忽略。
5. 输出必须是 JSON 且只输出 JSON，不要任何解释文字。

输出 JSON 格式：
{"items": [{"type": "task_assign|progress|risk", "task": "任务名或null",
            "assignee": "执行人或null", "reporter": "布置/汇报人或null",
            "status": "todo|doing|done 或null", "deadline": "截止时间或null",
            "detail": "细节或null", "raw_text": "消息原文"}]}"""

# 三个示例分别覆盖：任务分配、进度汇报（同一任务的另一种表述）、闲聊（空输出）
FEW_SHOT_EXAMPLES: list[tuple[str, str]] = [
    (
        "[2026-10-20 09:12] 王强：张伟，下周三前把标签打印系统的原型图出一版，周四下午评审。",
        '{"items": [{"type": "task_assign", "task": "标签打印系统的原型图", "assignee": "张伟",'
        ' "reporter": "王强", "status": "todo", "deadline": "下周三前", "detail": "周四下午评审",'
        ' "raw_text": "张伟，下周三前把标签打印系统的原型图出一版，周四下午评审。"}]}',
    ),
    (
        "[2026-10-21 16:30] 张伟：原型图初稿完成 80% 了，还差追溯页面和打印预览。",
        '{"items": [{"type": "progress", "task": "原型图", "assignee": "张伟", "reporter": null,'
        ' "status": "doing", "deadline": null, "detail": "完成 80%，还差追溯页面和打印预览",'
        ' "raw_text": "原型图初稿完成 80% 了，还差追溯页面和打印预览。"}]}',
    ),
    (
        "[2026-10-20 12:01] 李娜：中午食堂人真多啊。\n[2026-10-20 12:02] 王强：哈哈确实。",
        '{"items": []}',
    ),
]

HUMAN_TEMPLATE = """以下示例帮助你理解任务（注意示例是“示范”，不是待分析内容）：

{examples}

现在请分析下面的对话片段。若提供【上文末尾】，仅用于理解语境，不要抽取其中内容；
只分析【待分析的新消息】。

【上文末尾】
{context}

【待分析的新消息】
{conversation}

只输出 JSON。"""


def _escape_braces(text: str) -> str:
    """转义 str.format 语法的花括号，避免 JSON 示例被当成模板变量。"""
    return text.replace("{", "{{").replace("}", "}}")


def build_prompt() -> ChatPromptTemplate:
    """构造 Few-shot 提示词模板（系统提示 + 内联示例 + 人类输入）。"""
    examples_text = "\n\n".join(
        f"示例 {i + 1} 输入：\n{inp}\n示例 {i + 1} 输出：\n{out}"
        for i, (inp, out) in enumerate(FEW_SHOT_EXAMPLES)
    )
    human = HUMAN_TEMPLATE.format(examples=_escape_braces(examples_text))
    return ChatPromptTemplate.from_messages(
        [
            ("system", _escape_braces(SYSTEM_TEMPLATE)),
            ("human", human),
        ]
    )
