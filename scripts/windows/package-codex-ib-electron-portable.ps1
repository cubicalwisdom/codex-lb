[CmdletBinding()]
param(
    [string]$OutputDir,
    [switch]$SkipFrontendBuild,
    [switch]$NoClean,
    [switch]$ReuseRuntime
)

$ErrorActionPreference = "Stop"

function Resolve-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-InsideDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Child,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $childFull = Resolve-FullPath $Child
    $parentFull = Resolve-FullPath $Parent
    $comparison = [System.StringComparison]::OrdinalIgnoreCase
    $prefix = $parentFull.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar

    if (-not ($childFull.Equals($parentFull, $comparison) -or $childFull.StartsWith($prefix, $comparison))) {
        throw "Refusing to operate outside '$parentFull': '$childFull'"
    }
}

function Get-UvPath {
    $command = Get-Command uv.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    foreach ($candidate in @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe")
    )) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw "Could not find uv.exe."
}

function Get-BunPath {
    if ($env:BUN -and (Test-Path -LiteralPath $env:BUN)) {
        return $env:BUN
    }

    $command = Get-Command bun.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $wingetPath = Join-Path $env:USERPROFILE "AppData\Local\Microsoft\WinGet\Links\bun.exe"
    if (Test-Path -LiteralPath $wingetPath) {
        return $wingetPath
    }

    throw "Could not find bun.exe. Install Bun or pass -SkipFrontendBuild after building app/static."
}

function Invoke-RobocopyMirror {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [string[]]$ExtraExcludeDirectories = @()
    )

    $excludeDirectories = @("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", "node_modules") + $ExtraExcludeDirectories
    $excludeFiles = @("*.pyc", "*.pyo")

    & robocopy.exe $Source $Destination /MIR /NFL /NDL /NJH /NJS /NP /XD $excludeDirectories /XF $excludeFiles | Out-Host
    $exitCode = $LASTEXITCODE
    $global:LASTEXITCODE = 0

    if ($exitCode -gt 7) {
        throw "robocopy failed copying '$Source' to '$Destination' with exit code $exitCode"
    }
}

function Write-PortableReadme {
    param([Parameter(Mandatory = $true)][string]$TargetDir)

    $readme = @'
Codex IB Electron Portable
==========================

Run:
  Codex IB.exe

Keep the full folder together. The EXE needs these sidecar folders:
  - .python        portable CPython runtime
  - .venv          portable Python runtime and Python packages
  - app            Codex IB backend and built frontend assets
  - config         runtime configuration package
  - portable-data  local Codex IB database/encryption key
  - logs           Electron launcher and backend logs

Target PC requirements:
  - Windows x64
  - No Docker required
  - No Python install required
  - No uv install required
  - No Bun/Node install required

The app opens its own Electron window at http://127.0.0.1:2455/codexneo.
If another Codex IB server is already healthy on port 2455, the Electron shell reuses it.
'@

    Set-Content -LiteralPath (Join-Path $TargetDir "README-PORTABLE-ELECTRON.txt") -Encoding UTF8 -Value $readme
}

function Copy-PythonRuntimeSidecar {
    param([Parameter(Mandatory = $true)][string]$TargetDir)

    $venvConfig = Join-Path $TargetDir ".venv\pyvenv.cfg"
    if (-not (Test-Path -LiteralPath $venvConfig)) {
        throw "Missing venv config: $venvConfig"
    }

    $pythonHome = ((Get-Content -LiteralPath $venvConfig | Where-Object { $_ -like "home = *" }) -replace "^home = ", "").Trim()
    if (-not [System.IO.Path]::IsPathRooted($pythonHome)) {
        $pythonHome = [System.IO.Path]::GetFullPath((Join-Path (Join-Path $TargetDir ".venv") $pythonHome))
    }
    if (-not (Test-Path -LiteralPath $pythonHome)) {
        throw "Python runtime source not found: $pythonHome"
    }

    $sidecar = Join-Path $TargetDir ".python"
    & robocopy.exe $pythonHome $sidecar /MIR /NFL /NDL /NJH /NJS /NP | Out-Host
    $exitCode = $LASTEXITCODE
    $global:LASTEXITCODE = 0

    if ($exitCode -gt 7) {
        throw "robocopy failed copying Python runtime '$pythonHome' to '$sidecar' with exit code $exitCode"
    }

    $content = Get-Content -LiteralPath $venvConfig
    $content = $content -replace "^home = .*$", "home = ..\.python"
    Set-Content -LiteralPath $venvConfig -Encoding UTF8 -Value $content
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$distRoot = Join-Path $repoRoot "dist"
$targetRoot = if ($OutputDir) { Resolve-FullPath $OutputDir } else { Join-Path $distRoot "CodexIB-Electron-Portable" }
$electronOut = Join-Path $distRoot "electron-packager-work"
$electronSource = Join-Path $repoRoot "desktop\electron"

Assert-InsideDirectory -Child $targetRoot -Parent $distRoot
Assert-InsideDirectory -Child $electronOut -Parent $distRoot

if (-not $SkipFrontendBuild) {
    $bun = Get-BunPath
    Push-Location (Join-Path $repoRoot "frontend")
    try {
        & $bun run build
    }
    finally {
        Pop-Location
    }
}

$indexHtml = Join-Path $repoRoot "app\static\index.html"
if (-not (Test-Path -LiteralPath $indexHtml)) {
    throw "Missing app/static/index.html. Run the frontend build before packaging."
}

if (-not (Test-Path -LiteralPath (Join-Path $electronSource "node_modules\electron"))) {
    Push-Location $electronSource
    try {
        npm install
    }
    finally {
        Pop-Location
    }
}

if ((Test-Path -LiteralPath $targetRoot) -and -not $NoClean) {
    Remove-Item -LiteralPath $targetRoot -Recurse -Force
}
if (Test-Path -LiteralPath $electronOut) {
    Remove-Item -LiteralPath $electronOut -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $distRoot | Out-Null

Push-Location $electronSource
try {
    npx electron-packager . "Codex IB" --platform=win32 --arch=x64 --asar --overwrite --out "$electronOut"
}
finally {
    Pop-Location
}

$packagedDir = Get-ChildItem -LiteralPath $electronOut -Directory | Where-Object { $_.Name -like "Codex IB-win32-*" } | Select-Object -First 1
if (-not $packagedDir) {
    throw "Could not find Electron packaged output under '$electronOut'."
}

Move-Item -LiteralPath $packagedDir.FullName -Destination $targetRoot
Remove-Item -LiteralPath $electronOut -Recurse -Force

New-Item -ItemType Directory -Force -Path (Join-Path $targetRoot "logs"), (Join-Path $targetRoot "portable-data") | Out-Null

Invoke-RobocopyMirror -Source (Join-Path $repoRoot "app") -Destination (Join-Path $targetRoot "app")
Invoke-RobocopyMirror -Source (Join-Path $repoRoot "config") -Destination (Join-Path $targetRoot "config")

foreach ($file in @("pyproject.toml", "uv.lock", "README.md", "LICENSE", ".env.example")) {
    $sourceFile = Join-Path $repoRoot $file
    if (Test-Path -LiteralPath $sourceFile) {
        Copy-Item -LiteralPath $sourceFile -Destination (Join-Path $targetRoot $file) -Force
    }
}

$runtimeVenv = Join-Path $targetRoot ".venv"
if (-not ($ReuseRuntime -and (Test-Path -LiteralPath (Join-Path $runtimeVenv "Scripts\python.exe")))) {
    if (Test-Path -LiteralPath $runtimeVenv) {
        Remove-Item -LiteralPath $runtimeVenv -Recurse -Force
    }

    $uv = Get-UvPath
    & $uv venv $runtimeVenv --relocatable --managed-python --python 3.13 --clear

    $oldProjectEnvironment = $env:UV_PROJECT_ENVIRONMENT
    $oldLinkMode = $env:UV_LINK_MODE
    try {
        $env:UV_PROJECT_ENVIRONMENT = $runtimeVenv
        $env:UV_LINK_MODE = "copy"
        Push-Location $repoRoot
        try {
            & $uv sync --frozen --no-dev --no-editable --compile-bytecode --managed-python
        }
        finally {
            Pop-Location
        }
    }
    finally {
        if ($null -eq $oldProjectEnvironment) { Remove-Item Env:\UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue } else { $env:UV_PROJECT_ENVIRONMENT = $oldProjectEnvironment }
        if ($null -eq $oldLinkMode) { Remove-Item Env:\UV_LINK_MODE -ErrorAction SilentlyContinue } else { $env:UV_LINK_MODE = $oldLinkMode }
    }
}

Copy-PythonRuntimeSidecar -TargetDir $targetRoot

Write-PortableReadme -TargetDir $targetRoot

Write-Host "Electron portable Codex IB package created:"
Write-Host "  $targetRoot"
Write-Host "Run:"
Write-Host "  $targetRoot\Codex IB.exe"
Write-Host "Open URL:"
Write-Host "  http://127.0.0.1:2455/codexneo"
