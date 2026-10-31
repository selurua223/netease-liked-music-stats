"""Normalize provider-specific song fields into stable report rows."""

from __future__ import annotations

import math
import unicodedata
from typing import Any


def artist_names(song: dict[str, Any]) -> list[str]:
    artists = song.get("artists") or song.get("ar") or []
    result: list[str] = []
    seen: set[str] = set()
    for artist in artists:
        if not isinstance(artist, dict):
            continue
        name = str(artist.get("name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result or ["(未知歌手)"]


def duration_ms(song: dict[str, Any]) -> int:
    return int(song.get("duration", song.get("dt")) or 0)


def popularity(song: dict[str, Any]) -> float | None:
    for key in ("popularity", "score", "pop"):
        value = song.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric) and 0 <= numeric <= 100:
            return numeric
    return None


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


def album_id(song: dict[str, Any]) -> str:
    album = song.get("album") or song.get("al") or {}
    if not isinstance(album, dict) or album.get("id") is None:
        return ""
    return str(album["id"]).strip()


def song_row(song: dict[str, Any]) -> dict[str, Any]:
    duration = duration_ms(song)
    heat = popularity(song)
    return {
        "id": int(song["id"]),
        "title": normalize_title(song.get("name")),
        "artists": artist_names(song),
        "album": album_name(song),
        "albumId": album_id(song),
        "durationMs": duration,
        "duration": format_duration(duration),
        "popularity": heat,
    }
