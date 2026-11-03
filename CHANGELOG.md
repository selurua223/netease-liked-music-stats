# Changelog

## v0.5.0

### AI handoff

- Added a post-download explanation that the statistics files can be sent to an AI assistant for a taste review.
- Added a copyable prompt in the ZIP `README.txt`, listing which files to send and what to ask.
- Added an in-app 「用 AI 解读」 dialog plus `GET /api/ai-guide`, sharing the same copy with the archive.
- Added a one-line hint to the CLI after a successful run.

### Failure paths

- The AI hand-off note now appears only after the ZIP has actually downloaded; a failed download shows a retry hint instead.
- The analysis overlay gained 重试/关闭 buttons, and no longer appends a duplicate close button on every failure.
- The prompt asks the AI to read `integrity.status` and `missingSongCount` first, and to lower confidence when data is incomplete.

### Compatibility

- Fixed share links whose `creatorId`/`userid` parameter came before `id`: the API used to take the first long number in the URL and analyze the wrong playlist ID. It now reads the `id` parameter (normal query and `#/playlist?id=` form) first.
- Fixed a Python 3.10 crash: `datetime.UTC` is 3.11-only, so the API and CLI failed to import on the documented minimum version. Replaced with `datetime.timezone.utc`.
- CI now runs the test suite on Python 3.10 and 3.12.

## v0.4.1

- Added one-click ZIP export for every report artifact.
- Added optional automatic ZIP download after analysis completes.
- Added a download-all API endpoint and archive integration tests.

## v0.4.0

### Data trust

- Separated field completeness, sample sufficiency, and conclusion reliability.
- Added small-sample protection: fewer than 10 songs cannot produce strong profile findings.
- Added per-insight sample sizes and reliability levels.
- Saved original song-detail responses in `raw_data.json`.
- Distinguished `complete`, `warning`, and `partial` integrity states.
- Ignored empty artist records while retaining a single unknown-artist fallback.
- Validated popularity values against the 0–100 range.
- Allowed reports to complete when every duration is missing.

### Music DNA

- Renamed profile labels to describe collection structure instead of inferred listening behavior.
- Added explicit metric definitions, formulas, numerators, denominators, sample sizes, and missing counts.
- Added album-ID-based de-duplication and normalized album entropy.
- Added sample and field-coverage details to the profile page.
- Added metric explanation dialogs and links from findings to related songs.

### Verification

- Added tests for small samples, invalid artists, missing popularity and durations, album identity, incomplete collections, raw-data persistence, and API song filtering.

## v0.3.0

- Added Music DNA collection profile.
- Added artist pagination with 15 rows per page.
- Added profile screenshots and documentation.

## v0.2.0

- Added local FastAPI server and browser interface.
- Added dashboard, artist, song, profile, and history views.
- Added report comparison and local export endpoints.
- Refactored the CLI into reusable core modules.

## v0.1.0

- Initial public Codex Skill release.
