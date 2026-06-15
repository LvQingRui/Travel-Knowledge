#!/usr/bin/env bash
# 下载 BGE-M3 模型到本地（国内推荐，避免 HuggingFace 直连失败）
set -e

cd "$(dirname "$0")/.."
MODEL_DIR="$(pwd)/models/bge-m3"

echo "=========================================="
echo "  下载 BGE-M3 模型到: $MODEL_DIR"
echo "=========================================="

mkdir -p models

# 读取 .env 中的镜像配置
if [ -f .env ]; then
    val=$(grep '^HF_ENDPOINT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "' | tr -d '\r')
    [ -n "$val" ] && export HF_ENDPOINT="$val"
fi
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

if ! command -v conda &>/dev/null; then
    echo "未检测到 conda"
    exit 1
fi

echo ""
echo "方式一：HuggingFace 镜像下载（推荐）"
echo "镜像地址: $HF_ENDPOINT"
echo ""

conda run --no-capture-output -n travel pip install -U huggingface_hub -q

conda run --no-capture-output -n travel \
    huggingface-cli download BAAI/bge-m3 \
    --local-dir "$MODEL_DIR" \
    --local-dir-use-symlinks False

echo ""
echo "=========================================="
echo "  下载完成！"
echo ""
echo "  请在 .env 中添加："
echo "  BGE_MODEL_PATH=./models/bge-m3"
echo "  HF_ENDPOINT=https://hf-mirror.com"
echo ""
echo "  然后重启服务，重新上传文档"
echo "=========================================="
