"""
Transcription engine — Deepgram Nova-3 (cloud) or faster-whisper (local).

Both engines return the same format: a flat list of word-level timestamps.
[{"word": "hello", "start": 1.234, "end": 1.567}, ...]
"""

import os
import re
import sys
import json
import time
import subprocess
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Deepgram language codes
DEEPGRAM_LANGUAGES = {
    "hi": "hi",
    "ur": "ur",
    "he": "he",
    "en": "en",
    "auto": None,
}


def transcribe(video_path: str, engine: str = "deepgram", language: str = "auto") -> list:
    """
    Transcribe video and return word-level timestamps.

    Args:
        video_path: Path to the video file
        engine: "deepgram" (cloud, fast) or "whisper" (local, free)
        language: "en", "hi", "ur", "he", or "auto"

    Returns:
        List of {"word": str, "start": float, "end": float}
    """
    if engine == "deepgram":
        return _transcribe_deepgram(video_path, language)
    elif engine == "whisper":
        return _transcribe_whisper(video_path, language)
    else:
        raise ValueError(f"Unknown engine: {engine}. Use 'deepgram' or 'whisper'.")


# ---------------------------------------------------------------------------
# Deepgram Nova-3 (Cloud)
# ---------------------------------------------------------------------------

def _transcribe_deepgram(video_path: str, language: str = "auto") -> list:
    """Transcribe using Deepgram Nova-3 cloud API."""
    import requests

    api_key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "DEEPGRAM_API_KEY not set. Add it to .env or run:\n"
            "  export DEEPGRAM_API_KEY=your-key-here\n\n"
            "Or use local mode: python kraken.py video.mp4 --engine whisper"
        )

    # 1. Extract audio as MP3
    print("  Extracting audio...")
    mp3_path = _extract_audio_mp3(video_path)

    # 2. Split into chunks for long videos
    duration = _get_audio_duration(mp3_path)
    chunks = _split_audio(mp3_path, chunk_seconds=120)
    print(f"  Transcribing {duration:.0f}s in {len(chunks)} chunk(s) with Deepgram Nova-3...")

    # 3. Transcribe each chunk
    all_words = []
    start_time = time.time()

    for i, (chunk_path, offset) in enumerate(chunks):
        print(f"  Chunk {i + 1}/{len(chunks)} (offset {offset:.0f}s)...")

        result = _call_deepgram_api(chunk_path, api_key, language)
        words = _parse_deepgram_response(result)

        # Offset timestamps to absolute position
        for w in words:
            w["start"] = round(w["start"] + offset, 3)
            w["end"] = round(w["end"] + offset, 3)

        all_words.extend(words)
        print(f"    {len(words)} words")

    elapsed = time.time() - start_time
    print(f"  Deepgram done: {len(all_words)} words in {elapsed:.1f}s")

    # Cleanup temp files
    _cleanup_temp(mp3_path, chunks)

    return all_words


def _extract_audio_mp3(video_path: str) -> str:
    """Extract audio from video as mono 16kHz MP3."""
    tmp_dir = tempfile.mkdtemp(prefix="kraken_")
    mp3_path = os.path.join(tmp_dir, "audio.mp3")

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-ac", "1", "-ar", "16000", "-b:a", "64k",
        mp3_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr[:500]}")

    size_mb = os.path.getsize(mp3_path) / 1024 / 1024
    print(f"  Audio extracted: {size_mb:.1f} MB")
    return mp3_path


def _split_audio(audio_path: str, chunk_seconds: int = 120) -> list:
    """Split audio into chunks for reliable upload. Returns [(path, offset)]."""
    duration = _get_audio_duration(audio_path)
    if duration <= chunk_seconds + 30:
        return [(audio_path, 0.0)]

    chunks = []
    chunk_dir = os.path.join(os.path.dirname(audio_path), "chunks")
    os.makedirs(chunk_dir, exist_ok=True)

    offset = 0.0
    idx = 0
    while offset < duration:
        chunk_path = os.path.join(chunk_dir, f"chunk_{idx:02d}.mp3")
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{offset:.3f}",
            "-i", audio_path,
            "-t", f"{chunk_seconds:.3f}",
            "-ac", "1", "-ar", "16000", "-b:a", "32k",
            chunk_path,
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        chunks.append((chunk_path, offset))
        offset += chunk_seconds
        idx += 1

    return chunks


def _call_deepgram_api(audio_path: str, api_key: str, language: str = "auto") -> dict:
    """Call Deepgram REST API."""
    import requests

    params = {
        "model": "nova-3",
        "smart_format": "true",
        "punctuate": "true",
        "utterances": "true",
        "diarize": "true",
        "detect_language": "true",
    }

    lang_code = DEEPGRAM_LANGUAGES.get(language)
    if lang_code:
        params["language"] = lang_code
        params.pop("detect_language", None)

    content_type = "audio/mpeg" if audio_path.endswith(".mp3") else "audio/wav"

    with open(audio_path, "rb") as f:
        audio_data = f.read()

    response = requests.post(
        "https://api.deepgram.com/v1/listen",
        params=params,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": content_type,
        },
        data=audio_data,
        timeout=(30, 300),
    )

    if response.status_code != 200:
        raise RuntimeError(f"Deepgram API error ({response.status_code}): {response.text[:500]}")

    data = response.json()
    if "err_code" in data:
        raise RuntimeError(f"Deepgram error: {data.get('err_msg', data.get('err_code'))}")

    return data


def _parse_deepgram_response(result: dict) -> list:
    """
    Convert Deepgram API response to flat word list.
    Returns [{"word": str, "start": float, "end": float}, ...]
    """
    words = []
    try:
        channel = result["results"]["channels"][0]
        all_words = channel["alternatives"][0].get("words", [])
    except (KeyError, IndexError):
        return words

    for w in all_words:
        text = w.get("word", "").strip()
        start = w.get("start", 0)
        end = w.get("end", 0)
        if not text or end - start < 0.005:
            continue
        words.append({
            "word": text,
            "start": round(start, 3),
            "end": round(end, 3),
        })

    return words


def _get_audio_duration(audio_path: str) -> float:
    """Get duration using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", audio_path],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _cleanup_temp(mp3_path: str, chunks: list):
    """Remove temporary audio files."""
    import shutil
    try:
        tmp_dir = os.path.dirname(mp3_path)
        if "kraken_" in tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Faster-Whisper (Local)
# ---------------------------------------------------------------------------

def _transcribe_whisper(video_path: str, language: str = "auto") -> list:
    """Transcribe using faster-whisper locally (GPU or CPU)."""
    try:
        from faster_whisper import WhisperModel
        import torch
    except ImportError:
        raise RuntimeError(
            "faster-whisper not installed. Run:\n"
            "  pip install faster-whisper torch\n\n"
            "Or use cloud mode: python kraken.py video.mp4 --engine deepgram"
        )

    # 1. Extract audio as WAV
    print("  Extracting audio...")
    tmp_dir = tempfile.mkdtemp(prefix="kraken_")
    wav_path = os.path.join(tmp_dir, "audio.wav")

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000",
        wav_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    # 2. Load model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    print(f"  Loading whisper large-v3 on {device}...")

    model = WhisperModel("large-v3", device=device, compute_type=compute_type)

    # 3. Transcribe
    lang_arg = None if language == "auto" else language
    print("  Transcribing (this may take a while on CPU)...")
    start_time = time.time()

    segments, info = model.transcribe(
        wav_path,
        beam_size=5,
        language=lang_arg,
        vad_filter=True,
        word_timestamps=True,
    )

    print(f"  Detected language: {info.language} ({info.language_probability:.0%})")

    # 4. Flatten to word list
    all_words = []
    for segment in segments:
        text = segment.text.strip()
        # Skip hallucinations
        has_text = re.search(r"[a-zA-Z\u0600-\u06FF\u0590-\u05FF\u0900-\u097F]", text)
        if not has_text or len(text) < 2:
            continue

        for w in segment.words:
            word_text = w.word.strip()
            if not word_text or w.end - w.start < 0.01:
                continue
            all_words.append({
                "word": word_text,
                "start": round(w.start, 3),
                "end": round(w.end, 3),
            })

    elapsed = time.time() - start_time
    print(f"  Whisper done: {len(all_words)} words in {elapsed:.1f}s")

    # Cleanup
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    return all_words
