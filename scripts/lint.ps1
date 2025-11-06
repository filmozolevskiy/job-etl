# Pre-commit linting script for PowerShell
# Run Ruff linter on all Python files

Write-Host "🔍 Running Ruff linter..." -ForegroundColor Cyan
ruff check .

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ All checks passed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "❌ Linting failed. Run 'ruff check --fix .' to auto-fix issues." -ForegroundColor Red
    exit 1
}

