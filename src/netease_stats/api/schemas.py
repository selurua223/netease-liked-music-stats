"""Validated API request and response structures."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator


PLAYLIST_ID_PATTERN = re.compile(r"(?<!\d)(\d{5,20})(?!\d)")


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
        match = PLAYLIST_ID_PATTERN.search(compact)
        if not match:
            raise ValueError("Please provide a public playlist URL or numeric playlist ID")
        return match.group(1)

    @property
    def playlist_id(self) -> int:
        return int(self.playlist)
