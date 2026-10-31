"""Evidence-backed Music DNA metrics and deterministic profile labels."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any


PROFILE_VERSION = "1.1"
LOW_POPULARITY_THRESHOLD = 40
HIGH_POPULARITY_THRESHOLD = 80
SAMPLE_LIMITS = (
    (10, "不充分", "基础统计"),
    (30, "有限", "初步发现"),
    (100, "中等", "一般画像"),
    (math.inf, "充分", "完整画像"),
)


def _normalized_entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 0 or len(counts) <= 1:
        return 0.0
    probabilities = [count / total for count in counts if count > 0]
    entropy = -sum(value * math.log(value) for value in probabilities)
    return entropy / math.log(len(probabilities))


def _sample_sufficiency(count: int) -> dict[str, Any]:
    for upper, level, label in SAMPLE_LIMITS:
        if count < upper:
            return {
                "level": level,
                "label": label,
                "sampleSize": count,
                "guidance": (
                    "样本量不足以支撑强画像结论，仅供基础参考。"
                    if count < 10
                    else "画像已生成，但受到样本规模限制。"
                    if count < 100
                    else "样本量足以生成相对稳定的结构画像。"
                ),
            }
    raise AssertionError("unreachable")


def _coverage_level(value: float) -> str:
    if value >= 0.95:
        return "高"
    if value >= 0.75:
        return "中"
    return "低"


def _reliability(coverage: float, sample_size: int, *, strong_required: int = 30) -> str:
    if sample_size < 10:
        return "低"
    if sample_size < strong_required:
        return "中" if coverage >= 0.65 else "低"
    if coverage >= 0.9:
        return "高"
    if coverage >= 0.65:
        return "中"
    return "低"


def _album_key(row: dict[str, Any]) -> str:
    album_identifier = str(row.get("albumId") or "").strip()
    if album_identifier:
        return f"id:{album_identifier}"
    album = str(row.get("album") or "").strip()
    return f"name:{album.casefold()}" if album else ""


def _metric_definition(
    label: str,
    value: float,
    unit: str,
    formula: str,
    numerator: int | float,
    denominator: int | float,
    sample_size: int,
    missing_count: int,
    note: str,
) -> dict[str, Any]:
    return {
        "label": label,
        "value": round(value, 4),
        "displayValue": (
            f"{value * 100:.1f}%"
            if unit == "ratio"
            else f"{value * 100:.1f} / 100"
        ),
        "unit": unit,
        "formula": formula,
        "fractionLabel": (
            "分子 / 分母" if unit == "ratio" else "有效样本 / 类别数"
        ),
        "numerator": numerator,
        "denominator": denominator,
        "sampleSize": sample_size,
        "missingCount": missing_count,
        "note": note,
    }


def build_profile(
    rows: list[dict[str, Any]],
    *,
    expected_song_count: int | None = None,
    missing_song_count: int = 0,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("Music profile requires at least one song")

    song_count = len(rows)
    expected_count = max(song_count, expected_song_count or song_count)
    artist_counts: Counter[str] = Counter()
    title_groups: dict[str, int] = defaultdict(int)
    album_counts: Counter[str] = Counter()
    pair_song_ids: dict[tuple[str, str], list[int]] = defaultdict(list)
    durations: list[int] = []
    popularity_values: list[float] = []
    collaboration_songs = 0
    valid_artist_rows = 0
    long_songs = 0
    short_songs = 0
    low_popularity_song_ids: list[int] = []
    long_song_ids: list[int] = []

    for row in rows:
        artists = list(dict.fromkeys(row["artists"]))
        valid_artists = [artist for artist in artists if artist != "(未知歌手)"]
        if valid_artists:
            valid_artist_rows += 1
        counted_artists = valid_artists or ["(未知歌手)"]
        artist_counts.update(counted_artists)
        title_groups[row["title"]] += 1
        album_key = _album_key(row)
        if album_key:
            album_counts[album_key] += 1
        if len(valid_artists) > 1:
            collaboration_songs += 1
            for pair in combinations(sorted(valid_artists), 2):
                pair_song_ids[pair].append(int(row["id"]))
        duration = int(row.get("durationMs") or 0)
        if duration > 0:
            durations.append(duration)
            if duration >= 5 * 60_000:
                long_songs += 1
                long_song_ids.append(int(row["id"]))
            if duration < 2 * 60_000:
                short_songs += 1
        popularity = row.get("popularity")
        if isinstance(popularity, (int, float)) and 0 <= popularity <= 100:
            popularity_values.append(float(popularity))
            if popularity < LOW_POPULARITY_THRESHOLD:
                low_popularity_song_ids.append(int(row["id"]))

    total_artist_credits = sum(artist_counts.values())
    artist_credit_share = [
        count / total_artist_credits for count in artist_counts.values()
    ]
    artist_entropy = _normalized_entropy(list(artist_counts.values()))
    artist_hhi = sum(share * share for share in artist_credit_share)
    top10_credit_count = sum(count for _, count in artist_counts.most_common(10))
    top10_credit_share = (
        top10_credit_count / total_artist_credits
        if total_artist_credits
        else 0.0
    )

    low_popularity_count = len(low_popularity_song_ids)
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
    duration_coverage = len(durations) / song_count
    long_song_ratio = long_songs / len(durations) if durations else 0.0
    short_song_ratio = short_songs / len(durations) if durations else 0.0
    collaboration_ratio = collaboration_songs / song_count
    album_coverage = sum(bool(_album_key(row)) for row in rows) / song_count
    distinct_album_count = len(album_counts)
    album_breadth = distinct_album_count / song_count
    album_entropy = _normalized_entropy(list(album_counts.values()))
    duplicate_groups = sum(count >= 2 for count in title_groups.values())
    retrieval_coverage = song_count / expected_count if expected_count else 1.0
    completeness = min(
        retrieval_coverage,
        popularity_coverage,
        duration_coverage,
        album_coverage,
    )
    sample_sufficiency = _sample_sufficiency(song_count)
    overall_reliability = _reliability(completeness, song_count)

    top_pair = pair_song_ids and max(
        pair_song_ids.items(),
        key=lambda item: len(item[1]),
    )
    metrics = {
        "artistCount": len(artist_counts),
        "artistCreditCount": total_artist_credits,
        "artistNormalizedEntropy": round(artist_entropy, 4),
        "artistHhi": round(artist_hhi, 5),
        "top10ArtistCreditShare": round(top10_credit_share, 4),
        "lowPopularityThreshold": LOW_POPULARITY_THRESHOLD,
        "highPopularityThreshold": HIGH_POPULARITY_THRESHOLD,
        "lowPopularityRatio": round(low_popularity_ratio, 4),
        "highPopularityRatio": round(high_popularity_ratio, 4),
        "popularityCoverage": round(popularity_coverage, 4),
        "collaborationRatio": round(collaboration_ratio, 4),
        "validAlbumCount": distinct_album_count,
        "albumCoverage": round(album_coverage, 4),
        "albumBreadth": round(album_breadth, 4),
        "albumDiversity": round(album_entropy, 4),
        "averageDurationMs": average_duration,
        "medianDurationMs": duration_median,
        "durationCoverage": round(duration_coverage, 4),
        "longSongRatio": round(long_song_ratio, 4),
        "shortSongRatio": round(short_song_ratio, 4),
        "duplicateTitleGroups": duplicate_groups,
        "topCollaborationPair": (
            {
                "artists": list(top_pair[0]),
                "songCount": len(top_pair[1]),
                "songIds": top_pair[1][:50],
            }
            if top_pair
            else None
        ),
        "sampleSizes": {
            "songsTotal": song_count,
            "songsExpected": expected_count,
            "songsMissing": missing_song_count,
            "artistsValid": len(artist_counts),
            "artistRowsValid": valid_artist_rows,
            "artistCredits": total_artist_credits,
            "popularityValid": len(popularity_values),
            "durationValid": len(durations),
            "albumValid": sum(bool(_album_key(row)) for row in rows),
        },
    }

    tags: list[str] = []
    if song_count >= 10 and artist_entropy >= 0.72:
        tags.append("多元歌手收藏")
    if len(artist_counts) > 10 and top10_credit_share >= 0.55:
        tags.append("核心歌手集中")
    if len(popularity_values) >= 10 and low_popularity_ratio >= 0.3:
        tags.append("低热度作品收藏")
    if collaboration_ratio >= 0.2:
        tags.append("合作作品偏好")
    if len(durations) >= 10 and long_song_ratio >= 0.25:
        tags.append("长篇作品收藏")
    if len(durations) >= 10 and short_song_ratio >= 0.25:
        tags.append("短篇作品收藏")
    if album_coverage >= 0.8 and album_entropy >= 0.75:
        tags.append("专辑分布广泛")

    if song_count < 10:
        primary = "基础统计型"
        description = "当前样本较少，仅展示收藏结构的基础统计。"
        secondary_tags = []
    elif artist_entropy >= 0.7 and low_popularity_ratio >= 0.3:
        primary = "低热度作品收藏型"
        description = "收藏覆盖较多不同歌手，同时低热度作品占有一定比例。"
        secondary_tags = ["多元歌手收藏", "低热度作品收藏"]
    elif len(artist_counts) > 10 and top10_credit_share >= 0.55:
        primary = "核心歌手集中型"
        description = "收藏明显围绕少数高频歌手展开。"
        secondary_tags = ["核心歌手集中"]
    elif collaboration_ratio >= 0.2:
        primary = "合作作品偏好型"
        description = "多人合作作品在收藏中占有明显比例。"
        secondary_tags = ["合作作品偏好"]
    elif len(durations) >= 10 and long_song_ratio >= 0.25:
        primary = "长篇作品收藏型"
        description = "长篇作品在收藏中占有较高比例。"
        secondary_tags = ["长篇作品收藏"]
    else:
        primary = "收藏结构均衡型"
        description = "收藏在歌手、时长和热度之间较为均衡。"
        secondary_tags = [tag for tag in tags if tag != primary][:3]

    insights: list[dict[str, Any]] = []
    if song_count >= 30 and artist_entropy >= 0.68:
        insights.append(
            {
                "title": "歌手署名分布较广",
                "description": "收藏并未高度集中在少数歌手。",
                "evidence": (
                    f"归一化歌手熵 {artist_entropy:.2f}；"
                    f"分母为 {total_artist_credits} 次歌手署名"
                ),
                "confidence": _reliability(
                    valid_artist_rows / song_count,
                    song_count,
                ),
                "reliability": _reliability(
                    valid_artist_rows / song_count,
                    song_count,
                ),
                "sampleSize": song_count,
                "songIds": [],
            }
        )
    if len(popularity_values) >= 10 and low_popularity_ratio >= 0.3:
        insights.append(
            {
                "title": "低热度作品占比较高",
                "description": "收藏并不完全集中于高热度歌曲。",
                "evidence": (
                    f"{low_popularity_count}/{len(popularity_values)} 首有效热度歌曲"
                    f"低于 {LOW_POPULARITY_THRESHOLD}，"
                    f"占 {low_popularity_ratio:.1%}"
                ),
                "confidence": _reliability(
                    popularity_coverage,
                    len(popularity_values),
                ),
                "reliability": _reliability(
                    popularity_coverage,
                    len(popularity_values),
                ),
                "sampleSize": len(popularity_values),
                "songIds": low_popularity_song_ids[:50],
            }
        )
    if len(durations) >= 10 and long_song_ratio >= 0.2:
        insights.append(
            {
                "title": "长篇作品占有一定比例",
                "description": "收藏中存在较多五分钟以上的作品。",
                "evidence": (
                    f"{long_songs}/{len(durations)} 首有效时长歌曲超过五分钟，"
                    f"占 {long_song_ratio:.1%}"
                ),
                "confidence": _reliability(duration_coverage, len(durations)),
                "reliability": _reliability(duration_coverage, len(durations)),
                "sampleSize": len(durations),
                "songIds": long_song_ids[:50],
            }
        )
    if song_count >= 10 and top_pair and len(top_pair[1]) >= 2:
        pair_reliability = _reliability(
            valid_artist_rows / song_count,
            song_count,
        )
        insights.append(
            {
                "title": "重复出现的合作组合",
                "description": f"{top_pair[0][0]} 与 {top_pair[0][1]} 多次共同出现。",
                "evidence": (
                    f"在 {len(top_pair[1])} 首歌曲中共同出现；"
                    f"当前歌单共 {song_count} 首"
                ),
                "confidence": pair_reliability,
                "reliability": pair_reliability,
                "sampleSize": song_count,
                "songIds": top_pair[1][:50],
            }
        )

    metric_definitions = {
        "artistDiversity": _metric_definition(
            "歌手多样性",
            artist_entropy,
            "score",
            "H = -Σ pᵢ ln(pᵢ) / ln(n)",
            total_artist_credits,
            len(artist_counts),
            song_count,
            sum("(未知歌手)" in row["artists"] for row in rows),
            "pᵢ 为每位歌手占全部歌手署名次数的比例；合作歌曲按每位歌手分别计数。",
        ),
        "top10Share": _metric_definition(
            "TOP 10 歌手贡献",
            top10_credit_share,
            "ratio",
            "TOP 10 歌手署名次数 / 全部歌手署名次数",
            top10_credit_count,
            total_artist_credits,
            song_count,
            0,
            "不是互斥歌曲占比；合作歌曲会为多位歌手增加署名次数。",
        ),
        "lowPopularityShare": _metric_definition(
            "低热度作品",
            low_popularity_ratio,
            "ratio",
            f"热度 < {LOW_POPULARITY_THRESHOLD} 的有效歌曲 / 有效热度歌曲",
            low_popularity_count,
            len(popularity_values),
            len(popularity_values),
            song_count - len(popularity_values),
            "热度是本项目采用的平台分值分层，不代表播放次数或官方分类。",
        ),
        "collaborationShare": _metric_definition(
            "合作歌曲",
            collaboration_ratio,
            "ratio",
            "至少有两位有效署名歌手的歌曲 / 全部歌曲",
            collaboration_songs,
            song_count,
            song_count,
            0,
            "名称为空的歌手记录会被忽略；只有完全没有有效歌手时才标记未知。",
        ),
        "longSongShare": _metric_definition(
            "长篇作品",
            long_song_ratio,
            "ratio",
            "时长 ≥ 5 分钟的有效歌曲 / 有效时长歌曲",
            long_songs,
            len(durations),
            len(durations),
            song_count - len(durations),
            "只描述收藏中的作品长度结构，不推断聆听场景。",
        ),
        "albumDiversity": _metric_definition(
            "专辑多样性",
            album_entropy,
            "score",
            "H = -Σ pᵢ ln(pᵢ) / ln(n)",
            sum(album_counts.values()),
            len(album_counts),
            sum(album_counts.values()),
            song_count - sum(album_counts.values()),
            "优先使用专辑 ID 去重；缺失 ID 时回退到专辑名称。",
        ),
    }

    radar = [
        {
            "key": key,
            "label": definition["label"],
            "value": round(definition["value"] * 100, 1),
        }
        for key, definition in metric_definitions.items()
    ]

    return {
        "version": PROFILE_VERSION,
        "primaryType": primary,
        "secondaryTags": secondary_tags[:3],
        "description": description,
        "metrics": metrics,
        "metricDefinitions": metric_definitions,
        "radar": radar,
        "insights": insights,
        "dataQuality": {
            "retrievalCoverage": round(retrieval_coverage, 4),
            "fieldCompleteness": round(completeness, 4),
            "completenessLevel": _coverage_level(completeness),
            "sampleSufficiency": sample_sufficiency,
            "conclusionReliability": overall_reliability,
            "summary": (
                f"当前返回 {song_count}/{expected_count} 首歌曲；"
                f"热度有效 {len(popularity_values)} 首，"
                f"时长有效 {len(durations)} 首。"
            ),
        },
        "disclaimer": (
            "画像反映当前公开歌单的收藏结构，不等同于完整收听历史、"
            "用户主动探索行为或心理特征。"
        ),
    }
