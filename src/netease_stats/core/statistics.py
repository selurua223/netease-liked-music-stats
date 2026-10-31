"""Deterministic statistics over normalized playlist rows."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any

from .normalizer import format_duration


def _duration_bucket(milliseconds: int) -> str:
    if milliseconds < 2 * 60_000:
        return "少于 2 分钟"
    if milliseconds < 3 * 60_000:
        return "2–3 分钟"
    if milliseconds < 4 * 60_000:
        return "3–4 分钟"
    if milliseconds < 5 * 60_000:
        return "4–5 分钟"
    return "5 分钟以上"


def _popularity_bucket(score: float) -> str:
    if score < 20:
        return "0–19"
    if score < 40:
        return "20–39"
    if score < 60:
        return "40–59"
    if score < 80:
        return "60–79"
    return "80–100"


def build_summary(
    playlist: dict[str, Any],
    rows: list[dict[str, Any]],
    missing_ids: list[int],
    playlist_id: int,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("A report requires at least one normalized song")

    artist_counts: Counter[str] = Counter()
    title_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    duration_buckets: Counter[str] = Counter()
    popularity_buckets: Counter[str] = Counter()
    durations: list[int] = []
    popularity_values: list[float] = []

    for row in rows:
        artist_counts.update(row["artists"])
        title_groups[row["title"]].append(row)
        if row["durationMs"] > 0:
            durations.append(row["durationMs"])
            duration_buckets[_duration_bucket(row["durationMs"])] += 1
        if row["popularity"] is not None:
            popularity_values.append(row["popularity"])
            popularity_buckets[_popularity_bucket(row["popularity"])] += 1

    if not durations:
        raise ValueError("No positive song durations were available")

    duplicate_groups = [
        {"title": title, "count": len(group), "songs": group}
        for title, group in title_groups.items()
        if len(group) >= 2
    ]
    duplicate_groups.sort(key=lambda item: (-item["count"], item["title"].casefold()))

    max_duration = max(durations)
    min_duration = min(durations)
    longest = [row for row in rows if row["durationMs"] == max_duration]
    shortest = [row for row in rows if row["durationMs"] == min_duration]
    hottest: list[dict[str, Any]] = []
    coldest: list[dict[str, Any]] = []
    if popularity_values:
        max_popularity = max(popularity_values)
        min_popularity = min(popularity_values)
        hottest = [
            row for row in rows if row["popularity"] == max_popularity
        ]
        coldest = [
            row for row in rows if row["popularity"] == min_popularity
        ]

    top_artists = artist_counts.most_common(10)
    top_names = {name for name, _ in top_artists}
    top_artist_song_ids = {
        row["id"] for row in rows if top_names.intersection(row["artists"])
    }
    average_duration = round(statistics.mean(durations))
    total_duration = sum(durations)
    average_popularity = (
        round(statistics.mean(popularity_values), 2)
        if popularity_values
        else None
    )

    return {
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
            "averageDurationMs": average_duration,
            "averageDuration": format_duration(average_duration),
            "totalDurationMs": total_duration,
            "totalDuration": format_duration(total_duration),
            "duplicateTitleGroups": len(duplicate_groups),
            "songsInDuplicateTitleGroups": sum(
                item["count"] for item in duplicate_groups
            ),
            "popularityCoverage": len(popularity_values),
            "averagePopularity": average_popularity,
            "topArtistCoverage": (
                round(len(top_artist_song_ids) / len(rows) * 100, 1)
                if rows
                else 0
            ),
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
        "distributions": {
            "duration": [
                {"label": label, "count": duration_buckets[label]}
                for label in ("少于 2 分钟", "2–3 分钟", "3–4 分钟", "4–5 分钟", "5 分钟以上")
            ],
            "popularity": [
                {"label": label, "count": popularity_buckets[label]}
                for label in ("0–19", "20–39", "40–59", "60–79", "80–100")
            ],
        },
    }
