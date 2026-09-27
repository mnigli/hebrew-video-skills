#!/usr/bin/env python3
"""Apply signature-checked Windows fixes to the isolated Sofit runtime."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    try:
        import sofit.render
    except ImportError:
        print("ERROR: Sofit is not installed in this Python environment.", file=sys.stderr)
        return 2

    render_path = Path(sofit.render.__file__).resolve()
    source = render_path.read_text(encoding="utf-8")
    changed = False

    pipe_original = 'cmd = [\n        "ffmpeg", "-i", str(video_path),'
    pipe_replacement = (
        'cmd = [\n        "ffmpeg", "-hide_banner", "-loglevel", "error", '
        '"-i", str(video_path),'
    )
    if pipe_replacement not in source:
        if pipe_original not in source:
            print(
                "ERROR: the pinned Sofit pipe signature changed; refusing an unsafe patch.",
                file=sys.stderr,
            )
            return 2
        source = source.replace(pipe_original, pipe_replacement, 1)
        changed = True

    raqm_anchor = """except Exception:  # pragma: no cover - depends on env
    _bidi_display = None
"""
    raqm_replacement = raqm_anchor + """
try:
    from PIL import features as _pil_features
    _PILLOW_HAS_RAQM = bool(_pil_features.check(\"raqm\"))
except Exception:  # pragma: no cover - depends on Pillow build
    _PILLOW_HAS_RAQM = False
"""
    if "_PILLOW_HAS_RAQM = bool" not in source:
        if raqm_anchor not in source:
            print(
                "ERROR: the pinned Sofit BiDi import signature changed; refusing an unsafe patch.",
                file=sys.stderr,
            )
            return 2
        source = source.replace(raqm_anchor, raqm_replacement, 1)
        changed = True

    order_original = """    out: list[dict] = []
    for ltr, run in reversed(runs):
        out.extend(run if ltr else list(reversed(run)))
    return out
"""
    order_replacement = """    out: list[dict] = []
    for ltr, run in reversed(runs):
        out.extend(run if ltr else list(reversed(run)))
    if _PILLOW_HAS_RAQM:
        return out

    # Pillow builds without libraqm draw each Hebrew token left-to-right.
    # Shape only the token glyph order here; the word sequence above is already
    # in visual left-to-right order and mixed Latin/digits must remain intact.
    shaped: list[dict] = []
    for word in out:
        item = dict(word)
        token = item.get(\"text\") or \"\"
        if any(\"\\u0590\" <= char <= \"\\u05ff\" or \"\\u0600\" <= char <= \"\\u06ff\"
               for char in token):
            item[\"text\"] = _shape_bidi(token)
        shaped.append(item)
    return shaped
"""
    if "Pillow builds without libraqm draw each Hebrew token" not in source:
        if order_original not in source:
            print(
                "ERROR: the pinned Sofit word-order signature changed; refusing an unsafe patch.",
                file=sys.stderr,
            )
            return 2
        source = source.replace(order_original, order_replacement, 1)
        changed = True

    simple_original = """        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=pil_font)
            tw = bbox[2] - bbox[0]
            x = (width - tw) // 2

            # Draw outline
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), line, font=pil_font, fill=(0, 0, 0, 255))
            # Draw text
            draw.text((x, y), line, font=pil_font, fill=(255, 255, 255, 255))
"""
    simple_replacement = """        for line in wrapped:
            display_line = line if _PILLOW_HAS_RAQM else _shape_bidi(line)
            bbox = draw.textbbox((0, 0), display_line, font=pil_font)
            tw = bbox[2] - bbox[0]
            x = (width - tw) // 2

            # Draw outline
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), display_line, font=pil_font, fill=(0, 0, 0, 255))
            # Draw text
            draw.text((x, y), display_line, font=pil_font, fill=(255, 255, 255, 255))
"""
    if "display_line = line if _PILLOW_HAS_RAQM" not in source:
        if simple_original not in source:
            print(
                "ERROR: the pinned Sofit simple-caption signature changed; refusing an unsafe patch.",
                file=sys.stderr,
            )
            return 2
        source = source.replace(simple_original, simple_replacement, 1)
        changed = True

    if changed:
        render_path.write_text(source, encoding="utf-8")
        print(f"Patched Sofit Windows rendering compatibility: {render_path}")
    else:
        print(f"Sofit runtime patches already applied: {render_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
