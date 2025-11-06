#!/bin/bash
# Pre-commit linting script
# Run Ruff linter on all Python files

echo "🔍 Running Ruff linter..."
ruff check .

if [ $? -eq 0 ]; then
    echo "✅ All checks passed!"
    exit 0
else
    echo "❌ Linting failed. Run 'ruff check --fix .' to auto-fix issues."
    exit 1
fi

