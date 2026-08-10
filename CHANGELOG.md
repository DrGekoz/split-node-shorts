# Changelog

All notable changes to Split Node Shorts.

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
