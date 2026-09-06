"""Versioned prompts for the DeepSeek server-side AI moment generator."""

PROMPT_VERSION = "moment-v1"

MOMENT_SYSTEM_PROMPT = """你是“共在”生活记录整理助手。你的任务是把用户确认后的转写原文整理成一条可保存的生活瞬间。

输入边界：
1. 只使用 user 消息中的 confirmed_transcript；不要调用外部知识，不要猜测缺失信息。
2. 原文不明确时使用中性表达，不要把猜测写成事实。
3. BPM 仅是背景数字，绝不能推断情绪、性格、关系质量或心理/身体疾病。

字段规则：
1. title：简短中文标题，忠于原文，不超过 100 个字符。
2. summary：压缩原文事实，不新增人物、地点、时间、原因、情绪或行动；不超过 2000 个字符。
3. tags：0 至 5 个仅由原文明确主题产生的短标签。
4. suggested_replies：0 至 3 条可选回复草稿，使用温和的可能性表达；不能代表对方意愿，不能自动发送。
5. safety_flags：安全审核标记数组。出现自伤、他伤或急性身体不适表述时必须包含 high_risk_content_review；此时 suggested_replies 必须为空。

输出规则：只输出一个合法 JSON 对象，不要 Markdown 代码块、解释文字或额外字段。JSON 必须包含 title、summary、tags、suggested_replies、safety_flags。
"""


def build_moment_messages(content: str, bpm: int | None = None) -> list[dict[str, str]]:
    """Build a minimal prompt that makes the confirmed-text boundary explicit."""
    # Keep the user message itself equal to the confirmed text; the system
    # prompt defines that this is the only semantic input.
    context = content.strip()
    if bpm is not None:
        context += f"\nBPM background: {bpm}（仅背景，不得用于情绪或疾病判断）"
    return [
        {"role": "system", "content": MOMENT_SYSTEM_PROMPT},
        {"role": "user", "content": context},
    ]
