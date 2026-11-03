"""Copy shared by the ZIP bundle and the web UI for handing reports to an AI.

The statistics files are the product; turning them into a taste review is a job
for whatever AI assistant the user already trusts. This module owns that copy so
the archive README and the in-app dialog cannot drift apart.
"""

from __future__ import annotations

from typing import Any


AI_PROMPT = """下面是我用本地工具统计的网易云歌单数据，附件里有这些文件：
summary.json（完整统计和 Music DNA 指标）、report.md（可读摘要）、songs.csv（全部歌曲明细）。

请先读 summary.json 里的 overview、artistCounts、duplicateTitles 和 profile 字段，然后完成四件事：
1. 用 3-5 句话概括这份收藏的结构：歌手集中度、热度分布、时长结构、合作比例、专辑跨度。
2. 给出 2-3 条关于我音乐口味的推断，每条都要引用文件里的具体数字或具体歌曲作为证据。
3. 先看 summary.json 的 integrity.status 和 overview.missingSongCount：不是 complete 或有缺失时，
   先说明缺了多少首、把结论强度降下来；再指出其他局限，例如热度分值经常饱和在 100、
   同名歌曲只是标题完全相同、样本量是否足够，并说明哪些结论不能下。
4. 最后推荐 3 位我可能喜欢但还没收藏的歌手和 3 张专辑，并说明推荐依据是哪些已收藏歌曲。

要求：只依据文件里的数据，不要编造曲风标签、收听时长或播放次数；信息不足时直接说不知道。"""

AI_NOTICE = (
    "统计文件只包含公开歌单的数据，不含账号、Cookie、音频或设备信息。"
    "你可以把它们发给任意 AI 助手（ChatGPT、Claude、DeepSeek、Kimi 等），"
    "让 AI 基于这些数据解读你的音乐品味；文件只在你主动发送时才会离开这台电脑。"
)

AI_FILE_HINTS: tuple[dict[str, str], ...] = (
    {
        "file": "summary.json",
        "hint": "完整统计与 Music DNA 指标，信息最全，优先发送这一个也能得到结论",
    },
    {
        "file": "report.md",
        "hint": "人类可读摘要，适合让 AI 先快速理解整体结构",
    },
    {
        "file": "songs.csv",
        "hint": "全部歌曲明细，需要逐首分析时才发；几千首的歌单体积较大",
    },
)

AI_TIPS: tuple[str, ...] = (
    "热度是网易云平台分值而不是播放次数，且经常大量歌曲同为 100，值得先提醒 AI 别当播放量看。",
    "少于 30 首时画像标签只有参考价值，可以让 AI 直接说明样本不足。",
    "只发 summary.json 也能得出结论；发 songs.csv 才能让 AI 引用具体歌曲。",
)


def ai_guide() -> dict[str, Any]:
    """Return the structured guide used by the web dialog."""

    return {
        "notice": AI_NOTICE,
        "files": [dict(item) for item in AI_FILE_HINTS],
        "prompt": AI_PROMPT,
        "tips": list(AI_TIPS),
    }


def readme_section() -> str:
    """Plain-text section appended to the archive README."""

    lines = [
        "把文件交给 AI，解读你的音乐品味",
        "-" * 40,
        AI_NOTICE,
        "",
        "建议发送顺序：",
    ]
    lines.extend(f"  - {item['file']}：{item['hint']}" for item in AI_FILE_HINTS)
    lines.extend(
        [
            "",
            "可以直接复制的提示词：",
            "-" * 40,
            AI_PROMPT,
            "-" * 40,
            "",
            "提示：",
        ]
    )
    lines.extend(f"  - {tip}" for tip in AI_TIPS)
    return "\n".join(lines)
