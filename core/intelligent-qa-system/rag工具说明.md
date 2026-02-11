# 智能问答系统 (Intelligent QA System)

基于 RAG (Retrieval-Augmented Generation) 的智能问答助手，支持本地文档知识库检索与大模型生成。

## 📋 项目模块
- ✅ 配置管理
- ✅ 文档加载（PDF、Word、Markdown）
- ✅ 文本处理（切分、清洗）
- ✅ 向量化（本地模型 / Qwen API）
- ✅ 向量存储（FAISS）
- ✅ 语义检索
- ✅ LLM 集成（Qwen / DeepSeek）
- ✅ RAG 问答链
- ✅ MCP server

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```
或者
```bash
conda env create -f environment.yml
```
或者
```
uv run run_api.py
```

### 2. 配置环境变量

编辑 `.env` 文件：

```bash
# Embedding 模型
EMBEDDING_MODEL=qwen  # 或 local

# LLM 模型
DEFAULT_LLM=qwen  # 或 deepseek

# API Keys
QWEN_API_KEY=your_qwen_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

也可以在 `config/settings.py` 中修改其他默认参数：

```python
# 检索参数
TOP_K = 5  # 返回文档数量
SIMILARITY_THRESHOLD = 0.3  # 相似度阈值

# LLM 参数
LLM_TEMPERATURE = 0.7  # 生成温度
LLM_MAX_TOKENS = 2000  # 最大 token 数
```

### 3. 准备文档

将你的文档放到对应目录:
- PDF 文件 → `data/documents/pdfs/`
- Word 文件 → `data/documents/docx/`
- Markdown 文件 → `data/documents/markdown/`


### 4. 构建向量索引

```bash
python scripts/build_index.py
```

### 5. 启动 HTTP MCP 服务器
```bash
uvicorn rag_http_api:app --host 127.0.0.1 --port 9000 --reload
```

## 📁 项目结构

```
intelligent-qa-system/
├── config/
│   └── settings.py              # 配置管理
├── data/
│   ├── documents/               # 文档存储
│   │   ├── pdfs/
│   │   ├── docx/
│   │   └── markdown/
│   └── vector_store/            # FAISS 索引
├── src/
│   ├── document_loader/         # 文档加载
│   ├── text_processor/          # 文本处理
│   ├── embeddings/              # 向量化
│   ├── vector_store/            # 向量存储
│   ├── retriever/               # 检索
│   ├── llm/                     # LLM (Qwen, DeepSeek)
│   └── qa_chain/                # RAG 问答链
├── scripts/
│   ├── test_document_loader.py  # 测试文档加载
│   ├── build_index.py           # 构建索引
│   ├── test_query.py            # 测试检索
│   └── test_rag.py              # 测试问答
├── mcp-client-test/
│   └── test-mcp-client.ts       # 测试ts版本clinet连接
├── rag_http_api.py              # 启动mcp服务器
├── requirements.txt             # 依赖
├── .env                         # 配置
└── README.md                    # 说明文档
```



