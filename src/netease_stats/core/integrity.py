"""Completeness checks used before a report is published."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class IntegrityResult:
    status: str
    declared_count: int
    requested_count: int
    returned_count: int
    missing_count: int
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_coverage(
    playlist: dict[str, Any],
    track_ids: list[int],
    returned_songs: dict[int, dict[str, Any]],
    missing_ids: list[int],
) -> IntegrityResult:
    warnings: list[str] = []
    declared = int(playlist.get("trackCount") or 0)
    if declared and declared != len(track_ids):
        warnings.append(
            f"Playlist declares {declared} tracks but exposes {len(track_ids)} unique IDs"
        )
    if missing_ids:
        warnings.append(f"{len(missing_ids)} requested songs were not returned")
    expected = {int(song_id) for song_id in track_ids}
    unexpected = sorted(set(returned_songs) - expected)
    if unexpected:
        warnings.append(f"Provider returned {len(unexpected)} unrequested song IDs")

    complete = not missing_ids and not unexpected
    return IntegrityResult(
        status="complete" if complete else "partial",
        declared_count=declared,
        requested_count=len(track_ids),
        returned_count=len(returned_songs),
        missing_count=len(missing_ids),
        warnings=warnings,
    )
