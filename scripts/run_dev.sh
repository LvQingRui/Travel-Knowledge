#!/usr/bin/env bash
# 本地开发启动脚本
set -e

cd "$(dirname "$0")/.."

if ! command -v conda &>/dev/null; then
    echo "未检测到 conda，请先安装 Anaconda/Miniconda"
    exit 1
fi

if ! conda env list | grep -q "^travel "; then
    echo "创建 conda 环境 travel (Python 3.11)..."
    conda env create -f environment.yml
fi

echo "启动开发服务器..."
echo "提示: 请求日志会实时打印在下方，按 Ctrl+C 停止"
echo ""

PORT=8000
if lsof -i :"$PORT" -sTCP:LISTEN -t &>/dev/null; then
    PID=$(lsof -i :"$PORT" -sTCP:LISTEN -t | head -1)
    echo "错误: 端口 $PORT 已被占用 (PID: $PID)"
    echo "请先结束旧进程: kill $PID"
    echo "或强制结束: kill -9 $PID"
    exit 1
fi

# HuggingFace 镜像加速（国内下载 BGE-M3 用，可在 .env 中配置 HF_ENDPOINT / HF_TOKEN）
if [ -f .env ]; then
    val=$(grep '^HF_ENDPOINT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "' | tr -d '\r')
    [ -n "$val" ] && export HF_ENDPOINT="$val"
    val=$(grep '^HF_TOKEN=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "' | tr -d '\r')
    [ -n "$val" ] && export HF_TOKEN="$val"
fi
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

# --no-capture-output 让 conda 不吞掉 uvicorn 日志
conda run --no-capture-output -n travel \
    uvicorn app.main:app --reload --host 0.0.0.0 --port "$PORT" --log-level info
