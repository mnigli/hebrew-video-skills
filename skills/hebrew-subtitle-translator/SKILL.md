---
name: hebrew-subtitle-translator
description: Transcribe and translate existing videos into Hebrew subtitles, then deliver an optional burned-in MP4. Use for interviews, lectures, podcasts and clips whose spoken content should be preserved; not for selecting advertising highlights or rewriting the message as a promo.
---

# Hebrew Subtitle Translator

Preserve the source video's message and sequence. Transcribe its actual audio, translate accurately into Hebrew, and deliver readable, correctly timed subtitles. Do not shorten, reframe as an advertisement, add a hook, or write a CTA unless the user asks for that separately. For advertising selection, use the sibling `hebrew-promo-video-editor` skill instead.

Read [references/workflow.md](references/workflow.md) for the end-to-end process and [references/quality-gates.md](references/quality-gates.md) when reviewing the transcript, translation, render and output.

## Core rules

1. Inspect source duration, orientation, resolution, language, audio quality and speaker changes. Record the user's requested output resolution and whether they want a sidecar SRT, burned MP4, or both.
2. Generate a timestamped transcript from the **source audio** using a language-appropriate engine. Do not substitute YouTube or platform captions for final transcription; they may help verify names and spelling. Preserve speaker-turn boundaries.
3. Translate with a Luna model when it is available and appropriate to the user's workflow. Preserve meaning, uncertainty, names, numbers and register. Never fill an ASR gap from topic context or make an uncertain quotation appear certain.
4. If the transcript is unreliable, try a targeted improvement (better source/audio track, appropriate model, cleaned audio or bounded re-transcription). If meaningful speech remains unresolved, report the limitation and stop before burning misleading subtitles. Context supplied by the user helps identify names, not reconstruct unheard speech.
5. Keep each cue on one speaker, normally one or two short lines. Check timing, reading speed, punctuation and Hebrew bidirectional rendering. Place captions in the **lower safe area**, clear of faces, lower-thirds and platform controls.
6. For long-form interviews use a restrained, Netflix-like treatment: a clean Hebrew sans-serif such as Noto Sans Hebrew, white text, readable weight and size, thin dark outline and subtle shadow. For short social videos, a somewhat larger/heavier Sofit treatment is appropriate if it remains legible and does not cover the subject.
7. Deliver the SRT and, when requested, an H.264/AAC `yuv420p` MP4 with `+faststart`. Keep the transcript, reviewed translation and render metadata so corrections do not require starting over. Inspect actual captioned frames and the finished audio/video before handoff.

Do not upload, publish or redistribute the source or result unless the user requests that action. Downloading a supplied source for processing is not permission to publish it.
