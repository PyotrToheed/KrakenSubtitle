"""
FFmpeg subtitle burner — overlays ASS subtitles onto video.
"""

import os
import json
import shutil
import subprocess
import sys
import tempfile


def get_video_info(video_path: str) -> dict:
    """Get video width, height, and duration using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        fmt = data.get("format", {})
        return {
            "width": int(stream.get("width", 1920)),
            "height": int(stream.get("height", 1080)),
            "duration": float(fmt.get("duration", 0)),
        }
    except Exception as e:
        print(f"  Warning: ffprobe failed ({e}), using defaults 1920x1080")
        return {"width": 1920, "height": 1080, "duration": 0}


def escape_ass_path(path: str) -> str:
    """
    Escape subtitle path for FFmpeg's libass filter on Windows.
    FFmpeg uses : as a special character, and backslashes must be forward slashes.
    """
    abs_path = os.path.abspath(path)
    escaped = abs_path.replace("\\", "/").replace(":", "\\:")
    escaped = escaped.replace("'", "'\\''")
    return escaped


def burn(video_path: str, ass_path: str, output_path: str, crf: int = 18) -> bool:
    """
    Burn ASS subtitles onto video using FFmpeg.

    Copies the ASS file to a safe temp path (no special characters) to avoid
    FFmpeg subtitle filter path issues with apostrophes, spaces, etc.

    Returns True on success, False on failure.
    """
    # Copy ASS to a safe temp path — avoids apostrophes/special chars in filename
    # breaking FFmpeg's subtitles='...' filter
    safe_dir = tempfile.mkdtemp(prefix="kraken_burn_")
    safe_ass = os.path.join(safe_dir, "subs.ass")
    shutil.copy2(ass_path, safe_ass)

    sub_escaped = escape_ass_path(safe_ass)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles='{sub_escaped}'",
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour max for long videos
            encoding="utf-8",
            errors="replace",
        )

        if process.returncode != 0:
            print(f"  FFmpeg error: {process.stderr[-500:]}", file=sys.stderr)
            return False

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  Output: {output_path} ({size_mb:.1f} MB)")
        return True

    except subprocess.TimeoutExpired:
        print("  FFmpeg timed out (1 hour limit)", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  FFmpeg failed: {e}", file=sys.stderr)
        return False
    finally:
        # Cleanup safe temp copy
        shutil.rmtree(safe_dir, ignore_errors=True)
