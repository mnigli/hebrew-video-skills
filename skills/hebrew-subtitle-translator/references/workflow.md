# Source-to-Hebrew subtitle workflow

Use this only for translation/subtitling. Promotional selection and multi-source advertising edits belong to `hebrew-promo-video-editor`.

## 1. Source and transcript

- Probe the media with FFprobe. Verify that the chosen video and audio tracks correspond to the requested source; prefer the best available source track without upscaling a low-quality image and calling it HD.
- Transcribe the original audio locally when possible. Use a language-appropriate ASR model and keep word/segment timestamps. For multi-speaker material, diarize if supported or inspect turns and split cues at changes.
- Treat automated text as a draft. Check names, places, numerals, technical terms, emotionally consequential statements, and a sample from each speaker against the audio. Compare platform captions only as a secondary spelling aid.
- If two engines disagree materially or emit fluent-looking nonsense, do not translate the disagreement into false certainty. Request a clearer source or human review; a summary inferred from context must be explicitly labeled as a summary, never as speech subtitles.

## 2. Translate and review

- Use the user's preferred Luna model when available. The [Sofit Luna Video](https://github.com/mnigli/sofit-luna-video) pipeline exposes `sofit-video`, `--source-lang`, `--luna-model`, `--mode` and `--dry-run`. Its default model may differ from the currently available Luna version, so set the model explicitly only after checking the local CLI.
- Translate coherent speaker-bounded groups, then review the output against source units. Keep one source-to-target mapping per cue. Do not strengthen claims, normalize away uncertainty, or invent a sentence ending.
- Preserve resumable intermediate files. Fix the reviewed translation, not the source transcript, when the source words were recognized correctly but translated poorly.

Example after installing the separate pipeline and confirming the local model name:

```powershell
sofit-video "C:\media\interview.mp4" --source-lang en --mode long --dry-run --output "C:\output\interview.he.mp4"
sofit-video "C:\media\interview.mp4" --source-lang en --mode long --output "C:\output\interview.he.mp4"
```

For a non-English source, change `--source-lang` and choose a matching transcription model when needed. For an already Hebrew video that needs captions but no translation, use `--translator none`. Do not assume automatic language selection is accurate for Yiddish or code-switching.

## 3. Subtitle layout and burn-in

- Keep the editable UTF-8 SRT alongside the video. For Hebrew SRT/libass, wrap every rendered Hebrew line with `U+200F` at both ends. Isolate left-to-right names, numbers or URLs with `U+2066` and `U+2069` when their order would otherwise change.
- Long-form: white Noto Sans Hebrew Regular or Medium, thin outline, subtle shadow, bottom-center. Use a sufficiently large size for the actual output resolution; judge rendered pixels, not an ASS font-size number alone. Maximum two lines.
- Short vertical: use Sofit's short/social renderer when suitable; allow a larger and somewhat heavier face, but keep the caption box in the lower safe zone and above platform controls. Inspect a face close-up and a two-person frame before full rendering.
- Burn with FFmpeg/Sofit to H.264/AAC `yuv420p` and `+faststart`. A separate SRT remains useful for corrections and accessibility.

## 4. Final checks

Sample the first and last frames, several mid-video captions, punctuation, numerals, mixed Hebrew/Latin text, and at least three speaker transitions when present. Check the entire caption bounding box stays low and does not cover faces. Verify duration, audio presence, end of the final sentence, SRT/MP4 synchronization, codec compatibility and actual output dimensions. Never call an upscaled render a higher-quality source.
