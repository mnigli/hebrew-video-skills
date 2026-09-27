# Quality gates for translated subtitles

The final MP4 is ready only when these checks pass:

| Gate | Evidence |
| --- | --- |
Source authority | Timestamped transcript produced from the requested media's audio; platform captions used only as a cross-check. |
Speech fidelity | Uncertain speech is marked or withheld, not reconstructed from context. Proper names, numbers and key claims have been checked. |
Speaker integrity | No cue crosses a speaker change; representative transitions agree with the recording. |
Translation | Reviewed Hebrew conveys the source statement, tone and degree of certainty without promotional rewriting. |
Timing | Cues begin/end with speech, remain readable, and do not linger over the next speaker. |
RTL | Hebrew punctuation appears on the correct visual side; mixed LTR text stays in logical order. |
Placement | Rendered captions sit in the lower safe area, within two lines, clear of faces and controls. |
Delivery | MP4 plays with audible AAC sound, H.264 `yuv420p` video, expected dimensions and clean first/last frames; editable SRT is retained. |

If the transcript gate fails, do not treat attractive subtitle styling as a substitute for translation accuracy. A user-approved explanatory overlay or summary is a different deliverable and must be labeled accordingly.
