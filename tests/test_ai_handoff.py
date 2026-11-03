from __future__ import annotations

from netease_stats.core.ai_handoff import ai_guide, readme_section


def test_guide_lists_the_files_to_send():
    guide = ai_guide()
    assert [item["file"] for item in guide["files"]] == [
        "summary.json",
        "report.md",
        "songs.csv",
    ]
    assert all(item["hint"] for item in guide["files"])
    assert guide["notice"] and guide["tips"]


def test_prompt_asks_for_evidence_and_flags_data_limits():
    prompt = ai_guide()["prompt"]
    assert "summary.json" in prompt
    assert "songs.csv" in prompt
    assert "证据" in prompt
    # 热度饱和是小样本之外最容易误导 AI 的一点，提示词必须点名。
    assert "100" in prompt
    # 数据不完整时 AI 要先降级结论，而不是把部分样本当全量。
    assert "integrity.status" in prompt
    assert "不要编造" in prompt


def test_readme_section_is_self_contained_plain_text():
    section = readme_section()
    assert "把文件交给 AI" in section
    assert "只包含公开歌单" in section
    assert ai_guide()["prompt"] in section
    assert "summary.json" in section
    assert "songs.csv" in section
