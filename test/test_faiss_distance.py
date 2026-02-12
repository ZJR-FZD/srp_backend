"""
测试 FAISS IndexFlatL2 返回的距离值含义
"""
import numpy as np
import faiss

# 创建一个简单的 IndexFlatL2
dim = 4
index = faiss.IndexFlatL2(dim)

# 创建 3 个文档向量
doc_vectors = np.array([
    [1.0, 0.0, 0.0, 0.0],   # 文档 0
    [0.7, 0.7, 0.0, 0.0],   # 文档 1 (与 query 有部分相似)
    [0.0, 0.0, 0.0, 1.0],   # 文档 2 (完全不同)
], dtype='float32')

# L2 归一化（和 faiss_store.py 中 add_documents 一样）
faiss.normalize_L2(doc_vectors)
index.add(doc_vectors)

# 查询向量（和文档 0 完全相同）
query = np.array([[1.0, 0.0, 0.0, 0.0]], dtype='float32')
faiss.normalize_L2(query)

# 搜索
distances, indices = index.search(query, 3)

print("=" * 60)
print("FAISS IndexFlatL2 距离测试")
print("=" * 60)
print(f"query (归一化后): {query}")
print(f"doc_vectors (归一化后): {doc_vectors}")
print()
print(f"FAISS distances: {distances[0]}")
print(f"FAISS indices:   {indices[0]}")
print()

for dist, idx in zip(distances[0], indices[0]):
    # 公式: cosine = 1 - dist / 2 （假设 dist 是 L2²）
    cosine_v1 = 1.0 - float(dist) / 2.0
    
    # 手动计算余弦相似度
    a = query[0]
    b = doc_vectors[idx]
    manual_cosine = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    # 手动计算 L2 距离
    l2_dist = float(np.linalg.norm(a - b))
    l2_sq = l2_dist ** 2
    
    print(f"idx={idx}: raw_dist={dist:.6f}, "
          f"manual_L2={l2_dist:.6f}, manual_L2²={l2_sq:.6f}, "
          f"cosine_from_formula={cosine_v1:.6f}, manual_cosine={manual_cosine:.6f}")

print()
print("结论：如果 raw_dist == manual_L2²，则 FAISS 返回的是 L2²")
print("      如果 raw_dist == manual_L2，则 FAISS 返回的是 L2 距离本身")
