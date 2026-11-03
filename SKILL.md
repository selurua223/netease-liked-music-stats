---
name: netease-liked-music-stats
description: Analyze a public NetEase Cloud Music "liked songs" playlist (网易云音乐“喜欢的音乐”) and produce validated artist counts, duplicate-title groups, duration extrema, popularity extrema, and auditable CSV reports.
---

# NetEase Liked Music Stats

Use this skill when the user asks for statistics about a NetEase Cloud Music playlist, especially a playlist named “我喜欢的音乐” or “喜欢的音乐”. The expected outcome is a complete analysis of every track, not an estimate based on the rows currently rendered in the desktop app.

This skill is for public NetEase playlists. It does not access private account libraries, download audio, or change the playlist.

## Companion local web app

The repository also includes a local-only browser interface. When the user asks to use the dashboard rather than the CLI, run `python run.py`, keep the service bound to loopback, and open `http://127.0.0.1:8765`. The Web interface and the Skill both call the same `src/netease_stats/core/` implementation.

## Workflow

1. Resolve the playlist ID unambiguously.

   Prefer a playlist ID or public share URL supplied by the user. If the user refers to the currently open NetEase desktop page, use the available Computer Use capability to verify the visible playlist name, owner, and track count. The page may expose the playlist ID indirectly; use a read-only client cache only when its relevance can be verified. If the ID cannot be established confidently, ask for the public playlist link or numeric ID rather than guessing from the owner name.

2. Fetch the playlist preview and all track IDs.

   The playlist-detail response contains a complete `playlist.trackIds` array even though `playlist.tracks` contains only a few preview tracks. Use the ID array as the source of truth and validate that its count agrees with `playlist.trackCount` and the count visible in the app.

3. Run the deterministic analyzer.

   ```bash
   python scripts/netease_liked_stats.py \
     --playlist-id PLAYLIST_ID \
     --out-dir OUTPUT_DIR
   ```

   The script fetches song details in batches of 200 and writes raw data, an all-songs table, artist counts, duplicate-title groups, extrema, a JSON summary, and a Markdown summary. Read [references/api-contract.md](references/api-contract.md) when debugging endpoint behavior or adapting the script.

4. Check completeness before reporting.

   Require all requested IDs to resolve to song objects with no duplicates and no missing IDs. Treat a partial batch as a defect: the old NetEase song-detail endpoint accepts a larger input array but returns only about 201 songs, so a 500-item request can silently hide most of the batch. Use at most 200 IDs per request.

5. Report the definitions alongside the result.

   - Artist count: every distinct artist credited on a song receives one count; a collaboration therefore contributes to multiple artists.
   - Duplicate title: exact song `name` after Unicode normalization and trimming outer whitespace. Do not merge versions whose titles contain different suffixes.
   - Duration: the song-detail `duration` value, converted from milliseconds.
   - Popularity: the song-detail `popularity` score, with `score` and `pop` as compatibility fallbacks.

   Describe popularity as NetEase’s bounded, coarse platform score, not as play count and not as a metric with a publicly documented formula. Preserve ties and report how many songs share each extreme.

6. Present a compact answer and link the complete files.

   Include the playlist total, unique artist count, top artist counts, duplicate-title summary, and duration/popularity extrema. Put the complete 3,000-plus-row artist ranking and 200-plus duplicate groups in CSV files rather than pasting them all into chat.

   Mention the optional AI handoff once: the exported `summary.json`, `report.md`, and `songs.csv` can be sent to any AI assistant for a taste review, and the ZIP `README.txt` already contains a ready-to-paste prompt. Do not send the files anywhere yourself; that decision belongs to the user.

## Acceptance checks

Before handing off the result:

- The number of fetched songs equals the unique track-ID count.
- Every requested song ID is present unless the user explicitly accepts a documented missing-track count.
- The sum of artist counts is at least the number of songs.
- The duplicate report contains only titles with at least two distinct songs.
- Longest and shortest durations are computed from positive duration values.
- Highest and lowest popularity groups identify their tie counts.
- The final explanation labels the source and definitions rather than implying that the popularity formula is known.
