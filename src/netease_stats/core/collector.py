"""Read-only client for public NetEase Cloud Music playlist endpoints."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


PLAYLIST_ENDPOINT = "https://music.163.com/api/v6/playlist/detail"
SONG_ENDPOINT = "https://music.163.com/api/song/detail"
USER_AGENT = "Mozilla/5.0"
REFERER = "https://music.163.com/"
MAX_BATCH_SIZE = 200


class ProviderError(RuntimeError):
    """Raised when the upstream provider cannot return usable data."""


@dataclass(frozen=True)
class BatchProgress:
    batch: int
    total_batches: int
    requested: int
    returned: int
    cumulative: int
    missing: int


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
        except Exception as error:  # Network and JSON failures share retry handling.
            last_error = error
            if attempt < 3:
                time.sleep(0.75 * (attempt + 1))
    raise ProviderError(f"Request failed after four attempts: {url}") from last_error


def fetch_playlist(playlist_id: int, timeout: float = 30) -> dict[str, Any]:
    query = urllib.parse.urlencode({"id": playlist_id})
    data = request_json(f"{PLAYLIST_ENDPOINT}?{query}", timeout)
    if data.get("code") != 200 or not isinstance(data.get("playlist"), dict):
        raise ProviderError(f"Playlist request failed: {data.get('code')}")
    return data["playlist"]


def unique_track_ids(playlist: dict[str, Any]) -> list[int]:
    raw_ids = playlist.get("trackIds")
    if not isinstance(raw_ids, list):
        raise ProviderError("Playlist response does not contain trackIds")

    track_ids: list[int] = []
    seen: set[int] = set()
    for item in raw_ids:
        song_id = int(item["id"] if isinstance(item, dict) else item)
        if song_id not in seen:
            seen.add(song_id)
            track_ids.append(song_id)
    return track_ids


def fetch_songs(
    track_ids: list[int],
    batch_size: int = MAX_BATCH_SIZE,
    timeout: float = 30,
    progress: Callable[[BatchProgress], None] | None = None,
) -> tuple[dict[int, dict[str, Any]], list[int]]:
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}")

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
            raise ProviderError(
                f"Song batch {batch_number} failed: {data.get('code')}"
            )

        returned = data.get("songs") or []
        returned_ids: set[int] = set()
        for song in returned:
            if not isinstance(song, dict) or song.get("id") is None:
                continue
            song_id = int(song["id"])
            returned_ids.add(song_id)
            songs[song_id] = song

        batch_missing = [song_id for song_id in batch if song_id not in returned_ids]
        missing.extend(batch_missing)
        if progress:
            progress(
                BatchProgress(
                    batch=batch_number,
                    total_batches=total_batches,
                    requested=len(batch),
                    returned=len(returned),
                    cumulative=len(songs),
                    missing=len(batch_missing),
                )
            )
    return songs, missing
