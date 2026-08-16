# Changelog

All notable changes to Split Node Shorts.

## [1.5.9] - 2026-08-16

### Fix: codex image grabbing determinism

- Each codex image call now runs in its OWN isolated `CODEX_HOME` so its output lands in a unique `generated_images/` namespace - deterministic grabbing instead of racing over the shared `~/.codex/generated_images`. Joe 2026-08-16.

## [1.5.8] - 2026-08-16

### Arcane style simplified

- Cut the default `arcane` style prompt from 12 lines of overlapping descriptors to a concise descriptor. New arcane = stylized painterly 3D animation, bold inked outlines, cel-shaded graphic-novel texture, gritty weathered surfaces, dramatic rim lighting, saturated slightly-dirty colors, cinematic video-game concept art finish, no text/logos.

## [1.5.7] - 2026-08-16

### LLM backend selector

- At startup, pick which LLM writes the script: **LM Studio** (lists the currently-loaded models, you choose one) or **Codex** (lists models sorted cheapest-first, you choose one). `_llm_chat` routes to Codex when selected.
- Headless/cron runs can set `LLM_PROVIDER` + `LLM_MODEL` env vars to skip the prompt. Joe 2026-08-16.

### Repo hygiene

- `cast_refs/` is no longer tracked in git (re-downloaded/generated at runtime).

## [1.5.5] - 2026-08-14

### Shorts from an existing Split Node episode

Joe 2026-08-14. New mode that turns a finished Split Node episode into one or
more ~60s vertical Shorts by condensing its best narration, reusing the
episode's own shots, and linking back to the source documentary.

- **Mode prompt** — at startup, choose `1. Short from an existing Split Node
  episode` or `2. New Short from RSS` (env override `SHORTS_FROM_EPISODE=1/0`).
- **Episode scan** — lists finished episodes from Split Node's `episodes/`
  folder (those with a narration map, TTS, shots and video).
- **Whisper verify** — faster-whisper transcribes each narration clip so the
  system knows what's said and how long it is (`WHISPER_VERIFY=0` to skip and
  trust the stored narration text).
- **Gemma pick** — local gemma-4-e4b reviews the narration and selects the best
  contiguous ~60s window, with a deterministic trim-to-budget pass locking it
  to ~60s regardless of model drift.
- **Face-aware shot reuse** — the matching 16:9 shots are cropped to 9:16 with
  OpenCV face tracking, keeping the face in frame with minimal horizontal shift
  (not necessarily centered). No new images generated.
- **Multiple Shorts** — up to 5 distinct ~60s windows per episode.
- **Related video** — the full episode's URL is put at the top of the short's
  description so it links back to the source documentary.
- Verified end-to-end: 56s vertical short rendered from ep015 with subtitles,
  thumbnail and correct 1080x1920 face-cropped shots.

## [1.5.4] - 2026-08-14

### Fix RSS finding no stories + Codex default image backend

Joe 2026-08-14.

- **RSS scan found nothing.** The `_money_score` threshold was `>= 40`, but a
  real money story with a single strong keyword (e.g. "billion", "million" =
  30) scored below it, so nearly every candidate was dropped and the scan
  reported "No money-exploit stories found". Lowered the threshold to `>= 30`
  so one strong keyword passes. Verified: the same scan now returns 17
  candidates instead of 0.
- **Codex image backend (default).** Images now generate via the local OpenAI
  **Codex CLI** `/imagegen` (GPT Image 2) with no API key, instead of
  Higgsfield. `IMAGE_BACKEND=codex` is the new default (`.env` updated);
  `higgsfield` / `gptimage2` still available. Output-claiming is deterministic
  and parallel-safe (snapshot the PNG set before each call, claim the newest
  new file). Video clips stay on Higgsfield (`wan3_0`). Verified: a vertical
  9:16 image generated in ~71s.

## [1.5.3] - 2026-08-14

### Fix: broken byline regex crashed every article fetch

Joe 2026-08-14. `_is_junk_paragraph`'s author-byline regex had an escaped
`\]` inside its character class, producing an unterminated character set that
threw `re.error` on EVERY `fetch_article_paragraphs` call. That made every RSS
candidate report "did not resolve" and get auto-skipped (even though the links
were fine). Rewrote the byline pattern (handles "By John Smith", "By J.R.R.
Tolkien", "by Mary-Kate Jones", initials; case-flexible "By"; no false
positives on story sentences). Verified: fetches that previously failed now
return paragraphs.

## [1.5.2] - 2026-08-14

### Parse links before presenting them

Joe 2026-08-14. `_pick_story` now **fetches + extracts every candidate article
before it's shown to you**. A link that fails to resolve (blocked, dead,
paywalled, empty) is **auto-skipped** with no prompt — you only ever see links
that actually parse, and the next working story is offered instead. The
resolved paragraphs are returned with the accepted story (no double fetch);
custom-URL input is also verified up front.

## [1.5.1] - 2026-08-14

### SA3 startup port prompt: type a port to override

Joe 2026-08-14. At the SA3 startup prompt you can now **type a different port
directly** if the auto-detected one is wrong, instead of only accepting it or
saying no. The detected-port prompt accepts Enter/Y/yes (accept detected), a
port number (override), or n/no (fall through to manual entry). Blank still
skips music and falls back to voice-only.

## [1.5.0] - 2026-08-14

### Story-adaptive Stable Audio 3 music bed + SA3 startup port prompt

Joe 2026-08-14. Split Node Shorts now generates a real, story-adaptive music
bed with Stable Audio 3 instead of a static pool. The medium model (already
loaded in the running Pinokio Gradio UI) is driven through its `/generate`
endpoint via `gradio_client` — no second model load. The bed follows the
narration: the story text is split proportionally across chunks so each
segment's music prompt reflects what's happening at that point in the short.

- **SA3 resident-model generation** (`sa3_music.py` → `generate_via_gradio`).
  Chunks any bed longer than **380s (6:20)** into `N × 380s` segments plus a
  final remainder; the story context is split proportionally across the chunks
  for adaptive prompts.
- **Ducking.** The bed is set at a `-10dB` base and sidechain-ducked to
  **-19.5dB under the voice** during the mix (FFmpeg `sidechaincompress`).
- **Never breaks.** If SA3 is unavailable or generation fails, the pipeline
  falls back to voice-only. Toggle with `MUSIC_BACKEND` (default `sa3`);
  `SN_SA3_BED_PROMPT` overrides the base musical-style prompt.
- **SA3 startup port prompt.** SA3's Pinokio launcher opens on a different
  localhost port each run (7860, 7861, …), so `resolve_sa3_port` is called at
  startup (right after the banner, before any work): it socket-probes
  **7860–7890** for the Gradio `/config` signature (`pingpong` + `Stable
  Audio`), auto-detects a single live UI and asks **"use it? [Y/n]"**, otherwise
  prompts for the port manually (blank skips music → static-pool fallback).

## [1.3.0] - 2026-08-14

### Story resolve-and-retry (don't quit on a blocked article)

Joe 2026-08-14. Previously, if a selected RSS article was blocked / dead /
paywalled / returned no content, the pipeline quit. Now the story-pick step
resolves the article up front: if it doesn't fetch, it's rejected (2-week
cooldown) and the run loops back to picking a different story instead of
exiting. Retries up to `STORY_RESOLVE_ATTEMPTS` (default 5). Also re-picks if
the script LLM returns no scenes for a resolved article.

## [1.2.0] - 2026-08-14

### Up-to-scratch with Split Node (pipeline hardening, no render changes)

Joe 2026-08-14. Ported the fixes from Split Node that translate to Shorts
(which has no characters/faces, so the character-rendering fixes don't apply).
Subtitles, audio and ffmpeg render are UNTOUCHED.

- **Junk-paragraph filter.** `fetch_article_paragraphs` now drops boilerplate /
  nav / promo / paywall / cookie-consent / byline noise via `_is_junk_paragraph`
  (ported JUNK_PATTERNS), so only real story content reaches the script LLM.
  Improves script factual quality.
- **LLM liveness probe.** `_llm_reachable` now probes the CHAT endpoint (tiny
  "hi" call, 8s timeout) instead of `/v1/models`. `/v1/models` can respond while
  inference is hung, which let the gate pass and then block every subsequent LLM
  call on a 180s timeout. Real liveness test = no more serial stalls.
- **Hands/anatomy clause.** Stylized image models (Arcane) hallucinate fingers on
  hand-visible scenes (clicking / typing / counting cash). `_scene_shows_hands`
  detects those scenes and appends an anatomy-correct-hands clause to the image
  prompt.
- **Parallel image + TTS generation.** Each scene's image + TTS + duration are
  fully independent, so they now render concurrently via a thread pool instead
  of one-at-a-time. Gated by `IMAGE_CONCURRENCY` (default 1 = exactly the old
  sequential behaviour, so nothing changes unless you opt in).

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
