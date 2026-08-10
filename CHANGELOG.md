# Changelog

All notable changes to Split Node Shorts.

## [1.1.0] - 2026-08-11

### Fix: silent shorts (no audio / one image / no subtitles) + real YouTube replacement

Three bugs produced a broken first short (video only, a single repeated image,
no captions). All fixed and verified:

- **TTS produced no audio (JSON vs multipart).** PocketTTS's `/tts` endpoint
  expects `multipart/form-data` (fields `text`, `voice_url` or `voice_wav`), but
  the client sent JSON — which the server silently 422s. `_tts()` now posts
  multipart via `requests`, and accepts either a built-in voice name
  (`voice_url`) or a cloned `.wav` file (`voice_wav`).
- **Ken Burns showed only image 1.** The images-only renderer fed each still
  with `-loop 1 -framerate 30`, making every input an infinite stream so the
  concat never advanced past the first frame — the exact Split Node ep12 bug.
  Now each image is a **single frame** (no `-loop`/`-framerate`) and `zoompan`
  generates the frames, so all scenes advance correctly (verified 13/13 distinct).
- **No subtitles.** Word-level captions couldn't run without TTS audio; once TTS
  worked they burn in (faster-whisper + styled ASS, default `mrbeast`).
- **YouTube token refresh was serving a stale token.** `google.auth` refreshed
  but wrote back a token that API calls still rejected as expired, so uploads
  were failing with 401. Refreshed manually and persisted a valid token.
- **Verified replacement:** the broken first short was deleted from YouTube and
  the corrected short re-uploaded public with matching title/desc/tags, a
  compressed (under-2MB) custom thumbnail, and added to the 'Split Node Shorts'
  playlist.

## [1.0.1] - 2026-08-11

### Fix: launcher closed immediately / died at the LM Studio check

- **Root cause 1 (immediate close):** the `.bat` was written with **LF-only line
  endings**. `cmd.exe` needs CRLF for multi-line parenthesized `if (...)` blocks,
  so the first `if %errorlevel% ... ( ) else ( )` block aborted the whole script.
- **Root cause 2 ("then was unexpected at this time"):** the LM Studio check's
  WARN `echo` line contained a literal `(load gemma-4-e4b-uncensored)` inside the
  parenthesized block. cmd parsed the `(` as opening an inner block, then choked
  on `then`. Removed the parentheses from the echo text.
- **Root cause 3 (hang at Higgsfield check):** `higgsfield account status >nul 2>&1`
  hung when run as a bat line (interaction between the `.cmd` shim and the null
  redirect). Removed the check — it was redundant, since `split_node_shorts.py`
  invokes Higgsfield itself with proper error handling.
- Verified end-to-end: checks pass (Python / PocketTTS / LM Studio), RSS scan
  finds candidates, pipeline reaches the story pick, and the window pauses at the
  end instead of closing.

## [1.0.0] - 2026-08-11

### Initial release

- **Vertical 9:16 Shorts pipeline** (1080x1920, 30fps, hevc_nvenc), target 60s / hard cap 180s.
- **RSS money-exploit scanner** — 30+ money/finance/scam/frugal feeds, keyword-tiered scoring, recency-first, with **2-week "no" suppression** (persisted cooldown, hidden for 14 days).
- **6-phase viral script formula** — Declare → Assess → Isolate → Process → Build → Reveal, written by Gemma 4 (LM Studio, local, no cloud LLM).
- **Higgsfield image generation** — Nano Banana 2 (`nano_banana_flash`, 1.5 cr) vertical 9:16; `gptimage2` backend wired for GPT Image 2 when the rate limit lifts.
- **Higgsfield video generation** — Wan 3.0 (`wan3_0`, 2.5 cr/s) default, Kling 3 / Kling 3 Turbo supported via env.
- **Per-run generation mode** — asks whether to generate AI video clips or images-only (Ken Burns stills); `GENERATE_VIDEOS=0/1` env override.
- **Word-level animated subtitles** — ported `ass_subtitles.py` from Crayon Diet (faster-whisper word timings + 6 styled ASS caption modes), burned into every short.
- **Arcane + selectable style profiles** — same system as Split Node; custom styles persist in `style_sheets/custom_styles.json`.
- **Live video price monitor** — re-queries the model cost every run and prints a `[PRICE CHANGE]` warning if it moves.
- **Auto-upload** — YouTube resumable upload to the Split Node channel's **'Split Node Shorts'** playlist, with single-frame custom thumbnail via API.
- **One-click launcher** — `SplitNodeShorts.bat` with health checks (Python / PocketTTS / LM Studio / Higgsfield), Start Menu shortcut.
