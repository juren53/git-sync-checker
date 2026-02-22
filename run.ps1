# Python venv launcher — generic template
# Drop this script into any Python project, edit the CONFIGURATION block, and run.

$ErrorActionPreference = "Stop"

# --- CONFIGURATION ---
$AppName     = "GSC [git-sync-checker]"   # Display name shown in status messages
$EntryPoint  = "git_sync_checker.py"      # Main Python script to run
$VenvDir     = "venv"                     # Virtual environment directory name
$Requirements = "requirements.txt"        # Pip requirements file
# --- END CONFIGURATION ---

# Resolve project directory (where this script lives)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check if an existing venv's base Python is still present.
# Reads pyvenv.cfg directly — never runs the (potentially broken) venv Python.
function Test-VenvValid {
    param([string]$VenvPath)
    $cfg = Join-Path $VenvPath "pyvenv.cfg"
    if (-not (Test-Path $cfg)) { return $false }
    $homeLine = Get-Content $cfg | Where-Object { $_ -match "^home\s*=" }
    if (-not $homeLine) { return $false }
    $pythonHome = ($homeLine -split "=", 2)[1].Trim()
    return (Test-Path (Join-Path $pythonHome "python.exe"))
}

# Find a working system Python, bypassing any currently activated (possibly broken) venv.
# Priority: py launcher > common install paths > PATH python
function Find-Python {
    # 1. py launcher — Windows-level tool, not affected by venv activation
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $null = & py --version 2>&1
            if ($LASTEXITCODE -eq 0) { return "py" }
        } catch {}
    }

    # 2. Common installation directories (avoids PATH pollution from activated venv)
    $searchPatterns = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe",
        "C:\Python3*\python.exe",
        "C:\Python*\python.exe"
    )
    foreach ($pattern in $searchPatterns) {
        $candidate = Get-Item $pattern -ErrorAction SilentlyContinue |
                     Sort-Object Name -Descending |
                     Select-Object -First 1
        if ($candidate) {
            try {
                $null = & $candidate.FullName --version 2>&1
                if ($LASTEXITCODE -eq 0) { return $candidate.FullName }
            } catch {}
        }
    }

    # 3. PATH python — last resort; may be the broken venv python if one is active
    foreach ($cmd in @("python", "python3")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) {
            try {
                $null = & $found.Source --version 2>&1
                if ($LASTEXITCODE -eq 0) { return $found.Source }
            } catch {}
        }
    }

    return $null
}

# Wipe venv if it exists but points to a missing Python
if ((Test-Path $VenvDir) -and -not (Test-VenvValid $VenvDir)) {
    Write-Host "[$AppName] Existing venv has a broken Python reference, recreating..."
    Remove-Item $VenvDir -Recurse -Force
}

# Create venv if it doesn't exist
if (-not (Test-Path $VenvDir)) {
    Write-Host "[$AppName] Creating virtual environment..."
    $pythonExe = Find-Python
    if (-not $pythonExe) {
        Write-Error "Error: no working Python found. Install Python from https://python.org"
        exit 1
    }
    Write-Host "[$AppName] Using Python: $pythonExe"
    & $pythonExe -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Error: Failed to create venv."
        exit 1
    }
}

# Activate venv
$ActivateScript = "$VenvDir\Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    & $ActivateScript
} else {
    Write-Error "Error: cannot find venv activate script"
    exit 1
}

# Install/update dependencies if requirements.txt is newer than the marker
$Marker = "$VenvDir\.deps_installed"
$installDeps = $false
if (-not (Test-Path $Marker)) {
    $installDeps = $true
} elseif ((Get-Item $Requirements).LastWriteTime -gt (Get-Item $Marker).LastWriteTime) {
    $installDeps = $true
}

if ($installDeps) {
    Write-Host "[$AppName] Installing dependencies..."
    pip install --upgrade pip -q
    pip install -r $Requirements -q
    New-Item -ItemType File -Path $Marker -Force | Out-Null
}

# Launch the application, passing through any command-line arguments
python $EntryPoint @args
