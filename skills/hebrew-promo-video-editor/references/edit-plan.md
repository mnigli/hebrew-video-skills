# Multi-source edit plan

`scripts/promo_video.py` consumes a versioned JSON plan. Paths may be absolute or relative to the plan file.

## Minimal example

```json
{
  "version": 1,
  "project": {
    "name": "Project promo",
    "landing_page": "https://example.com"
  },
  "canvas": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "fit": "cover",
    "background": "black"
  },
  "audio": {
    "normalize": true,
    "target_lufs": -16
  },
  "sources": {
    "promo": {"path": "C:/media/promo.mp4"},
    "body": {"path": "../renders/body/body.mp4"}
  },
  "timeline": [
    {
      "source": "promo",
      "start": 78.2,
      "end": 81.0,
      "role": "opening",
      "audio": "mute"
    },
    {
      "source": "body",
      "start": 0.0,
      "end": 42.4,
      "role": "message",
      "audio": "source"
    },
    {
      "source": "promo",
      "start": 78.2,
      "end": 81.0,
      "role": "closing",
      "audio": "mute"
    }
  ],
  "subtitles": {
    "enabled": false,
    "path": "captions.ass",
    "font_name": "Noto Sans Hebrew",
    "font_size": 18,
    "margin_v": 24
  },
  "output": {
    "path": "../renders/final.mp4",
    "video_crf": 19,
    "video_preset": "medium",
    "audio_sample_rate": 48000,
    "audio_bitrate": "192k"
  }
}
```

## Fields

- `version`: must be `1`.
- `canvas`: even output dimensions, FPS, and default `fit` mode. `fit` is `cover`, `contain`, or `stretch`.
- `sources`: aliases mapped to media paths. Reuse an alias for multiple timeline ranges.
- `timeline`: ordered output segments. `start` and `end` are seconds in the source.
- `role`: `opening`, `hook`, `message`, `proof`, `broll`, `closing`, or `brand`.
- `audio`: `source` or `mute`. Muted ranges receive silence so concatenation stays synchronized.
- Segment overrides: `fit`, `fade_in`, and `fade_out` are optional. Fades are seconds and should be used deliberately.
- `audio.normalize`: applies one-pass loudness normalization to each spoken source range. Disable it if the body was already mastered and levels match.
- `subtitles`: optional final-timeline SRT or ASS burn. Keep it disabled when Sofit has already burned captions into the body video. For SRT, `font_size` and `margin_v` are libass style units rather than output pixels; the initialized values are lower-safe-area starting points and must be confirmed on rendered close-up and two-speaker frames.
- `output`: delivery settings. The renderer always emits H.264/AAC, `yuv420p`, and `+faststart`; `audio_sample_rate` defaults to 48000 Hz for broad playback compatibility.

## Commands

```powershell
python scripts/promo_video.py init --project-dir "C:\work\promo" --interview "C:\media\interview.mp4" --promo "C:\media\promo.mp4" --aspect 16:9
python scripts/promo_video.py validate "C:\work\promo\spec\edit-plan.json"
python scripts/promo_video.py render "C:\work\promo\spec\edit-plan.json"
python scripts/promo_video.py qc "C:\work\promo\spec\edit-plan.json"
```

Use `--force` only when replacing the exact output is intentional. Prefer a new versioned output filename for editorial iterations.
