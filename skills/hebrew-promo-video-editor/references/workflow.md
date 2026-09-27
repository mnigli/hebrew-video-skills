# End-to-end workflow

Read this reference for a full job from source media to deliverable.

## 1. Prepare and inspect

Record the interview/main source, each promo/B-roll source, landing-page URL, desired duration, aspect ratio, CTA, logo, and any speaker constraints. Probe every source and create frame samples around likely branded opening/closing material.

Run the dependency check:

```powershell
python scripts/promo_video.py doctor
```

If Sofit is missing, install the isolated pinned runtime:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_runtime.ps1
```

The runtime executables are under `.runtime\Scripts` on Windows and `.runtime/bin` on Unix-like systems.

## 2. Transcribe locally — mandatory for final output

Always run the configured transcription engine against the media's actual audio. Do not import YouTube captions, automatic platform captions, or a downloaded subtitle track as the transcript for a final deliverable, even when that path appears faster. Platform captions may be consulted only as a secondary reference for names and spellings, or used when the user explicitly asks for a rough draft rather than a finished result.

Before translation or edit selection, determine whether the recording contains multiple speakers. Use diarization when the available engine supports it. Otherwise, inspect speaker changes and split segments at those boundaries. A subtitle cue must not contain speech from two different speakers.

```powershell
.runtime\Scripts\python.exe scripts/export_transcript.py "C:\media\interview.mp4" "C:\work\analysis\interview.transcript.json"
```

Transcription uses the configured faster-whisper model, produces word timestamps, and is cached by Sofit. The Hebrew default is `ivrit-ai/whisper-large-v3-turbo-ct2`; use the project's language-appropriate model for other source languages. It can take a long time on CPU.

To shorten turnaround time, reuse the transcription/audio cache, use supported compute acceleration, overlap independent preparation work, and parallelize later translation batches. Never obtain speed by replacing source-audio transcription with platform captions.

Review the transcript against [selection-policy.md](selection-policy.md). Confirm important audio manually, especially names and numbers.

## 3. Define the body selection

Create a small selection JSON:

```json
{
  "clips": [
    {
      "id": "body",
      "hook": "",
      "focus": null,
      "segments": [
        {"start": 12.4, "end": 27.8},
        {"start": 35.1, "end": 52.6}
      ]
    }
  ]
}
```

Ranges must be chronological, sentence-complete, and long enough not to feel jumpy. Use `scripts/promo_video.py sample` around the proposed first and last cut points.

Build a Sofit render spec with exact word timings:

```powershell
.runtime\Scripts\python.exe scripts/build_sofit_spec.py `
  --transcript "C:\work\analysis\interview.transcript.json" `
  --selection "C:\work\spec\selection.json" `
  --source-video "C:\media\interview.mp4" `
  --output "C:\work\spec\body.clips.json"
```

## 4. Render the captioned body

```powershell
.runtime\Scripts\python.exe scripts\run_sofit.py --render-from "C:\work\spec\body.clips.json" `
  --render-clips "C:\work\renders\body" --only body --aspect 16:9 --no-hook-card
```

Add `--logo` only when the user supplied/approved it. For `9:16`, inspect the face crop and caption safe areas. Correct transcription text in the saved `body.clips.json`, preserving `t` and `d`, then re-render the affected body.

### Caption placement default

- Keep captions bottom-aligned in the lower safe area, with the entire rendered caption box inside the bottom third whenever the source composition permits.
- Use at most two lines. If text reaches the speaker's face or important upper-body gestures, shorten the line, rebreak it, or reduce the font before raising the caption.
- For SRT rendered through FFmpeg/libass, use `Noto Sans Hebrew` Regular (or the closest clean sans-serif with full Hebrew coverage) for a restrained Netflix-like interview style. Start with white text, a thin dark outline, a subtle shadow, `Alignment=2`, `FontSize=18`, and `MarginV=24` for landscape video; use `MarginV=40` as a portrait starting point. Avoid heavy bold faces and thick cartoon-like outlines. These are ASS style units, not guaranteed output pixels, so tune them from rendered frames rather than trusting the numbers alone.
- Move captions upward only enough to clear an existing lower-third, logo, CTA, or platform safe area. Use top placement only when the lower area is genuinely unusable.
- Render and inspect both a tight close-up and a two-speaker shot before the full export. The preview must show that captions remain low and do not cover faces.

## 5. Assemble promo opening/body/closing

Initialize the project plan, edit its timeline, validate it, and render:

```powershell
.runtime\Scripts\python.exe scripts/promo_video.py init `
  --project-dir "C:\work" --interview "C:\work\renders\body\body.mp4" `
  --promo "C:\media\promo.mp4" --aspect 16:9 --output "renders\final-v1.mp4"

.runtime\Scripts\python.exe scripts/promo_video.py validate "C:\work\spec\edit-plan.json"
.runtime\Scripts\python.exe scripts/promo_video.py render "C:\work\spec\edit-plan.json"
```

When promo footage has another narrator, prefer `"audio": "mute"` for branded visuals unless the alternate voice is an intentional self-contained intro or outro.

## 6. Mandatory QC

```powershell
.runtime\Scripts\python.exe scripts/promo_video.py qc "C:\work\spec\edit-plan.json"
```

Open the generated first frame, last frame, and contact sheet. Also watch with sound from at least two seconds before the final spoken sentence through the end. Verify:

- clean first frame and intentional last frame;
- no cut-off word, sentence, breath, or music tail;
- no accidental narrator/speaker switch;
- representative subtitle cues match the source audio, including at least three speaker transitions when multiple speakers are present;
- no subtitle cue spans a change of speaker;
- correct Hebrew RTL, punctuation, mixed-language order, no more than two lines, and a bottom-third placement that does not cover faces or important upper-body gestures;
- factual consistency across audio, captions, hook, CTA, and landing-page claims;
- expected aspect, duration, audible track, and broad player compatibility.

If any check fails, change the source range or spec and re-render a new version. Do not mask a bad source cut with a decorative transition.
