#!/usr/bin/env bash
set -e

echo "=== Ruff Fix ==="
ruff check app/ scripts/ tests/ --fix

echo "=== Ruff Format ==="
ruff format app/ scripts/ tests/

echo "=== 格式化完成 ==="
