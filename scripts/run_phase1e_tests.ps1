# Phase 1.E Integration Test Runner
# Run this script to execute end-to-end integration tests with real APIs

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "PHASE 1.E: Integration Testing & Debugging" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "❌ ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please create .env with required credentials:" -ForegroundColor Yellow
    Write-Host "  - OPENAI_API_KEY" -ForegroundColor Yellow
    Write-Host "  - SUPABASE_URL" -ForegroundColor Yellow
    Write-Host "  - SUPABASE_KEY" -ForegroundColor Yellow
    Write-Host "  - JWT_SECRET_KEY" -ForegroundColor Yellow
    exit 1
}

# Load environment variables
Write-Host "📋 Loading environment variables..." -ForegroundColor Green
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)\s*=\s*(.+)\s*$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# Check required variables
$required = @(
    "OPENAI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "JWT_SECRET_KEY"
)

$missing = @()
foreach ($var in $required) {
    if (-not [Environment]::GetEnvironmentVariable($var, "Process")) {
        $missing += $var
    }
}

if ($missing.Count -gt 0) {
    Write-Host "❌ ERROR: Missing required environment variables:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    exit 1
}

Write-Host "✓ All required environment variables present" -ForegroundColor Green
Write-Host ""

# Enable integration testing
[Environment]::SetEnvironmentVariable("INTEGRATION_TEST", "true", "Process")

# Run integration tests
Write-Host "🧪 Running Phase 1.E Integration Tests..." -ForegroundColor Cyan
Write-Host "This may take several minutes as it makes real API calls." -ForegroundColor Yellow
Write-Host ""

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "📦 Activating virtual environment..." -ForegroundColor Green
    & .venv\Scripts\Activate.ps1
}

# Run pytest with integration tests only
$testCommand = "python -m pytest tests/integration/test_e2e_chat_flow.py -v --tb=short -s"

Write-Host "Running: $testCommand" -ForegroundColor Gray
Write-Host ""

Invoke-Expression $testCommand

$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan

if ($exitCode -eq 0) {
    Write-Host "✅ PHASE 1.E: ALL TESTS PASSED" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Yellow
    Write-Host "1. Review test output above" -ForegroundColor White
    Write-Host "2. Check performance metrics" -ForegroundColor White
    Write-Host "3. Verify all citations and suggestions" -ForegroundColor White
    Write-Host "4. Create docs/PHASE_1E_COMPLETION.md" -ForegroundColor White
    Write-Host "5. Proceed to Phase 1.1" -ForegroundColor White
} else {
    Write-Host "❌ PHASE 1.E: TESTS FAILED" -ForegroundColor Red
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Required Actions:" -ForegroundColor Yellow
    Write-Host "1. Review error messages above" -ForegroundColor White
    Write-Host "2. Fix identified issues" -ForegroundColor White
    Write-Host "3. Re-run tests" -ForegroundColor White
    Write-Host "4. Do NOT proceed to Phase 1.1 until all tests pass" -ForegroundColor Red
}

Write-Host ""

exit $exitCode
