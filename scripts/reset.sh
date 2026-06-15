#!/usr/bin/env bash
# 完全重置所有基础设施服务（会删除所有数据！）
set -e

cd "$(dirname "$0")/.."

echo "=========================================="
echo "  旅游知识库 - 基础设施完全重置"
echo "  警告：将删除所有 Docker 容器和数据！"
echo "=========================================="
read -p "确认重置？输入 yes 继续: " confirm
if [ "$confirm" != "yes" ]; then
    echo "已取消"
    exit 0
fi

echo "[1/4] 停止并删除所有容器..."
docker compose down -v --remove-orphans 2>/dev/null || true

echo "[2/4] 删除残留容器（如有）..."
docker rm -f travel-milvus travel-minio travel-mongodb travel-etcd 2>/dev/null || true

echo "[3/4] 清理数据目录..."
sudo rm -rf data/

echo "[4/4] 重新启动服务..."
docker compose up -d

echo ""
echo "等待服务启动（约 2 分钟）..."
sleep 30
docker compose ps
echo ""
echo "健康检查："
curl -sf http://localhost:9091/healthz && echo "Milvus: OK" || echo "Milvus: 还在启动中，请稍后再试"
echo ""
echo "如果 Milvus 仍是 starting，再等 1-2 分钟后执行："
echo "  docker compose ps"
echo "  docker compose logs milvus --tail 30"
