#!/usr/bin/env python3
"""
RAG HTTP API 启动脚本

使用方法：
    uv run run_api.py
    或
    uv run --port 8001 run_api.py
"""
import uvicorn
import os
from config.settings import settings

# 从环境变量读取配置
HOST = os.getenv("RAG_HOST", "0.0.0.0")
PORT = int(os.getenv("RAG_PORT", "9000"))

if __name__ == "__main__":
    settings.display()
    print(f"\n🚀 Starting RAG API Server on http://{HOST}:{PORT}")
    print(f"📚 API Docs: http://{HOST}:{PORT}/docs")
    print(f"🔍 Search Endpoint: POST http://{HOST}:{PORT}/rag/search")
    print("\n")

    uvicorn.run(
        "rag_http_api:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info"
    )
