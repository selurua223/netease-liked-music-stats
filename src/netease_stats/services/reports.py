"""Read reports and exports from the local data directory."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from netease_stats.core.profile import build_profile


REPORT_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")
EXPORT_FILES = {
    "markdown": "report.md",
    "summary": "summary.json",
    "metadata": "metadata.json",
    "songs": "songs.csv",
    "artists": "artist_counts.csv",
    "duplicates": "duplicate_titles.csv",
    "extrema": "extrema.csv",
    "raw": "raw_data.json",
}


class ReportNotFoundError(FileNotFoundError):
    pass


class ReportRepository:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def report_dir(self, report_id: str) -> Path:
        if not REPORT_ID_PATTERN.fullmatch(report_id):
            raise ReportNotFoundError("Invalid report ID")
        path = (self.root / report_id).resolve()
        if path.parent != self.root:
            raise ReportNotFoundError("Report path escapes data directory")
        if not path.is_dir():
            raise ReportNotFoundError("Report not found")
        return path

    def list_reports(self) -> list[dict[str, Any]]:
        reports = []
        for metadata_path in self.root.glob("*/metadata.json"):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            reports.append(metadata)
        reports.sort(key=lambda item: item.get("generatedAt", ""), reverse=True)
        return reports

    def load_summary(self, report_id: str) -> dict[str, Any]:
        path = self.report_dir(report_id) / "summary.json"
        if not path.is_file():
            raise ReportNotFoundError("Summary not found")
        summary = json.loads(path.read_text(encoding="utf-8"))
        if "profile" not in summary:
            songs_path = path.with_name("songs.json")
            if songs_path.is_file():
                summary["profile"] = build_profile(
                    json.loads(songs_path.read_text(encoding="utf-8"))
                )
        return summary

    def load_songs(self, report_id: str) -> list[dict[str, Any]]:
        path = self.report_dir(report_id) / "songs.json"
        if not path.is_file():
            raise ReportNotFoundError("Song data not found")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ReportNotFoundError("Invalid song data")
        return data

    def export_path(self, report_id: str, kind: str) -> tuple[Path, str]:
        filename = EXPORT_FILES.get(kind)
        if filename is None:
            raise ReportNotFoundError("Unsupported export type")
        path = self.report_dir(report_id) / filename
        if not path.is_file():
            raise ReportNotFoundError("Requested export is unavailable")
        media_types = {
            ".md": "text/markdown; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".csv": "text/csv; charset=utf-8",
        }
        return path, media_types.get(path.suffix, "application/octet-stream")

    def compare(self, report_id: str, other_id: str) -> dict[str, Any]:
        current_summary = self.load_summary(report_id)
        other_summary = self.load_summary(other_id)
        current_songs = self.load_songs(report_id)
        other_songs = self.load_songs(other_id)
        current_ids = {row["id"] for row in current_songs}
        other_ids = {row["id"] for row in other_songs}
        current_artists = {
            item["artist"] for item in current_summary.get("artistCounts", [])
        }
        other_artists = {
            item["artist"] for item in other_summary.get("artistCounts", [])
        }
        added_ids = current_ids - other_ids
        removed_ids = other_ids - current_ids
        current_by_id = {row["id"]: row for row in current_songs}
        other_by_id = {row["id"]: row for row in other_songs}
        return {
            "base": self._report_label(other_summary),
            "target": self._report_label(current_summary),
            "addedSongCount": len(added_ids),
            "removedSongCount": len(removed_ids),
            "addedArtistCount": len(current_artists - other_artists),
            "removedArtistCount": len(other_artists - current_artists),
            "addedSongs": [
                self._song_label(current_by_id[song_id])
                for song_id in list(sorted(added_ids))[:20]
            ],
            "removedSongs": [
                self._song_label(other_by_id[song_id])
                for song_id in list(sorted(removed_ids))[:20]
            ],
        }

    @staticmethod
    def _report_label(summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": summary.get("playlist", {}).get("id"),
            "name": summary.get("playlist", {}).get("name"),
            "generatedAt": summary.get("metadata", {}).get("generatedAt"),
            "songCount": summary.get("overview", {}).get("fetchedSongCount"),
        }

    @staticmethod
    def _song_label(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "artists": row["artists"],
        }
