#!/usr/bin/env bash
set -e

echo "=== 运行测试 ==="

pytest tests/ -v \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-fail-under=70 \
    "$@"

echo "=== 测试完成 ==="
