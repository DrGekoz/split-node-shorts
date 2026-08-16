"""Split Node Shorts - vertical AI money-exploit Shorts generator.

Pipeline (mirrors Split Node, but vertical 9:16 + Higgsfield backend):
  RSS scan (money exploits) -> LLM pick (Y/n, 2-week 'no' suppression)
  -> fetch article -> LLM 6-phase Shorts script (Declare/Assess/Isolate/
     Process/Build/Reveal, target ~60s, max 180s)
  -> Higgsfield images (nano_banana_flash 9:16, 1.5cr) with optional
     real-person refs + Arcane/selectable style
  -> Higgsfield video clips (kling3_0 9:16, duration per phase)
  -> PocketTTS narration (marius)
  -> ffmpeg vertical render (subtitles burned)
  -> thumbnail (single frame)
  -> YouTube upload -> Split Node channel, 'Split Node Shorts' playlist

Backends: IMAGE_BACKEND=codex (default, local Codex CLI GPT Image 2, no API
key) or higgsfield (nano_banana_flash) / gptimage2 (GPT Image 2 via higgsfield).
VIDEO stays higgsfield (wan3_0). Default is codex.
"""

import os, re, sys, json, ssl, random, time, subprocess, shutil, tempfile, math
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_DIR = Path(__file__).resolve().parent

# ---- env loader -----------------------------------------------------
def _load_dotenv():
    env = PROJECT_DIR / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
_load_dotenv()

# ---- dirs -----------------------------------------------------------
SHOTS_DIR = PROJECT_DIR / "shots"
RENDERED_AUDIO = PROJECT_DIR / "rendered_audio"
RENDERED_VIDEO = PROJECT_DIR / "rendered_video"
THUMBNAILS_DIR = PROJECT_DIR / "thumbnails"
VOICE_DIR = PROJECT_DIR / "voice_refs"
STYLE_DIR = PROJECT_DIR / "style_sheets"
for d in [SHOTS_DIR, RENDERED_AUDIO, RENDERED_VIDEO, THUMBNAILS_DIR, VOICE_DIR, STYLE_DIR]:
    d.mkdir(exist_ok=True)

USED_FILE = PROJECT_DIR / ".used_shorts.json"
REJECTED_FILE = PROJECT_DIR / ".rejected_shorts.json"
COUNTER_FILE = PROJECT_DIR / ".short_counter"
RESUME_FILE = PROJECT_DIR / ".resume_state.json"
CUSTOM_STYLES_FILE = STYLE_DIR / "custom_styles.json"

REJECT_COOLDOWN_DAYS = float(os.environ.get("REJECT_COOLDOWN_DAYS", "14"))  # 2 weeks

# ---- services -------------------------------------------------------
LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma-4-e4b-uncensored-hauhaucs-aggressive")

# ---- LLM backend selection (Joe 2026-08-16) ------------------------------
# Chosen at startup via _select_llm(): either LM Studio (a loaded local model)
# or Codex (a cloud OpenAI model, listed cheapest-first). _llm_chat dispatches
# to Codex when LLM_PROVIDER=='codex', else LM Studio with LLM_MODEL.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "").strip().lower()
NARRATIVE_MODEL = LLM_MODEL

# Approx USD per 1M input tokens for the Codex/OpenAI models that actually work
# on a ChatGPT account. Used ONLY to sort the Codex picker cheapest-first.
CODEX_MODEL_CATALOG = {
    "gpt-5.4": 1.25,   # tested default
    "gpt-5.3": 1.25,
    "gpt-5.2": 1.25,
    "gpt-5":   1.25,
    "gpt-5.5": 2.50,   # pricier
}


def _lmstudio_loaded_models() -> list:
    """IDs of the models currently loaded in LM Studio (/v1/models)."""
    try:
        req = urllib.request.Request(
            "http://localhost:1234/v1/models",
            headers={"User-Agent": "splitnode/1.1"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode())
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    except Exception:
        return []


def _select_llm() -> None:
    """Startup prompt: pick the LLM backend + model.
      1 = LM Studio (lists currently-loaded models, you pick)
      2 = Codex     (lists models sorted cheapest-first, you pick)
    LLM_PROVIDER + LLM_MODEL env vars skip the prompt (headless/cron runs)."""
    global LLM_PROVIDER, LLM_MODEL, NARRATIVE_MODEL
    if LLM_PROVIDER and LLM_MODEL:
        NARRATIVE_MODEL = LLM_MODEL
        print(f"  [LLM] backend={LLM_PROVIDER} model={NARRATIVE_MODEL} (env)")
        return
    print("\n  Select the LLM backend for this run:")
    print("    1) LM Studio  (local - shows loaded models, you pick)")
    print("    2) Codex      (cloud OpenAI - models sorted by cheapest)")
    choice = input("  LLM backend [1/2, Enter=LM Studio]: ").strip().lower()
    if choice in ("2", "codex"):
        _select_llm_codex()
    else:
        _select_llm_lmstudio()


def _select_llm_lmstudio() -> None:
    global LLM_PROVIDER, LLM_MODEL, NARRATIVE_MODEL
    models = _lmstudio_loaded_models()
    if not models:
        print("  [LLM] LM Studio not reachable / nothing loaded on :1234")
        LLM_PROVIDER = "lmstudio"
        LLM_MODEL = LLM_MODEL or "gemma-4-e4b-uncensored-hauhaucs-aggressive"
        NARRATIVE_MODEL = LLM_MODEL
        print(f"  [LLM] defaulting to LM Studio / {LLM_MODEL}")
        return
    print("  Loaded LM Studio models:")
    for i, m in enumerate(models, 1):
        print(f"    {i}) {m}")
    idx = input(f"  Pick model [1-{len(models)}, Enter={models[0]}]: ").strip()
    try:
        LLM_MODEL = models[int(idx) - 1]
    except (ValueError, IndexError):
        LLM_MODEL = models[0]
    LLM_PROVIDER = "lmstudio"
    NARRATIVE_MODEL = LLM_MODEL
    print(f"  [LLM] LM Studio -> {LLM_MODEL}")


def _select_llm_codex() -> None:
    global LLM_PROVIDER, LLM_MODEL, NARRATIVE_MODEL
    cat = sorted(CODEX_MODEL_CATALOG.items(), key=lambda kv: (kv[1], kv[0]))
    print("  Codex models (cheapest first):")
    for i, (m, price) in enumerate(cat, 1):
        star = "  (default)" if m == "gpt-5.4" else ""
        print(f"    {i}) {m:<10} ~${price:.2f}/1M in{star}")
    idx = input(f"  Pick model [1-{len(cat)}, Enter={cat[0][0]}]: ").strip()
    try:
        NARRATIVE_MODEL = cat[int(idx) - 1][0]
    except (ValueError, IndexError):
        NARRATIVE_MODEL = cat[0][0]
    LLM_PROVIDER = "codex"
    # Keep a valid LOCAL model so _llm_reachable()/aux probes don't break.
    if not LLM_MODEL:
        locals_ = _lmstudio_loaded_models()
        LLM_MODEL = (locals_[0] if locals_
                     else "gemma-4-e4b-uncensored-hauhaucs-aggressive")
    print(f"  [LLM] Codex -> {NARRATIVE_MODEL} (aux LM Studio -> {LLM_MODEL})")


def _codex_llm_chat(messages, max_tokens=900, temp=0.8) -> str:
    """Run an LLM prompt through the Codex CLI with the selected model.
    Mirrors _llm_chat's contract (returns text, or '' on failure) so callers'
    retry/fallback logic is untouched. System+user messages combined into ONE
    prompt and piped to codex on stdin via a temp file (the ep014 PowerShell
    arg-length fix)."""
    if not _codex_available():
        print("  [CODEX] codex CLI not found on PATH - falling back to LM Studio")
        return ""
    sys_p = next((m.get("content", "") for m in messages
                  if m.get("role") == "system"), "")
    user_p = "\n\n".join(m.get("content", "") for m in messages
                         if m.get("role") == "user")
    prompt = f"{sys_p}\n\n{user_p}".strip() if sys_p else user_p
    if not prompt:
        return ""
    import tempfile, uuid, subprocess
    _tmp = os.path.join(tempfile.gettempdir(),
                        f"codex_llm_{uuid.uuid4().hex[:8]}.txt")
    try:
        with open(_tmp, "w", encoding="utf-8") as _f:
            _f.write(prompt)
    except Exception as _e:
        print(f"  [CODEX] could not write prompt temp file: {_e}")
        return ""
    ps_cmd = (f"Get-Content -Raw '{_tmp}' | codex exec --skip-git-repo-check "
              f"-c 'model=\"{NARRATIVE_MODEL}\"'")
    try:
        proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_cmd],
                              capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        print(f"  [CODEX] timed out on LLM call ({NARRATIVE_MODEL})")
        try:
            os.remove(_tmp)
        except Exception:
            pass
        return ""
    try:
        os.remove(_tmp)
    except Exception:
        pass
    out = (proc.stdout or "").strip()
    out = re.sub(r"^```[a-zA-Z]*\s*", "", out)
    out = re.sub(r"\s*```$", "", out).strip()
    return out
POCKET_TTS_URL = os.environ.get("POCKET_TTS_URL", "http://127.0.0.1:8769")
# Voice clones (Joe 2026-08-14): reuse Split Node's two clones instead of the
# generic built-in 'marius'. The DECLARE/hook phase uses the announcement INTRO
# voice; every other phase uses the storytelling STORY voice. Fall back to the
# built-in catalog name if the clone files are missing.
_TTS_INTRO = os.environ.get("TTS_VOICE_INTRO",
                            r"F:\aaaaaVIBECODING\System Breakers\voice_refs\split_node_intro.wav")
_TTS_STORY = os.environ.get("TTS_VOICE_STORY",
                            r"F:\aaaaaVIBECODING\System Breakers\voice_refs\split_node_story.wav")
TTS_VOICE = os.environ.get("TTS_VOICE", "marius")

# ---- channel / branding --------------------------------------------
CHANNEL_NAME = os.environ.get("CHANNEL_NAME", "Split Node")
YOUTUBE_PLAYLIST = os.environ.get("YOUTUBE_PLAYLIST", "Split Node Shorts")
YOUTUBE_CREDENTIALS = Path.home() / ".youtube-upload-credentials.json"
DISCORD_INVITE = os.environ.get("DISCORD_INVITE", "https://discord.gg/YSdqKR4wVB")
UPLOAD_ENABLED = os.environ.get("YOUTUBE_UPLOAD_ENABLED", "1") == "1"
YOUTUBE_BASE_TAGS = [
    "split node shorts", "money loophole", "ai shorts", "money hack", "beat the system",
    "exploit", "money secrets", "viral shorts", "ai documentary", "how to make money",
]

# ---- output (vertical only) ----------------------------------------
W_RES, H_RES = 1080, 1920          # 9:16 vertical
FPS = 30
# target 60s, hard max 180s
TARGET_SECONDS = float(os.environ.get("TARGET_SECONDS", "60"))
MAX_SECONDS = float(os.environ.get("MAX_SECONDS", "180"))
SECONDS_PER_LINE = 4.5             # ~narration pace for shorts
# per-run choice: generate AI video clips or images only. Env override:
#   GENERATE_VIDEOS=1  -> videos;  GENERATE_VIDEOS=0 -> images only.
GENERATE_VIDEOS = int(os.environ.get("GENERATE_VIDEOS", "1")) == 1

# ---- Higgsfield backend --------------------------------------------
# default model for images - cheaper of nano_banana_flash (1.5cr) / pro (2cr)
HIGGS_IMAGE_MODEL = os.environ.get("HIGGS_IMAGE_MODEL", "nano_banana_flash")
# VIDEO default: Wan 3.0 (5cr, cheapest of the options chosen by Joe). Price is
# re-queried on every run and a change is surfaced to the user.
HIGGS_VIDEO_MODEL = os.environ.get("HIGGS_VIDEO_MODEL", "wan3_0")
GPT_IMAGE_MODEL = os.environ.get("GPT_IMAGE_MODEL", "gpt_image_2")
IMAGE_BACKEND = os.environ.get("IMAGE_BACKEND", "codex").strip().lower()  # codex | higgsfield | gptimage2
VIDEO_BACKEND = os.environ.get("VIDEO_BACKEND", "higgsfield").strip().lower()
# Price-monitor state file: remembers the last-seen video model cost so a price
# change can be surfaced to the user on the next run.
PRICE_STATE_FILE = PROJECT_DIR / ".video_price_state.json"

# ---- RSS: TOPIC PACK 1 - MONEY EXPLOITS ----------------------------
# Formidable feed list so the scanner never runs dry.
MONEY_FEEDS = [
    # personal finance / money hacks
    "https://www.moneysavingexpert.com/latest-news/feed/",
    "https://www.thepennyhoarder.com/feed/",
    "https://wallethacks.com/feed/",
    "https://www.moneycrashers.com/feed/",
    "https://www.nerdwallet.com/blog/feed/",
    "https://www.bankrate.com/feed/",
    "https://www.kiplinger.com/feed/",
    "https://money.com/feed/",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "https://www.businessinsider.com/personal-finance/rss",
    "https://www.forbes.com/money/feed/",
    "https://www.fool.com/feed/",
    # consumer / scams / fraud (money exploits live here)
    "https://www.consumer.ftc.gov/blog/feed",
    "https://krebsonsecurity.com/feed/",
    "https://www.scamwatch.gov.au/feed/",
    "https://www.aarp.org/money/scams-fraud/info-2019/feed/",
    "https://www.theguardian.com/money/rss",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    # deals / coupons / glitches
    "https://thekrazycouponlady.com/feed/",
    "https://hip2save.com/feed/",
    "https://www.bradsdeals.com/feed",
    # lifestyle / frugal
    "https://www.reddit.com/r/personalfinance/.rss",
    "https://www.reddit.com/r/Frugal/.rss",
    "https://www.reddit.com/r/beermoney/.rss",
    "https://www.reddit.com/r/churning/.rss",
    "https://www.reddit.com/r/UnethicalLifeProTips/.rss",
    "https://www.reddit.com/r/lifehacks/.rss",
    "https://www.reddit.com/r/CreditCards/.rss",
    # general news (money exploits surface here)
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.theguardian.com/world/rss",
    "https://feeds.washingtonpost.com/rss/world",
    "https://www.independent.co.uk/news/business/rss",
    "https://apnews.com/apf-finance/feed",
]

# keyword tiers - strong phrases weigh far more than weak ones
MONEY_KEYWORDS_STRONG = [
    "loophole", "exploit", "refund", "glitch", "scam", "fraud", "class action",
    "million", "millions", "billion", "free money", "payout", "settlement",
    "churning", "arbitrage", "cash back", "cashback", "cashed out", "for free",
    "got away", "beat the system", "insider", "breach", "pays you",
]
MONEY_KEYWORDS_WEAK = [
    "money", "bank", "credit", "coupon", "deal", "discount", "invest", "savings",
    "refund", "wallet", "cash", "points", "airline", "hotel", "loyalty", "reward",
    "price", "tax", "insurance", "subscribe", "trick", "secret", "hack",
    "overcharge", "hidden fee", "avoid", "save", "make money", "income",
]
MONEY_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "with", "how", "why",
    "what", "your", "you", "this", "that", "are", "was", "were", "is", "in",
    "on", "at", "from", "by", "it", "be", "as", "will", "can", "have", "has",
}

# ---- styles (Arcane default + others, selectable like Split Node) --
STYLE_PROFILES = {
    "arcane": (
        "Stylized painterly 3D animation, bold inked outlines, cel-shaded "
        "graphic-novel texture, gritty weathered surfaces, dramatic rim lighting, "
        "saturated slightly-dirty colors, cinematic video-game concept art "
        "finish, NO TEXT, no words, no letters, no captions, no watermarks, no logos"),
    "bold-outline": (
        "bold thick black outlines, flat cel-shaded color, comic book illustration, "
        "high contrast, clean graphic shapes, dynamic angles, dramatic lighting, high detail"),
    "artsy": (
        "loose expressive brushstrokes, impressionistic painterly texture, visible "
        "canvas weave, warm muted palette, soft atmospheric light, hand-painted "
        "fine-art look, high detail"),
    "photoreal": (
        "hyper-realistic photograph, tack-sharp focus, natural skin texture, cinematic "
        "color grade, shallow depth of field, subtle film grain, high detail, "
        "professional documentary photography"),
    "noir": (
        "black and white film noir, dramatic low-key lighting, deep crushed shadows, "
        "hard contrast, gritty textured grain, moody shadows, high detail"),
    "synthwave": (
        "retro synthwave aesthetic, neon glow, purple and pink palette, chrome "
        "reflections, glowing grid floor, 1980s retro-futurism, high detail"),
}

def _load_style_profiles() -> dict:
    merged = dict(STYLE_PROFILES)
    try:
        if CUSTOM_STYLES_FILE.is_file():
            custom = json.loads(CUSTOM_STYLES_FILE.read_text(encoding="utf-8"))
            if isinstance(custom, dict):
                for k, v in custom.items():
                    if isinstance(v, str) and v.strip():
                        merged[k.strip().lower()] = v.strip()
    except Exception:
        pass
    return merged

def _active_style_name() -> str:
    return os.environ.get("STYLE", "").strip().lower() or "arcane"

def _style_descriptor() -> str:
    profiles = _load_style_profiles()
    return profiles.get(_active_style_name(), profiles.get("arcane", ""))

def add_custom_style(name: str, descriptor: str) -> bool:
    name = name.strip().lower(); descriptor = descriptor.strip()
    if not name or not descriptor:
        return False
    if name in STYLE_PROFILES:
        return False
    profiles = {}
    try:
        if CUSTOM_STYLES_FILE.is_file():
            profiles = json.loads(CUSTOM_STYLES_FILE.read_text(encoding="utf-8"))
    except Exception:
        profiles = {}
    if not isinstance(profiles, dict):
        profiles = {}
    profiles[name] = descriptor
    CUSTOM_STYLES_FILE.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    print(f"  [STYLE] added '{name}' -> selectable via STYLE={name}")
    return True


# Hands/anatomy hardening (ported from Split Node Bug 3, Joe 2026-08-14):
# stylized image models (Arcane etc.) hallucinate hands/fingers on shots that
# show them. When a scene's narration references hands/clicking/typing, append
# an explicit anatomy-correct-hands clause so the model keeps fingers right.
def _scene_shows_hands(text: str) -> bool:
    t = (text or "").lower()
    return bool(re.search(
        r"\b(hand|hands|fingers|fingertips|click|clicking|clicks|typing|types|"
        r"taps|tapping|presses|press|button|grab|grabbing|hold|holding|"
        r"clutch|grip|writes|wrote|signs|signing|counts?|cash|stacks|fist)\b", t))

def _hands_clause() -> str:
    return (" Anatomy-correct hands: exactly five natural fingers per hand, "
            "correct proportions, no extra, fused, webbed or claw-like fingers, "
            "no deformed or misplaced digits.")


# ---- LLM (gemma 4 uncensored via LM Studio) ------------------------
def _llm_chat(messages, max_tokens=900, temp=0.8) -> str:
    if LLM_PROVIDER == "codex":
        return _codex_llm_chat(messages, max_tokens=max_tokens, temp=temp)
    data = json.dumps({
        "model": LLM_MODEL, "messages": messages,
        "max_tokens": max_tokens, "temperature": temp,
    }).encode()
    req = urllib.request.Request(LM_STUDIO_URL, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            result = json.loads(r.read())
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [LLM error] {e}")
        return ""

def _llm_reachable() -> bool:
    """Liveness probe of LM Studio (ported from Split Node 2026-08-09).

    Probes the CHAT endpoint (NOT /v1/models) with a short timeout: /v1/models
    can still respond while inference is dead/hung, which would let the gate
    pass and then block on a 180s per-call timeout on every subsequent LLM call.
    A tiny chat call is the real liveness test.
    """
    if LLM_PROVIDER == "codex":
        return _codex_available()
    try:
        _payload = {"model": LLM_MODEL,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 2, "temperature": 0.1}
        req = urllib.request.Request(LM_STUDIO_URL, data=json.dumps(_payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False

def _llm_json(messages, max_tokens=1200, temp=0.5) -> dict:
    text = _llm_chat(messages, max_tokens=max_tokens, temp=temp)
    text = re.sub(r"```json|```", "", text).strip()
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except Exception:
        return {}


# ---- RSS scan (money exploits) --------------------------------------
def _fetch_rss(feed_url):
    print(f"  [RSS] {feed_url}")
    try:
        ssl_ctx = ssl._create_unverified_context()
        req = urllib.request.Request(feed_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 SplitNodeShorts/1.0"})
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            desc = item.findtext("description", "")
            date = item.findtext("pubDate", "") or ""
            if title and link:
                items.append({"title": title, "link": link,
                              "description": desc, "date": date})
        if not items:
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                title = entry.findtext("{http://www.w3.org/2005/Atom}title", "")
                link = (entry.find("{http://www.w3.org/2005/Atom}link") or {}).get("href", "") \
                    if entry.find("{http://www.w3.org/2005/Atom}link") is not None else ""
                date = entry.findtext("{http://www.w3.org/2005/Atom}updated", "")
                if title and link:
                    items.append({"title": title, "link": link,
                                  "description": "", "date": date})
        return items
    except Exception as e:
        print(f"  [RSS] failed: {str(e)[:50]}")
        return []

def _money_score(title, desc):
    text = f"{title} {desc}".lower()
    strong = sum(1 for k in MONEY_KEYWORDS_STRONG if k in text)
    weak = sum(1 for k in MONEY_KEYWORDS_WEAK if k in text)
    score = strong * 30 + weak * 10
    if strong == 0 and weak == 0:
        return 0
    # top-of-funnel filter: title itself should hint at money
    if not any(k in title.lower() for k in MONEY_KEYWORDS_STRONG + MONEY_KEYWORDS_WEAK):
        score *= 0.5
    return score

def _load_used() -> set:
    if USED_FILE.is_file():
        try:
            return set(json.loads(USED_FILE.read_text()))
        except Exception:
            return set()
    return set()

def _save_used(url):
    used = _load_used(); used.add(url)
    USED_FILE.write_text(json.dumps(sorted(used), indent=2))

def _load_rejected() -> dict:
    """{url: iso timestamp} pruned to entries newer than the 2-week cooldown."""
    if REJECTED_FILE.is_file():
        try:
            data = json.loads(REJECTED_FILE.read_text())
            cutoff = datetime.now(timezone.utc) - timedelta(days=REJECT_COOLDOWN_DAYS)
            pruned = {}
            for k, v in data.items():
                try:
                    ts = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts >= cutoff:
                        pruned[k] = v
                except Exception:
                    continue
            return pruned
        except Exception:
            pass
    return {}

def _save_rejected(url):
    rejected = _load_rejected()
    rejected[url] = datetime.now(timezone.utc).isoformat()
    REJECTED_FILE.write_text(json.dumps(rejected, indent=2))

def _scan_money_candidates(used, rejected):
    """Scan feeds for fresh money-exploit stories.

    Dedupe + freshness (Joe 2026-08-14): dedupe by BOTH link AND a normalized
    title (the same story circulates across many money feeds with slightly
    different URLs), and drop anything older than FRESHNESS_DAYS so we never
    re-tell last week's headline. Recency-first, score tiebreak."""
    candidates = []
    seen_links = set()
    seen_titles = set()
    freshness_days = float(os.environ.get("FRESHNESS_DAYS", "14"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=freshness_days)

    def _norm_title(t):
        return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()[:60]

    feeds = list(MONEY_FEEDS); random.shuffle(feeds)
    for feed in feeds:
        for it in _fetch_rss(feed):
            link = it["link"]
            nt = _norm_title(it["title"])
            if link in used or link in rejected or link in seen_links:
                continue
            if nt and nt in seen_titles:
                continue  # same story from another feed
            # freshness filter: skip stories older than the cutoff
            try:
                d = datetime.strptime(it.get("date", ""), "%a, %d %b %Y %H:%M:%S %z")
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                if d < cutoff:
                    continue
            except Exception:
                pass  # unparseable date -> keep (can't judge freshness)
            score = _money_score(it["title"], it.get("description", ""))
            if score < 30:
                continue
            it["score"] = score
            seen_links.add(link)
            if nt:
                seen_titles.add(nt)
            candidates.append(it)
        if len(candidates) >= 15:
            break
        time.sleep(0.3)
    # recency-first, score tiebreak
    def _date(it):
        try:
            return datetime.strptime(it.get("date", ""), "%a, %d %b %Y %H:%M:%S %z")
        except Exception:
            return datetime(1970, 1, 1)
    candidates.sort(key=lambda it: (str(_date(it)), it["score"]), reverse=True)
    return candidates


# ---- story pick (Y/n, 2-week 'no' suppression) ---------------------
def _pick_story():
    """Pick a money-exploit story with user confirmation.

    Joe 2026-08-14: each candidate is PARSED (article fetched + extracted)
    BEFORE it is presented to the user. A link that fails to resolve (blocked,
    dead, paywalled, empty) is auto-skipped to the next candidate with no
    prompt - only working links are offered. Returns (url, title, paragraphs)
    on accept, or ("", "", []) on abort.
    """
    used = _load_used()
    rejected = _load_rejected()
    rejected_set = set(rejected.keys())

    print("\n[STORY] Pick a topic source:")
    print("  [RSS]  scan feeds for a money-exploit story")
    print("  [URL]  enter your own article URL")
    src = input("  Enter a URL, or press Enter for RSS: ").strip().strip('"\'')
    if src and src.lower().startswith(("http://", "https://")):
        title = _fetch_page_title(src)
        paras = fetch_article_paragraphs(src)
        if not paras:
            print(f"  [RESOLVE] custom article did not resolve - aborting")
            return "", "", []
        _save_used(src)
        return src, title, paras

    print("\n[RSS] Scanning money-exploit feeds...")
    pool = _scan_money_candidates(used, rejected_set)
    if not pool:
        print("  [FAIL] No money-exploit stories found. Try again later.")
        return "", "", []
    print(f"  [RSS] {len(pool)} candidate stories found\n")

    pool_idx, rounds = 0, 0
    while True:
        if pool_idx >= len(pool):
            rounds += 1
            if rounds >= 6:
                print("  [FAIL] Ran out of stories after 6 re-polls.")
                return "", "", []
            print(f"\n  [RSS] Pool exhausted. Re-polling feeds...")
            time.sleep(2)
            pool = _scan_money_candidates(used, rejected_set)
            pool_idx = 0
            if not pool:
                return "", "", []
        chosen = pool[pool_idx]; pool_idx += 1
        # PARSE BEFORE PRESENTING (Joe 2026-08-14): auto-skip links that don't
        # resolve, only offer the user working stories.
        paras = fetch_article_paragraphs(chosen["link"])
        if not paras:
            print(f"  [AUTO-SKIP] article did not resolve (blocked/no content): "
                  f"{chosen['link'][:70]}")
            _save_rejected(chosen["link"])
            rejected_set.add(chosen["link"])
            continue
        print(f"  {'='*58}")
        print(f"  CANDIDATE STORY:")
        print(f"    {chosen['title']}")
        print(f"    {chosen['link']}")
        print(f"    [money_score={chosen['score']}]  [resolved: {len(paras)} paragraphs]")
        print(f"  {'='*58}")
        resp = input("  Use this topic? (Y/n/q): ").strip().lower()
        if resp in ("q", "quit"):
            print("  [SKIP] Aborted")
            return "", "", []
        if resp in ("", "y", "yes"):
            _save_used(chosen["link"])
            return chosen["link"], chosen["title"], paras
        # user said no - suppress for 2 weeks
        _save_rejected(chosen["link"])
        rejected_set.add(chosen["link"])
        print("  [NO] Rejected - hidden for 2 weeks")


def _fetch_page_title(url):
    try:
        ssl_ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
            html = r.read().decode("utf-8", errors="ignore")
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()[:120]
    except Exception:
        pass
    return url[:120]


# ---- Shorts script (6-phase formula) --------------------------------
SHORTS_SCRIPT_SYSTEM = (
    "You write viral YouTube SHORTS scripts for 'Split Node Shorts', a channel that "
    "tells true stories of ordinary people who beat money systems - loopholes, glitches, "
    "refunds, exploits, frauds, class actions. Vertical 9:16 format.\n\n"
    "Use the PROVEN 6-PHASE formula (Brazzers / Jack Craig method that generates "
    "millions of views):\n"
    "1. DECLARE - cold open with an absurd declaration that hooks in the first 2 "
    "seconds (a big specific number, an impossible-sounding claim).\n"
    "2. ASSESS - inspect the system / the scam / the exploit.\n"
    "3. ISOLATE - the single trick or loophole, called out clearly.\n"
    "4. PROCESS - the step-by-step execution (fast, rhythmic).\n"
    "5. BUILD - the parts coming together toward the win.\n"
    "6. REVEAL - the final result / payout / twist. End with a completion beat that "
    "loops back ('but the story doesn't end there' hook or a follow-up tease).\n\n"
    "HARD RULES:\n"
    "- Each line is a SEPARATE scene/image. One clear visual per line.\n"
    "- Target {target}s total, HARD MAX {max}s. ~{spl}s per line -> aim for "
    "{nlines} lines. Trim ruthlessly.\n"
    "- First line is the DECLARATION hook (2-5 words, big number).\n"
    "- Spoken-word friendly: short punchy lines, no em dashes.\n"
    "- Label each scene with a phase tag at the start, e.g. 'DECLARE: ...'.\n"
    "- Provide a 'NUMBER' field = the single absurd number from the hook.\n"
    "- Provide a 'TITLE' = the video title.\n"
    "Return STRICT JSON only:\n"
    "{{\"title\":\"...\", \"number\":\"...\", \"scenes\":[{{\"phase\":\"DECLARE\","
    "\"text\":\"line\"}}, ...]}}"
).format(target=int(TARGET_SECONDS), max=int(MAX_SECONDS),
         spl=SECONDS_PER_LINE, nlines=max(3, int(TARGET_SECONDS / SECONDS_PER_LINE)))


# SECOND script template (Joe 2026-08-14): break the 6-phase monotony. Same
# JSON schema (title/number/scenes[{phase,text}]) so _build_script + the whole
# downstream parse is IDENTICAL - only the story shape differs. This one opens
# on the human moment / problem first (relatable cold-open), then escalates to
# the reveal, instead of leading with the absurd declaration. Rotated against
# the 6-phase template via _script_template() so the feed never feels like a loop.
SHORTS_SCRIPT_SYSTEM_STORYFIRST = (
    "You write viral YouTube SHORTS scripts for 'Split Node Shorts', a channel that "
    "tells true stories of ordinary people who beat money systems - loopholes, glitches, "
    "refunds, exploits, frauds, class actions. Vertical 9:16 format.\n\n"
    "Use the STORY-FIRST formula (relatable cold-open -> escalation -> reveal). "
    "It hooks through empathy and curiosity rather than an absurd number:\n"
    "1. HOOK - open on the ordinary person in a relatable moment: the struggle, the "
    "tight spot, the unfair rule they're stuck with. Make the viewer think 'that's me'. "
    "Land this in the first 2 seconds.\n"
    "2. THE RULE - name the system/rule/scam that's holding them back, plainly.\n"
    "3. THE LOOPHOLE - the single overlooked trick or exception they spot in the fine print.\n"
    "4. THE PLAN - the step-by-step execution (fast, rhythmic).\n"
    "5. THE RISK - the near-miss, the almost-caught, the moment it could all collapse.\n"
    "6. THE WIN - the final payout / twist. End with a completion beat that loops back "
    "('but the story doesn't end there' or a follow-up tease).\n\n"
    "HARD RULES:\n"
    "- Each line is a SEPARATE scene/image. One clear visual per line.\n"
    "- Target {target}s total, HARD MAX {max}s. ~{spl}s per line -> aim for "
    "{nlines} lines. Trim ruthlessly.\n"
    "- First line is the HOOK (a relatable human moment, 2-5 words, no number needed).\n"
    "- Spoken-word friendly: short punchy lines, no em dashes.\n"
    "- Label each scene with a phase tag at the start, e.g. 'HOOK: ...'.\n"
    "- Provide a 'NUMBER' field = a specific figure from the story (the payout, the "
    "loophole size, the fee dodged) if one exists, else an empty string.\n"
    "- Provide a 'TITLE' = the video title.\n"
    "Return STRICT JSON only:\n"
    "{{\"title\":\"...\", \"number\":\"...\", \"scenes\":[{{\"phase\":\"HOOK\","
    "\"text\":\"line\"}}, ...]}}"
).format(target=int(TARGET_SECONDS), max=int(MAX_SECONDS),
         spl=SECONDS_PER_LINE, nlines=max(3, int(TARGET_SECONDS / SECONDS_PER_LINE)))


def _script_template() -> str:
    """Pick the script-writing template for this run. Rotates between the
    6-phase and story-first templates so consecutive Shorts don't feel like a
    loop (Joe 2026-08-14). Env override: SHORTS_TEMPLATE=6phase | storyfirst
    pins one; SHORTS_TEMPLATE=alternate toggles each run (needs SHORTS_TEMPLATE_STATE
    writable); default = alternate. All templates share the same JSON schema."""
    mode = os.environ.get("SHORTS_TEMPLATE", "alternate").strip().lower()
    if mode == "6phase":
        return SHORTS_SCRIPT_SYSTEM
    if mode == "storyfirst":
        return SHORTS_SCRIPT_SYSTEM_STORYFIRST
    # alternate: flip a persisted flag so the feed genuinely alternates.
    flag = os.environ.get("SHORTS_TEMPLATE_STATE",
                          str(PROJECT_DIR / ".template_state"))
    use_story = False
    try:
        if os.path.isfile(flag):
            use_story = open(flag).read().strip() != "story"
    except Exception:
        pass
    try:
        with open(flag, "w") as f:
            # store which template we are ABOUT to use so the NEXT run flips
            f.write("story" if use_story else "6phase")
    except Exception:
        pass
    return SHORTS_SCRIPT_SYSTEM_STORYFIRST if use_story else SHORTS_SCRIPT_SYSTEM


def _build_script(topic, article_url, content):
    msg = [
        {"role": "system", "content": _script_template()},
        {"role": "user", "content": (
            f"Story/topic: {topic}\nSource: {article_url}\n\n"
            f"Article content (for facts, keep it true):\n{content[:3000]}\n\n"
            "Write the Shorts script now. STRICT JSON only.")}
    ]
    data = _llm_json(msg, max_tokens=1400, temp=0.85)
    return data


# ---- article fetch --------------------------------------------------
# Junk-paragraph filter ported from Split Node (Joe 2026-08-14): strips
# boilerplate/nav/promo/paywall/consent noise from the article so only real
# story content reaches the script LLM. Improves script factual quality.
JUNK_PATTERNS = [
    r'\b(cookie (policy|notice|consent|banner|preferences)|accept (all )?cookies|we use cookies)\b',
    r'\bsubscribe\b', r'\bnewsletter\b', r'\bsign\s?up\b', r'\blog\s?in\b', r'\bsign\s?in\b',
    r'\bcreate (a|an) (free )?account\b', r'\balready (have|a) (an )?account\b',
    r'\b(privacy policy|terms of (service|use|conditions))\b',
    r'\bsponsor(ed)?\s*(content|post|story)?\b', r'\badvertisement\b',
    r'\b(related (articles?|stories?|posts?|content)|you might also like|you may also like|more (from|on|like this))\b',
    r'\brecommended for you\b', r'\btrending (now|stories)?\b', r'\bmost (read|popular|viewed)\b',
    r'\bread more\b', r'\bcontinue reading\b', r'\bshare (this|the) (article|story|post)\b',
    r'\bfollow (us|her|him|them) on\b',
    r'\b(download (the|our) app|get the app|available on (ios|android|the app store|google play))\b',
    r'\b(unlimited access|digital access|subscription required|become a (member|subscriber)|already a subscriber|subscribe now)\b',
    r'\b(paywall|premium (content|article|subscriber))\b',
    r'\b(all rights reserved)\b', r'\b©\b', r'\bclick here\b',
    r'\bopens? in a new (tab|window)\b', r'\b(contact us|send us a tip|email us|feedback|corrections?)\b',
    r'\b(photo credits?|image credits?|credit:)\b', r'\b(editor\s?\'?s? note|disclosure)\b',
]

def _is_junk_paragraph(text: str) -> bool:
    """Heuristic junk filter: boilerplate, nav, promo, ads, contact noise, bylines."""
    low = text.lower()
    if any(skip in low for skip in [
        'url(', '.css', 'javascript', '{', ';}', 'no-repeat',
        'margin:', 'padding:', 'border:', 'width:', 'height:'
    ]):
        return True
    for pat in JUNK_PATTERNS:
        if re.search(pat, low):
            return True
    if len(text) > 40 and text == text.upper():
        return True
    if re.match(r"^[Bb]y\s+[A-Z]\.?(?:[a-zA-Z'\-\.]*\s+)?[A-Z][a-zA-Z'\-\.]*(\s+[A-Z]\.?[a-zA-Z'\-\.]*){0,4}\.?$", text):
        return True
    if re.search(r'\bis (a|an|the)?\s*(staff|senior|contributing|freelance|award-winning)?\s*(writer|reporter|journalist|editor|correspondent|columnist)\s+(at|for|with)\b', low):
        return True
    if re.search(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b', text):
        return True
    if len(text) < 20:
        return True
    return False


def fetch_article_paragraphs(url):
    try:
        ssl_ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20, context=ssl_ctx) as r:
            html = r.read().decode("utf-8", errors="ignore")
        html = re.sub(r"(?is)<(script|style|nav|footer|header|aside|form|figure|iframe)[^>]*>.*?</\1>", " ", html)
        paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.S | re.I)
        out = []
        for p in paras:
            txt = re.sub(r"<[^>]+>", " ", p)
            txt = re.sub(r"\s+", " ", txt).strip()
            if _is_junk_paragraph(txt):
                continue
            if len(txt) > 60 and len(out) < 30:
                out.append(txt)
        return out
    except Exception as e:
        print(f"  [FETCH] {e}")
        return []


# ---- Higgsfield generation -----------------------------------------
def _hf(args):
    """Run a higgsfield CLI command, capture output, return (exit, text).
    Invokes node directly on the CLI JS entry (Windows npm-shim PATH resolution
    fails inside Python subprocess, so we bypass the shim entirely)."""
    cli_js = _find_higgsfield_js()
    if not cli_js:
        return 1, "higgsfield CLI not found (npm i -g @higgsfield/cli)"
    cmd = ["node", cli_js] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                           shell=False)
    except Exception as e:
        return 1, f"higgsfield invoke error: {e}"
    return r.returncode, (r.stdout or "") + (r.stderr or "")

_HIGGSFIELD_JS_CACHE = None
def _find_higgsfield_js() -> str:
    """Locate higgsfield's CLI JS entry point. Env override HIGGSFIELD_JS wins;
    else scan the npm global root and a couple of known locations."""
    global _HIGGSFIELD_JS_CACHE
    if _HIGGSFIELD_JS_CACHE:
        return _HIGGSFIELD_JS_CACHE
    cands = [os.environ.get("HIGGSFIELD_JS", "")]
    # npm global root
    try:
        root = subprocess.run(["npm", "prefix", "-g"], capture_output=True,
                              text=True, timeout=30).stdout.strip()
        if root:
            cands.append(os.path.join(root, "node_modules", "@higgsfield", "cli",
                                      "bin", "higgsfield.js"))
    except Exception:
        pass
    for base in [r"C:\nvm4w\nodejs", r"C:\nvm\nodejs", r"C:\Users\josep\AppData\Roaming\npm",
                 r"C:\Users\josep\AppData\Local\nvm\v24.15.0"]:
        cands.append(os.path.join(base, "node_modules", "@higgsfield", "cli",
                                  "bin", "higgsfield.js"))
    for c in cands:
        if c and os.path.isfile(c):
            _HIGGSFIELD_JS_CACHE = c
            return c
    return ""

def _query_model_cost(model: str, extra_args=None) -> float:
    """Query the live credit cost of a model (no credits spent). Returns float
    or 0.0 if it can't be determined."""
    args = ["generate", "cost", model, "--prompt", "test"]
    if extra_args:
        args += extra_args
    rc, out = _hf(args)
    if rc != 0:
        return 0.0
    m = re.search(r"([\d.]+)\s*credits?", out)
    return float(m.group(1)) if m else 0.0

def _check_video_price():
    """Ping the REAL price of the video model each run. Surfaces a clear warning
    if it changed since the last run (Joe: notify me if the price ever changes).
    Always prints the current price. Reports the per-second rate (credit/sec),
    the meaningful number for video models which are billed by duration.
    Returns the per-second cost in credits."""
    cost = _query_model_cost(HIGGS_VIDEO_MODEL,
                             ["--duration", "2"] if HIGGS_VIDEO_MODEL in ("wan3_0", "kling3_0_turbo") else None)
    per_sec = round(cost / 2.0, 2) if cost > 0 else 0.0
    last = None
    if PRICE_STATE_FILE.is_file():
        try:
            last = json.loads(PRICE_STATE_FILE.read_text()).get("per_sec")
        except Exception:
            last = None
    if per_sec > 0:
        if last is None:
            print(f"  [PRICE] {HIGGS_VIDEO_MODEL} = {per_sec} credits/sec (baseline set)")
        elif abs(float(last) - per_sec) > 1e-9:
            print("  " + "=" * 52)
            print(f"  [PRICE CHANGE] {HIGGS_VIDEO_MODEL} price moved!")
            print(f"    was {last} credits/sec -> now {per_sec} credits/sec")
            print("  " + "=" * 52)
        else:
            print(f"  [PRICE] {HIGGS_VIDEO_MODEL} = {per_sec} credits/sec (unchanged)")
        try:
            PRICE_STATE_FILE.write_text(json.dumps({"model": HIGGS_VIDEO_MODEL,
                                                    "per_sec": per_sec,
                                                    "checked": datetime.now(timezone.utc).isoformat()},
                                                   indent=2))
        except Exception:
            pass
    else:
        print(f"  [PRICE] could not query {HIGGS_VIDEO_MODEL} cost")
    return per_sec

# Codex output-claiming is shared across parallel threads (each call records
# the PNGs present before it runs, generates, then claims the newest file that
# is new AND not already claimed by another thread).
_CODEX_LOCK = None
_CODEX_CLAIMED = set()


def _codex_lock():
    global _CODEX_LOCK
    if _CODEX_LOCK is None:
        import threading
        _CODEX_LOCK = threading.Lock()
    return _CODEX_LOCK


def _codex_available() -> bool:
    try:
        import shutil
        return shutil.which("codex") is not None or shutil.which("codex.exe") is not None
    except Exception:
        return False


def _generate_image_codex(prompt, out_path, timeout=900):
    """Generate one image via the OpenAI Codex CLI (/imagegen -> GPT Image 2).

    Codex CLI 0.147+ does NOT print a "Saved at:" path for a fresh generation -
    it just reports "Generated the image...". The PNG lands in a fresh uuid dir
    under ~/.codex/generated_images/<uuid>/call_*.png. We snapshot the PNG set
    BEFORE the call, then claim the NEWEST png that is new since the snapshot
    and not already claimed by a concurrent thread. No API key needed.
    """
    import glob
    import shutil
    import subprocess
    import tempfile
    import uuid
    if not _codex_available():
        print("  [IMG] codex CLI not found on PATH - install with: npm install -g @openai/codex")
        return False
    generated = Path.home() / ".codex" / "generated_images"
    generated.mkdir(parents=True, exist_ok=True)

    def _snapshot() -> dict:
        m = {}
        for p in (glob.glob(str(generated / "**" / "call_*.png"), recursive=True)
                  + glob.glob(str(generated / "**" / "ig_*.png"), recursive=True)):
            if os.path.isfile(p):
                m[os.path.abspath(p)] = os.path.getmtime(p)
        return m

    with _codex_lock():
        before = _snapshot()

    _tmp = os.path.join(tempfile.gettempdir(), f"codex_payload_{uuid.uuid4().hex[:8]}.txt")
    with open(_tmp, "w", encoding="utf-8") as _f:
        _f.write("/imagegen " + prompt)
    try:
        ps_cmd = f"Get-Content -Raw '{_tmp}' | codex exec --skip-git-repo-check"
        proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_cmd],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print("  [IMG] codex timed out generating image")
        try:
            os.remove(_tmp)
        except Exception:
            pass
        return False
    try:
        os.remove(_tmp)
    except Exception:
        pass
    out_text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "",
                      (proc.stdout or "") + "\n" + (proc.stderr or ""))
    # Rate-limit / failure detection (before anything else).
    if re.search(r"(?i)rate\s*limit|429|too\s*many\s*requests|quota|"
                 r"limit\s*exceeded|capacity|temporarily\s*unavailable|"
                 r"overloaded|slow\s*down|try\s*again\s*in", out_text):
        print("  [IMG] codex rate-limited - will retry this image")
        return False
    # Poll briefly for the new PNG to appear (Windows flushes async).
    src = None
    for _i in range(int(os.environ.get("CODEX_FLUSH_WAIT", "15"))):
        with _codex_lock():
            after = _snapshot()
        cands = []
        for ap in after:
            if ap in before or ap in _CODEX_CLAIMED:
                continue
            cands.append((after[ap], ap))
        if cands:
            # Newest new file = this call's output (fresh uuid dir per call).
            cands.sort(reverse=True)
            ap = cands[0][1]
            with _codex_lock():
                if ap not in _CODEX_CLAIMED:
                    _CODEX_CLAIMED.add(ap)
                    src = ap
            if src:
                break
        if _i == 0:
            print("  [IMG] codex: waiting for image to flush to disk...")
        import time as _t
        _t.sleep(1)
    if src is None:
        print("  [IMG] codex could not deterministically locate this call's output - retrying")
        return False
    try:
        shutil.copy2(src, out_path)
    except Exception as e:
        print(f"  [IMG] codex copy failed: {e}")
        return False
    try:
        os.remove(src)
        try:
            os.rmdir(os.path.dirname(src))
        except Exception:
            pass
    except Exception:
        pass
    return os.path.isfile(out_path) and os.path.getsize(out_path) > 1000


_IMG_BAN_RE = re.compile(
    r"\b(unreal\s+engine(?:\s*5)?|machin(?:e|es|ery))\b", re.IGNORECASE)


def _sanitize_image_prompt(prompt):
    """Strip banned words ('unreal engine', 'machine') from an image/video prompt
    and tidy the spacing left behind (Joe 2026-08-15). These must never reach the
    visual generator."""
    if not prompt:
        return prompt
    p = _IMG_BAN_RE.sub("", prompt)
    p = re.sub(r"\s{2,}", " ", p)
    p = re.sub(r"\s+([,.;:!?])", r"\1", p)
    p = re.sub(r"([,.;:!?])\s*,", r"\1", p)
    return p.strip()


def _generate_image(prompt, out_path, refs=None):
    """Generate one vertical 9:16 image.

    Backend higgsfield -> nano_banana_flash (1.5cr); gptimage2 -> GPT Image 2;
    codex -> local Codex CLI /imagegen (GPT Image 2, no API key)."""
    prompt = _sanitize_image_prompt(prompt)
    if IMAGE_BACKEND == "codex":
        return _generate_image_codex(prompt, out_path)
    model = GPT_IMAGE_MODEL if IMAGE_BACKEND == "gptimage2" else HIGGS_IMAGE_MODEL
    cmd = ["generate", "create", model,
           "--prompt", prompt, "--aspect_ratio", "9:16", "--resolution", "2k",
           "--wait", "--wait-timeout", "20m"]
    if refs:
        for ref in refs:
            cmd += ["--image-references", str(ref)]
    rc, out = _hf(cmd)
    if rc != 0:
        print(f"  [IMG] {model} failed: {out[-300:]}")
        return False
    # extract the result file URL / save via upload->download not needed: CLI
    # prints the media URL. We re-fetch below into out_path if possible.
    url = _extract_media_url(out)
    if url:
        return _download(url, out_path)
    # no URL parse - look for a written file path
    return False

def _extract_media_url(out):
    m = re.search(r"(https?://[^\s\"']+\.(?:mp4|png|jpg|jpeg|webp|glb)[^\s\"']*)", out)
    if m:
        return m.group(1)
    m = re.search(r"(https?://[^\s\"']+)", out)
    return m.group(1) if m else None

def _download(url, out_path):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(out_path, "wb") as f:
            shutil.copyfileobj(r, f)
        return os.path.getsize(out_path) > 1000
    except Exception as e:
        print(f"  [DL] {e}")
        return False

def _generate_video(start_image, prompt, duration):
    """Generate a vertical 9:16 video clip via Higgsfield (default wan3_0, 5cr).
    duration clamped to the model's supported range (wan3_0: 2-30s)."""
    duration = max(2, min(int(round(duration)), 30))
    prompt = _sanitize_image_prompt(prompt)
    cmd = ["generate", "create", HIGGS_VIDEO_MODEL,
           "--prompt", prompt, "--aspect_ratio", "9:16",
           "--duration", str(duration),
           "--start-image", str(start_image),
           "--resolution", "1080p",
           "--generate_audio", "false",
           "--wait", "--wait-timeout", "20m"]
    rc, out = _hf(cmd)
    if rc != 0:
        print(f"  [VID] {HIGGS_VIDEO_MODEL} failed: {out[-300:]}")
        return None
    url = _extract_media_url(out)
    if not url:
        print(f"  [VID] no result URL: {out[-200:]}")
        return None
    out_path = str(SHOTS_DIR / f"clip_{len(os.listdir(SHOTS_DIR)):03d}.mp4")
    if _download(url, out_path):
        return out_path
    return None


# ---- TTS ------------------------------------------------------------
def _voice_for_phase(phase: str) -> str:
    """Pick the voice clone for a scene phase (Joe 2026-08-14): the DECLARE /
    hook cold-open uses the announcement INTRO voice, everything else uses the
    storytelling STORY voice. Falls back to the configured TTS_VOICE if the
    clone file for that phase is missing (so a missing clone never breaks TTS)."""
    phase = (phase or "").upper()
    if phase == "DECLARE" or phase == "HOOK":
        return _TTS_INTRO if os.path.isfile(_TTS_INTRO) else TTS_VOICE
    return _TTS_STORY if os.path.isfile(_TTS_STORY) else TTS_VOICE


def _tts(text, out_path, voice=None):
    """PocketTTS narration via multipart/form-data (the /tts endpoint expects
    multipart, NOT JSON — a JSON POST silently 422s and produces no audio).
    voice is a built-in catalog voice name (sent as voice_url) or a cloned
    .wav file path (sent as voice_wav). Defaults to TTS_VOICE."""
    try:
        import requests
        # multipart form fields: text (required), voice_url (built-in name) or
        # voice_wav (cloned clip file)
        data = {"text": text}
        files = {}
        voice = voice or TTS_VOICE
        if os.path.isfile(str(voice)):
            files["voice_wav"] = open(str(voice), "rb")
        else:
            data["voice_url"] = str(voice)
        r = requests.post(f"{POCKET_TTS_URL}/tts", data=data, files=files,
                          timeout=240)
        for f in files.values():
            try:
                f.close()
            except Exception:
                pass
        if r.status_code != 200:
            print(f"  [TTS] HTTP {r.status_code}: {r.text[:200]}")
            return False
        with open(out_path, "wb") as f:
            f.write(r.content)
        return os.path.getsize(out_path) > 1000
    except Exception as e:
        print(f"  [TTS] {e}")
        return False

def _audio_duration(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "default=nw=1:nk=1", path],
                           capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


# ---- ffmpeg vertical render ----------------------------------------
def _render(shots, script_data, output_path):
    """Render a vertical Short. Uses AI video clips when present, else Ken Burns
    (slow-zoom) on still images (images-only mode). Muxes TTS audio."""
    total = sum(s.get("dur", 0) for s in shots)
    print(f"\n[VIDEO] Rendering vertical Short ({_fmt(total)})...")

    clips = [s["clip"] for s in shots if s.get("clip") and os.path.isfile(s["clip"])]
    imgs = [s["image"] for s in shots if s.get("image") and os.path.isfile(s["image"])]
    if clips:
        return _render_from_clips(shots, clips, output_path, total)
    if imgs:
        return _render_kenburns(shots, imgs, output_path, total)
    print("  [FAIL] No video clips or images to render")
    return ""

def _render_kenburns(shots, imgs, output_path, total):
    """Images-only: slow-zoom each still image to its TTS duration, concat, mux audio.

    Uses the Split Node single-pass pattern: each image is fed as a SINGLE frame
    (no -loop/-framerate) and zoompan generates the d=N frames from that one
    input. Adding -loop 1 makes every input infinite and the concat never
    advances past image 1 (all later shots repeat frame 1) — the exact bug fixed
    in Split Node ep12."""
    print("  [RENDER] images-only mode (Ken Burns slow-zoom)")
    OV_W, OV_H = W_RES * 2, H_RES * 2
    audio_in = _build_audio(shots)
    parts = []
    valid_imgs = []
    for i, s in enumerate(shots):
        p = s.get("image")
        if not (p and os.path.isfile(p)):
            continue
        dur = max(s.get("dur", 3), 0.5)
        n_frames = max(int(dur * 30), 30)
        zoom = f"z='if(eq(on,1),1,min(1+0.08*(on-1)/{max(n_frames-1,1)},1.08))'"
        # single-frame input (no loop=1) + zoompan generates d=N frames
        parts.append(
            f"[{len(valid_imgs)}:v]"
            f"scale={OV_W}:{OV_H}:flags=lanczos:force_original_aspect_ratio=increase,"
            f"crop={OV_W}:{OV_H},"
            f"zoompan={zoom}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={n_frames}:s={W_RES}x{H_RES}:fps=30,"
            f"fade=t=in:st=0:d=0.2,fade=t=out:st={max(dur-0.2,0):.2f}:d=0.2,"
            f"setsar=1,format=yuv420p[v{i}]")
        valid_imgs.append(p)
    if not parts:
        return ""
    concat_in = "".join(f"[v{i}]" for i in range(len(parts)))
    parts.append(f"{concat_in}concat=n={len(parts)}:v=1:a=0[vout]")
    graph = ";\n".join(parts)
    graph_file = str(RENDERED_VIDEO / "_kb_graph.txt")
    with open(graph_file, "w") as f:
        f.write(graph)
    cmd = ["ffmpeg", "-y"]
    # single-frame image inputs - NO -loop / -framerate (the concat-advance bug)
    for p in valid_imgs:
        cmd += ["-i", p]
    audio_idx = len(valid_imgs)
    if audio_in and os.path.isfile(audio_in):
        cmd += ["-i", audio_in]
    cmd += ["-filter_complex_script", graph_file, "-map", "[vout]"]
    if audio_in and os.path.isfile(audio_in):
        cmd += ["-map", f"{audio_idx}:a"]
    cmd += ["-c:v", "hevc_nvenc", "-preset", "p7", "-rc", "vbr", "-cq", "28",
            "-b:v", "0", "-pix_fmt", "yuv420p"]
    if audio_in and os.path.isfile(audio_in):
        cmd += ["-c:a", "aac", "-b:a", "160k"]
    cmd += ["-movflags", "+faststart", "-t", f"{total:.3f}", "-y", output_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200,
                       cwd=str(RENDERED_VIDEO))
    try:
        os.unlink(graph_file)
    except Exception:
        pass
    if r.returncode != 0 or not os.path.isfile(output_path) or os.path.getsize(output_path) < 1000:
        print(f"  [RENDER] kenburns failed: {r.stderr[-800:]}")
        return ""
    print(f"  [OK] {_fmt(_audio_duration(output_path))} -> {output_path}")
    return output_path

def _render_from_clips(shots, clips, output_path, total):
    """Videos mode: concat generated clips, mux TTS audio.
    (Word-level subs are burned in a later pass via _add_word_subtitles.)"""
    listfile = str(tempfile.mkdtemp(prefix="sns_")) + "/list.txt"
    with open(listfile, "w") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n")
    concat_mp4 = str(RENDERED_VIDEO / "_concat.mp4")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                        "-c", "copy", "-movflags", "+faststart", concat_mp4],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not os.path.isfile(concat_mp4):
        print(f"  [CONCAT] failed: {r.stderr[-500:]}")
        return ""

    audio_in = _build_audio(shots)
    cmd = ["ffmpeg", "-y", "-i", concat_mp4]
    if audio_in:
        cmd += ["-i", audio_in]
        mapa = ["-map", "0:v", "-map", "1:a"]
    else:
        mapa = ["-map", "0:v", "-map", "0:a"]
    cmd += [*mapa,
            "-c:v", "hevc_nvenc", "-preset", "p7", "-rc", "vbr", "-cq", "28",
            "-b:v", "0", "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{total:.3f}", output_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200,
                       cwd=str(RENDERED_VIDEO))
    if r.returncode != 0 or not os.path.isfile(output_path) or os.path.getsize(output_path) < 1000:
        print(f"  [RENDER] failed: {r.stderr[-800:]}")
        return ""
    print(f"  [OK] {_fmt(_audio_duration(output_path))} -> {output_path}")
    return output_path

def _build_audio(shots):
    """Concatenate TTS clips -> a single mix WAV. Returns path or None.

    A Stable Audio 3 music bed is generated (via the shared sa3_music module)
    and sidechain-ducked under the voice, matching Split Node / Crayon Diet.
    If SA3 is unavailable or fails, falls back to voice-only (never breaks)."""
    tts = [s["tts"] for s in shots if s.get("tts") and os.path.isfile(s["tts"])]
    if not tts:
        return None
    listfile = str(tempfile.mkdtemp(prefix="sns_a_")) + "/a.txt"
    with open(listfile, "w") as f:
        for t in tts:
            f.write(f"file '{os.path.abspath(t).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n")
    voice = str(RENDERED_AUDIO / "voice.wav")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                        "-af", "volume=2.0dB,alimiter=limit=1.0", "-ar", "44100", "-ac", "2", voice],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not os.path.isfile(voice):
        return None
    voice_dur = _audio_duration(voice)

    out = str(RENDERED_AUDIO / "mix.wav")
    # Music bed via Stable Audio 3 (resident medium model), ducked under the voice
    try:
        if os.environ.get("MUSIC_BACKEND", "sa3").strip().lower() == "sa3":
            import sa3_music
            if sa3_music.available():
                tmpdir = tempfile.mkdtemp(prefix="sns_bed_")
                try:
                    bed = os.path.join(tmpdir, "bed.wav")
                    prompt = os.environ.get(
                        "SN_SA3_BED_PROMPT",
                        "Tense documentary background music, suspenseful electronic "
                        "score, no vocals, building tension, cinematic, high quality production")
                    # Resident-model gen (chunked @380s internally); base music at -10dB.
                    # Story-adaptive: build prompt from the actual scene script so the
                    # bed follows what's happening in the short (Joe 2026-08-14).
                    story = " ".join(
                        s.get("spoken", "") or s.get("text", "") or ""
                        for s in shots if (s.get("spoken") or s.get("text")))
                    if sa3_music.generate_via_gradio(prompt, voice_dur, bed,
                                                     timeout=1800,
                                                     story_context=story):
                        mix = ["ffmpeg", "-y",
                               "-i", voice,
                               "-i", bed,
                               "-filter_complex",
                               "[1:a]volume=-10dB[lv];"
                               "[lv][0:a]sidechaincompress=threshold=0.02:ratio=8:"
                               "attack=30:release=350:makeup=1[ducked];"
                               "[0:a][ducked]amix=inputs=2:duration=first:normalize=0[out]",
                               "-map", "[out]", "-ar", "44100", "-ac", "2", out]
                        rr = subprocess.run(mix, capture_output=True, text=True, timeout=600)
                        if rr.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 1000:
                            print(f"  [AUDIO] ducked SA3 music bed under voice "
                                  f"({_fmt(voice_dur)}, -10dB base -> -19.5dB under voice)")
                            return out
                        print("  [AUDIO] SA3 mix failed, voice only")
                    else:
                        print("  [AUDIO] SA3 bed failed, voice only")
                finally:
                    try:
                        shutil.rmtree(tmpdir, ignore_errors=True)
                    except Exception:
                        pass
    except Exception as e:
        print(f"  [AUDIO] music bed failed ({e}), voice only")

    return voice if os.path.isfile(voice) else None

def _fmt(s):
    s = int(round(s))
    return f"{s//60}:{s%60:02d}"


# ---- thumbnail ------------------------------------------------------
def _thumbnail_frame(video_path, out_path):
    """Extract a single frame (mid-video) as the thumbnail - 'only for 1 single frame'."""
    dur = _audio_duration(video_path)
    at = max(dur / 2, 0.5)
    r = subprocess.run(["ffmpeg", "-y", "-ss", f"{at:.2f}", "-i", video_path,
                        "-frames:v", "1", "-q:v", "2", out_path],
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 1000


# ---- YouTube upload -------------------------------------------------
def _get_youtube_creds():
    import youtube_reauth
    # Shorts upload to the Split Node channel, so the OAuth client secret
    # lives in the Split Node (System Breakers) project folder.
    secret_dir = r"F:\aaaaaVIBECODING\System Breakers"
    return youtube_reauth.ensure_youtube_creds(
        YOUTUBE_CREDENTIALS, Path(__file__).resolve().parent,
        "Split Node Shorts", secrets_dir=secret_dir)

def _upload_video(video_path, title, description, tags_str, privacy="public"):
    creds = _get_youtube_creds()
    if not creds:
        return None
    import requests
    file_size = os.path.getsize(video_path)
    if len(description) > 4990:
        description = description[:4990].rsplit("\n", 1)[0] + "\n\n[truncated]"
    body = {
        "snippet": {"title": title, "description": description,
                    "tags": tags_str.split(",")[:499], "categoryId": "22"},
        "status": {"privacyStatus": privacy, "embeddable": True,
                   "selfDeclaredMadeForKids": False},
    }
    try:
        upload_url = None
        r = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={"Authorization": f"Bearer {creds.token}",
                     "Content-Type": "application/json",
                     "X-Upload-Content-Length": str(file_size),
                     "X-Upload-Content-Type": "video/mp4"},
            json=body, timeout=30)
        if r.status_code != 200:
            print(f"  [WARN] Upload init failed (HTTP {r.status_code})")
            if r.status_code in (401, 403):
                print("  [WARN] Token invalid - re-authorizing and retrying...")
                creds = _get_youtube_creds()  # re-auths inline if needed
                if creds:
                    r = requests.post(
                        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                        headers={"Authorization": f"Bearer {creds.token}",
                                 "Content-Type": "application/json",
                                 "X-Upload-Content-Length": str(file_size),
                                 "X-Upload-Content-Type": "video/mp4"},
                        json=body, timeout=30)
                    if r.status_code == 200:
                        upload_url = r.headers.get("Location")
            if not upload_url:
                return None
        else:
            upload_url = r.headers.get("Location")
        if not upload_url:
            return None
        chunk = 256 * 1024
        sent = 0
        with open(video_path, "rb") as f:
            while sent < file_size:
                c = f.read(chunk)
                if not c:
                    break
                rr = requests.put(upload_url, headers={
                    "Content-Length": str(len(c)),
                    "Content-Range": f"bytes {sent}-{sent+len(c)-1}/{file_size}"},
                    data=c, timeout=120)
                if rr.status_code not in (308, 200, 201):
                    return None
                sent += len(c)
        if rr.status_code in (200, 201):
            return rr.json().get("id")
        return None
    except Exception as e:
        print(f"  [WARN] Upload error: {e}")
        return None

def _upload_thumbnail(video_id, thumb_path):
    if not os.path.isfile(thumb_path):
        return
    import requests
    creds = _get_youtube_creds()
    if not creds:
        return
    try:
        r = requests.post(
            f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}",
            headers={"Authorization": f"Bearer {creds.token}"},
            files={"thumbnail": open(thumb_path, "rb")}, timeout=30)
        if r.status_code == 200:
            print(f"  [OK] Thumbnail uploaded")
        else:
            print(f"  [WARN] Thumbnail upload failed: {r.status_code}")
    except Exception as e:
        print(f"  [WARN] Thumbnail error: {e}")

def _playlist_id(creds, name):
    import requests
    r = requests.get("https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50",
                     headers={"Authorization": f"Bearer {creds.token}"}, timeout=15)
    if r.status_code == 200:
        for pl in r.json().get("items", []):
            if pl["snippet"]["title"].lower() == name.lower():
                return pl["id"]
    return None

def _create_playlist(creds, name):
    import requests
    r = requests.post("https://www.googleapis.com/youtube/v3/playlists?part=snippet,status",
                      headers={"Authorization": f"Bearer {creds.token}",
                               "Content-Type": "application/json"},
                      json={"snippet": {"title": name, "description": "Split Node Shorts - AI money-exploit shorts"},
                            "status": {"privacyStatus": "public"}}, timeout=15)
    if r.status_code == 200:
        return r.json().get("id")
    return None

def _add_to_playlist(video_id, playlist):
    import requests
    creds = _get_youtube_creds()
    if not creds:
        return
    pid = _playlist_id(creds, playlist)
    if not pid:
        pid = _create_playlist(creds, playlist)
    if not pid:
        return
    r = requests.post("https://www.googleapis.com/youtube/v3/playlistItems?part=snippet",
                      headers={"Authorization": f"Bearer {creds.token}",
                               "Content-Type": "application/json"},
                      json={"snippet": {"playlistId": pid, "resourceId": {
                          "kind": "youtube#video", "videoId": video_id}}}, timeout=15)
    print(f"  [OK] Added to playlist '{playlist}' ({r.status_code})")


# ---- titles / description / tags (video formula) --------------------
TITLE_SYSTEM = (
    "You are a viral YouTube SHORTS title generator for 'Split Node Shorts' - a "
    "channel about ordinary people who beat money systems. Use the proven formula:\n"
    "DECLARATION format with a big absurd SPECIFIC NUMBER + 2 emojis.\n"
    "Examples: 'He turned $1 into $1M with ONE loophole 💸🤯'\n"
    "          'The bank glitch that pays you $500 a day 💰😳'\n"
    "Rules: under 100 chars, starts with the number or the absurd claim, reference "
    "the story, exactly 2 emojis. Return ONLY the title, no quotes."
)

def _generate_title(topic, number):
    msg = [{"role": "system", "content": TITLE_SYSTEM},
           {"role": "user", "content": f"Story: {topic}\nKey number: {number}\nWrite the title."}]
    t = _llm_chat(msg, max_tokens=60, temp=0.9).strip().strip('"\'')
    if 10 <= len(t) <= 100:
        return t
    return f"The {topic[:50]} money loophole 💸🤯"

DESCRIPTION_SYSTEM = (
    "Write a YouTube SHORTS description for 'Split Node Shorts' - AI shorts about "
    "ordinary people who beat money systems (loopholes, glitches, refunds, exploits). "
    "Structure: 1-2 sentence hook on THIS story, 1 line about the channel, 1 line "
    "teasing the reveal ('full story in comments'). End with 3 topic hashtags on "
    "their own line. 40-90 words. No em dashes, no markdown."
)

def _generate_description(topic, title):
    msg = [{"role": "system", "content": DESCRIPTION_SYSTEM},
           {"role": "user", "content": f"Story: {topic}\nTitle: {title}\nWrite the description."}]
    d = _llm_chat(msg, max_tokens=200, temp=0.75).strip().strip('"\'')
    return d if d else (f"{topic}\n\n#MoneyHacks #Loophole #BeatTheSystem")

TAG_SYSTEM = (
    "Generate exactly 12 comma-separated YouTube SHORTS tags for a short about a "
    "money exploit / loophole story. Mix: 3 viral, 3 curiosity, 3 specific topic, "
    "3 broad category. All relevant to THIS short. Return ONLY the tags, comma separated."
)

def _generate_tags(topic):
    msg = [{"role": "system", "content": TAG_SYSTEM},
           {"role": "user", "content": f"Topic: {topic}"}]
    text = _llm_chat(msg, max_tokens=150, temp=0.6)
    tags = [t.strip().lower() for t in text.split(",") if t.strip()]
    tags = [t for t in tags if 2 < len(t) < 50]
    return YOUTUBE_BASE_TAGS + tags[:12]


# ---- main orchestration ---------------------------------------------
# ===================================================================
# SHORTS FROM AN EXISTING SPLIT NODE EPISODE (Joe 2026-08-14)
# ===================================================================
# Reuses a finished Split Node episode: loads its narration map + existing
# TTS clips + shot images, whispers the TTS to see what's said, has the local
# gemma-4-e4b pick the best ~60s of narration, matches the correct shots,
# face-crops them to 9:16 vertical, and renders/uploads a short. Supports
# multiple shorts per episode. On upload, links the full episode as related.
SN_EPISODES_DIR = os.environ.get(
    "SN_EPISODES_DIR", r"F:/aaaaaVIBECODING/System Breakers/episodes")


def _face_crop_offset(img_path, crop_ratio=9.0 / 16.0):
    """Return the horizontal source-crop offset (x, width) that keeps a
    detected face in a crop window of the given ratio, with MINIMAL horizontal
    shift from center (Joe: move it as low as possible, face just needs to be
    in frame, not centered). Falls back to a centered crop when no face."""
    try:
        import cv2
        img = cv2.imread(str(img_path))
        if img is None:
            return None
        h, w = img.shape[:2]
        # target crop width for ratio (crop a vertical slice of the wide shot)
        cw = min(int(h * (1.0 / crop_ratio)), w)  # 16:9 shot -> ~9:16 slice width
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
        if len(faces) == 0:
            return None  # centered crop
        # biggest face centre
        (fx, fy, fw, fh) = max(faces, key=lambda f: f[2] * f[3])
        face_cx = fx + fw / 2.0
        # centred window; shift only as much as needed to bring the face in
        x_center = (w - cw) / 2.0
        x = x_center
        if face_cx < x:
            x = max(0, face_cx - cw * 0.05)      # face near left edge
        elif face_cx > x + cw:
            x = min(w - cw, face_cx - cw * 0.95)  # face near right edge
        return (x, cw)
    except Exception as e:
        print(f"  [FACE] detection skipped ({e}) - centered crop")
        return None


def _prep_vertical_shot(src_img, dst_img):
    """Face-aware crop a 16:9 Split Node shot into a 9:16 vertical still.
    Returns dst path on success, else '' (caller falls back to the source)."""
    try:
        from PIL import Image
        im = Image.open(src_img).convert("RGB")
        w, h = im.size
        off = _face_crop_offset(src_img)
        if off is None:
            # vertical slice preserving height: crop width = h*(9/16) keeps it
            # a 9:16-ish region out of the 16:9 frame -> then scale to 1080x1920
            cw = max(int(round(h * 9.0 / 16.0)), 1)
            cw = min(cw, w)
            x = (w - cw) // 2
        else:
            x, cw = off
        crop = im.crop((int(x), 0, int(x + cw), h))
        crop = crop.resize((1080, 1920), Image.LANCZOS)
        crop.save(dst_img, "PNG")
        return dst_img
    except Exception as e:
        print(f"  [FACE] vertical prep failed ({e}) - using source")
        return ""


def _list_sn_episodes():
    """Return sorted [(ep_num, ep_dir)] from Split Node's episodes folder that
    look finished (have a narration_map + at least one shot + a video)."""
    out = []
    root = Path(SN_EPISODES_DIR)
    if not root.is_dir():
        print(f"  [EPISODES] not found: {root}")
        return out
    for d in sorted(root.glob("ep*")):
        if not d.is_dir():
            continue
        m = re.search(r"ep(\d+)$", d.name)
        if not m:
            continue
        num = int(m.group(1))
        has_map = (d / "tts" / "narration_map.json").is_file()
        has_video = any((d / "video").glob("*.mp4"))
        if has_map and has_video:
            out.append((num, str(d)))
    return sorted(out)


def _load_episode_assets(ep_dir):
    """Load narration_map, tts clips, and shot images for an episode.
    Returns (narration_map, tts_clips, shot_map) where:
      narration_map = {idx_str: text}
      tts_clips = {idx_str: path}
      shot_map = {idx_str: path}  (best shot image per narration index)"""
    ep = Path(ep_dir)
    nmp = ep / "tts" / "narration_map.json"
    nm = {}
    if nmp.is_file():
        try:
            nm = json.loads(nmp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [EP] narration_map load failed: {e}")
    tts_clips = {}
    for w in sorted((ep / "tts").glob("narration_*.wav")):
        m = re.search(r"narration_(\d+)\.wav$", w.name)
        if m:
            tts_clips[str(int(m.group(1)))] = str(w)
    # shots: shotNN_*.png -> index NN-1 (1-based filename)
    shots = {}
    for f in sorted(ep.glob("shot*.png")):
        m = re.match(r"shot(\d+)_", f.name)
        if m:
            idx = int(m.group(1)) - 1
            shots.setdefault(str(idx), str(f))
    # Normalise narration_map keys to canonical int-strings too ('0'/'00' both -> '0')
    nm = {str(int(k)): v for k, v in nm.items()}
    return nm, tts_clips, shots


def _whisper_episode(ep_dir, narration_map, tts_clips):
    """Determine what each narration clip says + its duration.

    Faster-whisper is used to VERIFY the spoken text (Joe: 'use faster-whisper
    to see what the TTS is saying'). It loads the model once and transcribes
    each clip. Set WHISPER_VERIFY=0 to skip whisper entirely and trust the
    stored narration_map text (much faster - ~160 clips take minutes on CPU).
    Durations always come from ffprobe regardless.
    Returns {idx: {'text': spoken, 'dur': seconds}}."""
    verify = os.environ.get("WHISPER_VERIFY", "1") == "1"
    model = None
    if verify:
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="cpu", compute_type="int8")
            print("  [WHISPER] verifying narration with faster-whisper "
                  f"({len(tts_clips)} clips) - set WHISPER_VERIFY=0 to skip")
        except Exception as e:
            print(f"  [WHISPER] model load failed ({e}) - using stored narration")
            model = None
    res = {}
    idxs = sorted(set(narration_map) | set(tts_clips),
                  key=lambda s: int(s))
    for idx in idxs:
        tts = tts_clips.get(idx)
        text = (narration_map.get(idx) or "").strip()
        dur = _audio_duration(tts) if tts else 0.0
        if tts and model is not None:
            try:
                segments, _ = model.transcribe(tts, language="en",
                                               word_timestamps=False,
                                               vad_filter=False)
                spoken = " ".join(s.text.strip() for s in segments).strip()
                if spoken:
                    text = spoken
            except Exception:
                pass
        res[idx] = {"text": text, "dur": max(dur, 0.0)}
    return res


def _gemma_pick_short(narration, target=60.0, count=1, episode_title="",
                      excluded=()):
    """Ask local gemma-4-e4b to pick the best ~`target`-second window(s) of
    narration that condense the episode into a self-contained short.
    narration = {idx: {text, dur}}. Returns a list of idx-lists (one per short),
    each a contiguous run of indices summing ~target seconds."""
    items = sorted(narration.items(), key=lambda kv: int(kv[0]))
    total = sum(v["dur"] for _, v in items)
    if total <= 0:
        return []
    # Build a compact listing: idx: (dur) text
    listing = "\n".join(
        f"  [{i}] ({v['dur']:.1f}s) {v['text'][:140]}"
        for i, v in items)
    ex = ""
    if excluded:
        ex = ("\nIMPORTANT: these narration windows are ALREADY used for other "
              "shorts - pick a DIFFERENT part of the story, do not reuse them:\n" +
              "\n".join(f"  - indices {list(e)}" for e in excluded))
    sys_msg = (
        "You are a short-form video editor. Given a documentary narration "
        "split into numbered clips with their durations (seconds each), choose "
        "the BEST contiguous run of clips that tells a complete, self-contained "
        f"story. CRITICAL: the run must sum to roughly {target:.0f} seconds of "
        "audio - use the per-clip durations to pick the right NUMBER of clips "
        "(typically 6-12). A hook in the first clip, then the core "
        "conflict/reveal, then a payoff. Do NOT pick more clips than fit the "
        "budget. Return STRICTLY JSON only: "
        '{"windows": [[start_idx, end_idx], ...]} with exactly ' +
        str(count) + " window(s), start/end as integers (indices from the list).")
    user = (f"Episode: {episode_title or '(untitled)'}\n"
            f"Total narration: {total:.0f}s. Pick {count} window(s) that each "
            f"sum to ~{target:.0f}s. A 60s window needs roughly "
            f"{max(6, int(target / max([v['dur'] for v in narration.values()] or [1.0]))) }"
            f" clips. Use the durations below to stay in budget.\n\n"
            f"NARRATION CLIPS:\n{listing}\n{ex}\n\n"
            'Respond with only the JSON object.')
    try:
        raw = _llm_chat([{"role": "system", "content": sys_msg},
                         {"role": "user", "content": user}],
                        max_tokens=300, temp=0.3)
        raw = re.sub(r"```json|```", "", raw).strip()
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            print(f"  [GEMMA] no JSON in response: {raw[:200]}")
            return []
        data = json.loads(m.group(0))
        wins = data.get("windows") or []
    except Exception as e:
        print(f"  [GEMMA] selection failed ({e}) - falling back to time splits")
        wins = []
    # Validate / normalise windows to contiguous index lists.
    all_idx = [i for i, _ in items]
    result = []
    if not wins:
        # Fallback: split the timeline evenly into `count` windows.
        chunk = max(total / count, 1.0)
        cursor = 0.0
        bucket, cur_idx = [], 0
        for i, v in items:
            bucket.append(i)
            cursor += v["dur"]
            if cursor >= chunk and cur_idx < count - 1:
                if bucket:
                    result.append(bucket)
                bucket, cursor = [], 0.0
                cur_idx += 1
        if bucket:
            result.append(bucket)
        return result[:count]
    for (s, e) in wins:
        try:
            s, e = int(s), int(e)
        except Exception:
            continue
        sel = [i for i in all_idx if s <= int(i) <= e]
        if sel and sel not in result:
            result.append(sel)
    if not result:
        return result[:count]
    # DETERMINISTIC trim-to-budget: gemma often picks a window far over target,
    # so walk the chosen run and find the contiguous sub-window whose duration
    # is closest to (and not wildly over) `target` - guarantees ~60s shorts
    # regardless of how badly the small model honours the budget (Joe 2026-08-14).
    trimmed = []
    for sel in result:
        durs = [narration[i]["dur"] for i in sel]
        best_i, best_j, best_abs = 0, 0, float("inf")
        i = 0
        cur = 0.0
        for j, d in enumerate(durs):
            cur += d
            while cur > target * 1.6 and i < j:
                cur -= durs[i]
                i += 1
            if i <= j:
                cand = abs(cur - target)
                if cand < best_abs:
                    best_abs, best_i, best_j = cand, i, j
        # prefer a window at/under target+20% over an over-budget one
        best_dur = sum(durs[best_i:best_j + 1])
        if best_dur > target * 1.3:
            i = 0
            cur = 0.0
            for j, d in enumerate(durs):
                cur += d
                if cur >= target:
                    best_i, best_j = i, j
                    break
                while cur > target and i < j:
                    cur -= durs[i]
                    i += 1
        trimmed.append(sel[best_i:best_j + 1])
    return trimmed[:count]


def _find_main_video_url(ep_dir):
    """Find the full episode's YouTube URL if we can derive it. The pipeline
    doesn't persist the video id on disk, so we ask the user (or blank)."""
    print(f"\n  [RELATED] Enter the full episode's YouTube URL (so the short "
          f"links back to it as related).")
    print(f"            Episode folder: {ep_dir}")
    url = input("  YouTube URL (or Enter to skip): ").strip()
    return url


def run_from_episode():
    """Make vertical Shorts from a finished Split Node episode."""
    print("\n" + "=" * 58)
    print("  SHORTS FROM SPLIT NODE EPISODE")
    print("=" * 58)
    # SA3 opens on a different port each launch - resolve before any music.
    try:
        import sa3_music
        sa3_music.resolve_sa3_port(project="Split Node Shorts (episode)")
    except Exception as e:
        print(f"  [SA3] port check skipped ({e}) - will fall back if music is needed")
    eps = _list_sn_episodes()
    if not eps:
        print("  [FAIL] No finished Split Node episodes found.")
        return
    print("  Available episodes:")
    for num, d in eps:
        video = next(((Path(d) / "video").glob("*.mp4")), None)
        print(f"    ep{num:03d}  {os.path.basename(video or d)}")
    while True:
        raw = input("  Episode number to make Short(s) from: ").strip()
        try:
            want = int(raw)
            match = next((e for e in eps if e[0] == want), None)
        except Exception:
            match = None
        if match:
            ep_num, ep_dir = match
            break
        print("  [WARN] not a valid episode number from the list")
    try:
        n_shorts = int(input("  How many Shorts to make from this episode? [1]: ").strip() or "1")
    except ValueError:
        n_shorts = 1
    n_shorts = max(1, min(n_shorts, 5))
    if os.environ.get("YOUTUBE_UPLOAD_ENABLED", "1") == "1":
        main_url = _find_main_video_url(ep_dir)
    else:
        main_url = ""

    # Whisper the episode's TTS so we know exactly what's said.
    print(f"\n[EP] Loading episode {ep_num} ({ep_dir})...")
    nm, tts_clips, shot_map = _load_episode_assets(ep_dir)
    if not nm:
        print("  [FAIL] No narration map.")
        return
    spoken = _whisper_episode(ep_dir, nm, tts_clips)
    print(f"  [EP] {len(spoken)} narration clips loaded "
          f"({sum(v['dur'] for v in spoken.values()):.0f}s total)")

    excluded = []
    for short_i in range(1, n_shorts + 1):
        print(f"\n{'='*58}\n  SHORT {short_i}/{n_shorts}\n{'='*58}")
        wins = _gemma_pick_short(spoken, target=60.0, count=1,
                                 excluded=excluded)
        if not wins:
            print("  [FAIL] Could not pick narration for this short.")
            continue
        chosen = wins[0]
        excluded.append(chosen)
        # Build shots: image (face-cropped vertical) + tts + dur + spoken
        shots = []
        for idx in chosen:
            v = spoken.get(idx, {"text": "", "dur": 0.0})
            if not v["text"]:
                continue
            src_img = shot_map.get(idx, "")
            if not src_img or not os.path.isfile(src_img):
                continue
            tts = tts_clips.get(idx, "")
            if not tts or not os.path.isfile(tts):
                continue
            vert = str(SHOTS_DIR / f"ep{ep_num}_short{short_i}_idx{idx}.png")
            prep = _prep_vertical_shot(src_img, vert)
            img = prep or src_img
            shots.append({"idx": idx, "image": img, "tts": tts,
                          "dur": max(v["dur"], 1.0), "spoken": v["text"],
                          "text": v["text"], "phase": "DECLARE"})
        if len(shots) < 3:
            print(f"  [FAIL] Only {len(shots)} usable shots - need at least 3.")
            continue
        total = sum(s["dur"] for s in shots)
        if total > MAX_SECONDS:
            print(f"  [TRIM] selected {_fmt(total)} > max - trimming tail")
            while total > MAX_SECONDS and len(shots) > 4:
                shots.pop()
                total = sum(s["dur"] for s in shots)
        print(f"\n[SCENE BOARD] short {short_i} ({_fmt(total)}):")
        for s in shots:
            print(f"  {s['idx']:>4} {s['spoken'][:70]}")

        # Render (Ken Burns stills on the face-cropped verticals).
        counter = 0
        if COUNTER_FILE.is_file():
            try:
                counter = int(COUNTER_FILE.read_text().strip())
            except Exception:
                counter = 0
        counter += 1
        out = str(RENDERED_VIDEO / f"ep{ep_num}_short_{counter:03d}.mp4")
        script_data = {"title": ""}
        video = _render(shots, script_data, out)
        if not video:
            print("  [FAIL] Render failed")
            continue
        video = _add_word_subtitles(video, shots,
                                    style=os.environ.get("SUBTITLE_STYLE", "mrbeast"))
        thumb = str(THUMBNAILS_DIR / f"ep{ep_num}_short_{counter:03d}.png")
        thumb_ok = _thumbnail_frame(video, thumb)
        print(f"  [THUMB] {'OK' if thumb_ok else 'failed'} -> {thumb}")

        # Titles / desc / tags; append the main episode as the related link.
        topic = " ".join(s["spoken"] for s in shots[:2])
        title = _generate_title(topic, str(ep_num)) or f"Split Node ep{ep_num} Short"
        desc = _generate_description(topic, title)
        if main_url:
            desc = (f"Full documentary: {main_url}\n\n" + desc)
        tags = _generate_tags(topic)
        tags_str = ",".join(tags)
        print(f"\n  [TITLE] {title}")

        if UPLOAD_ENABLED:
            print(f"\n  {'='*50}\n  YOUTUBE UPLOAD -> {CHANNEL_NAME} / "
                  f"'{YOUTUBE_PLAYLIST}'\n  {'='*50}")
            vid = _upload_video(video, title, desc, tags_str)
            if vid:
                print(f"  [OK] Uploaded: https://youtu.be/{vid}")
                if thumb_ok:
                    _upload_thumbnail(vid, thumb)
                _add_to_playlist(vid, YOUTUBE_PLAYLIST)
                COUNTER_FILE.write_text(str(counter))
                print(f"  [DONE] Short #{counter:03d} live!")
            else:
                print("  [SKIP] Upload failed - video saved locally")
        else:
            print("  [SKIP] Upload disabled (YOUTUBE_UPLOAD_ENABLED=0)")
        print(f"\n  Short complete:\n    video:  {video}\n    thumb:  {thumb}")


def run():
    print("=" * 58)
    print("  SPLIT NODE SHORTS - vertical money-exploit Shorts generator")
    print(f"  backend=image:{IMAGE_BACKEND}  video:{VIDEO_BACKEND}")
    print(f"  style={_active_style_name()}  target={int(TARGET_SECONDS)}s  max={int(MAX_SECONDS)}s")
    print("=" * 58)

    # Pick the LLM backend + model (LM Studio loaded models, or Codex cheapest).
    _select_llm()

    # Ask which mode: make Shorts from an existing Split Node episode, or the
    # normal RSS money-exploit flow (Joe 2026-08-14).
    if os.environ.get("SHORTS_FROM_EPISODE") == "1":
        mode = "episode"
    elif os.environ.get("SHORTS_FROM_EPISODE") == "0":
        mode = "rss"
    else:
        print("\n  What do you want to make?")
        print("    1. Short from an existing Split Node episode (reuse TTS + shots)")
        print("    2. New Short from RSS (money-exploit story)")
        while True:
            resp = input("  Pick 1 or 2 [1]: ").strip().lower()
            if resp in ("", "1", "episode", "ep"):
                mode = "episode"
                break
            if resp in ("2", "rss", "new"):
                mode = "rss"
                break
            print(f"  [WARN] '{resp}' not recognised - enter 1 (episode) or 2 (RSS)")
    if mode == "episode":
        run_from_episode()
        _pause()
        return

    # Ask which port Stable Audio 3 is running on BEFORE anything else
    # (SA3's Pinokio launcher opens on a different port each run).
    try:
        import sa3_music
        sa3_music.resolve_sa3_port(project="Split Node Shorts")
    except Exception as e:
        print(f"  [SA3] port check skipped ({e}) - will fall back if music is needed")

    if not _llm_reachable():
        print("  [FATAL] LM Studio not reachable. Load gemma-4-e4b-uncensored first.")
        return

    # Ping the live video-model price every run; surface a change if it moved.
    _check_video_price()

    # Pick a story. _pick_story now PARSES each candidate before presenting it
    # and auto-skips links that don't resolve, so the returned article is
    # already fetched (Joe 2026-08-14). If the script still can't be built from
    # it, reject it and loop back to picking a different one instead of quitting.
    max_attempts = int(os.environ.get("STORY_RESOLVE_ATTEMPTS", "5"))
    url, topic = "", ""
    content = []
    script = {}
    for _attempt in range(1, max_attempts + 1):
        url, topic, content = _pick_story()
        if not url:
            return
        print(f"\n  [TOPIC] {topic}\n  [URL] {url}")
        if not content:
            print(f"  [FAIL] Article did not resolve (blocked / no content): {url}")
            print(f"  [RETRY] Picking a different story ({_attempt}/{max_attempts})...")
            _save_rejected(url)
            continue
        content_text = "\n".join(content)
        print("\n[BIBLE] Building Shorts script (6-phase formula)...")
        script = _build_script(topic, url, content_text)
        if script and script.get("scenes"):
            break
        print(f"  [FAIL] Could not build a script from this article ({url})")
        print(f"  [RETRY] Picking a different story ({_attempt}/{max_attempts})...")
        _save_rejected(url)
        content = []
    if not content or not script or not script.get("scenes"):
        print(f"  [FAIL] Could not resolve + script a story after {max_attempts} attempts.")
        return
    content_text = "\n".join(content)

    scenes = script["scenes"]
    num = script.get("number", "")
    title = script.get("title", "")
    print(f"  [SCRIPT] {len(scenes)} scenes | title: {title} | number: {num}")
    for s in scenes:
        print(f"    [{s.get('phase','')}] {s.get('text','')}")

    # sanitize scene text into prompt-friendly + spoken forms
    shots = []
    for i, s in enumerate(scenes):
        text = s.get("text", "").strip()
        phase = s.get("phase", "").upper()
        if not text:
            continue
        spoken = re.sub(r"^[A-Z]+:\s*", "", text)  # strip 'DECLARE:' prefix for TTS
        shots.append({"idx": i, "phase": phase, "text": text, "spoken": spoken,
                      "dur": SECONDS_PER_LINE})

    total = sum(s["dur"] for s in shots)
    if total > MAX_SECONDS:
        print(f"  [WARN] script {_fmt(total)} > max {int(MAX_SECONDS)}s - trimming")
        while total > MAX_SECONDS and len(shots) > 4:
            shots.pop(); total = sum(s["dur"] for s in shots)
        print(f"  [TRIM] now {_fmt(total)}")

    print("\n[SCENE BOARD]")
    for i, s in enumerate(shots):
        print(f"  {i+1:2}. [{s['phase']}] {s['spoken'][:70]}")

    # ---- generation mode: videos+images OR images only (per run) ----
    gen_videos = _ask_gen_mode()
    if gen_videos:
        print(f"  [MODE] generating AI video clips ({HIGGS_VIDEO_MODEL})")
    else:
        print("  [MODE] images only (Ken Burns stills)")

    # ---- generate images + TTS (parallel, per scene) ----
    # Parallelism ported from Split Node (Joe 2026-08-14): each scene's image +
    # TTS + duration are fully independent (distinct files, distinct dict keys),
    # so they can render concurrently instead of one-at-a-time. Gated by
    # IMAGE_CONCURRENCY (default 1 = exactly the old sequential behaviour).
    # Downstream render/subtitle/audio only read the finished per-scene fields,
    # so parallelism cannot break them.
    print(f"\n[GEN] Generating {len(shots)} vertical images ({IMAGE_BACKEND}) + TTS...")
    style = _style_descriptor()
    _conc = max(1, int(os.environ.get("IMAGE_CONCURRENCY", "1")))
    if _conc > 1 and len(shots) > 1:
        from concurrent.futures import ThreadPoolExecutor as _TPE

        def _gen_one(i_s):
            i, s = i_s
            img = str(SHOTS_DIR / f"scene_{i:03d}.png")
            prompt = (f"{style}. Vertical 9:16 frame for a money-exploit short. "
                      f"Scene: {s['spoken']}.")
            if _scene_shows_hands(s["spoken"]):
                prompt += _hands_clause()
            print(f"  [IMG {i+1}/{len(shots)}] {s['spoken'][:50]}...")
            _generate_image(prompt, img)
            s["image"] = img if os.path.isfile(img) else None
            tts = str(RENDERED_AUDIO / f"scene_{i:03d}.wav")
            _tts(s["spoken"], tts, _voice_for_phase(s["phase"]))
            s["tts"] = tts if os.path.isfile(tts) else None
            s["dur"] = max(_audio_duration(tts), 2.0) if os.path.isfile(tts) else s["dur"]

        with _TPE(max_workers=_conc) as _ex:
            list(_ex.map(_gen_one, list(enumerate(shots))))
    else:
        for i, s in enumerate(shots):
            img = str(SHOTS_DIR / f"scene_{i:03d}.png")
            prompt = (f"{style}. Vertical 9:16 frame for a money-exploit short. "
                      f"Scene: {s['spoken']}.")
            # Hands/anatomy clause (Split Node Bug 3 port): stylized models hallucinate
            # fingers on hand-visible scenes (clicking/typing/counting cash).
            if _scene_shows_hands(s["spoken"]):
                prompt += _hands_clause()
            print(f"  [IMG {i+1}/{len(shots)}] {s['spoken'][:50]}...")
            _generate_image(prompt, img)
            s["image"] = img if os.path.isfile(img) else None

            tts = str(RENDERED_AUDIO / f"scene_{i:03d}.wav")
            _tts(s["spoken"], tts, _voice_for_phase(s["phase"]))
            s["tts"] = tts if os.path.isfile(tts) else None
            s["dur"] = max(_audio_duration(tts), 2.0) if os.path.isfile(tts) else s["dur"]

    # ---- generate video clips from each image (skipped in images-only) ----
    if gen_videos:
        print(f"\n[VIDEO] Generating {len(shots)} video clips ({HIGGS_VIDEO_MODEL})...")
        for i, s in enumerate(shots):
            if not s.get("image"):
                continue
            clip = _generate_video(s["image"], s["spoken"], max(3, min(int(round(s["dur"])), 15)))
            if clip:
                s["clip"] = clip
                actual = _audio_duration(clip)
                if actual > 0:
                    s["dur"] = max(s["dur"], min(actual, s["dur"] + 1))
    else:
        print(f"\n[VIDEO] Skipping video clips (images-only mode)")

    # ---- render ----
    counter = 0
    if COUNTER_FILE.is_file():
        try:
            counter = int(COUNTER_FILE.read_text().strip())
        except Exception:
            counter = 0
    counter += 1
    out = str(RENDERED_VIDEO / f"split_node_short_{counter:03d}.mp4")
    video = _render(shots, script, out)
    if not video:
        print("  [FAIL] Render failed")
        return

    # ---- word-level animated subtitles (Crayon Diet method) ----
    sub_style = os.environ.get("SUBTITLE_STYLE", "mrbeast")
    video = _add_word_subtitles(video, shots, style=sub_style)

    # ---- thumbnail (single frame) ----
    thumb = str(THUMBNAILS_DIR / f"short_{counter:03d}.png")
    thumb_ok = _thumbnail_frame(video, thumb)
    print(f"  [THUMB] {'OK' if thumb_ok else 'failed'} -> {thumb}")

    # ---- titles / description / tags ----
    if not title:
        title = _generate_title(topic, num)
    desc = _generate_description(topic, title)
    tags = _generate_tags(topic)
    tags_str = ",".join(tags)
    print(f"\n  [TITLE] {title}")
    print(f"  [TAGS] {tags_str[:150]}...")

    # ---- upload ----
    if UPLOAD_ENABLED:
        print(f"\n  {'='*50}\n  YOUTUBE UPLOAD -> {CHANNEL_NAME} / '{YOUTUBE_PLAYLIST}'\n  {'='*50}")
        vid = _upload_video(video, title, desc, tags_str)
        if vid:
            print(f"  [OK] Uploaded: https://youtu.be/{vid}")
            if thumb_ok:
                _upload_thumbnail(vid, thumb)
            _add_to_playlist(vid, YOUTUBE_PLAYLIST)
            COUNTER_FILE.write_text(str(counter))
            print(f"  [DONE] Short #{counter:03d} live!")
        else:
            print("  [SKIP] Upload failed - video saved locally")
    else:
        print("  [SKIP] Upload disabled (YOUTUBE_UPLOAD_ENABLED=0)")

    print(f"\n  Short #{counter:03d} complete:\n    video:  {video}\n    thumb:  {thumb}")


def _ask_gen_mode() -> bool:
    """Ask per run whether to generate AI video clips or images only.
    Returns True for videos, False for images-only. Env override skips prompt."""
    if os.environ.get("GENERATE_VIDEOS") is not None:
        return int(os.environ["GENERATE_VIDEOS"]) == 1
    print("\n  Generation mode:")
    print("    1. Videos + images  (Higgsfield kling/wan clips - uses credits)")
    print("    2. Images only      (Ken Burns stills - cheapest, ~1.5cr/image)")
    while True:
        resp = input("  Pick 1 or 2 [1]: ").strip().lower()
        if resp in ("", "1", "video", "videos", "y"):
            return True
        if resp in ("2", "image", "images", "still", "n"):
            return False
        print(f"  [WARN] '{resp}' not recognised - enter 1 (videos) or 2 (images)")


# ---- word-level subtitles (ported from Crayon Diet) -----------------
def _concat_tts(shots) -> str:
    """Concatenate all TTS clips into one WAV for whisper timing."""
    tts = [s["tts"] for s in shots if s.get("tts") and os.path.isfile(s["tts"])]
    if not tts:
        return ""
    concat_wav = str(RENDERED_AUDIO / "_subs_concat.wav")
    listfile = str(tempfile.mkdtemp(prefix="sns_s_")) + "/l.txt"
    with open(listfile, "w") as f:
        for t in tts:
            f.write(f"file '{os.path.abspath(t).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                        "-c", "copy", concat_wav], capture_output=True, text=True, timeout=120)
    try:
        os.unlink(listfile)
    except Exception:
        pass
    return concat_wav if r.returncode == 0 and os.path.isfile(concat_wav) else ""

def _word_timings(concat_wav):
    """Run faster-whisper (CPU int8, like Crayon Diet) to get per-word timings."""
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(concat_wav, language="en",
                                   word_timestamps=True, vad_filter=False)
    words = []
    for seg in segments:
        if seg.words:
            for w in seg.words:
                words.append({"word": w.word.strip(),
                              "start": w.start, "end": w.end})
    return words

def _add_word_subtitles(video_path, shots, style="mrbeast") -> str:
    """Burn word-level animated subtitles (Crayon Diet method) into a video.
    Returns path to the captioned video (replaces the original file), or the
    original path on failure."""
    try:
        from ass_subtitles import generate_ass, burn_ass
    except Exception as e:
        print(f"  [SUBS] ass_subtitles import failed: {e}")
        return video_path
    concat_wav = _concat_tts(shots)
    if not concat_wav or not os.path.isfile(concat_wav):
        print("  [SUBS] no TTS to subtitle")
        return video_path
    try:
        words = _word_timings(concat_wav)
        if not words:
            print("  [SUBS] whisper returned no words")
            return video_path
        print(f"  [SUBS] got {len(words)} words")
    except Exception as e:
        print(f"  [SUBS] whisper failed ({e})")
        return video_path
    finally:
        try:
            os.unlink(concat_wav)
        except Exception:
            pass

    ass_path = video_path + ".ass"
    try:
        ok = generate_ass(words, ass_path, style=style,
                          video_width=W_RES, video_height=H_RES)
        if not ok:
            print("  [SUBS] ASS generation failed")
            return video_path
    except Exception as e:
        print(f"  [SUBS] ASS gen error: {e}")
        return video_path

    print(f"  [SUBS] burning {style} captions...")
    out = burn_ass(video_path, ass_path, timeout=1200)
    try:
        os.unlink(ass_path)
    except Exception:
        pass
    if out and os.path.isfile(out):
        # replace original with captioned version
        try:
            os.unlink(video_path)
        except Exception:
            pass
        os.rename(out, video_path)
        print("  [SUBS] styled captions burned in")
        return video_path
    print("  [SUBS] burn failed - keeping uncaptioned")
    return video_path


if __name__ == "__main__":
    # CLI helper commands
    if len(sys.argv) > 1 and sys.argv[1] == "styles":
        for name, desc in sorted(_load_style_profiles().items()):
            print(f"  {name:16} {desc[:60]}")
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "add-style":
        if len(sys.argv) >= 4:
            add_custom_style(sys.argv[2], " ".join(sys.argv[3:]))
        sys.exit(0)
    run()
