"""Validated API request and response structures."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, Field, field_validator


PLAYLIST_ID_PATTERN = re.compile(r"(?<!\d)(\d{5,20})(?!\d)")
PLAYLIST_ID_KEYS = ("id", "playlistId", "playlist_id")


def _query_parameters(value: str) -> dict[str, list[str]]:
    """Read query parameters from both `?id=` and `#/playlist?id=` link shapes."""

    parts = urlsplit(value)
    parameters: dict[str, list[str]] = {}
    if parts.query:
        parameters.update(parse_qs(parts.query))
    if "?" in parts.fragment:
        parameters.update(parse_qs(parts.fragment.split("?", 1)[1]))
    return parameters


def _playlist_id_parameter(value: str) -> str | None:
    """Prefer the `id` parameter; share links also carry a creatorId/userid."""

    parameters = _query_parameters(value)
    for key in PLAYLIST_ID_KEYS:
        for candidate in parameters.get(key, []):
            candidate = candidate.strip()
            if candidate.isdigit() and 5 <= len(candidate) <= 20:
                return candidate
    return None


class AnalyzeRequest(BaseModel):
    playlist: str = Field(min_length=1, max_length=2048)
    include_raw_data: bool = True
    generate_csv: bool = True

    @field_validator("playlist")
    @classmethod
    def validate_playlist_reference(cls, value: str) -> str:
        compact = value.strip()
        if compact.isdigit():
            return compact
        # A share link may put creatorId/userid before id, so read `id` instead of
        # taking the first long number in the string.
        from_parameter = _playlist_id_parameter(compact)
        if from_parameter:
            return from_parameter
        match = PLAYLIST_ID_PATTERN.search(compact)
        if not match:
            raise ValueError("Please provide a public playlist URL or numeric playlist ID")
        return match.group(1)

    @property
    def playlist_id(self) -> int:
        return int(self.playlist)
