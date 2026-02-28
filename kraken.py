"""
KrakenSubtitle — Word-by-word karaoke subtitles for any video.

Usage:
    python kraken.py video.mp4
    python kraken.py video.mp4 -o output.mp4
    python kraken.py video.mp4 --engine whisper
    python kraken.py video.mp4 --language hi
    python kraken.py video.mp4 --font "Arial Bold" --font-size 56 --color "#FF5733"
"""

import argparse
import os
import sys
import time
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from transcriber import transcribe
from subtitle_generator import generate_ass
from burner import get_video_info, burn


def parse_args():
    parser = argparse.ArgumentParser(
        description="KrakenSubtitle — Word-by-word karaoke subtitles for any video.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python kraken.py video.mp4                      Basic usage (Deepgram, auto language)\n"
            "  python kraken.py video.mp4 -o subtitled.mp4     Custom output name\n"
            "  python kraken.py video.mp4 --engine whisper     Local mode (no API key needed)\n"
            "  python kraken.py video.mp4 --language hi        Force Hindi\n"
            "  python kraken.py video.mp4 --color \"#FF5733\"    Custom highlight color\n"
        ),
    )

    parser.add_argument("input", help="Path to input video file")
    parser.add_argument("-o", "--output", help="Output video path (default: input_subtitled.mp4)")
    parser.add_argument("--engine", choices=["deepgram", "whisper"], default="deepgram",
                        help="Transcription engine (default: deepgram)")
    parser.add_argument("--language", default="auto",
                        choices=["auto", "en", "hi", "ur", "he"],
                        help="Language (default: auto-detect)")
    parser.add_argument("--font", default="Montserrat ExtraBold",
                        help="Subtitle font name (default: Montserrat ExtraBold)")
    parser.add_argument("--font-size", type=int, default=44,
                        help="Font size in pixels (default: 44)")
    parser.add_argument("--color", default="#00D4FF",
                        help="Highlight color as hex (default: #00D4FF cyan)")
    parser.add_argument("--outline", type=int, default=4,
                        help="Outline thickness (default: 4)")
    parser.add_argument("--position", choices=["bottom", "center"], default="bottom",
                        help="Subtitle position (default: bottom)")
    parser.add_argument("--crf", type=int, default=18,
                        help="Video quality 0-51, lower=better (default: 18)")
    parser.add_argument("--keep-subs", action="store_true",
                        help="Keep the .ass subtitle file after burning")

    return parser.parse_args()


def main():
    args = parse_args()

    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # Default output name
    if not args.output:
        stem = os.path.splitext(os.path.basename(args.input))[0]
        output_dir = os.path.dirname(os.path.abspath(args.input))
        args.output = os.path.join(output_dir, f"{stem}_subtitled.mp4")

    print()
    print("=" * 55)
    print("  KrakenSubtitle")
    print("=" * 55)
    print(f"  Input:    {os.path.basename(args.input)}")
    print(f"  Engine:   {args.engine}")
    print(f"  Language: {args.language}")
    print(f"  Output:   {os.path.basename(args.output)}")
    print("=" * 55)
    print()

    total_start = time.time()

    # ---------------------------------------------------------------
    # Step 1: Transcribe
    # ---------------------------------------------------------------
    print("[1/3] Transcribing...")
    words = transcribe(args.input, engine=args.engine, language=args.language)

    if not words:
        print("Error: No words detected in the video.")
        sys.exit(1)

    print(f"  Total: {len(words)} words detected")
    print()

    # ---------------------------------------------------------------
    # Step 2: Generate subtitles
    # ---------------------------------------------------------------
    print("[2/3] Generating subtitles...")

    # Get video resolution for proper subtitle scaling
    info = get_video_info(args.input)
    print(f"  Video: {info['width']}x{info['height']}, {info['duration']:.1f}s")

    # Create ASS file
    if args.keep_subs:
        stem = os.path.splitext(os.path.basename(args.input))[0]
        ass_path = os.path.join(os.path.dirname(os.path.abspath(args.input)), f"{stem}.ass")
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".ass", delete=False, prefix="kraken_")
        ass_path = tmp.name
        tmp.close()

    generate_ass(
        words=words,
        output_path=ass_path,
        video_width=info["width"],
        video_height=info["height"],
        font=args.font,
        font_size=args.font_size,
        highlight_color=args.color,
        outline=args.outline,
        position=args.position,
    )
    print()

    # ---------------------------------------------------------------
    # Step 3: Burn subtitles into video
    # ---------------------------------------------------------------
    print("[3/3] Burning subtitles into video...")
    success = burn(args.input, ass_path, args.output, crf=args.crf)

    # Cleanup
    if not args.keep_subs and os.path.exists(ass_path):
        os.remove(ass_path)

    total_elapsed = time.time() - total_start

    print()
    if success:
        print("=" * 55)
        print(f"  Done in {total_elapsed:.1f}s")
        print(f"  Output: {args.output}")
        if args.keep_subs:
            print(f"  Subs:   {ass_path}")
        print("=" * 55)
    else:
        print("  Failed to burn subtitles. Check FFmpeg output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
