#!/usr/bin/env bash
# ============================================================================
# QMI平台 - 容器启动前检查脚本（Docker Compose prestart）
#
# 作用：
#   1. 等待 MongoDB 就绪
#   2. 等待 Redis 就绪
#   3. 为后端服务提供健康依赖保障
# ============================================================================
set -euo pipefail

echo "========== QMI prestart 检查 =========="

# ── MongoDB 健康检查 ──────────────────────────────────────────────
echo "[1/2] 等待 MongoDB 就绪..."
max_retries=30
retry=0
while [ $retry -lt $max_retries ]; do
    if python -c "
import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
async def check():
    url = os.getenv('MONGODB_URL', 'mongodb://mongo:27017')
    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=2000)
    try:
        await client.admin.command('ping')
        print('ok')
    except Exception as e:
        print(f'fail: {e}')
asyncio.run(check())
" | grep -q "ok"; then
        echo "  ✅ MongoDB 已就绪"
        break
    fi
    retry=$((retry + 1))
    echo "  ⏳ 等待 MongoDB... ($retry/$max_retries)"
    sleep 2
done

if [ $retry -ge $max_retries ]; then
    echo "  ❌ MongoDB 连接超时"
    exit 1
fi

# ── Redis 健康检查 ───────────────────────────────────────────────
echo "[2/2] 等待 Redis 就绪..."
max_retries=15
retry=0
while [ $retry -lt $max_retries ]; do
    if python -c "
import os, asyncio
import redis.asyncio as aioredis
async def check():
    url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    r = aioredis.from_url(url, socket_connect_timeout=2)
    try:
        await r.ping()
        print('ok')
    except Exception as e:
        print(f'fail: {e}')
    finally:
        await r.close()
asyncio.run(check())
" | grep -q "ok"; then
        echo "  ✅ Redis 已就绪"
        break
    fi
    retry=$((retry + 1))
    echo "  ⏳ 等待 Redis... ($retry/$max_retries)"
    sleep 2
done

if [ $retry -ge $max_retries ]; then
    echo "  ❌ Redis 连接超时"
    exit 1
fi

echo "========== prestart 检查完成，启动应用 =========="
