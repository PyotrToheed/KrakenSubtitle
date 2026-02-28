"""
Kraken Subtitle Generator — Word-by-word karaoke ASS subtitles.

Groups words into 3-word phrases. Active word highlights in color with pop animation.
Supports RTL languages (Hebrew, Urdu). Overlap prevention built in.
"""

import os
import re
from pathlib import Path


# Timing constants
MAX_BRIDGE_DURATION = 1.2   # Max gap to bridge between phrases (seconds)
MAX_EVENT_DURATION = 2.0    # Absolute max for any single subtitle event
STACKED_THRESHOLD = 0.20    # 200ms window for detecting stacked words
MIN_BLOCK_SIZE = 4          # Min words to count as a stacked block
WORDS_PER_SEC = 4.0         # Rate for redistributing stacked words
MIN_READABLE_DURATION = 0.08  # 80ms minimum per word


def hex_to_ass_color(hex_color: str) -> str:
    """
    Convert #RRGGBB hex color to ASS &HBBGGRR format.
    ASS uses Blue-Green-Red order, not RGB.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return "&H00D4FF"  # Default cyan
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    return f"&H{b}{g}{r}"


def generate_ass(
    words: list,
    output_path: str,
    video_width: int = 1920,
    video_height: int = 1080,
    font: str = "Montserrat ExtraBold",
    font_size: int = 44,
    highlight_color: str = "#00D4FF",
    outline: int = 4,
    position: str = "bottom",
) -> str:
    """
    Generate ASS subtitle file with word-by-word karaoke highlighting.

    Args:
        words: List of {"word": str, "start": float, "end": float}
        output_path: Where to save the .ass file
        video_width: Video width in pixels
        video_height: Video height in pixels
        font: Font name
        font_size: Font size in pixels
        highlight_color: Active word color as #RRGGBB hex
        outline: Outline thickness in pixels
        position: "bottom" or "center"

    Returns:
        Path to the generated .ass file
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Convert hex color to ASS format
    ass_highlight = hex_to_ass_color(highlight_color)

    # RTL detection (Hebrew / Urdu)
    is_rtl = False
    sample_text = "".join([w.get("word", "") for w in words[:10]])
    if any("\u0590" <= c <= "\u05FF" for c in sample_text):
        is_rtl = True
        font = "Arial"  # Better RTL rendering
    if any("\u0600" <= c <= "\u06FF" for c in sample_text):
        is_rtl = True
        font = "Arial"

    # Alignment: 2 = bottom-center, 5 = center-center
    alignment = 5 if position == "center" else 2

    # Margin from bottom — adaptive to aspect ratio
    if video_height > video_width:
        margin_v = 140  # Vertical video (9:16)
    else:
        margin_v = 60   # Horizontal video (16:9)

    header = (
        f"[Script Info]\n"
        f"Title: Kraken Subtitles\n"
        f"ScriptType: v4.00+\n"
        f"PlayResX: {video_width}\n"
        f"PlayResY: {video_height}\n"
        f"ScaledBorderAndShadow: yes\n"
        f"\n"
        f"[V4+ Styles]\n"
        f"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        f"OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        f"ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        f"Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{font_size},&H00FFFFFF,{ass_highlight},"
        f"&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,{outline},2,"
        f"{alignment},50,50,{margin_v},1\n"
        f"\n"
        f"[Events]\n"
        f"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        f"Effect, Text\n"
    )

    # Pre-process: sort, clean, skip ghosts
    words = sorted(words, key=lambda w: w.get("start", 0))
    cleaned = []
    for w in words:
        ws = w.get("start", 0)
        we = w.get("end", 0)
        text = w.get("word", "").strip()
        if not text or we - ws < 0.01:
            continue
        cleaned.append({"word": text, "start": ws, "end": we})
    words = cleaned

    if not words:
        # Write empty ASS file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header)
        return output_path

    # Fix stacked timestamp blocks
    words = _fix_stacked_blocks(words)

    # Group into 3-word phrases
    max_words = 3
    phrases = []
    current_phrase = []

    for idx, word in enumerate(words):
        current_phrase.append(word)
        pause_after = 0
        if idx < len(words) - 1:
            pause_after = words[idx + 1]["start"] - word["end"]
        if len(current_phrase) >= max_words or (
            pause_after > 0.6 and len(current_phrase) >= 2
        ):
            phrases.append(current_phrase)
            current_phrase = []

    if current_phrase:
        if len(current_phrase) == 1 and phrases:
            phrases[-1].extend(current_phrase)
        else:
            phrases.append(current_phrase)

    # Generate dialogue events
    events = []
    punct = ".,?!"

    for p_idx, phrase in enumerate(phrases):
        phrase_words = [
            w["word"].strip() if is_rtl else w["word"].strip().upper()
            for w in phrase
        ]

        for i, word_obj in enumerate(phrase):
            event_start = word_obj["start"]
            real_end = word_obj["end"]

            if i < len(phrase) - 1:
                next_start = phrase[i + 1]["start"]
                real_end = max(next_start, event_start + 0.01)
                real_end = min(real_end, next_start)
            elif p_idx < len(phrases) - 1:
                next_phrase_start = phrases[p_idx + 1][0]["start"]
                gap = next_phrase_start - event_start
                if gap < MAX_BRIDGE_DURATION:
                    real_end = next_phrase_start
                else:
                    real_end = min(real_end, event_start + MAX_BRIDGE_DURATION)
                real_end = max(real_end, event_start + 0.01)
                real_end = min(real_end, next_phrase_start)
            else:
                real_end = min(real_end, event_start + 2.0)
                real_end = max(real_end, event_start + 0.05)

            # Safety cap
            if real_end - event_start > MAX_EVENT_DURATION:
                real_end = event_start + MAX_EVENT_DURATION

            # Build styled line with highlight on active word
            prefix = " ".join(phrase_words[:i]).translate(
                str.maketrans("", "", punct)
            )
            active = phrase_words[i].translate(str.maketrans("", "", punct))
            suffix = " ".join(phrase_words[i + 1 :]).translate(
                str.maketrans("", "", punct)
            )

            if prefix:
                prefix += " "
            if suffix:
                suffix = " " + suffix

            tag_pop = "{\\1c" + ass_highlight + "\\fscx110\\fscy110}"
            tag_reset = "{\\1c&H00FFFFFF\\fscx100\\fscy100}"
            styled = f"{prefix}{tag_pop}{active}{tag_reset}{suffix}"

            events.append((event_start, real_end, styled))

    # Overlap prevention post-pass
    events.sort(key=lambda e: e[0])
    fixed = []
    for es, ee, text in events:
        if fixed and es < fixed[-1][1]:
            prev = fixed[-1]
            new_end = es
            if new_end - prev[0] >= 0.01:
                fixed[-1] = (prev[0], new_end, prev[2])
            else:
                fixed.pop()
        fixed.append((es, ee, text))

    # Write ASS file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        for es, ee, text in fixed:
            f.write(
                f"Dialogue: 0,{_seconds_to_ass_time(es)},"
                f"{_seconds_to_ass_time(ee)},Default,,0,0,0,,{text}\n"
            )

    overlaps_fixed = len(events) - len(fixed)
    print(f"  Generated {len(fixed)} subtitle events ({overlaps_fixed} overlaps fixed)")
    return output_path


def _fix_stacked_blocks(words: list) -> list:
    """
    Fix blocks of words sharing the same timestamp (forced alignment artifacts).
    Redistributes them across available time gaps.
    """
    if len(words) < 4:
        return words

    result = list(words)
    drop_indices = set()
    i = 0

    while i < len(result):
        block_start = i
        j = i + 1
        while j < len(result) and abs(
            result[j]["start"] - result[j - 1]["start"]
        ) < STACKED_THRESHOLD:
            j += 1

        block_size = j - block_start

        if block_size >= MIN_BLOCK_SIZE:
            anchor = result[block_start]["start"]
            estimated = block_size / WORDS_PER_SEC

            gap_before = 0.0
            if block_start > 0:
                gap_before = anchor - result[block_start - 1]["end"]

            gap_after = float("inf")
            if j < len(result):
                gap_after = result[j]["start"] - anchor

            if gap_before > 2.0:
                spread = min(estimated, gap_before - 0.5) if gap_before <= 10.0 else gap_before - 0.5
                spread = max(spread, 2.0)
                word_dur = max(0.15, min(spread / block_size, 1.0 if gap_before > 10.0 else 0.5))
                actual_span = block_size * word_dur
                start = anchor - actual_span

                for k in range(block_size):
                    idx = block_start + k
                    result[idx]["start"] = round(start + k * word_dur, 3)
                    result[idx]["end"] = round(start + (k + 1) * word_dur, 3)
            else:
                max_forward = gap_after - 0.02 if gap_after < float("inf") else estimated
                if max_forward <= 0:
                    max_forward = 0.5
                word_dur = max_forward / block_size

                if word_dur < MIN_READABLE_DURATION:
                    for k in range(block_size):
                        drop_indices.add(block_start + k)
                else:
                    word_dur = min(word_dur, 0.5)
                    for k in range(block_size):
                        idx = block_start + k
                        result[idx]["start"] = round(anchor + k * word_dur, 3)
                        result[idx]["end"] = round(anchor + (k + 1) * word_dur, 3)

            i = j
        else:
            i += 1

    if drop_indices:
        result = [w for idx, w in enumerate(result) if idx not in drop_indices]

    result.sort(key=lambda w: w["start"])
    return result


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert float seconds to ASS time format H:MM:SS.cc (centiseconds)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int(round((seconds % 1) * 100))
    if centisecs >= 100:
        centisecs = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
