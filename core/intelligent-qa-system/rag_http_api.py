from fastapi import FastAPI
from pydantic import BaseModel
from config.settings import settings
from src.vector_store.store_manager import VectorStoreManager
from src.retriever.semantic_search import SemanticRetriever

app = FastAPI(title="RAG HTTP API")

# ===== 初始化（和 FastMCP 共用逻辑）=====
_store_manager = VectorStoreManager(
    embedding_model=settings.EMBEDDING_MODEL
)
_store_manager.load_index()
_retriever = SemanticRetriever(_store_manager)


class SearchRequest(BaseModel):
    query: str


@app.post("/rag/search")
def search_knowledge_base(req: SearchRequest):
    results = _retriever.retrieve(query=req.query)

    if not results:
        return {"query": req.query, "total": 0, "results": []}

    return {
        "query": req.query,
        "total": len(results),
        "results": [
            {
                "content": r.document.content,
                "score": round(r.score, 3),
                "rank": r.rank,
                "source": r.document.metadata.get("filename", "Unknown"),
            }
            for r in results
        ],
    }
