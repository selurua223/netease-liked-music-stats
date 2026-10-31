"""Small in-process task manager for local analysis jobs."""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from netease_stats.core.analyzer import analyze_playlist

from .reports import ReportRepository


Analyzer = Callable[..., dict[str, Any]]


class TaskService:
    def __init__(
        self,
        repository: ReportRepository,
        analyzer: Analyzer = analyze_playlist,
    ):
        self.repository = repository
        self.analyzer = analyzer
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="netease-analysis",
        )

    def create(
        self,
        playlist_id: int,
        *,
        include_raw_data: bool = True,
        generate_csv: bool = True,
    ) -> dict[str, Any]:
        task_id = secrets.token_hex(8)
        report_id = secrets.token_hex(6)
        task = {
            "id": task_id,
            "reportId": report_id,
            "playlistId": playlist_id,
            "status": "queued",
            "stage": "queued",
            "message": "分析任务已创建",
            "completed": 0,
            "total": 0,
            "percent": 0,
            "error": None,
            "createdAt": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            self._tasks[task_id] = task
        self._executor.submit(
            self._run,
            task_id,
            playlist_id,
            report_id,
            include_raw_data,
            generate_csv,
        )
        return dict(task)

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def _update(self, task_id: str, **changes: Any) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.update(changes)

    def _run(
        self,
        task_id: str,
        playlist_id: int,
        report_id: str,
        include_raw_data: bool,
        generate_csv: bool,
    ) -> None:
        self._update(
            task_id,
            status="running",
            stage="starting",
            message="正在准备分析任务",
            percent=2,
        )

        def progress(event: dict[str, Any]) -> None:
            completed = event.get("completed")
            total = event.get("total")
            percent = 5
            if isinstance(completed, int) and isinstance(total, int) and total:
                percent = min(95, 8 + round(completed / total * 84))
            self._update(
                task_id,
                stage=event["stage"],
                message=event["message"],
                completed=completed or 0,
                total=total or 0,
                percent=percent,
            )

        try:
            report_dir = self.repository.root / report_id
            self.analyzer(
                playlist_id,
                report_dir,
                include_raw_data=include_raw_data,
                generate_csv=generate_csv,
                progress=progress,
            )
            self._update(
                task_id,
                status="completed",
                stage="completed",
                message="分析完成",
                percent=100,
            )
        except Exception as error:
            self._update(
                task_id,
                status="failed",
                stage="failed",
                message="分析失败",
                error=str(error),
            )
