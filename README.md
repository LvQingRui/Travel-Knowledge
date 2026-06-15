# Travel-Knowledge

旅游智能知识库系统，基于 RAG（检索增强生成）技术，提供景点检索、线路推荐、美食攻略等智能问答服务。

## 功能特性

- Markdown 文档批量导入与向量化
- 混合检索（稠密向量 + BM25 稀疏向量）
- 多路召回（向量 + HyDE + Web 搜索）+ Reranker 精排
- DeepSeek 流式问答 + 引用溯源
- MongoDB 多轮会话历史
- 轻量 Web 聊天界面

## 技术栈

| 类别 | 技术 |
|------|------|
| 后端 | FastAPI + LangGraph |
| 向量库 | Milvus |
| 文档库 | MongoDB |
| 文件存储 | MinIO |
| LLM | DeepSeek / 通义千问 |
| 嵌入 | DashScope text-embedding-v3 |
| 稀疏向量 | BGE-M3（本地） |
| 重排序 | BGE-Reranker-Large（本地） |

## 快速开始

### 1. 克隆项目

```bash
git clone git@github.com:LvQingRui/Travel-Knowledge.git
cd Travel-Knowledge
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入服务器 IP 和 API Key
```

### 3. 启动基础设施（阿里云服务器）

```bash
docker compose up -d
```

### 4. 安装 Python 依赖

```bash
conda create -n travel python=3.11 -y
conda activate travel
pip install -r requirements.txt
```

### 5. 下载本地模型（可选，也可手动放置）

```bash
bash scripts/download_bge.sh
# Reranker 模型放到 app/models/bge-reranker-large/
```

### 6. 启动服务

```bash
./scripts/run_dev.sh
```

访问聊天界面：http://localhost:8000/chat-ui

## 批量导入文档

```bash
python scripts/batch_import.py /你的文档目录/ --recursive
```

## 项目结构

```
Travel-Knowledge/
├── app/              # 后端应用
├── static/           # 前端聊天界面
├── scripts/          # 工具脚本
├── samples/          # 示例文档
├── docker-compose.yml
└── requirements.txt
```

## 注意事项

- `.env` 含密钥，切勿提交到 Git
- `app/models/bge-m3/` 和 `app/models/bge-reranker-large/` 为本地模型，需自行下载
- 服务器 Docker 数据在 `data/` 目录，不会上传
