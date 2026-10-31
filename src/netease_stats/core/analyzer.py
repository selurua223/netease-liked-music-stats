"""Orchestrate playlist collection, verification, statistics, and report output."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from netease_stats import __version__

from .collector import fetch_playlist, fetch_songs, unique_track_ids
from .integrity import validate_coverage
from .normalizer import song_row
from .profile import build_profile
from .reporting import write_report
from .statistics import build_summary


ProgressCallback = Callable[[dict[str, Any]], None]


def _emit(
    callback: ProgressCallback | None,
    stage: str,
    message: str,
    completed: int | None = None,
    total: int | None = None,
) -> None:
    if callback:
        callback(
            {
                "stage": stage,
                "message": message,
                "completed": completed,
                "total": total,
            }
        )


def analyze_playlist(
    playlist_id: int,
    out_dir: Path,
    *,
    batch_size: int = 200,
    timeout: float = 30,
    include_raw_data: bool = True,
    generate_csv: bool = True,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    _emit(progress, "playlist", "正在读取歌单信息")
    playlist = fetch_playlist(playlist_id, timeout)
    track_ids = unique_track_ids(playlist)
    _emit(
        progress,
        "playlist",
        f"已发现 {len(track_ids)} 首歌曲，准备获取详情",
        0,
        len(track_ids),
    )

    def on_batch(batch: Any) -> None:
        _emit(
            progress,
            "collecting",
            f"第 {batch.batch}/{batch.total_batches} 批，已读取 {batch.cumulative} 首",
            batch.cumulative,
            len(track_ids),
        )

    songs, missing_ids = fetch_songs(
        track_ids,
        batch_size=batch_size,
        timeout=timeout,
        progress=on_batch,
    )
    ordered_songs = [songs[song_id] for song_id in track_ids if song_id in songs]
    rows = [song_row(song) for song in ordered_songs]

    _emit(progress, "statistics", "正在计算统计指标", len(rows), len(track_ids))
    summary = build_summary(playlist, rows, missing_ids, playlist_id)
    summary["profile"] = build_profile(rows)
    integrity = validate_coverage(playlist, track_ids, songs, missing_ids)
    summary["integrity"] = integrity.to_dict()
    summary["metadata"] = {
        "projectVersion": __version__,
        "generatedAt": datetime.now(UTC).isoformat(),
        "dataSource": "public NetEase Cloud Music API",
        "privacy": "local-only; no account credentials",
    }

    metadata = {
        "reportId": out_dir.name,
        "playlistId": playlist_id,
        "playlistName": playlist.get("name"),
        "generatedAt": summary["metadata"]["generatedAt"],
        "projectVersion": __version__,
        "dataSource": summary["metadata"]["dataSource"],
        "requestedCount": len(track_ids),
        "returnedCount": len(rows),
        "missingCount": len(missing_ids),
        "integrityStatus": integrity.status,
    }
    _emit(progress, "reporting", "正在写入报告文件", len(rows), len(track_ids))
    write_report(
        out_dir,
        summary,
        rows,
        playlist,
        track_ids,
        missing_ids,
        metadata,
        include_raw_data=include_raw_data,
        generate_csv=generate_csv,
    )
    _emit(progress, "completed", "分析完成", len(rows), len(track_ids))
    return summary
