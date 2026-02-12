# test_index_debug.py
import faiss
import numpy as np
from pathlib import Path
import json

# 加载索引
index_path = Path(r"E:\srp\robot-agent-main\core\intelligent-qa-system\data\vector_store\faiss_index.bin")
index = faiss.read_index(str(index_path))

print(f"索引类型: {type(index)}")
print(f"索引维度: {index.d}")
print(f"索引向量数: {index.ntotal}")
print(f"是否训练: {index.is_trained}")

# 测试搜索（用随机向量）
query = np.random.randn(1, index.d).astype(np.float32)
faiss.normalize_L2(query)

distances, indices = index.search(query, 5)
print(f"\n搜索结果:")
print(f"距离: {distances[0]}")
print(f"索引: {indices[0]}")

# 尝试提取向量
if hasattr(index, 'reconstruct'):
    print(f"\n✅ 索引支持 reconstruct")
    vec = index.reconstruct(0)
    print(f"第一个向量: {vec[:10]}...")
    print(f"范数: {np.linalg.norm(vec):.4f}")
else:
    print(f"\n❌ 索引不支持 reconstruct")

# 检查元数据
metadata_path = Path(r"E:\srp\robot-agent-main\core\intelligent-qa-system\data\vector_store\metadata.json")
with open(metadata_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

print(f"\n元数据:")
print(f"文档数: {metadata['document_count']}")
print(f"索引类型: {metadata['index_type']}")
print(f"维度: {metadata['dimension']}")