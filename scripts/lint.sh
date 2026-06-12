#!/usr/bin/env bash
set -e

echo "=== Ruff 检查 ==="
ruff check app/ scripts/ tests/

echo "=== Ruff 格式化检查 ==="
ruff format --check app/ scripts/ tests/

echo "=== 检查通过 ==="
