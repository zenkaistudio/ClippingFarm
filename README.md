# ClippingFarm
> all things ZENKAI clipping

An automated local pipeline for turning streamer/creator VODs into polished, vertical, ready-to-post short clips — built for social media clipping campaigns on platforms like Whop Content Rewards.

## What it does

Feed it a long-form video → it finds the best viral moments → cuts, reframes to 9:16, burns in karaoke-style captions + hook title → ready for TikTok/IG Reels/YouTube Shorts.

```
input/vod.mp4
    → transcribe (mlx-whisper, word-level timestamps, Apple Silicon GPU)
    → detect moments (Claude AI, structured tool-use output)
    → cut clips (ffmpeg, frame-accurate)
    → vertical reframe (1080x1920 center-crop)
    → captions + hook title overlay (ASS karaoke burn-in, ffmpeg-full/libass)
output/<video_id>__clip01__<hook-slug>.mp4
```

## Requirements

- macOS, Apple Silicon (M1/M2/M3)
- Python 3.10+ (3.14 recommended — already available via Homebrew)
- `ffmpeg-full` (Homebrew) — required for libass/drawtext caption burn-in
- An Anthropic API key

### Install ffmpeg-full

```bash
brew install ffmpeg-full
```

> Note: if you already have `ffmpeg` installed, run `brew reinstall ffmpeg` afterward to fix any shared library conflicts.

## Setup

```bash
git clone https://github.com/zenkaistudio/ClippingFarm.git
cd ClippingFarm
/opt/homebrew/bin/python3.14 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # add your ANTHROPIC_API_KEY
cp config.example.json config.json   # adjust settings as needed
```

## Usage

Drop your video into `input/`, then:

```bash
source venv/bin/activate
python scripts/run_pipeline.py --input input/your_vod.mp4 --num-clips 6
```

### Run a single stage

```bash
python scripts/run_pipeline.py --input input/vod.mp4 --stage transcribe
python scripts/run_pipeline.py --input input/vod.mp4 --stage detect_moments
python scripts/run_pipeline.py --input input/vod.mp4 --stage cut
python scripts/run_pipeline.py --input input/vod.mp4 --stage reframe
python scripts/run_pipeline.py --input input/vod.mp4 --stage captions
```

### Re-run a stage

```bash
python scripts/run_pipeline.py --input input/vod.mp4 --stage detect_moments --force
```

## Config

Edit `config.json` to tune the pipeline:

| Key | Default | Description |
|-----|---------|-------------|
| `num_clips` | 6 | Number of clips to produce |
| `clip_length_seconds.min` | 20 | Minimum clip length |
| `clip_length_seconds.max` | 60 | Maximum clip length |
| `whisper_model` | `mlx-community/whisper-medium-mlx` | Whisper model for transcription |
| `claude_model` | `claude-sonnet-4-6` | Claude model for moment detection |
| `crop_offset_x` | 0 | Horizontal crop offset (tune per streamer layout) |

## Output

Finished clips land in `output/` named: `<video_id>__clip01__<hook-title-slug>.mp4`

Each clip includes:
- Vertical 9:16 crop (1080x1920)
- Word-level karaoke caption highlighting (yellow → white sync)
- Hook title overlay (top third)

## Campaign workflows

See [`docs/workflow_guide.md`](docs/workflow_guide.md) for the clipping business system, posting cadence, and caption strategy.

Moment detection prompt: [`scripts/prompts/moment_detection.md`](scripts/prompts/moment_detection.md)  
Post description formula: [`scripts/prompts/post_description.md`](scripts/prompts/post_description.md)
