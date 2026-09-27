[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$SkillRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $SkillRoot ".runtime"
$RuntimePython = if ($IsWindows -or $env:OS -eq "Windows_NT") {
    Join-Path $RuntimeRoot "Scripts\python.exe"
} else {
    Join-Path $RuntimeRoot "bin/python"
}
$RuntimeSofit = if ($IsWindows -or $env:OS -eq "Windows_NT") {
    Join-Path $RuntimeRoot "Scripts\sofit.exe"
} else {
    Join-Path $RuntimeRoot "bin/sofit"
}
$SofitRef = "d1de4ff67e79c6fbc121c95022748cebe6585fb1"
$SofitRequirement = "sofit-cli[render,crop] @ https://github.com/navotvolkgroundup/sofit/archive/$SofitRef.zip"
$ToolsRoot = Join-Path $RuntimeRoot "tools"
$RuntimeFfmpeg = Join-Path $ToolsRoot "ffmpeg.exe"
$RuntimeFfprobe = Join-Path $ToolsRoot "ffprobe.exe"

if ($CheckOnly) {
    if (-not (Test-Path -LiteralPath $RuntimePython -PathType Leaf)) {
        Write-Error "Runtime is missing: $RuntimePython"
        exit 1
    }
    & $RuntimePython -c "import imageio_ffmpeg, sofit; print('runtime OK'); print(imageio_ffmpeg.get_ffmpeg_exe())"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if (-not (Test-Path -LiteralPath $RuntimeSofit -PathType Leaf)) {
        Write-Error "Sofit command is missing: $RuntimeSofit"
        exit 1
    }
    if (($IsWindows -or $env:OS -eq "Windows_NT") -and
        (-not (Test-Path -LiteralPath $RuntimeFfmpeg -PathType Leaf) -or
         -not (Test-Path -LiteralPath $RuntimeFfprobe -PathType Leaf))) {
        Write-Error "FFmpeg/ffprobe tools are missing under $ToolsRoot"
        exit 1
    }
    exit 0
}

if (-not $PythonExe) {
    $CodexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $CodexPython -PathType Leaf) {
        $PythonExe = $CodexPython
    } else {
        foreach ($CandidateName in @("python3", "python", "py")) {
            $Candidate = Get-Command $CandidateName -ErrorAction SilentlyContinue
            if (-not $Candidate) { continue }
            & $Candidate.Source --version *> $null
            if ($LASTEXITCODE -eq 0) {
                $PythonExe = $Candidate.Source
                break
            }
        }
    }
}

if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    Write-Error "Python 3.10+ was not found. Pass -PythonExe with an explicit interpreter path."
    exit 1
}

if (-not (Test-Path -LiteralPath $RuntimePython -PathType Leaf)) {
    & $PythonExe -m venv $RuntimeRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $RuntimePython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $RuntimePython -m pip install "imageio-ffmpeg>=0.6.0" $SofitRequirement
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $RuntimePython (Join-Path $PSScriptRoot "patch_sofit_runtime.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (($IsWindows -or $env:OS -eq "Windows_NT") -and
    (-not (Test-Path -LiteralPath $RuntimeFfmpeg -PathType Leaf) -or
     -not (Test-Path -LiteralPath $RuntimeFfprobe -PathType Leaf))) {
    $ArchiveUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    $ChecksumUrl = "$ArchiveUrl.sha256"
    $TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("hebrew-promo-ffmpeg-" + [guid]::NewGuid().ToString("N"))
    $ArchivePath = Join-Path $TempRoot "ffmpeg.zip"
    $ChecksumPath = Join-Path $TempRoot "ffmpeg.zip.sha256"
    $ExtractRoot = Join-Path $TempRoot "extract"
    New-Item -ItemType Directory -Path $TempRoot | Out-Null
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $ArchiveUrl -OutFile $ArchivePath
        Invoke-WebRequest -UseBasicParsing -Uri $ChecksumUrl -OutFile $ChecksumPath
        $ExpectedHash = ((Get-Content -Raw -LiteralPath $ChecksumPath).Trim() -split "\s+")[0].ToUpperInvariant()
        $ActualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArchivePath).Hash.ToUpperInvariant()
        if ($ExpectedHash -ne $ActualHash) {
            throw "FFmpeg archive checksum mismatch"
        }
        Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ExtractRoot
        $DownloadedFfmpeg = Get-ChildItem -LiteralPath $ExtractRoot -Filter "ffmpeg.exe" -File -Recurse | Select-Object -First 1
        $DownloadedFfprobe = Get-ChildItem -LiteralPath $ExtractRoot -Filter "ffprobe.exe" -File -Recurse | Select-Object -First 1
        if (-not $DownloadedFfmpeg -or -not $DownloadedFfprobe) {
            throw "FFmpeg archive did not contain ffmpeg.exe and ffprobe.exe"
        }
        New-Item -ItemType Directory -Force -Path $ToolsRoot | Out-Null
        Copy-Item -LiteralPath $DownloadedFfmpeg.FullName -Destination $RuntimeFfmpeg -Force
        Copy-Item -LiteralPath $DownloadedFfprobe.FullName -Destination $RuntimeFfprobe -Force
    }
    finally {
        if (Test-Path -LiteralPath $TempRoot) {
            Remove-Item -LiteralPath $TempRoot -Recurse -Force
        }
    }
}

& $RuntimePython -c "import imageio_ffmpeg, sofit; print('runtime OK'); print(imageio_ffmpeg.get_ffmpeg_exe())"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "Sofit: $RuntimeSofit"
