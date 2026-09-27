#!/usr/bin/env python3
"""Deterministic multi-source assembly and QA for Hebrew promo video edits."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ASPECTS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}
FITS = {"cover", "contain", "stretch"}
ROLES = {"opening", "hook", "message", "proof", "broll", "closing", "brand"}
AUDIO_MODES = {"source", "mute"}
SKILL_ROOT = Path(__file__).resolve().parents[1]


def configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def find_ffmpeg(explicit: str | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env_path = os.environ.get("HEBREW_PROMO_FFMPEG")
    if env_path:
        candidates.append(Path(env_path))
    system = shutil.which("ffmpeg")
    if system:
        candidates.append(Path(system))
    try:
        import imageio_ffmpeg  # type: ignore

        candidates.append(Path(imageio_ffmpeg.get_ffmpeg_exe()))
    except Exception:
        pass
    candidates.extend(SKILL_ROOT.glob(".runtime/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg*.exe"))
    candidates.extend(SKILL_ROOT.glob(".runtime/lib/python*/site-packages/imageio_ffmpeg/binaries/ffmpeg*"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def runtime_paths() -> tuple[Path, Path]:
    if os.name == "nt":
        return (
            SKILL_ROOT / ".runtime" / "Scripts" / "python.exe",
            SKILL_ROOT / ".runtime" / "Scripts" / "sofit.exe",
        )
    return (
        SKILL_ROOT / ".runtime" / "bin" / "python",
        SKILL_ROOT / ".runtime" / "bin" / "sofit",
    )


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(f"Command failed ({process.returncode}): {' '.join(command)}\n{detail}")
    return process


def require_ffmpeg(explicit: str | None) -> Path:
    ffmpeg = find_ffmpeg(explicit)
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg was not found. Run scripts/setup_runtime.ps1 or pass --ffmpeg PATH."
        )
    return ffmpeg


def parse_duration(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def probe_media(ffmpeg: Path, media: Path) -> dict[str, Any]:
    process = run_command(
        [str(ffmpeg), "-hide_banner", "-i", str(media)], check=False
    )
    text = process.stderr + "\n" + process.stdout
    duration_match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2}(?:\.\d+)?)", text)
    resolution_match = re.search(
        r"Stream #.*Video:.*?\b(\d{2,5})x(\d{2,5})(?:\b|[ ,])", text
    )
    return {
        "path": str(media),
        "duration": parse_duration(duration_match.group(1)) if duration_match else None,
        "width": int(resolution_match.group(1)) if resolution_match else None,
        "height": int(resolution_match.group(2)) if resolution_match else None,
        "has_video": bool(re.search(r"Stream #.*Video:", text)),
        "has_audio": bool(re.search(r"Stream #.*Audio:", text)),
    }


def resolve_from(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def load_plan(plan_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Plan not found: {plan_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {plan_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Edit plan root must be a JSON object.")
    return data


def source_entry_path(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict) and isinstance(entry.get("path"), str):
        return entry["path"]
    return None


def validate_plan(
    plan_path: Path, ffmpeg: Path, *, require_timeline: bool = True
) -> tuple[dict[str, Any], list[str], list[str], dict[str, dict[str, Any]]]:
    plan = load_plan(plan_path)
    errors: list[str] = []
    warnings: list[str] = []
    probes: dict[str, dict[str, Any]] = {}

    if plan.get("version") != 1:
        errors.append("version must be 1")

    canvas = plan.get("canvas")
    if not isinstance(canvas, dict):
        errors.append("canvas must be an object")
        canvas = {}
    width = canvas.get("width")
    height = canvas.get("height")
    fps = canvas.get("fps")
    if not isinstance(width, int) or width <= 0 or width % 2:
        errors.append("canvas.width must be a positive even integer")
    if not isinstance(height, int) or height <= 0 or height % 2:
        errors.append("canvas.height must be a positive even integer")
    if not isinstance(fps, (int, float)) or fps <= 0:
        errors.append("canvas.fps must be positive")
    if canvas.get("fit", "cover") not in FITS:
        errors.append(f"canvas.fit must be one of {sorted(FITS)}")

    sources = plan.get("sources")
    if not isinstance(sources, dict) or not sources:
        errors.append("sources must be a non-empty object")
        sources = {}
    source_paths: dict[str, Path] = {}
    for alias, entry in sources.items():
        raw_path = source_entry_path(entry)
        if not raw_path:
            errors.append(f"source '{alias}' needs a path")
            continue
        path = resolve_from(plan_path.parent, raw_path)
        source_paths[alias] = path
        if not path.is_file():
            errors.append(f"source '{alias}' does not exist: {path}")
            continue
        info = probe_media(ffmpeg, path)
        probes[alias] = info
        if not info["has_video"]:
            errors.append(f"source '{alias}' has no video stream")

    timeline = plan.get("timeline")
    if not isinstance(timeline, list):
        errors.append("timeline must be an array")
        timeline = []
    if require_timeline and not timeline:
        errors.append("timeline is empty; add at least one segment")

    kept_by_source: dict[str, list[float]] = {}
    for index, segment in enumerate(timeline):
        prefix = f"timeline[{index}]"
        if not isinstance(segment, dict):
            errors.append(f"{prefix} must be an object")
            continue
        alias = segment.get("source")
        if alias not in sources:
            errors.append(f"{prefix}.source is unknown: {alias!r}")
            continue
        try:
            start = float(segment.get("start"))
            end = float(segment.get("end"))
        except (TypeError, ValueError):
            errors.append(f"{prefix} start/end must be numbers")
            continue
        if start < 0 or end <= start:
            errors.append(f"{prefix} must satisfy 0 <= start < end")
            continue
        info = probes.get(alias)
        if info and info.get("duration") is not None and end > info["duration"] + 0.05:
            errors.append(
                f"{prefix}.end ({end:.3f}) exceeds source duration ({info['duration']:.3f})"
            )
        role = segment.get("role", "message")
        if role not in ROLES:
            errors.append(f"{prefix}.role must be one of {sorted(ROLES)}")
        audio_mode = segment.get("audio", "source")
        if audio_mode not in AUDIO_MODES:
            errors.append(f"{prefix}.audio must be one of {sorted(AUDIO_MODES)}")
        elif audio_mode == "source" and info and not info.get("has_audio"):
            errors.append(f"{prefix} requests source audio, but '{alias}' has no audio stream")
        fit = segment.get("fit", canvas.get("fit", "cover"))
        if fit not in FITS:
            errors.append(f"{prefix}.fit must be one of {sorted(FITS)}")
        duration = end - start
        for fade_name in ("fade_in", "fade_out"):
            fade = segment.get(fade_name, 0)
            if not isinstance(fade, (int, float)) or fade < 0 or fade >= duration:
                errors.append(f"{prefix}.{fade_name} must be >= 0 and shorter than the segment")
        if role in {"hook", "message", "proof"}:
            kept_by_source.setdefault(str(alias), []).append(start)

    for alias, starts in kept_by_source.items():
        if starts != sorted(starts):
            warnings.append(
                f"spoken ranges from '{alias}' are not chronological; confirm that reordering is intentional"
            )

    if timeline:
        first = timeline[0]
        last = timeline[-1]
        if isinstance(first, dict) and first.get("role", "message") not in {"opening", "hook", "brand"}:
            warnings.append("first segment is not marked opening/hook/brand")
        if isinstance(last, dict) and last.get("role", "message") not in {"closing", "brand", "message"}:
            warnings.append("last segment is not marked closing/brand/message")
        if isinstance(first, dict) and float(first.get("start", 0) or 0) == 0:
            warnings.append("first source range begins at 0.000; inspect the actual first frame")

    subtitles = plan.get("subtitles", {})
    if subtitles and not isinstance(subtitles, dict):
        errors.append("subtitles must be an object")
    elif isinstance(subtitles, dict) and subtitles.get("enabled"):
        raw = subtitles.get("path")
        if not isinstance(raw, str):
            errors.append("enabled subtitles need subtitles.path")
        else:
            sub_path = resolve_from(plan_path.parent, raw)
            if not sub_path.is_file():
                errors.append(f"subtitle file does not exist: {sub_path}")
            elif sub_path.suffix.lower() not in {".srt", ".ass", ".ssa"}:
                errors.append("subtitle path must end in .srt, .ass, or .ssa")

    output = plan.get("output")
    if not isinstance(output, dict) or not isinstance(output.get("path"), str):
        errors.append("output.path is required")

    return plan, errors, warnings, probes


def print_validation(errors: list[str], warnings: list[str]) -> None:
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)


def filter_path(path: Path) -> str:
    value = path.resolve().as_posix()
    for old, new in (("\\", "\\\\"), (":", "\\:"), ("'", "\\'"), (",", "\\,"), ("[", "\\["), ("]", "\\]")):
        value = value.replace(old, new)
    return value


def number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def build_filter_graph(plan_path: Path, plan: dict[str, Any]) -> tuple[str, list[Path], str, str]:
    canvas = plan["canvas"]
    width = int(canvas["width"])
    height = int(canvas["height"])
    fps = float(canvas["fps"])
    background = str(canvas.get("background", "black"))
    sources = plan["sources"]
    timeline = plan["timeline"]
    audio_cfg = plan.get("audio", {}) if isinstance(plan.get("audio"), dict) else {}
    normalize = bool(audio_cfg.get("normalize", False))
    target_lufs = float(audio_cfg.get("target_lufs", -16))

    inputs: list[Path] = []
    chains: list[str] = []
    concat_labels: list[str] = []
    for index, segment in enumerate(timeline):
        alias = segment["source"]
        raw_path = source_entry_path(sources[alias])
        assert raw_path is not None
        inputs.append(resolve_from(plan_path.parent, raw_path))
        start = float(segment["start"])
        end = float(segment["end"])
        duration = end - start
        fit = segment.get("fit", canvas.get("fit", "cover"))

        video_filters = [
            f"trim=start={number(start)}:end={number(end)}",
            "setpts=PTS-STARTPTS",
        ]
        if fit == "cover":
            video_filters.extend(
                [
                    f"scale={width}:{height}:force_original_aspect_ratio=increase",
                    f"crop={width}:{height}",
                ]
            )
        elif fit == "contain":
            video_filters.extend(
                [
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease",
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={background}",
                ]
            )
        else:
            video_filters.append(f"scale={width}:{height}")
        video_filters.extend([f"fps={number(fps)}", "setsar=1", "format=yuv420p"])
        fade_in = float(segment.get("fade_in", 0))
        fade_out = float(segment.get("fade_out", 0))
        if fade_in:
            video_filters.append(f"fade=t=in:st=0:d={number(fade_in)}")
        if fade_out:
            video_filters.append(
                f"fade=t=out:st={number(duration - fade_out)}:d={number(fade_out)}"
            )
        chains.append(f"[{index}:v:0]" + ",".join(video_filters) + f"[v{index}]")

        audio_mode = segment.get("audio", "source")
        if audio_mode == "source":
            audio_filters = [
                f"atrim=start={number(start)}:end={number(end)}",
                "asetpts=PTS-STARTPTS",
                "aresample=48000",
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo",
            ]
            if normalize:
                audio_filters.append(
                    f"loudnorm=I={number(target_lufs)}:TP=-1.5:LRA=11"
                )
            audio_filters.extend(
                ["aresample=48000:async=1:first_pts=0", "asetpts=N/SR/TB"]
            )
            if fade_in:
                audio_filters.append(f"afade=t=in:st=0:d={number(fade_in)}")
            if fade_out:
                audio_filters.append(
                    f"afade=t=out:st={number(duration - fade_out)}:d={number(fade_out)}"
                )
            chains.append(f"[{index}:a:0]" + ",".join(audio_filters) + f"[a{index}]")
        else:
            chains.append(
                f"anullsrc=r=48000:cl=stereo,atrim=duration={number(duration)},asetpts=PTS-STARTPTS[a{index}]"
            )
        concat_labels.append(f"[v{index}][a{index}]")

    chains.append(
        "".join(concat_labels)
        + f"concat=n={len(timeline)}:v=1:a=1[vcat][acat]"
    )

    video_label = "vcat"
    subtitles = plan.get("subtitles", {})
    if isinstance(subtitles, dict) and subtitles.get("enabled"):
        sub_path = resolve_from(plan_path.parent, subtitles["path"])
        escaped = filter_path(sub_path)
        if sub_path.suffix.lower() in {".ass", ".ssa"}:
            chains.append(f"[vcat]ass=filename='{escaped}'[vout]")
        else:
            font_name = str(subtitles.get("font_name", "Noto Sans Hebrew")).replace("'", "")
            font_size = int(subtitles.get("font_size", 18))
            margin_v = int(subtitles.get("margin_v", 24))
            style = (
                f"FontName={font_name},FontSize={font_size},PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0,"
                f"Alignment=2,MarginV={margin_v}"
            )
            chains.append(
                f"[vcat]subtitles=filename='{escaped}':force_style='{style}'[vout]"
            )
        video_label = "vout"

    return ";".join(chains), inputs, video_label, "acat"


def output_path_for(plan_path: Path, plan: dict[str, Any]) -> Path:
    return resolve_from(plan_path.parent, plan["output"]["path"])


def extract_frame(ffmpeg: Path, source: Path, timestamp: float, output: Path, *, scale: int | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    last_error: RuntimeError | None = None
    # Container duration is often one audio packet longer than the final video
    # frame. Step back when an exact near-EOF seek produces no frame.
    for fallback in (0.0, 0.1, 0.25, 0.5):
        seek = max(0.0, timestamp - fallback)
        command = [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            number(seek),
            "-i",
            str(source),
            "-frames:v",
            "1",
        ]
        if scale:
            command.extend(["-vf", f"scale={scale}:-2"])
        command.extend(["-q:v", "2", "-y", str(output)])
        try:
            run_command(command)
            if output.is_file() and output.stat().st_size:
                return
        except RuntimeError as exc:
            last_error = exc
        output.unlink(missing_ok=True)
    if last_error:
        raise last_error
    raise RuntimeError(f"Could not extract a frame from {source} near {timestamp:.3f}s")


def sample_frames(
    ffmpeg: Path,
    source: Path,
    start: float,
    end: float,
    count: int,
    output_dir: Path,
) -> tuple[list[Path], Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if count < 2:
        timestamps = [start]
    else:
        timestamps = [start + (end - start) * i / (count - 1) for i in range(count)]
    frames: list[Path] = []
    for index, timestamp in enumerate(timestamps, start=1):
        frame = output_dir / f"frame-{index:03d}.jpg"
        extract_frame(ffmpeg, source, timestamp, frame, scale=640)
        frames.append(frame)
    columns = math.ceil(math.sqrt(count))
    rows = math.ceil(count / columns)
    contact = output_dir / "contact-sheet.jpg"
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        "1",
        "-i",
        str(output_dir / "frame-%03d.jpg"),
        "-vf",
        f"tile=layout={columns}x{rows}:nb_frames={count}:padding=8:margin=8",
        "-frames:v",
        "1",
        "-q:v",
        "2",
        "-y",
        str(contact),
    ]
    run_command(command)
    return frames, contact


def cmd_doctor(args: argparse.Namespace) -> int:
    ffmpeg = find_ffmpeg(args.ffmpeg)
    runtime_python, runtime_sofit = runtime_paths()
    report: dict[str, Any] = {
        "python": sys.executable,
        "ffmpeg": str(ffmpeg) if ffmpeg else None,
        "sofit_command": shutil.which("sofit") or (str(runtime_sofit) if runtime_sofit.is_file() else None),
        "sofit_importable": importlib.util.find_spec("sofit") is not None,
        "runtime_python": str(runtime_python) if runtime_python.is_file() else None,
    }
    if ffmpeg:
        filters = run_command([str(ffmpeg), "-hide_banner", "-filters"], check=False)
        encoders = run_command([str(ffmpeg), "-hide_banner", "-encoders"], check=False)
        filter_text = filters.stdout + filters.stderr
        encoder_text = encoders.stdout + encoders.stderr
        report["subtitles_filter"] = "subtitles" in filter_text
        report["libx264_encoder"] = "libx264" in encoder_text
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not ffmpeg:
        print("Run scripts/setup_runtime.ps1 to install the isolated runtime.", file=sys.stderr)
        return 1
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).expanduser().resolve()
    for directory in ("analysis", "spec", "renders", "qc"):
        (project_dir / directory).mkdir(parents=True, exist_ok=True)
    plan_path = project_dir / "spec" / "edit-plan.json"
    if plan_path.exists() and not args.force:
        raise RuntimeError(f"Plan already exists: {plan_path}. Use --force only to replace it.")
    if args.aspect not in ASPECTS:
        raise RuntimeError(f"Unsupported aspect {args.aspect!r}; choose one of {sorted(ASPECTS)}")
    width, height = ASPECTS[args.aspect]
    sources: dict[str, Any] = {"interview": {"path": str(Path(args.interview).expanduser().resolve())}}
    for index, promo in enumerate(args.promo or [], start=1):
        alias = "promo" if len(args.promo or []) == 1 else f"promo{index}"
        sources[alias] = {"path": str(Path(promo).expanduser().resolve())}
    plan = {
        "version": 1,
        "project": {
            "name": args.name or project_dir.name,
            "landing_page": args.landing_page or "",
        },
        "canvas": {
            "width": width,
            "height": height,
            "fps": 30,
            "fit": "cover",
            "background": "black",
        },
        "audio": {"normalize": True, "target_lufs": -16},
        "sources": sources,
        "timeline": [],
        "subtitles": {
            "enabled": False,
            "path": "captions.ass",
            "font_name": "Noto Sans Hebrew",
            "font_size": 18,
            "margin_v": 24 if width > height else 40,
        },
        "output": {
            "path": args.output,
            "video_crf": 19,
            "video_preset": "medium",
            "audio_bitrate": "192k",
        },
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(plan_path)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    ffmpeg = require_ffmpeg(args.ffmpeg)
    plan_path = Path(args.plan).expanduser().resolve()
    _plan, errors, warnings, probes = validate_plan(plan_path, ffmpeg)
    print_validation(errors, warnings)
    print(json.dumps({"sources": probes}, ensure_ascii=False, indent=2))
    if errors:
        return 1
    print("VALID")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    ffmpeg = require_ffmpeg(args.ffmpeg)
    plan_path = Path(args.plan).expanduser().resolve()
    plan, errors, warnings, _probes = validate_plan(plan_path, ffmpeg)
    print_validation(errors, warnings)
    if errors:
        return 1
    output = output_path_for(plan_path, plan)
    if output.exists() and not args.force:
        raise RuntimeError(f"Output already exists: {output}. Use --force only to replace it.")
    output.parent.mkdir(parents=True, exist_ok=True)
    graph, inputs, video_label, audio_label = build_filter_graph(plan_path, plan)
    command = [str(ffmpeg), "-hide_banner", "-loglevel", "warning"]
    for source in inputs:
        command.extend(["-i", str(source)])
    output_cfg = plan["output"]
    command.extend(
        [
            "-filter_complex",
            graph,
            "-map",
            f"[{video_label}]",
            "-map",
            f"[{audio_label}]",
            "-c:v",
            "libx264",
            "-preset",
            str(output_cfg.get("video_preset", "medium")),
            "-crf",
            str(output_cfg.get("video_crf", 19)),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            str(output_cfg.get("audio_sample_rate", 48000)),
            "-b:a",
            str(output_cfg.get("audio_bitrate", "192k")),
            "-movflags",
            "+faststart",
            "-max_muxing_queue_size",
            "2048",
            "-y" if args.force else "-n",
            str(output),
        ]
    )
    process = subprocess.run(command)
    if process.returncode != 0:
        return process.returncode
    print(output)
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    ffmpeg = require_ffmpeg(args.ffmpeg)
    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        raise RuntimeError(f"Source not found: {source}")
    info = probe_media(ffmpeg, source)
    center = float(args.center)
    half = float(args.window) / 2
    start = max(0.0, center - half)
    end = center + half
    if info.get("duration") is not None:
        end = min(end, float(info["duration"]))
    output_dir = Path(args.output_dir).expanduser().resolve()
    frames, contact = sample_frames(ffmpeg, source, start, end, args.count, output_dir)
    print(
        json.dumps(
            {
                "source": str(source),
                "range": [start, end],
                "frames": [str(path) for path in frames],
                "contact_sheet": str(contact),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_qc(args: argparse.Namespace) -> int:
    ffmpeg = require_ffmpeg(args.ffmpeg)
    plan_path = Path(args.plan).expanduser().resolve()
    plan, errors, warnings, _probes = validate_plan(plan_path, ffmpeg)
    if errors:
        print_validation(errors, warnings)
        return 1
    output = Path(args.video).expanduser().resolve() if args.video else output_path_for(plan_path, plan)
    if not output.is_file():
        raise RuntimeError(f"Rendered video not found: {output}")
    info = probe_media(ffmpeg, output)
    canvas = plan["canvas"]
    if info.get("width") != canvas["width"] or info.get("height") != canvas["height"]:
        warnings.append(
            f"rendered dimensions are {info.get('width')}x{info.get('height')}, expected {canvas['width']}x{canvas['height']}"
        )
    if not info.get("has_audio"):
        errors.append("rendered video has no audio stream")
    expected_duration = sum(float(item["end"]) - float(item["start"]) for item in plan["timeline"])
    actual_duration = info.get("duration")
    if actual_duration is None:
        warnings.append("could not read rendered duration")
    elif abs(float(actual_duration) - expected_duration) > 0.35:
        warnings.append(
            f"rendered duration {actual_duration:.3f}s differs from timeline sum {expected_duration:.3f}s"
        )
    if args.output_dir:
        qc_dir = Path(args.output_dir).expanduser().resolve()
    else:
        qc_dir = plan_path.parent.parent / "qc" / output.stem
    qc_dir.mkdir(parents=True, exist_ok=True)
    fps = float(canvas["fps"])
    duration = float(actual_duration or expected_duration)
    first = qc_dir / "first-frame.png"
    last = qc_dir / "last-frame.png"
    extract_frame(ffmpeg, output, 0.0, first)
    extract_frame(ffmpeg, output, max(0.0, duration - 1.0 / fps), last)
    _frames, contact = sample_frames(
        ffmpeg,
        output,
        0.0,
        max(0.0, duration - 1.0 / fps),
        8,
        qc_dir / "timeline",
    )
    manual_checks = [
        "View first-frame.png and confirm it is clean and intentional.",
        "View last-frame.png and confirm it is clean, intentional, and not an accidental hold.",
        "View contact-sheet.jpg for framing, subtitle placement, speaker continuity, and transitions.",
        "Listen from two seconds before the final spoken sentence through the end.",
        "Check Hebrew RTL, mixed Hebrew/Latin order, names, numbers, claims, and CTA.",
    ]
    report = {
        "video": info,
        "expected_duration": expected_duration,
        "errors": errors,
        "warnings": warnings,
        "artifacts": {
            "first_frame": str(first),
            "last_frame": str(last),
            "contact_sheet": str(contact),
        },
        "manual_checks": manual_checks,
    }
    report_path = qc_dir / "qc-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print_validation(errors, warnings)
    print(report_path)
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble and QA short multi-source promotional videos."
    )
    parser.add_argument("--ffmpeg", help="explicit FFmpeg executable path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="check FFmpeg and Sofit availability")
    doctor.set_defaults(func=cmd_doctor)

    init = subparsers.add_parser("init", help="create a project edit-plan skeleton")
    init.add_argument("--project-dir", required=True)
    init.add_argument("--interview", required=True, help="main/interview source or pre-rendered body")
    init.add_argument("--promo", action="append", default=[], help="promo/B-roll source; repeatable")
    init.add_argument("--aspect", choices=sorted(ASPECTS), default="16:9")
    init.add_argument("--name")
    init.add_argument("--landing-page")
    init.add_argument("--output", default="../renders/final-v1.mp4")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    validate = subparsers.add_parser("validate", help="validate plan and source ranges")
    validate.add_argument("plan")
    validate.set_defaults(func=cmd_validate)

    render = subparsers.add_parser("render", help="render a validated edit plan")
    render.add_argument("plan")
    render.add_argument("--force", action="store_true")
    render.set_defaults(func=cmd_render)

    sample = subparsers.add_parser("sample", help="make a frame sheet around a cut point")
    sample.add_argument("source")
    sample.add_argument("--center", type=float, required=True)
    sample.add_argument("--window", type=float, default=1.6)
    sample.add_argument("--count", type=int, default=9)
    sample.add_argument("--output-dir", required=True)
    sample.set_defaults(func=cmd_sample)

    qc = subparsers.add_parser("qc", help="probe output and generate mandatory QC frames")
    qc.add_argument("plan")
    qc.add_argument("--video", help="override plan output for QC")
    qc.add_argument("--output-dir")
    qc.set_defaults(func=cmd_qc)

    return parser


def main() -> int:
    configure_output()
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
