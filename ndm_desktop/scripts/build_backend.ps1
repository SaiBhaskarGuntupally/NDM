$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$serviceDir = Join-Path $repoRoot "ndm_oncall"
$distDir = Join-Path $repoRoot "ndm_desktop\src-tauri\bin"

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path $venvPython) { $venvPython } else { "python" }

Push-Location $repoRoot
try {
  & $pythonExe -m PyInstaller --noconfirm --onefile --noconsole --name ndm_backend `
    --paths "$repoRoot" `
    --hidden-import ndm_oncall `
    --collect-submodules ndm_oncall `
    --add-data "$serviceDir\templates;templates" `
    --add-data "$serviceDir\static;static" `
    "$serviceDir\ndm_backend.py"

  Copy-Item "$repoRoot\dist\ndm_backend.exe" $distDir -Force
  Copy-Item "$repoRoot\dist\ndm_backend.exe" (Join-Path $distDir "ndm_backend-x86_64-pc-windows-msvc.exe") -Force
} finally {
  Pop-Location
}
