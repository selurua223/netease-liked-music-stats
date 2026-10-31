# Changelog

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
