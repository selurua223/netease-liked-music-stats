from __future__ import annotations

import json
from pathlib import Path

from netease_stats.core.integrity import validate_coverage
from netease_stats.core.normalizer import artist_names, popularity, song_row
from netease_stats.core.profile import build_profile
from netease_stats.core.reporting import write_report
from netease_stats.core.statistics import build_summary


def raw_song(
    song_id: int,
    name: str,
    artists: list[str],
    duration: int,
    popularity: int,
    album: str = "Test Album",
    album_id: int | None = None,
):
    return {
        "id": song_id,
        "name": name,
        "artists": [{"name": artist} for artist in artists],
        "album": {
            "name": album,
            **({"id": album_id} if album_id is not None else {}),
        },
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


def test_normalizer_ignores_invalid_artists_and_out_of_range_popularity():
    row = song_row(
        {
            "id": 2,
            "name": "Data",
            "artists": [{"name": "Artist A"}, {}, {"name": ""}],
            "album": {"id": 99, "name": "Album"},
            "duration": 0,
            "popularity": 101,
            "score": 55,
        }
    )
    assert row["artists"] == ["Artist A"]
    assert row["albumId"] == "99"
    assert row["popularity"] == 55
    assert artist_names({"artists": [{}, {"name": ""}]}) == ["(未知歌手)"]
    assert popularity({"popularity": -1, "score": 101, "pop": "bad"}) is None


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
    assert result.unexpected_count == 0


def test_integrity_warns_when_declared_count_differs():
    result = validate_coverage(
        {"trackCount": 3},
        [1, 2],
        {
            1: raw_song(1, "One", ["A"], 100000, 10),
            2: raw_song(2, "Two", ["A"], 100000, 20),
        },
        [],
    )
    assert result.status == "warning"
    assert result.declared_count == 3
    assert result.requested_count == 2


def test_statistics_tolerate_missing_duration_and_popularity():
    rows = [
        song_row(raw_song(1, "One", ["A"], 0, 0)),
        song_row(raw_song(2, "Two", ["B"], 0, 0)),
    ]
    rows[0]["popularity"] = None
    rows[1]["popularity"] = None
    summary = build_summary({"name": "Missing fields", "trackCount": 2}, rows, [], 1)
    assert summary["overview"]["averageDuration"] == "—"
    assert summary["overview"]["totalDuration"] == "—"
    assert summary["extremes"]["longest"] == []
    assert summary["extremes"]["shortest"] == []
    assert summary["extremes"]["hottest"] == []


def test_music_profile_uses_evidence_backed_metrics():
    rows = [
        song_row(raw_song(1, "Same", ["A", "B"], 100000, 20)),
        song_row(raw_song(2, "Same", ["A"], 320000, 90)),
        song_row(raw_song(3, "Other", ["C", "D"], 360000, 35)),
        song_row(raw_song(4, "Long", ["E"], 400000, 75)),
        song_row(raw_song(5, "Wide", ["F", "G"], 250000, 55)),
    ]
    profile = build_profile(rows)

    assert profile["version"] == "1.1"
    assert 0 < profile["metrics"]["artistNormalizedEntropy"] < 1
    assert 0 < profile["metrics"]["artistHhi"] < 1
    assert profile["metrics"]["lowPopularityRatio"] == 0.4
    assert profile["metrics"]["collaborationRatio"] == 0.6
    assert profile["radar"]
    assert profile["insights"] == []
    assert profile["dataQuality"]["sampleSufficiency"]["level"] == "不充分"
    assert profile["dataQuality"]["conclusionReliability"] == "低"


def test_profile_handles_album_ids_and_all_cooperation():
    rows = [
        song_row(raw_song(1, "A", ["A", "B"], 310000, 20, "Same", 1)),
        song_row(raw_song(2, "B", ["B", "C"], 320000, 20, "Same", 2)),
    ]
    profile = build_profile(rows)
    assert profile["metrics"]["validAlbumCount"] == 2
    assert profile["metrics"]["collaborationRatio"] == 1.0
    assert profile["dataQuality"]["conclusionReliability"] == "低"


def test_profile_handles_single_artist_and_all_optional_fields_missing():
    rows = []
    for index in range(12):
        row = song_row(
            raw_song(
                index + 1,
                f"Song {index + 1}",
                ["Only Artist"],
                0,
                0,
                "",
            )
        )
        row["popularity"] = None
        rows.append(row)
    profile = build_profile(rows)
    assert profile["metrics"]["artistCount"] == 1
    assert profile["metrics"]["artistNormalizedEntropy"] == 0
    assert profile["metrics"]["collaborationRatio"] == 0
    assert profile["metrics"]["popularityCoverage"] == 0
    assert profile["metrics"]["durationCoverage"] == 0
    assert profile["dataQuality"]["fieldCompleteness"] == 0
    assert profile["insights"] == []


def test_raw_report_contains_original_song_details(tmp_path: Path):
    raw_songs = [
        raw_song(1, "One", ["A"], 100000, 80),
        raw_song(2, "Two", ["B"], 120000, 60),
    ]
    rows = [song_row(song) for song in raw_songs]
    playlist = {"id": 7, "name": "Demo", "trackCount": 2}
    summary = build_summary(playlist, rows, [], 7)
    summary["profile"] = build_profile(rows)
    write_report(
        tmp_path,
        summary,
        rows,
        playlist,
        [1, 2],
        [],
        raw_songs,
        {"reportId": "aaaaaaaaaaaa"},
    )
    raw = json.loads((tmp_path / "raw_data.json").read_text(encoding="utf-8"))
    assert raw["songs"][0]["album"]["name"] == "Test Album"
    assert raw["songs"][0]["name"] == "One"


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
                "profile": {"version": "1.0", "primaryType": "旧画像"},
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
    upgraded = repository.load_summary("aaaaaaaaaaaa")
    assert upgraded["profile"]["version"] == "1.1"
    assert upgraded["profile"]["primaryType"] != "旧画像"
    comparison = repository.compare("bbbbbbbbbbbb", "aaaaaaaaaaaa")
    assert comparison["addedSongCount"] == 1
    assert comparison["removedSongCount"] == 1
    assert comparison["addedArtistCount"] == 1
    assert comparison["removedArtistCount"] == 1
