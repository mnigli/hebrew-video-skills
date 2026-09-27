#!/usr/bin/env python3
"""Export Sofit's cached/local Hebrew transcript as portable JSON."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


DEFAULT_MODEL = "ivrit-ai/whisper-large-v3-turbo-ct2"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Transcribe Hebrew media locally with Sofit and export word timestamps."
    )
    parser.add_argument("media")
    parser.add_argument("output")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--lang", default="he")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    media = Path(args.media).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not media.is_file():
        print(f"ERROR: media not found: {media}", file=sys.stderr)
        return 2
    if output.exists() and not args.force:
        print(f"ERROR: output already exists: {output}; use --force to replace it", file=sys.stderr)
        return 2

    try:
        from sofit.transcribe import transcribe
    except ImportError:
        print(
            "ERROR: Sofit is not installed in this Python environment. "
            "Run setup_runtime.ps1 and use the skill runtime Python.",
            file=sys.stderr,
        )
        return 2

    segments = transcribe(
        str(media),
        model=args.model,
        lang=args.lang,
        compute_type=args.compute_type,
        use_cache=not args.no_cache,
    )
    document = {
        "schema_version": 1,
        "source": {"media": str(media)},
        "model": args.model,
        "language": args.lang,
        "segments": [asdict(segment) for segment in segments],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{output} ({len(segments)} segments)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
