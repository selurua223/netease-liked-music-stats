from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from netease_stats.api.main import create_app
from netease_stats.core.normalizer import song_row
from netease_stats.core.reporting import write_report
from netease_stats.core.statistics import build_summary


def test_api_analysis_and_report_routes(tmp_path: Path):
    raw_songs = [
        {
            "id": 10,
            "name": "Same",
            "artists": [{"name": "Artist A"}, {"name": "Artist B"}],
            "album": {"name": "Album One"},
            "duration": 180000,
            "popularity": 90,
        },
        {
            "id": 11,
            "name": "Same",
            "artists": [{"name": "Artist B"}],
            "album": {"name": "Album Two"},
            "duration": 220000,
            "popularity": 80,
        },
        {
            "id": 12,
            "name": "Unique",
            "artists": [{"name": "Artist C"}],
            "album": {"name": "Album Three"},
            "duration": 120000,
            "popularity": 70,
        },
    ]

    def fake_analyzer(playlist_id, out_dir, *, progress, **kwargs):
        progress(
            {
                "stage": "collecting",
                "message": "fake progress",
                "completed": 3,
                "total": 3,
            }
        )
        playlist = {"id": playlist_id, "name": "Demo Playlist", "trackCount": 3}
        rows = [song_row(item) for item in raw_songs]
        summary = build_summary(playlist, rows, [], playlist_id)
        summary["integrity"] = {
            "status": "complete",
            "declared_count": 3,
            "requested_count": 3,
            "returned_count": 3,
            "missing_count": 0,
            "warnings": [],
        }
        summary["metadata"] = {
            "generatedAt": "2026-10-31T00:00:00+00:00",
            "projectVersion": "0.2.0",
        }
        metadata = {
            "reportId": out_dir.name,
            "playlistId": playlist_id,
            "playlistName": playlist["name"],
            "generatedAt": summary["metadata"]["generatedAt"],
            "returnedCount": 3,
            "missingCount": 0,
            "integrityStatus": "complete",
        }
        write_report(
            out_dir,
            summary,
            rows,
            playlist,
            [10, 11, 12],
            [],
            metadata,
        )
        return summary

    app = create_app(data_dir=tmp_path, analyzer=fake_analyzer)
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200

    response = client.post(
        "/api/analyze",
        json={"playlist": "https://music.163.com/#/playlist?id=123456"},
    )
    assert response.status_code == 202
    task = response.json()
    status = None
    for _ in range(40):
        status = client.get(f"/api/tasks/{task['task_id']}").json()
        if status["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert status and status["status"] == "completed"

    report_id = task["report_id"]
    summary = client.get(f"/api/reports/{report_id}")
    assert summary.status_code == 200
    assert summary.json()["overview"]["fetchedSongCount"] == 3
    assert summary.json()["profile"]["version"] == "1.0"

    songs = client.get(
        f"/api/reports/{report_id}/songs",
        params={"duplicate_only": "true", "sort": "duration", "order": "desc"},
    )
    assert songs.status_code == 200
    assert songs.json()["total"] == 2
    assert songs.json()["items"][0]["durationMs"] == 220000

    export = client.get(f"/api/reports/{report_id}/export", params={"kind": "summary"})
    assert export.status_code == 200
    assert "Demo Playlist" in export.text


def test_analyze_rejects_non_playlist_input(tmp_path: Path):
    app = create_app(
        data_dir=tmp_path,
        analyzer=lambda *args, **kwargs: {},
    )
    client = TestClient(app)
    response = client.post("/api/analyze", json={"playlist": "not a playlist"})
    assert response.status_code == 422
