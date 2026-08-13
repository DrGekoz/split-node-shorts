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

Backends: IMAGE_BACKEND=higgsfield (default, nano_banana_flash) or
gptimage2 (GPT Image 2 via higgsfield - for when the rate limit lifts).
Default is higgsfield.
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
POCKET_TTS_URL = os.environ.get("POCKET_TTS_URL", "http://127.0.0.1:8769")
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
IMAGE_BACKEND = os.environ.get("IMAGE_BACKEND", "higgsfield").strip().lower()  # higgsfield | gptimage2
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
        "Stylized hand-painted comic realism, cel-shaded 3D rendering, bold inked "
        "outlines, graphic-novel linework, exaggerated edge definition, painterly "
        "textures, distressed surfaces, gritty weathering, visible scratches and "
        "imperfections, high-contrast lighting, dramatic rim lighting, saturated "
        "but slightly dirty color palette, warm highlights against cool shadows, "
        "strong ambient occlusion, sharp facial and object definition, chunky "
        "simplified forms, slightly exaggerated proportions, textured brush strokes, "
        "rough cross-hatching, poster-like shading, cinematic depth of field, "
        "atmospheric bloom, punchy highlights, deep shadows, stylized realism, "
        "rebellious retro-futuristic aesthetic, polished video-game concept art "
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
    candidates = []
    seen_links = set()
    feeds = list(MONEY_FEEDS); random.shuffle(feeds)
    for feed in feeds:
        for it in _fetch_rss(feed):
            link = it["link"]
            if link in used or link in rejected or link in seen_links:
                continue
            score = _money_score(it["title"], it.get("description", ""))
            if score < 40:
                continue
            it["score"] = score
            seen_links.add(link)
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
    used = _load_used()
    rejected = _load_rejected()
    rejected_set = set(rejected.keys())

    print("\n[STORY] Pick a topic source:")
    print("  [RSS]  scan feeds for a money-exploit story")
    print("  [URL]  enter your own article URL")
    src = input("  Enter a URL, or press Enter for RSS: ").strip().strip('"\'')
    if src and src.lower().startswith(("http://", "https://")):
        _save_used(src)
        return src, _fetch_page_title(src)

    print("\n[RSS] Scanning money-exploit feeds...")
    pool = _scan_money_candidates(used, rejected_set)
    if not pool:
        print("  [FAIL] No money-exploit stories found. Try again later.")
        return "", ""
    print(f"  [RSS] {len(pool)} candidate stories found\n")

    pool_idx, rounds = 0, 0
    while True:
        if pool_idx >= len(pool):
            rounds += 1
            if rounds >= 6:
                print("  [FAIL] Ran out of stories after 6 re-polls.")
                return "", ""
            print(f"\n  [RSS] Pool exhausted. Re-polling feeds...")
            time.sleep(2)
            pool = _scan_money_candidates(used, rejected_set)
            pool_idx = 0
            if not pool:
                return "", ""
        chosen = pool[pool_idx]; pool_idx += 1
        print(f"  {'='*58}")
        print(f"  CANDIDATE STORY:")
        print(f"    {chosen['title']}")
        print(f"    {chosen['link']}")
        print(f"    [money_score={chosen['score']}]")
        print(f"  {'='*58}")
        resp = input("  Use this topic? (Y/n/q): ").strip().lower()
        if resp in ("q", "quit"):
            print("  [SKIP] Aborted")
            return "", ""
        if resp in ("", "y", "yes"):
            _save_used(chosen["link"])
            return chosen["link"], chosen["title"]
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

def _build_script(topic, article_url, content):
    msg = [
        {"role": "system", "content": SHORTS_SCRIPT_SYSTEM},
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
    if re.match(r'^by\s+[A-Z][a-zA-Z\'\-\]+(\s+[A-Z][a-zA-Z\'\-\]+){0,3}\.?$', text):
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

def _generate_image(prompt, out_path, refs=None):
    """Generate one vertical 9:16 image via Higgsfield.
    Backend higgsfield -> nano_banana_flash (1.5cr). gptimage2 -> GPT Image 2 (future)."""
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
def _tts(text, out_path):
    """PocketTTS narration via multipart/form-data (the /tts endpoint expects
    multipart, NOT JSON — a JSON POST silently 422s and produces no audio).
    TTS_VOICE is a built-in catalog voice name sent as voice_url, or a cloned
    .wav file path sent as voice_wav."""
    try:
        import requests
        # multipart form fields: text (required), voice_url (built-in name) or
        # voice_wav (cloned clip file)
        data = {"text": text}
        files = {}
        if os.path.isfile(str(TTS_VOICE)):
            files["voice_wav"] = open(str(TTS_VOICE), "rb")
        else:
            data["voice_url"] = str(TTS_VOICE)
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
    """Concatenate TTS clips in order -> a single mix WAV. Returns path or None."""
    tts = [s["tts"] for s in shots if s.get("tts") and os.path.isfile(s["tts"])]
    if not tts:
        return None
    listfile = str(tempfile.mkdtemp(prefix="sns_a_")) + "/a.txt"
    with open(listfile, "w") as f:
        for t in tts:
            f.write(f"file '{os.path.abspath(t).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n")
    out = str(RENDERED_AUDIO / "mix.wav")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                        "-af", "volume=2.0dB,alimiter=limit=1.0", "-ar", "44100", "-ac", "2", out],
                       capture_output=True, text=True, timeout=300)
    return out if r.returncode == 0 and os.path.isfile(out) else None

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
    if not YOUTUBE_CREDENTIALS.is_file():
        return None
    try:
        from google.oauth2.credentials import Credentials as GC
        from google.auth.transport.requests import Request as GRequest
        data = json.loads(YOUTUBE_CREDENTIALS.read_text())
        creds = GC(
            token=data.get("access_token", data.get("token", "")),
            refresh_token=data.get("refresh_token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            scopes=data.get("scopes", ["https://www.googleapis.com/auth/youtube.upload"]))
        if not creds.valid:
            creds.refresh(GRequest())
            data["access_token"] = creds.token
            data["token"] = creds.token
            YOUTUBE_CREDENTIALS.write_text(json.dumps(data, indent=2))
            print("  [OK] YouTube token refreshed")
        return creds
    except Exception as e:
        print(f"  [WARN] Credential load failed: {e}")
        return None

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
                print("  [WARN] Re-auth needed: python oauth_split_node.py")
            return None
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
def run():
    print("=" * 58)
    print("  SPLIT NODE SHORTS - vertical money-exploit Shorts generator")
    print(f"  backend=image:{IMAGE_BACKEND}  video:{VIDEO_BACKEND}")
    print(f"  style={_active_style_name()}  target={int(TARGET_SECONDS)}s  max={int(MAX_SECONDS)}s")
    print("=" * 58)

    if not _llm_reachable():
        print("  [FATAL] LM Studio not reachable. Load gemma-4-e4b-uncensored first.")
        return

    # Ping the live video-model price every run; surface a change if it moved.
    _check_video_price()

    # Pick a story AND resolve its article before committing. If the chosen
    # article is blocked / returns no content (or the script can't be built),
    # reject it and loop back to picking a different one instead of quitting
    # (Joe 2026-08-14).
    max_attempts = int(os.environ.get("STORY_RESOLVE_ATTEMPTS", "5"))
    url, topic = "", ""
    content = []
    script = {}
    for _attempt in range(1, max_attempts + 1):
        url, topic = _pick_story()
        if not url:
            return
        print(f"\n  [TOPIC] {topic}\n  [URL] {url}")
        content = fetch_article_paragraphs(url)
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
            prompt = (f"{style}. Vertical 9:16 cinematic frame for a money-exploit short. "
                      f"Scene: {s['spoken']}. Highly detailed, dramatic lighting.")
            if _scene_shows_hands(s["spoken"]):
                prompt += _hands_clause()
            print(f"  [IMG {i+1}/{len(shots)}] {s['spoken'][:50]}...")
            _generate_image(prompt, img)
            s["image"] = img if os.path.isfile(img) else None
            tts = str(RENDERED_AUDIO / f"scene_{i:03d}.wav")
            _tts(s["spoken"], tts)
            s["tts"] = tts if os.path.isfile(tts) else None
            s["dur"] = max(_audio_duration(tts), 2.0) if os.path.isfile(tts) else s["dur"]

        with _TPE(max_workers=_conc) as _ex:
            list(_ex.map(_gen_one, list(enumerate(shots))))
    else:
        for i, s in enumerate(shots):
            img = str(SHOTS_DIR / f"scene_{i:03d}.png")
            prompt = (f"{style}. Vertical 9:16 cinematic frame for a money-exploit short. "
                      f"Scene: {s['spoken']}. Highly detailed, dramatic lighting.")
            # Hands/anatomy clause (Split Node Bug 3 port): stylized models hallucinate
            # fingers on hand-visible scenes (clicking/typing/counting cash).
            if _scene_shows_hands(s["spoken"]):
                prompt += _hands_clause()
            print(f"  [IMG {i+1}/{len(shots)}] {s['spoken'][:50]}...")
            _generate_image(prompt, img)
            s["image"] = img if os.path.isfile(img) else None

            tts = str(RENDERED_AUDIO / f"scene_{i:03d}.wav")
            _tts(s["spoken"], tts)
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
