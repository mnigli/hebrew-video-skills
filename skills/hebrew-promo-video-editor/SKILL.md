---
name: hebrew-promo-video-editor
description: Select and edit persuasive Hebrew promotional highlights from interviews, testimonials, podcasts and branded footage. Use for ads and project promos that need a coherent marketing arc; not for preserving and translating an entire existing video.
---

# Hebrew Promo Video Editor

Turn long Hebrew-speaking footage plus optional branded/promotional footage into a polished short video. Use Sofit for local Hebrew transcription and caption rendering, then use the bundled timeline helper for deterministic multi-source assembly and QA.

This is an **editorial selection** skill. If the user wants the existing video's speech translated and subtitled without selecting advertising highlights, use the separate `hebrew-subtitle-translator` skill. When both are requested, select the ad-worthy material here first, then translate/caption the retained speech without changing its meaning.

## Route the work

- For transcript review and marketing-message selection, read [references/selection-policy.md](references/selection-policy.md).
- For a full Sofit-to-final-video run, read [references/workflow.md](references/workflow.md).
- When assembling more than one source or revising exact cuts, read [references/edit-plan.md](references/edit-plan.md).

## Required outcome

Deliver the final MP4 together with the edit plan, retained subtitle/clip spec, and QC frames. Keep intermediate renders so later feedback can be applied without reconstructing the edit.

## Operating rules

1. Inspect every supplied source and the user's project/landing-page context before selecting claims. Treat landing-page copy as context; do not put an unspoken claim into a speaker's mouth or subtitles.
2. Prefer a complete persuasive arc: hook, project identity, concrete benefit or differentiator, proof/trust, and a clean close. A short complete message is better than more disconnected claims.
3. Preserve the speaker's meaning and chronological order. Never cut mid-word or mid-sentence. Do not switch to a different speaker mid-message unless the user asks for it; use that footage muted as B-roll or as a short branded visual instead.
4. Verify names, numbers, prices, dates, guarantees, locations, and superlatives against the audio and supplied project material. Never silently strengthen a claim.
5. Treat the source audio as the transcription authority. For every final deliverable, run the configured transcription engine on the media even when YouTube or another platform exposes captions. Platform captions may be used only to cross-check names and spellings, or for an explicitly requested rough draft; never substitute them for transcription in a final video. A request to work faster permits caching, parallel work, and hardware acceleration, not skipping transcription.
6. For interviews and other multi-speaker material, preserve speaker-turn boundaries. Use diarization when the available engine supports it; otherwise inspect and split at speaker changes. Never create a subtitle unit that crosses from one speaker to another, and spot-check representative transitions against the audio.
7. Render Hebrew captions with Sofit's word-timed Pillow renderer when possible. For interview and documentary footage, prefer a restrained Netflix-like subtitle treatment: `Noto Sans Hebrew` Regular (or the closest clean sans-serif with full Hebrew coverage), white text, a thin dark outline plus a subtle shadow, and no heavy bold weight. Place captions in the lower safe area by default: keep their visible bounding box in the bottom third, bottom-align them, use no more than two lines, and keep them off faces and important upper-body gestures. Reduce font size or rebreak text before moving captions upward. Move them only enough to clear existing lower-thirds, logos, or platform UI; use the top only when the lower area is genuinely unusable. If using SRT/ASS through FFmpeg, inspect real rendered frames for placement as well as RTL order, punctuation, line breaks, mixed Hebrew/Latin text, font weight, outline thickness, and shadow, because libass margin units may scale differently from output pixels.
8. Treat the first and last frames as editorial decisions. Sample frames around every proposed opening/closing cut, choose a clean frame, and inspect the actual rendered first and last frames. Do not leave motion-blurred, transitional, black, duplicated, or unfinished frames.
9. Listen to the final audio ending. The last spoken phrase must finish a thought, and the visual must not linger after the audio unless a deliberate branded end card was requested.
10. Use H.264 video, AAC audio, `yuv420p`, and `+faststart` for delivery compatibility. Produce the requested aspect ratio; when none is given, preserve the source orientation for website/WhatsApp delivery and offer `9:16` as an additional social version.
11. Long transcription and rendering may run in the background. Report progress and do not discard earlier viable renders.

## Bundled helpers

Run `scripts/promo_video.py doctor` first. If the dedicated Sofit runtime is missing, run `scripts/setup_runtime.ps1`; this installs a pinned Sofit source revision in the skill's `.runtime` directory without modifying the user's project environment.

The setup also applies a narrowly signature-checked Windows fix inside that isolated runtime so Sofit's frame-overlay FFmpeg process cannot deadlock on an undrained progress pipe. Do not patch a system-wide Sofit installation.

Use:

- `scripts/export_transcript.py` to export Sofit's cached/local word-timed transcript.
- `scripts/build_sofit_spec.py` to turn approved timestamp ranges into a Sofit `clips.json` body render.
- `scripts/run_sofit.py` to run Sofit with the isolated FFmpeg binary available on its child-process `PATH`.
- `scripts/promo_video.py` to initialize, validate, render, sample, and QC a multi-source edit plan.

Do not publish or upload the result unless the user separately requests that external action.
