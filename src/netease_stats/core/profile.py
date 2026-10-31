"""Evidence-backed Music DNA metrics and deterministic profile labels."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any


PROFILE_VERSION = "1.0"
LOW_POPULARITY_THRESHOLD = 40
HIGH_POPULARITY_THRESHOLD = 80


def _normalized_entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 0 or len(counts) <= 1:
        return 0.0
    probabilities = [count / total for count in counts if count > 0]
    entropy = -sum(value * math.log(value) for value in probabilities)
    return entropy / math.log(len(probabilities))


def _confidence(ratio: float) -> str:
    if ratio >= 0.9:
        return "高"
    if ratio >= 0.65:
        return "中"
    return "低"


def build_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("Music profile requires at least one song")

    song_count = len(rows)
    artist_counts: Counter[str] = Counter()
    title_groups: dict[str, int] = defaultdict(int)
    albums: set[str] = set()
    pair_counts: Counter[tuple[str, str]] = Counter()
    durations: list[int] = []
    popularity_values: list[float] = []
    collaboration_songs = 0
    long_songs = 0
    short_songs = 0

    for row in rows:
        artists = list(dict.fromkeys(row["artists"]))
        artist_counts.update(artists)
        title_groups[row["title"]] += 1
        if row.get("album"):
            albums.add(row["album"])
        if len(artists) > 1:
            collaboration_songs += 1
            for pair in combinations(sorted(artists), 2):
                pair_counts[pair] += 1
        duration = int(row.get("durationMs") or 0)
        if duration > 0:
            durations.append(duration)
            long_songs += duration >= 5 * 60_000
            short_songs += duration < 2 * 60_000
        if row.get("popularity") is not None:
            popularity_values.append(float(row["popularity"]))

    total_artist_credits = sum(artist_counts.values())
    artist_credit_share = [
        count / total_artist_credits for count in artist_counts.values()
    ]
    artist_entropy = _normalized_entropy(list(artist_counts.values()))
    artist_hhi = sum(share * share for share in artist_credit_share)
    top10_credit_count = sum(count for _, count in artist_counts.most_common(10))
    top10_credit_share = top10_credit_count / total_artist_credits
    top10_names = {name for name, _ in artist_counts.most_common(10)}
    top10_song_count = sum(
        bool(top10_names.intersection(row["artists"])) for row in rows
    )
    top10_song_coverage = top10_song_count / song_count

    low_popularity_count = sum(
        value < LOW_POPULARITY_THRESHOLD for value in popularity_values
    )
    high_popularity_count = sum(
        value >= HIGH_POPULARITY_THRESHOLD for value in popularity_values
    )
    popularity_coverage = len(popularity_values) / song_count
    low_popularity_ratio = (
        low_popularity_count / len(popularity_values)
        if popularity_values
        else 0.0
    )
    high_popularity_ratio = (
        high_popularity_count / len(popularity_values)
        if popularity_values
        else 0.0
    )

    duration_median = int(statistics.median(durations)) if durations else 0
    average_duration = round(statistics.mean(durations)) if durations else 0
    long_song_ratio = long_songs / len(durations) if durations else 0.0
    short_song_ratio = short_songs / len(durations) if durations else 0.0
    collaboration_ratio = collaboration_songs / song_count
    album_diversity = len(albums) / song_count
    duplicate_groups = sum(count >= 2 for count in title_groups.values())

    top_pair = pair_counts.most_common(1)[0] if pair_counts else None
    metrics = {
        "artistCount": len(artist_counts),
        "artistNormalizedEntropy": round(artist_entropy, 4),
        "artistHhi": round(artist_hhi, 5),
        "top10ArtistCreditShare": round(top10_credit_share, 4),
        "top10ArtistSongCoverage": round(top10_song_coverage, 4),
        "lowPopularityThreshold": LOW_POPULARITY_THRESHOLD,
        "lowPopularityRatio": round(low_popularity_ratio, 4),
        "highPopularityRatio": round(high_popularity_ratio, 4),
        "popularityCoverage": round(popularity_coverage, 4),
        "collaborationRatio": round(collaboration_ratio, 4),
        "albumDiversity": round(album_diversity, 4),
        "averageDurationMs": average_duration,
        "medianDurationMs": duration_median,
        "longSongRatio": round(long_song_ratio, 4),
        "shortSongRatio": round(short_song_ratio, 4),
        "duplicateTitleGroups": duplicate_groups,
        "topCollaborationPair": (
            {
                "artists": list(top_pair[0]),
                "songCount": top_pair[1],
            }
            if top_pair
            else None
        ),
    }

    tags: list[str] = []
    if artist_entropy >= 0.72:
        tags.append("多元分布")
    if len(artist_counts) > 10 and top10_credit_share >= 0.55:
        tags.append("核心歌手突出")
    if low_popularity_ratio >= 0.3 and popularity_coverage >= 0.65:
        tags.append("低热度长尾")
    if collaboration_ratio >= 0.2:
        tags.append("合作歌曲活跃")
    if long_song_ratio >= 0.25:
        tags.append("长篇偏好")
    if short_song_ratio >= 0.25:
        tags.append("短篇偏好")
    if album_diversity >= 0.75:
        tags.append("专辑分布广泛")

    if artist_entropy >= 0.7 and low_popularity_ratio >= 0.3:
        primary = "长尾探索型"
        description = "收藏覆盖大量不同歌手，同时保留了较多低热度作品。"
    elif len(artist_counts) > 10 and top10_credit_share >= 0.55:
        primary = "核心歌手收藏型"
        description = "收藏明显围绕少数高频歌手展开。"
    elif collaboration_ratio >= 0.2:
        primary = "合作偏好型"
        description = "多人合作作品在收藏中占有明显比例。"
    elif long_song_ratio >= 0.25:
        primary = "长篇聆听型"
        description = "长篇作品在收藏中占有较高比例。"
    else:
        primary = "均衡收藏型"
        description = "收藏在歌手、时长和热度之间较为均衡。"

    secondary_tags = [tag for tag in tags if tag not in primary][:3]
    insights: list[dict[str, Any]] = []
    if artist_entropy >= 0.68:
        insights.append(
            {
                "title": "歌手分布较广",
                "description": "收藏并未高度集中在少数歌手。",
                "evidence": f"归一化歌手熵 {artist_entropy:.2f}/1.00",
                "confidence": "高",
            }
        )
    elif len(artist_counts) > 10 and top10_credit_share >= 0.5:
        insights.append(
            {
                "title": "高频歌手非常突出",
                "description": "TOP 10 歌手贡献了较大比例的歌手署名。",
                "evidence": f"TOP 10 歌手贡献 {top10_credit_share:.1%}",
                "confidence": "高",
            }
        )

    if popularity_coverage >= 0.65 and low_popularity_ratio >= 0.3:
        insights.append(
            {
                "title": "低热度作品占比不低",
                "description": "收藏并不完全集中于高热度歌曲。",
                "evidence": (
                    f"热度低于 {LOW_POPULARITY_THRESHOLD} 的作品占 "
                    f"{low_popularity_ratio:.1%}"
                ),
                "confidence": _confidence(popularity_coverage),
            }
        )

    if durations and long_song_ratio >= 0.2:
        insights.append(
            {
                "title": "长篇作品占有一定比例",
                "description": "收藏中存在不少五分钟以上的作品。",
                "evidence": f"五分钟以上作品占 {long_song_ratio:.1%}",
                "confidence": _confidence(len(durations) / song_count),
            }
        )

    if top_pair and top_pair[1] >= 2:
        insights.append(
            {
                "title": "重复出现的合作组合",
                "description": f"{top_pair[0][0]} 与 {top_pair[0][1]} 多次共同出现。",
                "evidence": f"共同出现在 {top_pair[1]} 首歌曲中",
                "confidence": "高",
            }
        )

    radar = [
        {"label": "歌手多样性", "value": round(artist_entropy * 100, 1)},
        {
            "label": "低热度探索",
            "value": round(low_popularity_ratio * 100, 1),
        },
        {"label": "长篇偏好", "value": round(long_song_ratio * 100, 1)},
        {
            "label": "合作活跃度",
            "value": round(collaboration_ratio * 100, 1),
        },
        {
            "label": "专辑广度",
            "value": round(min(1.0, album_diversity) * 100, 1),
        },
    ]

    return {
        "version": PROFILE_VERSION,
        "primaryType": primary,
        "secondaryTags": secondary_tags,
        "description": description,
        "metrics": metrics,
        "radar": radar,
        "insights": insights,
        "dataQuality": {
            "popularityCoverage": round(popularity_coverage, 4),
            "durationCoverage": round(len(durations) / song_count, 4),
            "confidence": _confidence(
                min(
                    popularity_coverage,
                    len(durations) / song_count if song_count else 0,
                )
            ),
        },
        "disclaimer": (
            "画像反映当前公开歌单的收藏结构，不等同于完整收听历史或心理特征。"
        ),
    }
