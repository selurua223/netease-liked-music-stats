"""Command-line interface retained for backwards compatibility."""

from __future__ import annotations

import argparse
from pathlib import Path

from .core.analyzer import analyze_playlist


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a complete, auditable report for a public NetEase playlist."
    )
    parser.add_argument("--playlist-id", required=True, type=int)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="write a report even if some requested songs are unavailable",
    )
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 200:
        parser.error("--batch-size must be between 1 and 200")

    def progress(event: dict[str, object]) -> None:
        completed = event.get("completed")
        total = event.get("total")
        suffix = ""
        if isinstance(completed, int) and isinstance(total, int) and total:
            suffix = f" [{completed}/{total}]"
        print(f"{event['message']}{suffix}", flush=True)

    summary = analyze_playlist(
        args.playlist_id,
        args.out_dir,
        batch_size=args.batch_size,
        timeout=args.timeout,
        progress=progress,
    )
    missing = summary["overview"]["missingSongCount"]
    if missing and not args.allow_missing:
        raise RuntimeError(f"{missing} requested songs were missing")
    print(
        "complete: "
        f"songs={summary['overview']['fetchedSongCount']} "
        f"artists={summary['overview']['uniqueArtists']} "
        f"duplicate_groups={summary['overview']['duplicateTitleGroups']} "
        f"missing={missing}",
        flush=True,
    )
    print(
        "提示：summary.json、report.md、songs.csv 可以直接发给 AI 助手，"
        "让它基于这些数据解读这份歌单的品味结构。",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
