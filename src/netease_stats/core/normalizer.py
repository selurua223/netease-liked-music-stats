"""Normalize provider-specific song fields into stable report rows."""

from __future__ import annotations

import unicodedata
from typing import Any


def artist_names(song: dict[str, Any]) -> list[str]:
    artists = song.get("artists") or song.get("ar") or []
    result: list[str] = []
    seen: set[str] = set()
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
