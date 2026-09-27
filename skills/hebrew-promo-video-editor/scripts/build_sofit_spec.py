#!/usr/bin/env python3
"""Build a caption-ready Sofit clips.json from reviewed timestamp ranges."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def transcript_segments(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        segments = document
    elif isinstance(document, dict):
        segments = document.get("segments")
    else:
        segments = None
    if not isinstance(segments, list):
        raise ValueError("transcript must contain a segments array")
    return [segment for segment in segments if isinstance(segment, dict)]


def word_value(word: dict[str, Any], key: str, alternate: str) -> Any:
    return word.get(key, word.get(alternate))


def words_for_range(
    transcript: list[dict[str, Any]], start: float, end: float
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for segment in transcript:
        try:
            seg_start = float(segment["start"])
            seg_end = float(segment["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if seg_end <= start or seg_start >= end:
            continue
        raw_words = segment.get("words")
        if isinstance(raw_words, list) and raw_words:
            for word in raw_words:
                if not isinstance(word, dict):
                    continue
                try:
                    word_start = float(word_value(word, "start", "t"))
                    word_end_raw = word_value(word, "end", "d")
                    if "end" in word:
                        word_end = float(word_end_raw)
                    else:
                        word_end = word_start + float(word_end_raw or 0)
                except (TypeError, ValueError):
                    continue
                text = str(word_value(word, "text", "word") or word.get("w") or "").strip()
                if not text or word_end <= start or word_start >= end:
                    continue
                clipped_start = max(word_start, start)
                clipped_end = min(word_end, end)
                output.append(
                    {
                        "t": round(clipped_start - start, 3),
                        "d": round(max(clipped_end - clipped_start, 0.01), 3),
                        "w": text,
                    }
                )
        else:
            text = str(segment.get("text") or "").strip()
            tokens = text.split()
            if not tokens:
                continue
            clipped_start = max(seg_start, start)
            clipped_end = min(seg_end, end)
            step = max(clipped_end - clipped_start, 0.01) / len(tokens)
            for index, token in enumerate(tokens):
                output.append(
                    {
                        "t": round(clipped_start - start + index * step, 3),
                        "d": round(step, 3),
                        "w": token,
                    }
                )
    output.sort(key=lambda item: item["t"])
    return output


def normalize_ranges(clip: dict[str, Any]) -> list[dict[str, float]]:
    ranges = clip.get("segments", clip.get("ranges"))
    if ranges is None and "start" in clip and "end" in clip:
        ranges = [{"start": clip["start"], "end": clip["end"]}]
    if not isinstance(ranges, list) or not ranges:
        raise ValueError(f"clip {clip.get('id')!r} needs segments/ranges")
    normalized: list[dict[str, float]] = []
    for index, item in enumerate(ranges):
        if not isinstance(item, dict):
            raise ValueError(f"range {index} in clip {clip.get('id')!r} must be an object")
        try:
            start = float(item["start"])
            end = float(item["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"range {index} in clip {clip.get('id')!r} needs numeric start/end"
            ) from exc
        if start < 0 or end <= start:
            raise ValueError(
                f"range {index} in clip {clip.get('id')!r} must satisfy 0 <= start < end"
            )
        normalized.append({"start": start, "end": end})
    starts = [item["start"] for item in normalized]
    if starts != sorted(starts):
        raise ValueError(f"ranges in clip {clip.get('id')!r} must be chronological")
    for previous, current in zip(normalized, normalized[1:]):
        if current["start"] < previous["end"]:
            raise ValueError(f"ranges in clip {clip.get('id')!r} overlap")
    return normalized


def build_clip(
    clip: dict[str, Any], transcript: list[dict[str, Any]], fallback_id: str
) -> dict[str, Any]:
    clip_id = str(clip.get("id") or fallback_id)
    ranges = normalize_ranges(clip)
    rendered_ranges = [
        {
            "start": round(item["start"], 3),
            "end": round(item["end"], 3),
            "words": words_for_range(transcript, item["start"], item["end"]),
        }
        for item in ranges
    ]
    for index, item in enumerate(rendered_ranges):
        if not item["words"]:
            raise ValueError(f"clip {clip_id!r} range {index} has no transcript words")
    result: dict[str, Any] = {
        "id": clip_id,
        "start": rendered_ranges[0]["start"],
        "end": rendered_ranges[-1]["end"],
        "hook": str(clip.get("hook") or ""),
        "hook_variants": [str(item) for item in clip.get("hook_variants", [])],
        "focus": clip.get("focus"),
    }
    if len(rendered_ranges) == 1:
        result["words"] = rendered_ranges[0]["words"]
    else:
        result["segments"] = rendered_ranges
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Build a Sofit clips.json from transcript timestamps and reviewed ranges."
    )
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--source-video", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    transcript_path = Path(args.transcript).expanduser().resolve()
    selection_path = Path(args.selection).expanduser().resolve()
    source_video = Path(args.source_video).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source_video.is_file():
        print(f"ERROR: source video not found: {source_video}", file=sys.stderr)
        return 2
    if output.exists() and not args.force:
        print(f"ERROR: output already exists: {output}; use --force to replace it", file=sys.stderr)
        return 2

    try:
        transcript = transcript_segments(load_json(transcript_path))
        selection = load_json(selection_path)
        if isinstance(selection, dict) and isinstance(selection.get("clips"), list):
            raw_clips = selection["clips"]
        elif isinstance(selection, dict):
            raw_clips = [selection]
        else:
            raise ValueError("selection must be an object or contain a clips array")
        clips = [
            build_clip(clip, transcript, f"clip-{index}")
            for index, clip in enumerate(raw_clips, start=1)
            if isinstance(clip, dict)
        ]
        if not clips:
            raise ValueError("selection contains no clips")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    document = {
        "schema_version": 1,
        "source": {"video": str(source_video)},
        "clips": clips,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{output} ({len(clips)} clips)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
