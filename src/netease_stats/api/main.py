"""Local-first FastAPI application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from netease_stats import __version__
from netease_stats.core.analyzer import analyze_playlist

from ..services.reports import ReportNotFoundError, ReportRepository
from ..services.tasks import Analyzer, TaskService

from .schemas import AnalyzeRequest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WEB_ROOT = PROJECT_ROOT / "web"
DEFAULT_DATA_DIR = PROJECT_ROOT / "outputs"


def create_app(
    data_dir: Path | None = None,
    analyzer: Analyzer = analyze_playlist,
) -> FastAPI:
    report_root = Path(
        data_dir or os.environ.get("NETEASE_STATS_DATA_DIR", DEFAULT_DATA_DIR)
    ).resolve()
    repository = ReportRepository(report_root / "web")
    tasks = TaskService(repository, analyzer=analyzer)

    app = FastAPI(
        title="NetEase Music Analytics",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "mode": "local-only",
            "reportCount": len(repository.list_reports()),
        }

    @app.post("/api/analyze", status_code=status.HTTP_202_ACCEPTED)
    def analyze(payload: AnalyzeRequest) -> dict[str, Any]:
        task = tasks.create(
            payload.playlist_id,
            include_raw_data=payload.include_raw_data,
            generate_csv=payload.generate_csv,
        )
        return {
            "task_id": task["id"],
            "report_id": task["reportId"],
            "status": task["status"],
            "message": task["message"],
        }

    @app.get("/api/tasks/{task_id}")
    def task_status(task_id: str) -> dict[str, Any]:
        task = tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @app.get("/api/reports")
    def reports() -> dict[str, Any]:
        return {"items": repository.list_reports()}

    @app.get("/api/reports/{report_id}")
    def report(report_id: str) -> dict[str, Any]:
        try:
            return repository.load_summary(report_id)
        except ReportNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/reports/{report_id}/songs")
    def songs(
        report_id: str,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=200)] = 30,
        search: str = "",
        artist: str = "",
        song_ids: str = "",
        sort: Annotated[
            str, Query(pattern="^(title|artists|album|duration|popularity)$")
        ] = "title",
        order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
        duplicate_only: bool = False,
    ) -> dict[str, Any]:
        try:
            rows = repository.load_songs(report_id)
            summary = repository.load_summary(report_id)
        except ReportNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

        query = search.strip().casefold()
        artist_query = artist.strip().casefold()
        requested_ids: set[int] = set()
        if song_ids.strip():
            for raw_id in song_ids.split(","):
                if raw_id.strip().isdigit():
                    requested_ids.add(int(raw_id.strip()))
        duplicate_titles = {
            item["title"] for item in summary.get("duplicateTitles", [])
        }
        if requested_ids:
            rows = [row for row in rows if int(row["id"]) in requested_ids]
        if query:
            rows = [
                row
                for row in rows
                if query in row["title"].casefold()
                or query in row["album"].casefold()
                or any(query in name.casefold() for name in row["artists"])
            ]
        if artist_query:
            rows = [
                row
                for row in rows
                if any(artist_query in name.casefold() for name in row["artists"])
            ]
        if duplicate_only:
            rows = [row for row in rows if row["title"] in duplicate_titles]

        sort_key = {
            "title": lambda row: row["title"].casefold(),
            "artists": lambda row: " / ".join(row["artists"]).casefold(),
            "album": lambda row: row["album"].casefold(),
            "duration": lambda row: row["durationMs"],
            "popularity": lambda row: (
                row["popularity"] is not None,
                row["popularity"] or 0,
            ),
        }[sort]
        rows.sort(key=sort_key, reverse=order == "desc")
        total = len(rows)
        start = (page - 1) * page_size
        return {
            "items": rows[start : start + page_size],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "pages": max(1, (total + page_size - 1) // page_size),
        }

    @app.get("/api/reports/{report_id}/export")
    def export(report_id: str, kind: str = "markdown") -> FileResponse:
        try:
            path, media_type = repository.export_path(report_id, kind)
        except ReportNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(path, media_type=media_type, filename=path.name)

    @app.get("/api/reports/{report_id}/compare/{other_id}")
    def compare(report_id: str, other_id: str) -> dict[str, Any]:
        try:
            return repository.compare(report_id, other_id)
        except ReportNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    if WEB_ROOT.is_dir():
        app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        path = WEB_ROOT / "index.html"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Web interface not found")
        return FileResponse(path)

    return app


app = create_app()
