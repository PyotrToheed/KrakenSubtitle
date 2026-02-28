# KrakenSubtitle

**One command. Word-by-word animated subtitles burned into your video.**

Give it a video — get it back with karaoke-style subtitles where each word highlights as it's spoken. Works with any video format, any resolution, any aspect ratio.

---

## How It Works

```
Your Video (any format)
       |
  Transcription         Deepgram Nova-3 (cloud) or Whisper (local)
       |
  Word Timestamps        Millisecond-accurate per-word timing
       |
  Subtitle Engine        3-word phrases, active word highlighted
       |
  FFmpeg Burn             Subtitles baked into video
       |
  Output Video            Ready to upload anywhere
```

## Quick Start

### 1. Install FFmpeg

```bash
# Windows
winget install ffmpeg

# Mac
brew install ffmpeg

# Linux
sudo apt install ffmpeg
```

### 2. Clone and install

```bash
git clone https://github.com/PyotrToheed/KrakenSubtitle.git
cd KrakenSubtitle
pip install -r requirements.txt
```

### 3. Set up Deepgram (recommended)

1. Go to [console.deepgram.com](https://console.deepgram.com)
2. Sign up — free tier gives **$200 credit** (enough for ~100 hours)
3. Create an API key
4. Create a `.env` file:

```bash
DEEPGRAM_API_KEY=your-key-here
```

### 4. Run it

```bash
python kraken.py your_video.mp4
```

Your subtitled video will be saved as `your_video_subtitled.mp4`.

---

## Usage

```bash
# Basic usage
python kraken.py video.mp4

# Custom output name
python kraken.py video.mp4 -o my_output.mp4

# Use local Whisper (no API key needed, slower)
python kraken.py video.mp4 --engine whisper

# Force language detection
python kraken.py video.mp4 --language hi

# Customize subtitle style
python kraken.py video.mp4 --font "Arial Bold" --font-size 56 --color "#FF5733"

# Center subtitles instead of bottom
python kraken.py video.mp4 --position center

# Keep the .ass subtitle file
python kraken.py video.mp4 --keep-subs
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `input` | required | Input video path |
| `-o, --output` | `{input}_subtitled.mp4` | Output video path |
| `--engine` | `deepgram` | `deepgram` (cloud) or `whisper` (local) |
| `--language` | `auto` | `en`, `hi`, `ur`, `he`, or `auto` |
| `--font` | `Montserrat ExtraBold` | Font name |
| `--font-size` | `44` | Font size in pixels |
| `--color` | `#00D4FF` | Active word highlight color (hex) |
| `--outline` | `4` | Outline thickness |
| `--position` | `bottom` | `bottom` or `center` |
| `--crf` | `18` | Video quality (0-51, lower = better) |
| `--keep-subs` | `false` | Keep the .ass file after burning |

## Supported Languages

| Language | Deepgram | Whisper | RTL |
|----------|----------|---------|-----|
| English | Yes | Yes | - |
| Hindi | Yes | Yes | - |
| Urdu | Yes | Yes | Yes |
| Hebrew | Yes | Yes | Yes |

## No API Key? Use Local Mode

```bash
pip install faster-whisper torch
python kraken.py video.mp4 --engine whisper
```

Runs the Whisper large-v3 AI model on your computer. Slower but completely free and offline. GPU (CUDA) recommended for speed.

## Subtitle Style

- **3-word phrases** — fast, dynamic text changes
- **Active word highlight** — cyan pop with 110% scale animation
- **Bold white text** — high contrast on any background
- **Black outline + shadow** — readable over bright and dark scenes
- **Overlap prevention** — no double-text glitches
- **Auto-scaling** — adapts to any video resolution (16:9, 9:16, square)
- **RTL support** — Hebrew and Urdu rendered correctly

## Project Structure

```
KrakenSubtitle/
  kraken.py              # CLI entry point
  transcriber.py         # Deepgram + Whisper transcription
  subtitle_generator.py  # ASS karaoke subtitle engine
  burner.py              # FFmpeg subtitle burn-in
  requirements.txt       # Python dependencies
  .env.example           # API key template
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Cloud Transcription | Deepgram Nova-3 |
| Local Transcription | faster-whisper large-v3 |
| Subtitle Format | ASS v4.00+ (Advanced SubStation Alpha) |
| Video Rendering | FFmpeg (libx264 + libass) |

## License

MIT — use it however you want.
