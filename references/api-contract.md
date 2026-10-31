# NetEase playlist analysis API notes

These notes record the behavior observed while analyzing a 6,800-track public “liked music” playlist. They are implementation notes, not an assertion that NetEase guarantees these endpoints or response shapes.

## Playlist detail

Request:

```text
GET https://music.163.com/api/v6/playlist/detail?id={playlist_id}
```

Relevant response fields:

- `playlist.trackCount`: advertised number of tracks.
- `playlist.trackIds`: complete ordered list of track IDs.
- `playlist.tracks`: a small preview only, often around six songs.
- `playlist.name`, `playlist.creator`, and `playlist.playCount`: useful for identifying the requested playlist.

Do not treat the short `tracks` array as the playlist contents. Use `trackIds`.

## Song details

Request for each batch:

```text
GET https://music.163.com/api/song/detail?ids=[id1,id2,...]
```

Observed constraints:

- A 200-ID request returned all 200 songs.
- A 500-ID request returned only 201 songs without necessarily reporting an error.
- Use batches no larger than 200 and compare returned IDs against requested IDs after every batch.

Relevant response fields:

- `songs[].id`: song identifier used to merge the response.
- `songs[].name`: title.
- `songs[].artists[]`: artist objects; use each distinct `name` once per song.
- `songs[].album.name`: album title.
- `songs[].duration`: duration in milliseconds.
- `songs[].popularity`: platform popularity score, commonly mirrored in `score`.

## Popularity interpretation

The returned value is not a raw play count. In the tested playlist it ranged from 5 to 100 and appeared in five-point buckets. An official derivation formula was not available, so reports should call it the platform popularity score and preserve ties.

## Access and safety

Use ordinary read-only HTTP requests with a browser-like User-Agent and the NetEase Music referer. Do not use account cookies or authentication credentials for a public playlist. Do not download audio, mutate playlists, or infer private listening information.

## Report data contract

Every completed analysis writes:

- `summary.json`: normalized statistics, integrity result, and Music DNA profile.
- `songs.json`: normalized rows used by Web pagination.
- `metadata.json`: playlist ID, generation time, version, and completeness.
- `raw_data.json`: original playlist response, ordered track IDs, missing IDs, and original song-detail objects when `include_raw_data` is enabled.
- CSV and Markdown exports derived from the normalized rows.

Integrity status values:

- `complete`: declared count and unique ID processing agree, with no missing or unexpected songs.
- `warning`: all exposed IDs were returned, but playlist count metadata does not agree.
- `partial`: at least one requested song detail is missing, or unexpected songs were returned.

The local API exposes paginated song queries and accepts an optional comma-separated `song_ids` filter so a Music DNA finding can link back to its evidence songs.
