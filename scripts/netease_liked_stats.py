#!/usr/bin/env python3
"""Build a complete, auditable report for a public NetEase playlist."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PLAYLIST_ENDPOINT = "https://music.163.com/api/v6/playlist/detail"
SONG_ENDPOINT = "https://music.163.com/api/song/detail"
USER_AGENT = "Mozilla/5.0"
REFERER = "https://music.163.com/"


def request_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Referer": REFERER},
    )
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except Exception as error:
            last_error = error
            if attempt < 3:
                time.sleep(0.75 * (attempt + 1))
    raise RuntimeError(f"Request failed after four attempts: {url}") from last_error


def fetch_playlist(playlist_id: int, timeout: float) -> dict[str, Any]:
    query = urllib.parse.urlencode({"id": playlist_id})
    data = request_json(f"{PLAYLIST_ENDPOINT}?{query}", timeout)
    if data.get("code") != 200 or not isinstance(data.get("playlist"), dict):
        raise RuntimeError(f"Playlist request failed: {data.get('code')}")
    return data


def unique_track_ids(playlist: dict[str, Any]) -> list[int]:
    raw_ids = playlist.get("trackIds")
    if not isinstance(raw_ids, list):
        raise RuntimeError("Playlist response does not contain trackIds")
    track_ids = []
    seen = set()
    for item in raw_ids:
        song_id = int(item["id"] if isinstance(item, dict) else item)
        if song_id not in seen:
            seen.add(song_id)
            track_ids.append(song_id)
    declared = int(playlist.get("trackCount") or 0)
    if declared and declared != len(track_ids):
        print(
            f"warning: trackCount={declared}, unique trackIds={len(track_ids)}",
            file=sys.stderr,
        )
    return track_ids


def fetch_songs(
    track_ids: list[int],
    batch_size: int,
    timeout: float,
) -> tuple[dict[int, dict[str, Any]], list[int]]:
    if not 1 <= batch_size <= 200:
        raise ValueError("batch_size must be between 1 and 200")

    songs: dict[int, dict[str, Any]] = {}
    missing: list[int] = []
    total_batches = (len(track_ids) + batch_size - 1) // batch_size
    for batch_number, start in enumerate(range(0, len(track_ids), batch_size), 1):
        batch = track_ids[start : start + batch_size]
        encoded_ids = urllib.parse.urlencode(
            {"ids": json.dumps(batch, separators=(",", ":"))}
        )
        data = request_json(f"{SONG_ENDPOINT}?{encoded_ids}", timeout)
        if data.get("code") != 200:
            raise RuntimeError(f"Song batch {batch_number} failed: {data.get('code')}")

        returned = data.get("songs") or []
        returned_ids = set()
        for song in returned:
            if not isinstance(song, dict) or song.get("id") is None:
                continue
            song_id = int(song["id"])
            returned_ids.add(song_id)
            songs[song_id] = song

        batch_missing = [song_id for song_id in batch if song_id not in returned_ids]
        missing.extend(batch_missing)
        print(
            f"batch {batch_number:02d}/{total_batches:02d} "
            f"requested={len(batch)} returned={len(returned)} "
            f"cumulative={len(songs)} missing={len(batch_missing)}",
            flush=True,
        )
    return songs, missing


def artist_names(song: dict[str, Any]) -> list[str]:
    artists = song.get("artists") or song.get("ar") or []
    result = []
    seen = set()
    for artist in artists:
        if not isinstance(artist, dict):
            continue
        name = str(artist.get("name") or "").strip() or "(未知歌手)"
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result or ["(未知歌手)"]


def duration_ms(song: dict[str, Any]) -> int:
    return int(song.get("duration", song.get("dt")) or 0)


def popularity(song: dict[str, Any]) -> float | None:
    value = song.get("popularity")
    if value is None:
        value = song.get("score")
    if value is None:
        value = song.get("pop")
    return None if value is None else float(value)


def normalize_title(title: Any) -> str:
    return unicodedata.normalize("NFC", str(title or "").strip()) or "(未命名)"


def format_duration(milliseconds: int) -> str:
    seconds = round(milliseconds / 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def album_name(song: dict[str, Any]) -> str:
    album = song.get("album") or song.get("al") or {}
    return str(album.get("name") or "").strip() if isinstance(album, dict) else ""


def song_row(song: dict[str, Any]) -> dict[str, Any]:
    duration = duration_ms(song)
    heat = popularity(song)
    return {
        "id": int(song["id"]),
        "title": normalize_title(song.get("name")),
        "artists": artist_names(song),
        "album": album_name(song),
        "durationMs": duration,
        "duration": format_duration(duration),
        "popularity": heat,
    }


def csv_write(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


def build_report(
    playlist: dict[str, Any],
    ordered_songs: list[dict[str, Any]],
    missing_ids: list[int],
    out_dir: Path,
    playlist_id: int,
) -> dict[str, Any]:
    rows = [song_row(song) for song in ordered_songs]
    artist_counts = Counter()
    title_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    durations = []
    popularity_values = []

    for row in rows:
        artist_counts.update(row["artists"])
        title_groups[row["title"]].append(row)
        if row["durationMs"] > 0:
            durations.append(row["durationMs"])
        if row["popularity"] is not None:
            popularity_values.append(row["popularity"])

    if not durations:
        raise RuntimeError("No positive song durations were available")
    if not popularity_values:
        raise RuntimeError("No popularity scores were available")

    duplicate_groups = [
        {"title": title, "count": len(group), "songs": group}
        for title, group in title_groups.items()
        if len(group) >= 2
    ]
    duplicate_groups.sort(key=lambda item: (-item["count"], item["title"].casefold()))

    max_duration = max(durations)
    min_duration = min(durations)
    max_popularity = max(popularity_values)
    min_popularity = min(popularity_values)
    longest = [row for row in rows if row["durationMs"] == max_duration]
    shortest = [row for row in rows if row["durationMs"] == min_duration]
    hottest = [row for row in rows if row["popularity"] == max_popularity]
    coldest = [row for row in rows if row["popularity"] == min_popularity]

    summary = {
        "playlist": {
            "id": playlist_id,
            "name": playlist.get("name"),
            "creator": playlist.get("creator"),
            "declaredTrackCount": playlist.get("trackCount"),
        },
        "overview": {
            "fetchedSongCount": len(rows),
            "uniqueArtists": len(artist_counts),
            "artistCredits": sum(artist_counts.values()),
            "averageDurationMs": round(statistics.mean(durations)),
            "averageDuration": format_duration(round(statistics.mean(durations))),
            "totalDurationMs": sum(durations),
            "totalDuration": format_duration(sum(durations)),
            "duplicateTitleGroups": len(duplicate_groups),
            "songsInDuplicateTitleGroups": sum(
                item["count"] for item in duplicate_groups
            ),
            "popularityCoverage": len(popularity_values),
            "missingSongCount": len(missing_ids),
            "missingSongIds": missing_ids,
        },
        "artistCounts": [
            {"artist": artist, "count": count}
            for artist, count in artist_counts.most_common()
        ],
        "duplicateTitles": duplicate_groups,
        "extremes": {
            "longest": longest,
            "shortest": shortest,
            "hottest": hottest,
            "coldest": coldest,
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    csv_write(
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
    csv_write(
        out_dir / "artist_counts.csv",
        ["排名", "歌手", "歌曲数量"],
        [
            [rank, artist, count]
            for rank, (artist, count) in enumerate(artist_counts.most_common(), 1)
        ],
    )
    csv_write(
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
            for group in duplicate_groups
            for row in group["songs"]
        ],
    )
    csv_write(
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
                ("时长最长", longest),
                ("时长最短", shortest),
                ("热度最高", hottest),
                ("热度最低", coldest),
            )
            for row in group
        ],
    )

    top_artists = summary["artistCounts"][:20]
    multi_version = [
        group for group in duplicate_groups if group["count"] >= 3
    ][:20]
    lines = [
        "# 网易云喜欢音乐统计",
        "",
        f"- 歌单：{summary['playlist']['name']}",
        f"- 歌曲：{len(rows)} 首",
        f"- 唯一歌手：{len(artist_counts)} 位",
        f"- 歌手署名：{sum(artist_counts.values())} 次",
        f"- 平均时长：{summary['overview']['averageDuration']}",
        f"- 总时长：{summary['overview']['totalDuration']}",
        f"- 同名歌曲：{len(duplicate_groups)} 组",
        f"- 热度范围：{min_popularity:g}–{max_popularity:g}",
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
        f"| 最长 | {longest[0]['title']} | {' / '.join(longest[0]['artists'])} | {longest[0]['duration']} |",
        f"| 最短 | {shortest[0]['title']} | {' / '.join(shortest[0]['artists'])} | {shortest[0]['duration']} |",
        f"| 热度最高 | {hottest[0]['title']} | {' / '.join(hottest[0]['artists'])} | {max_popularity:g}（{len(hottest)} 首并列） |",
        f"| 热度最低 | {coldest[0]['title']} | {' / '.join(coldest[0]['artists'])} | {min_popularity:g}（{len(coldest)} 首并列） |",
        "",
        "## 三首及以上同名歌曲",
        "",
    ]
    lines.extend(
        f"- {group['title']}（{group['count']}）："
        + " / ".join(row["artists"][0] for row in group["songs"])
        for group in multi_version
    )
    lines += [
        "",
        "热度为网易云歌曲详情接口返回的 `popularity` 平台分值，并非播放次数，官方未公开底层公式。",
        "",
    ]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playlist-id", required=True, type=int)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="write a report even if some requested songs are unavailable",
    )
    args = parser.parse_args()

    playlist_data = fetch_playlist(args.playlist_id, args.timeout)
    playlist = playlist_data["playlist"]
    track_ids = unique_track_ids(playlist)
    print(
        f"playlist={args.playlist_id} tracks={len(track_ids)}",
        flush=True,
    )

    songs, missing = fetch_songs(track_ids, args.batch_size, args.timeout)
    if missing and not args.allow_missing:
        raise RuntimeError(
            f"{len(missing)} requested songs were missing: {missing[:20]}"
        )

    ordered_songs = [songs[song_id] for song_id in track_ids if song_id in songs]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / "raw_data.json").open("w", encoding="utf-8") as file:
        json.dump(
            {
                "playlist": playlist,
                "trackIds": track_ids,
                "songs": ordered_songs,
                "missingIds": missing,
            },
            file,
            ensure_ascii=False,
        )

    summary = build_report(
        playlist,
        ordered_songs,
        missing,
        args.out_dir,
        args.playlist_id,
    )
    print(
        "complete: "
        f"songs={len(ordered_songs)} artists={summary['overview']['uniqueArtists']} "
        f"duplicate_groups={summary['overview']['duplicateTitleGroups']} "
        f"missing={len(missing)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
