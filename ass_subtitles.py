#!/usr/bin/env python3
"""
Styled ASS subtitle generation with word-level animations.
Ported from ai-video-captions (github.com/nicolaigaina/ai-video-captions)
for integration into The Crayon Diet.

6 styles: hormozi, mrbeast, karaoke, minimal, bounce, classic
"""

import os
import re
import subprocess

import pysubs2

# ── Style definitions ──────────────────────────────────────────────────

STYLES = {
    "hormozi": {
        "font_name": "Arial",
        "font_name_fallback": "Arial",
        "font_size": 105,
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H0000FFFF",  # yellow highlight
        "outline_color": "&H00000000",
        "shadow_color": "&H00000000",
        "outline_size": 3.0,
        "shadow_depth": 1.5,
        "bold": True,
        "italic": False,
        "letter_spacing": 8.0,
        "word_spacing": 100,
        "animation_type": "highlight",
    },
    "mrbeast": {
        "font_name": "Arial",
        "font_name_fallback": "Arial",
        "font_size": 110,
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H0000FF00",  # red highlight
        "outline_color": "&H00000000",
        "shadow_color": "&H00000000",
        "outline_size": 4.0,
        "shadow_depth": 2.0,
        "bold": True,
        "italic": False,
        "letter_spacing": 5.0,
        "word_spacing": 100,
        "animation_type": "scale",
    },
    "karaoke": {
        "font_name": "Arial",
        "font_name_fallback": "Arial",
        "font_size": 95,
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H0000FFFF",
        "outline_color": "&H00000000",
        "shadow_color": "&H00000000",
        "outline_size": 2.5,
        "shadow_depth": 1.0,
        "bold": True,
        "italic": False,
        "letter_spacing": 3.0,
        "word_spacing": 100,
        "animation_type": "karaoke",
    },
    "minimal": {
        "font_name": "Arial",
        "font_name_fallback": "Arial",
        "font_size": 80,
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H00FFFF00",
        "outline_color": "&H00000000",
        "shadow_color": "&H00000000",
        "outline_size": 1.5,
        "shadow_depth": 0.0,
        "bold": False,
        "italic": False,
        "letter_spacing": 0.0,
        "word_spacing": 100,
        "animation_type": "highlight",
    },
    "bounce": {
        "font_name": "Arial",
        "font_name_fallback": "Arial",
        "font_size": 100,
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H0000FFFF",
        "outline_color": "&H00000000",
        "shadow_color": "&H00000000",
        "outline_size": 3.0,
        "shadow_depth": 1.5,
        "bold": True,
        "italic": False,
        "letter_spacing": 5.0,
        "word_spacing": 100,
        "animation_type": "bounce",
    },
    "classic": {
        "font_name": "Arial",
        "font_name_fallback": "Arial",
        "font_size": 85,
        "primary_color": "&H00FFFFFF",
        "highlight_color": "&H00FFFF00",
        "outline_color": "&H00000000",
        "shadow_color": "&H00000000",
        "outline_size": 2.0,
        "shadow_depth": 1.0,
        "bold": False,
        "italic": False,
        "letter_spacing": 0.0,
        "word_spacing": 100,
        "animation_type": "highlight",
    },
}


def _parse_ass_color(ass_color: str) -> pysubs2.Color:
    """Parse ASS colour string &HAABBGGRR& to pysubs2.Color."""
    color_hex = ass_color.replace("&H", "").replace("&", "").zfill(8)
    alpha = int(color_hex[0:2], 16)
    blue = int(color_hex[2:4], 16)
    green = int(color_hex[4:6], 16)
    red = int(color_hex[6:8], 16)
    return pysubs2.Color(red, green, blue, alpha)


def _escape_ass(text: str) -> str:
    """Escape text for safe use in ASS subtitle files."""
    text = text.replace("\\", "\\\\")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    text = text.replace("\n", " ")
    return text


def _strip_emojis(text: str) -> str:
    """Remove emoji characters that libass may not render."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002500-\U00002BEF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub("", text).strip()


def generate_ass(
    word_timings: list[dict],
    output_path: str,
    *,
    style: str = "hormozi",
    video_width: int = 1080,
    video_height: int = 1920,
) -> bool:
    """Generate a styled ASS subtitle file from word timings.

    Args:
        word_timings: List of {"word": str, "start": float, "end": float}
        output_path: Path to write .ass file
        style: Style key (hormozi, mrbeast, karaoke, minimal, bounce, classic)
        video_width/video_height: Video resolution for positioning

    Returns:
        True if successful, False if no words provided.
    """
    if not word_timings:
        return False

    style_config = STYLES.get(style, STYLES["hormozi"])
    play_res_x = video_width
    play_res_y = video_height
    dimension_scale = max(video_height / 1920, 0.35)

    # Filter and clean words
    clip_words = []
    for w in word_timings:
        text = _strip_emojis(w["word"].strip())
        if not text:
            continue
        clip_words.append({
            "word": text,
            "start": w["start"],
            "end": w["end"],
        })

    if not clip_words:
        return False

    char_width = 0.55
    max_chars_per_line = max(5, int(850 / (style_config["font_size"] * char_width)))
    max_lines = 2

    # Group words into subtitle chunks
    subtitles = []  # [(start, end, [(word, start, end, line_idx), ...]), ...]
    current_lines = [[]]
    current_line_chars = [0]
    current_start = None
    current_end = None

    for seg in clip_words:
        word = seg["word"]
        seg_start = seg["start"]
        seg_end = seg["end"]

        if seg_end <= 0:
            continue

        word_length = len(word)

        if not any(current_lines):
            current_start = seg_start
            current_end = seg_end
            current_lines = [[(word, seg_start, seg_end)]]
            current_line_chars = [word_length]
        else:
            line_idx = len(current_lines) - 1
            chars = current_line_chars[line_idx]
            chars_with_word = chars + (1 if current_lines[line_idx] else 0) + word_length

            if chars_with_word <= max_chars_per_line:
                current_lines[line_idx].append((word, seg_start, seg_end))
                current_line_chars[line_idx] = chars_with_word
                current_end = seg_end
            elif line_idx + 1 < max_lines:
                current_lines.append([(word, seg_start, seg_end)])
                current_line_chars.append(word_length)
                current_end = seg_end
            else:
                flattened = []
                for li, line in enumerate(current_lines):
                    for wt in line:
                        flattened.append(wt + (li,))
                subtitles.append((current_start, current_end, flattened))

                current_start = seg_start
                current_end = seg_end
                current_lines = [[(word, seg_start, seg_end)]]
                current_line_chars = [word_length]

    # Flush last group
    if any(current_lines):
        flattened = []
        for li, line in enumerate(current_lines):
            for wt in line:
                flattened.append(wt + (li,))
        subtitles.append((current_start, current_end, flattened))

    # ── Create ASS file ──
    subs = pysubs2.SSAFile()
    subs.info["WrapStyle"] = "3"
    subs.info["ScaledBorderAndShadow"] = "yes"
    subs.info["PlayResX"] = play_res_x
    subs.info["PlayResY"] = play_res_y
    subs.info["ScriptType"] = "v4.00+"

    # Style definition
    s = pysubs2.SSAStyle()
    s.fontname = style_config["font_name"]
    s.fontsize = int(style_config["font_size"] * dimension_scale)
    s.primarycolor = _parse_ass_color(style_config["primary_color"])
    s.bold = style_config["bold"]
    s.italic = style_config["italic"]
    s.outline = round(style_config["outline_size"] * dimension_scale, 1)
    s.outlinecolor = _parse_ass_color(style_config["outline_color"])
    s.shadow = round(style_config["shadow_depth"] * dimension_scale, 1)
    s.shadowcolor = _parse_ass_color(style_config["shadow_color"])
    s.alignment = pysubs2.Alignment.BOTTOM_CENTER
    s.marginl = int(40 * dimension_scale)
    s.marginr = int(40 * dimension_scale)
    s.marginv = int(play_res_y * 10 / 100)  # 10% from bottom
    s.spacing = 0.5
    subs.styles["Default"] = s

    highlight_color = style_config["highlight_color"]
    animation_type = style_config["animation_type"]

    # Generate per-word events
    for _, line_end, word_list in subtitles:
        for idx, (word, word_start, _, _) in enumerate(word_list):
            event_end = word_list[idx + 1][1] if idx < len(word_list) - 1 else line_end

            text_parts = []
            prev_line_idx = None

            for i, (w, w_start, w_end, line_idx) in enumerate(word_list):
                if prev_line_idx is not None and line_idx != prev_line_idx:
                    text_parts.append("\\N")

                w_upper = _escape_ass(w.upper())

                if i == idx:
                    wc = highlight_color
                    if animation_type == "karaoke":
                        dur_cs = int((w_end - w_start) * 100) if w_end > w_start else 30
                        text_parts.append(f"{{\\kf{dur_cs}\\c{wc}}}{w_upper}{{\\r}}")
                    elif animation_type == "scale":
                        text_parts.append(f"{{\\fscx110\\fscy110\\c{wc}}}{w_upper}{{\\r}}")
                    elif animation_type == "bounce":
                        bp = 120
                        text_parts.append(
                            f"{{\\t(0,50,\\fscx{bp}\\fscy{bp})"
                            f"\\t(50,100,\\fscx100\\fscy100)"
                            f"\\c{wc}}}{w_upper}{{\\r}}"
                        )
                    else:
                        text_parts.append(f"{{\\c{wc}}}{w_upper}{{\\r}}")
                else:
                    text_parts.append(w_upper)

                prev_line_idx = line_idx

            text = " ".join(text_parts)
            if style_config["letter_spacing"] != 0:
                text = f"{{\\fsp{style_config['letter_spacing']}}}{text}"

            event = pysubs2.SSAEvent(
                start=pysubs2.make_time(s=word_start),
                end=pysubs2.make_time(s=event_end),
                text=text,
                style="Default",
            )
            subs.events.append(event)

    try:
        subs.save(output_path)
    except Exception as e:
        raise IOError(f"Failed to save ASS file: {e}") from e

    return True


def burn_ass(video_path: str, ass_path: str, output_path: str | None = None, timeout: int = 300) -> str | None:
    """Burn ASS subtitles into a video using ffmpeg.

    Args:
        video_path: Input video file
        ass_path: ASS subtitle file
        output_path: Output video path (default: replace .mp4 with _captioned.mp4)

    Returns:
        Path to captioned video, or None on failure.
    """
    if output_path is None:
        output_path = video_path.replace(".mp4", "_captioned.mp4")

    # Use relative filename to avoid Windows drive-letter colon in filter path
    import shutil
    vid_dir = os.path.dirname(os.path.abspath(video_path))
    temp_ass = "_subs_temp.ass"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles={temp_ass}",
        "-c:v", "hevc_nvenc", "-preset", "p7", "-rc", "vbr", "-cq", "28", "-b:v", "0",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    try:
        shutil.copy(ass_path, os.path.join(vid_dir, temp_ass))
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=vid_dir)
        try: os.unlink(os.path.join(vid_dir, temp_ass))
        except: pass
        if r.returncode != 0:
            print(f"  [ASS] Burn error: {r.stderr[-200:]}")
            return None
        if os.path.isfile(output_path) and os.path.getsize(output_path) > 1000:
            return output_path
        return None
    except subprocess.TimeoutExpired:
        print(f"  [ASS] Burn timed out")
        return None
    except Exception as e:
        print(f"  [ASS] Burn exception: {e}")
        return None
