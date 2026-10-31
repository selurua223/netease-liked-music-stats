"""Write stable, auditable report artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _csv_write(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


def _markdown_report(summary: dict[str, Any]) -> str:
    overview = summary["overview"]
    playlist = summary["playlist"]
    duplicate_groups = summary["duplicateTitles"]
    extremes = summary["extremes"]
    hottest = extremes["hottest"]
    coldest = extremes["coldest"]
    top_artists = summary["artistCounts"][:20]
    lines = [
        "# 网易云喜欢音乐统计",
        "",
        f"- 歌单：{playlist['name']}",
        f"- 歌曲：{overview['fetchedSongCount']} 首",
        f"- 唯一歌手：{overview['uniqueArtists']} 位",
        f"- 歌手署名：{overview['artistCredits']} 次",
        f"- 平均时长：{overview['averageDuration']}",
        f"- 总时长：{overview['totalDuration']}",
        f"- 同名歌曲：{overview['duplicateTitleGroups']} 组",
        f"- 缺失歌曲：{overview['missingSongCount']} 首",
        "",
        "## 歌手前 20 名",
        "",
        "| 排名 | 歌手 | 歌曲数 |",
        "|---:|---|---:|",
    ]
    lines.extend(
        f"| {rank} | {item['artist']} | {item['count']} |"
        for rank, item in enumerate(top_artists, 1)
    )
    lines += [
        "",
        "## 时长与热度极值",
        "",
        "| 类型 | 代表歌曲 | 歌手 | 数值 |",
        "|---|---|---|---:|",
    ]
    if extremes["longest"]:
        lines.append(
            f"| 最长 | {extremes['longest'][0]['title']} | "
            f"{' / '.join(extremes['longest'][0]['artists'])} | "
            f"{extremes['longest'][0]['duration']} |"
        )
    if extremes["shortest"]:
        lines.append(
            f"| 最短 | {extremes['shortest'][0]['title']} | "
            f"{' / '.join(extremes['shortest'][0]['artists'])} | "
            f"{extremes['shortest'][0]['duration']} |"
        )
    if hottest:
        lines.append(
            f"| 热度最高 | {hottest[0]['title']} | "
            f"{' / '.join(hottest[0]['artists'])} | "
            f"{hottest[0]['popularity']:g}（{len(hottest)} 首并列） |"
        )
    if coldest:
        lines.append(
            f"| 热度最低 | {coldest[0]['title']} | "
            f"{' / '.join(coldest[0]['artists'])} | "
            f"{coldest[0]['popularity']:g}（{len(coldest)} 首并列） |"
        )
    lines += ["", "## 三首及以上同名歌曲", ""]
    for group in [item for item in duplicate_groups if item["count"] >= 3][:20]:
        artists = " / ".join(
            sorted({artist for row in group["songs"] for artist in row["artists"]})
        )
        lines.append(f"- {group['title']}（{group['count']}）：{artists}")
    lines += [
        "",
        "热度为网易云歌曲详情接口返回的 `popularity` 平台分值，"
        "并非播放次数，官方未公开底层公式。",
        "",
    ]
    return "\n".join(lines)


def write_report(
    out_dir: Path,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    playlist: dict[str, Any],
    track_ids: list[int],
    missing_ids: list[int],
    raw_songs: list[dict[str, Any]] | None,
    metadata: dict[str, Any],
    *,
    include_raw_data: bool = True,
    generate_csv: bool = True,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "songs.json").write_text(
        json.dumps(rows, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "report.md").write_text(_markdown_report(summary), encoding="utf-8")

    if include_raw_data:
        (out_dir / "raw_data.json").write_text(
            json.dumps(
                {
                    "playlist": playlist,
                    "trackIds": track_ids,
                    "missingIds": missing_ids,
                    "songs": raw_songs or [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    if not generate_csv:
        return

    _csv_write(
        out_dir / "songs.csv",
        ["歌曲ID", "歌曲", "歌手", "专辑", "时长", "热度"],
        [
            [
                row["id"],
                row["title"],
                " / ".join(row["artists"]),
                row["album"],
                row["duration"],
                row["popularity"],
            ]
            for row in rows
        ],
    )
    _csv_write(
        out_dir / "artist_counts.csv",
        ["排名", "歌手", "歌曲数量"],
        [
            [rank, item["artist"], item["count"]]
            for rank, item in enumerate(summary["artistCounts"], 1)
        ],
    )
    _csv_write(
        out_dir / "duplicate_titles.csv",
        ["同名歌曲", "该名称歌曲数", "歌曲ID", "歌手", "专辑", "时长", "热度"],
        [
            [
                group["title"],
                group["count"],
                row["id"],
                " / ".join(row["artists"]),
                row["album"],
                row["duration"],
                row["popularity"],
            ]
            for group in summary["duplicateTitles"]
            for row in group["songs"]
        ],
    )
    _csv_write(
        out_dir / "extrema.csv",
        ["极值类型", "歌曲ID", "歌曲", "歌手", "专辑", "时长", "热度"],
        [
            [
                label,
                row["id"],
                row["title"],
                " / ".join(row["artists"]),
                row["album"],
                row["duration"],
                row["popularity"],
            ]
            for label, group in (
                ("时长最长", summary["extremes"]["longest"]),
                ("时长最短", summary["extremes"]["shortest"]),
                ("热度最高", summary["extremes"]["hottest"]),
                ("热度最低", summary["extremes"]["coldest"]),
            )
            for row in group
        ],
    )
