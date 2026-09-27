#!/usr/bin/env python3
"""Run the pinned Sofit CLI with imageio-ffmpeg available to child processes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        import imageio_ffmpeg
    except ImportError:
        print(
            "ERROR: imageio-ffmpeg is unavailable. Run setup_runtime.ps1 and use its Python.",
            file=sys.stderr,
        )
        return 2

    skill_root = Path(__file__).resolve().parents[1]
    runtime_python = Path(sys.executable).resolve()
    if not runtime_python.is_file():
        print(f"ERROR: Sofit runtime Python is missing: {runtime_python}", file=sys.stderr)
        return 2

    tools_dir = skill_root / ".runtime" / "tools"
    if os.name == "nt":
        required = [tools_dir / "ffmpeg.exe", tools_dir / "ffprobe.exe"]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            print(
                "ERROR: the isolated FFmpeg tools are incomplete. Re-run setup_runtime.ps1. "
                + "Missing: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            return 2
        ffmpeg_dir = str(tools_dir)
    else:
        ffmpeg_dir = str(Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve().parent)
    environment = os.environ.copy()
    environment["PATH"] = ffmpeg_dir + os.pathsep + environment.get("PATH", "")
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    # Run the module through the isolated interpreter instead of the generated
    # console-script executable. Some managed Windows installations block
    # newly-created .exe launchers even though the signed Python host is allowed.
    return subprocess.call(
        [str(runtime_python), "-m", "sofit.cli", *sys.argv[1:]], env=environment
    )


if __name__ == "__main__":
    raise SystemExit(main())
