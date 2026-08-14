# 🎬 Split Node Shorts

<div align="center">

![Split Node Shorts](https://img.shields.io/badge/Split%20Node%20Shorts-AI%20Vertical%20Short%20Pipeline-181717?style=for-the-badge&logo=youtube&logoColor=white)

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![LM Studio](https://img.shields.io/badge/LM%20Studio-Gemma%204-4B32C3?style=for-the-badge&logo=langchain&logoColor=white)](https://lmstudio.ai)
[![Higgsfield](https://img.shields.io/badge/Higgsfield-Image%20%2B%20Video-8A2BE2?style=for-the-badge)](https://higgsfield.ai)
[![PocketTTS](https://img.shields.io/badge/PocketTTS-Narration-F7931E?style=for-the-badge)](https://github.com/Kyutai-Labs/pocket-tts)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-NVENC-00B172?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org)
[![Vertical](https://img.shields.io/badge/Format-9%3A16%20%2F%201080p-FF6B35?style=for-the-badge)]()
[![Based on](https://img.shields.io/badge/Based%20on-Split%20Node-1DA1F2?style=for-the-badge&logo=github&logoColor=white)](https://github.com/DrGekoz/Split-Node-YouTube)

## ❤️ Support This Project

<a href="https://www.buymeacoffee.com/drgekoz" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;"></a>

**A vertical AI Shorts generator. Turns "money exploit" stories (loopholes, glitches, refunds, scams) into ~60-second 9:16 YouTube Shorts in the proven 6-phase viral formula — with LLM-written scripts, Higgsfield images + video clips, voice narration, word-level animated subtitles, a story-adaptive Stable Audio 3 music bed ducked under the voice, and auto-upload to the Split Node channel's 'Split Node Shorts' playlist. Headless: RSS in, rendered and uploaded short out.**

[The Pipeline](#the-pipeline) · [The 6-Phase Formula](#-the-6-phase-viral-formula) · [Supported Models](#supported-models--apis) · [Real-World Cost](#real-world-cost) · [Getting Started](#getting-started) · [Features](#features)

</div>

## 🎬 Example Output

Every short follows the proven viral formula that's generated hundreds of millions of views across Shorts: a declaration hook in the first 2 seconds, then a fast, completion-driven story that keeps viewers to the reveal.

---

> **Status:** This is the **companion pipeline to [Split Node](https://github.com/DrGekoz/Split-Node-YouTube)** — same architecture, same small-local-model LLM approach, but built for **vertical 9:16 Shorts** instead of 25-minute landscape documentaries. The LLM, TTS, rendering, subtitles, and upload all run locally; the only cloud cost is **Higgsfield credits** for image + video generation (optional).

---

## What is Split Node Shorts?

Split Node Shorts automates the entire vertical-Shorts production workflow. Feed it a "money exploit" story from RSS (or a URL), and it handles everything: scanning 30+ money/finance/scam feeds, LLM-scoring candidates, writing a 6-phase viral Shorts script, generating a vertical image per scene (Higgsfield Nano Banana 2), optionally generating a matching video clip per scene (Higgsfield Wan 3.0), narrating with PocketTTS, generating a **story-adaptive Stable Audio 3 music bed** ducked under the voice, burning in **word-level animated subtitles**, and uploading the finished short to the **Split Node channel's 'Split Node Shorts' playlist**.

Built for **content creators and automated channel operators** who want to ship consistent, on-brand AI Shorts — end to end — without touching a video editor.

> **I built this as a fully headless personal pipeline** — no UI, just `RSS in → rendered and uploaded short out`. Every run asks whether you want AI video clips or images-only (Ken Burns), so you control the credit burn.

---

## 🧠 How a tiny local model writes the whole script

Split Node Shorts inherits Split Node's core insight: **a small local model (Gemma 4) writes the entire script** because the pipeline chunks the work and injects exactly the context each step needs. No giant context window, no cloud LLM bills.

- **📰 RSS feed injection (story discovery)** — 30+ money-exploit feeds (finance, frugal, churning, coupons, scams, consumer fraud). Each candidate is keyword-scored against the niche; off-topic beats are discarded before the script stage.
- **🚫 2-week "no" suppression** — say no to a story and it's hidden for 14 days (persisted cooldown), so you never see it again in a single session or across runs.
- **✅ Parse-before-present** — every candidate is fetched + extracted **before** it's shown to you; a link that's blocked / dead / paywalled / empty is **auto-skipped** (no prompt) and you get the next working story — you only ever see links that actually resolve.
- **📃 Script injection** — the article's paragraphs are injected as context and the model writes a tight ~60s script in the **6-phase formula** (Declare → Assess → Isolate → Process → Build → Reveal). Target 60s, hard cap 180s.
- **🎨 Style injection (images)** — every image prompt gets the selected **style profile** injected (e.g. `arcane`, `noir`, `photoreal`, or a custom descriptor). Same style system as Split Node.

---

## 💸 Cost

| Component | Provider | Notes |
|---|---|---|
| Story + Script | LM Studio (local, Gemma 4) | Free |
| Narration TTS | PocketTTS (local) | Free |
| Subtitles + render | faster-whisper + FFmpeg (local) | Free |
| **Images** | Higgsfield Nano Banana 2 (`nano_banana_flash`) | 1.5 cr/image |
| **Video clips** *(optional)* | Higgsfield Wan 3.0 (`wan3_0`) | 2.5 cr/sec |
| Music bed | Stable Audio 3 (local, Pinokio) | Free (local) |
| Upload | YouTube Data API | Free quota |

**Images-only mode** (Ken Burns stills) runs a whole short for ~1.5 cr/scene — no video credits at all. The video model price is **re-queried on every run** and a `[PRICE CHANGE]` warning is printed if it ever moves.

---

## The Pipeline

```
RSS / URL money-exploit story
    │
    ▼
┌──────────────────────────────────────────────┐
│  1. STORY DISCOVERY                          │
│     30+ money/finance/scam feeds → keyword   │
│     score → 2-week 'no' suppression          │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│  2. SCRIPT (gemma-4-e4b, 6-phase formula)    │
│     DECLARE → ASSESS → ISOLATE → PROCESS     │
│     → BUILD → REVEAL · target 60s / max 180s │
│     Ask per run: videos OR images-only       │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│  3. IMAGES (Higgsfield nano_banana_flash)    │
│     9:16 vertical, 1080p · one per scene     │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│  4. VIDEO (optional, Higgsfield wan3_0)      │
│     9:16 clips, duration per scene           │
│     OR images-only (Ken Burns slow-zoom)     │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│  5. NARRATION (PocketTTS)                    │
│     one clip per scene                       │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│  6. MUSIC BED (Stable Audio 3, local)        │
│     story-adaptive, resident medium model    │
│     ducked -10dB -> -19.5dB under voice      │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│  7. RENDER + SUBTITLES                       │
│     hevc_nvenc vertical render               │
│     word-level animated captions             │
│     (faster-whisper + ASS)                   │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│  8. UPLOAD                                   │
│     YouTube → Split Node channel             │
│     'Split Node Shorts' playlist             │
│     single-frame custom thumbnail            │
└──────────────────────────────────────────────┘
```

### 🎯 The 6-Phase Viral Formula

The script engine follows the proven Shorts formula (the "Brazzers method"): a **DECLARATION** hook with a big absurd number in the first 2 seconds, then **ASSESS** → **ISOLATE** → **PROCESS** → **BUILD** → **REVEAL**. Completion compulsion keeps viewers to the payout reveal. Titles follow the declaration formula with a specific number + 2 emojis.

### 🧍 Visual Style

The default look is **Arcane** (same descriptor as Split Node): stylized hand-painted comic realism, cel-shaded, bold inked outlines. Fully customisable via the same **style profile** system — pick with `STYLE=`, add your own with `--add-style`.

### 💬 Subtitles

Word-level animated captions burned into every short (faster-whisper word timings + styled ASS). Selectable style via `SUBTITLE_STYLE`: `hormozi` / `mrbeast` (default) / `karaoke` / `minimal` / `bounce` / `classic`.

### 🎵 Music Bed

A **story-adaptive Stable Audio 3 (SA3) music bed** is generated and sidechain-ducked under the narration. Instead of a static MP3, the pipeline drives the **resident medium model** loaded in the running Pinokio Gradio UI via `gradio_client` (no second model load). The bed adapts to the story: the narration script is split **proportionally across chunks** so each segment's music prompt reflects what's happening in that part of the short.

- **Chunking** — the medium UI caps at **380s (6:20)** per generation; longer beds are split into `N × 380s` segments plus a final remainder (e.g. a 20 min video = 380s × 3 + 60s).
- **Ducking** — music is set at a `-10dB` base and ducked to **-19.5dB under the voice** via FFmpeg `sidechaincompress` during the mix.
- **Fallback** — if SA3 is unavailable or generation fails, the pipeline falls back to voice-only (a short never breaks).
- **Config** — `MUSIC_BACKEND` (default `sa3`) toggles the bed; `SN_SA3_BED_PROMPT` overrides the base musical-style prompt; `SA3_GRADIO_URL` sets the Gradio URL.

**Startup port prompt.** SA3's Pinokio launcher opens on a **different localhost port each run** (7860, 7861, …), so the hard-coded default is unreliable. At startup (right after the banner, before any work) the pipeline calls `resolve_sa3_port`: it socket-probes ports **7860–7890** for the Gradio `/config` signature (`pingpong` + `Stable Audio`), auto-detects a single live UI and asks **"use it? [Y/n, or type a port]"** — press Enter/Y to accept it, type a different port to override, or say no to enter it manually (blank skips music → static-pool fallback).

---

## Supported Models & APIs

| Selection | Values |
|---|---|
| `IMAGE_BACKEND` | `higgsfield` *(default, nano_banana_flash)* · `gptimage2` (GPT Image 2 via Higgsfield) |
| `VIDEO_BACKEND` | `higgsfield` *(default, wan3_0)* |
| `HIGGS_VIDEO_MODEL` | `wan3_0` *(default)* · `kling3_0` · `kling3_0_turbo` |
| `GENERATE_VIDEOS` | unset → **asks per run** · `1` = videos · `0` = images-only |
| `SUBTITLE_STYLE` | `mrbeast` *(default)* · hormozi · karaoke · minimal · bounce · classic |
| `STYLE` | `arcane` *(default)* · noir · photoreal · synthwave · + custom |
| `IMAGE_CONCURRENCY` | concurrent scenes during image+TTS gen · `1` *(default, sequential)* · `3`+ to parallelise |
| `STORY_RESOLVE_ATTEMPTS` | retries when a picked article doesn't resolve (blocked/no content) · default `5` |
| `MUSIC_BACKEND` | `sa3` *(default, Stable Audio 3)* · anything else = voice-only |

```bash
GENERATE_VIDEOS=0 python split_node_shorts.py    # images-only (Ken Burns, cheap)
GENERATE_VIDEOS=1 python split_node_shorts.py    # + AI video clips (uses credits)
HIGGS_VIDEO_MODEL=kling3_0_turbo python split_node_shorts.py  # cheaper Kling (1.5 cr/s)
SUBTITLE_STYLE=hormozi python split_node_shorts.py
STYLE=noir python split_node_shorts.py
python split_node_shorts.py styles               # list selectable styles
python split_node_shorts.py add-style vhs "<desc>"   # add + persist a style
```

### LLM — Script & Metadata

| Provider | Models / Notes |
|---|---|
| **LM Studio** *(local)* | Gemma 4 uncensored on `localhost:1234` — writes the 6-phase script, title, description, tags |

### Image Generation

| Provider | Model | Notes |
|---|---|---|
| **Higgsfield** | Nano Banana 2 (`nano_banana_flash`) | 1.5 cr/image, 9:16, 1080p |
| **Higgsfield** *(future)* | GPT Image 2 (`gpt_image_2`) | `IMAGE_BACKEND=gptimage2` — feed images back into Higgsfield for video |

### Video Generation

| Provider | Model | Notes |
|---|---|---|
| **Higgsfield** | Wan 3.0 (`wan3_0`, default) | 2.5 cr/sec, 9:16, duration per scene |
| **Higgsfield** | Kling 3.0 (`kling3_0`) / Turbo | 2 cr/s / 1.5 cr/s |

### Voice / TTS

| Provider | Capability |
|---|---|
| **PocketTTS** *(local, CUDA)* | Narration per scene (`marius` built-in voice) |

### Music

| Provider | Model | Notes |
|---|---|---|
| **Stable Audio 3** *(local, Pinokio)* | medium (resident) | Story-adaptive bed via Gradio `/generate`; chunked @380s; ducked under voice |

### Subtitles

| Provider | Capability |
|---|---|
| **faster-whisper** *(local)* | Word-level timings from the TTS mix |
| **ass_subtitles.py** | 6 styled word-animation caption styles, burned via FFmpeg |

---

## Real-World Cost

Because the LLM, TTS, subtitles and render run **locally**, a short costs almost nothing except optional Higgsfield generation:

| Component | Provider | Notes |
|---|---|---|
| Story + Script + Metadata | LM Studio (local) | Free |
| Narration TTS | PocketTTS (local) | Free |
| Subtitles + render | faster-whisper + FFmpeg | Free |
| Images *(per scene)* | Higgsfield Nano Banana 2 | 1.5 cr |
| Video clips *(per scene)* | Higgsfield Wan 3.0 | 2.5 cr/s |
| Music bed | Stable Audio 3 (local, Pinokio) | Free |
| Upload | YouTube Data API | Free quota |

**Tip:** use `GENERATE_VIDEOS=0` (images-only) to test / bulk-produce cheaply, then add video clips when you want motion. The video-model price is checked live every run.

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **LM Studio** on `localhost:1234` with `gemma-4-e4b-uncensored-hauhaucs-aggressive` loaded
- **PocketTTS** server on `127.0.0.1:8769`
- **Higgsfield CLI** installed (`npm i -g @higgsfield/cli`) and authenticated (`higgsfield auth login`) with a workspace selected
- **Stable Audio 3** via Pinokio (running Gradio UI; the pipeline asks which port at startup)
- **FFmpeg** with `hevc_nvenc` (NVIDIA)
- **YouTube API** credentials at `~/.youtube-upload-credentials.json` (same as Split Node)

### Install & Run

```bash
git clone https://github.com/DrGekoz/split-node-shorts
cd split-node-shorts
pip install pysubs2 faster-whisper

SplitNodeShorts.bat
# or
python split_node_shorts.py
```

Each run asks whether to generate **AI video clips** or **images only**, and asks **which port Stable Audio 3** is on (or auto-detects it). Env override: `GENERATE_VIDEOS=1` / `GENERATE_VIDEOS=0`.

---

## Project Structure

```
split-node-shorts/
├── split_node_shorts.py    Main pipeline (all 8 stages)
├── sa3_music.py            Stable Audio 3 music bed (port resolution + gradio driver)
├── ass_subtitles.py        Word-level styled caption engine (6 styles)
├── SplitNodeShorts.bat     One-click launcher (health checks)
│
├── style_sheets/           Style profiles + custom_styles.json
├── voice_refs/             TTS narration voice reference
│
├── shots/                  Scene images + clips — gitignored
├── rendered_audio/         Narration clips — gitignored
├── rendered_video/         Rendered shorts — gitignored
└── thumbnails/             Short thumbnails — gitignored
```

---

## Features

- **Proven 6-phase viral formula** — Declare/Assess/Isolate/Process/Build/Reveal, target 60s / max 180s
- **Vertical 9:16, 1080p** — built for YouTube Shorts
- **Two generation modes per run** — AI video clips (Higgsfield) or images-only (Ken Burns)
- **RSS money-exploit scanner** — 30+ feeds, keyword-scored, 2-week "no" suppression
- **Small local LLM** — Gemma 4 writes script/title/description/tags (no cloud LLM bills)
- **Word-level animated subtitles** — faster-whisper + 6 ASS styles
- **Arcane + selectable styles** — same system as Split Node, custom styles persist
- **Live price monitor** — video-model cost re-queried every run, change → warning
- **Story-adaptive SA3 music bed** — Stable Audio 3, chunked, ducked under voice (local)
- **Auto-upload** — Split Node channel, 'Split Node Shorts' playlist, single-frame thumbnail
- **Resume-safe & headless** — RSS in, uploaded short out
