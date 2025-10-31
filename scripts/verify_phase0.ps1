# Phase 0 Setup Verification Script
Write-Host "=== LEO Backend Phase 0 Verification ===" -ForegroundColor Cyan

# Check Python
Write-Host "`n1. Python version..." -ForegroundColor Yellow
python --version

# Check directories
Write-Host "`n2. Directory structure..." -ForegroundColor Yellow
$dirs = @("api/v1", "app", "core", "services/pipeline", "adapters", "nlp", "kb", "tests")
foreach ($d in $dirs) {
    if (Test-Path $d) { Write-Host "  OK $d" -ForegroundColor Green }
    else { Write-Host "  MISSING $d" -ForegroundColor Red }
}

# Check key files
Write-Host "`n3. Core files..." -ForegroundColor Yellow
$files = @("core/config.py", "app/main.py", "pyproject.toml", "Dockerfile", "README.md")
foreach ($f in $files) {
    if (Test-Path $f) { Write-Host "  OK $f" -ForegroundColor Green }
    else { Write-Host "  MISSING $f" -ForegroundColor Red }
}

# Check adapters
Write-Host "`n4. Adapter interfaces..." -ForegroundColor Yellow
$adapters = @("llm", "embeddings", "vectorstore", "memory", "translate", "maps", "moderation")
foreach ($a in $adapters) {
    $path = "adapters/$a/base.py"
    if (Test-Path $path) { Write-Host "  OK $path" -ForegroundColor Green }
    else { Write-Host "  MISSING $path" -ForegroundColor Red }
}

Write-Host "`n=== Phase 0 Complete ===" -ForegroundColor Green
Write-Host "Next: Install dependencies and run the app" -ForegroundColor Yellow
Write-Host "  pip install -e ." -ForegroundColor Cyan
Write-Host "  python -m uvicorn app.main:app --reload" -ForegroundColor Cyan
