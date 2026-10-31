from __future__ import annotations

import json

from netease_stats.core.integrity import validate_coverage
from netease_stats.core.normalizer import song_row
from netease_stats.core.statistics import build_summary


def raw_song(
    song_id: int,
    name: str,
    artists: list[str],
    duration: int,
    popularity: int,
    album: str = "Test Album",
):
    return {
        "id": song_id,
        "name": name,
        "artists": [{"name": artist} for artist in artists],
        "album": {"name": album},
        "duration": duration,
        "popularity": popularity,
    }


def test_normalizer_uses_provider_fallback_fields():
    row = song_row(
        {
            "id": 1,
            "name": "  Song  ",
            "ar": [{"name": "Artist A"}, {"name": "Artist A"}],
            "al": {"name": "Album"},
            "dt": 185000,
            "pop": 85,
        }
    )
    assert row["title"] == "Song"
    assert row["artists"] == ["Artist A"]
    assert row["duration"] == "3:05"
    assert row["popularity"] == 85


def test_statistics_preserve_ties_and_collaboration_counts():
    rows = [
        song_row(raw_song(1, "Same", ["A", "B"], 100000, 80)),
        song_row(raw_song(2, "Same", ["A"], 300000, 100)),
        song_row(raw_song(3, "Other", ["B"], 200000, 20)),
        song_row(raw_song(4, "Long", ["C"], 600000, 100)),
    ]
    summary = build_summary({"name": "Demo", "trackCount": 4}, rows, [], 42)

    assert summary["overview"]["fetchedSongCount"] == 4
    assert summary["overview"]["uniqueArtists"] == 3
    assert summary["overview"]["artistCredits"] == 5
    assert summary["overview"]["duplicateTitleGroups"] == 1
    assert [item["artist"] for item in summary["artistCounts"][:2]] == ["A", "B"]
    assert summary["extremes"]["shortest"][0]["id"] == 1
    assert summary["extremes"]["longest"][0]["id"] == 4
    assert {item["id"] for item in summary["extremes"]["hottest"]} == {2, 4}
    assert summary["overview"]["topArtistCoverage"] == 100.0


def test_integrity_marks_partial_when_song_is_missing():
    playlist = {"trackCount": 3}
    track_ids = [1, 2, 3]
    songs = {
        1: raw_song(1, "One", ["A"], 100000, 10),
        2: raw_song(2, "Two", ["A"], 100000, 20),
    }
    result = validate_coverage(playlist, track_ids, songs, [3])
    assert result.status == "partial"
    assert result.declared_count == 3
    assert result.returned_count == 2
    assert result.missing_count == 1


def test_report_repository_compare(tmp_path):
    from netease_stats.services.reports import ReportRepository

    first = tmp_path / "web" / "aaaaaaaaaaaa"
    second = tmp_path / "web" / "bbbbbbbbbbbb"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    first.joinpath("summary.json").write_text(
        json.dumps(
            {
                "playlist": {"id": 1, "name": "Old"},
                "metadata": {"generatedAt": "2026-01-01"},
                "overview": {"fetchedSongCount": 2},
                "artistCounts": [{"artist": "A", "count": 2}],
            }
        ),
        encoding="utf-8",
    )
    second.joinpath("summary.json").write_text(
        json.dumps(
            {
                "playlist": {"id": 2, "name": "New"},
                "metadata": {"generatedAt": "2026-01-02"},
                "overview": {"fetchedSongCount": 2},
                "artistCounts": [{"artist": "B", "count": 2}],
            }
        ),
        encoding="utf-8",
    )
    first.joinpath("songs.json").write_text(
        json.dumps(
            [
                {"id": 1, "title": "Stay", "artists": ["A"]},
                {"id": 2, "title": "Old", "artists": ["A"]},
            ]
        ),
        encoding="utf-8",
    )
    second.joinpath("songs.json").write_text(
        json.dumps(
            [
                {"id": 1, "title": "Stay", "artists": ["A"]},
                {"id": 3, "title": "New", "artists": ["B"]},
            ]
        ),
        encoding="utf-8",
    )
    repository = ReportRepository(tmp_path / "web")
    comparison = repository.compare("bbbbbbbbbbbb", "aaaaaaaaaaaa")
    assert comparison["addedSongCount"] == 1
    assert comparison["removedSongCount"] == 1
    assert comparison["addedArtistCount"] == 1
    assert comparison["removedArtistCount"] == 1
