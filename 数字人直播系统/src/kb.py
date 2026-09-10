"""记忆（RAG）：按语料库隔离的向量检索。每个语料一个 chroma collection，防串库。

改完某语料的 faq.json 后，跑一次 build_index(该语料) 重建索引即可。
"""
import json
import os

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # 国内镜像，国外网络可删

import chromadb
from sentence_transformers import SentenceTransformer

import config

BASE = os.path.dirname(os.path.abspath(__file__))
# 打包后 src/ 只读，chroma_db 写到 config.DATA_DIR（默认 BASE，打包时 ADH_DATA_DIR 指向用户数据目录）
DB_PATH = os.path.join(config.DATA_DIR, "chroma_db")
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"  # 中文向量，CPU 可跑

_model_cache = None
_client_cache = None


def get_model():
    global _model_cache
    if _model_cache is None:
        _model_cache = SentenceTransformer(EMBED_MODEL)
    return _model_cache


def _client():
    global _client_cache
    if _client_cache is None:
        # embedding_function=None：向量我们自己用 BGE 算，禁用 ChromaDB 默认 onnx 模型（否则联网下载超时）
        _client_cache = chromadb.PersistentClient(path=DB_PATH)
    return _client_cache


def get_collection(corpus_id):
    return _client().get_or_create_collection(f"faq_{corpus_id}", embedding_function=None)


def build_index(corpus):
    """把某语料的 faq.json 全部问答用 BGE 向量化后入库（清空重建该语料的 collection）。"""
    faq_path = config.corpus_faq_path(corpus["id"])
    with open(faq_path, encoding="utf-8") as f:
        faqs = json.load(f)
    texts = [f"问：{x['q']}\n答：{x['a']}" for x in faqs]
    embeddings = get_model().encode(texts, normalize_embeddings=True).tolist()

    coll = get_collection(corpus["id"])
    ids = coll.get()["ids"]
    if ids:
        coll.delete(ids=ids)
    coll.add(
        documents=texts,
        embeddings=embeddings,
        ids=[str(i) for i in range(len(faqs))],
        metadatas=[{"q": x["q"], "a": x["a"]} for x in faqs],
    )
    print(f"[kb] 已入库语料「{corpus['name']}」{len(faqs)} 条 FAQ")


def retrieve(comment, corpus_id, top_k=3):
    """在指定语料里检索最相关 FAQ，返回 [{'q':..,'a':..,'score':..}]，score 越小越相似。"""
    emb = get_model().encode([comment], normalize_embeddings=True).tolist()
    res = get_collection(corpus_id).query(query_embeddings=emb, n_results=top_k)
    metas = res["metadatas"][0]
    dists = res["distances"][0]
    return [{"q": m["q"], "a": m["a"], "score": round(d, 4)} for m, d in zip(metas, dists)]


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        for c in config.list_corpora():
            build_index(c)
    else:
        q = sys.argv[1] if len(sys.argv) > 1 else "多少钱"
        cid = config.get_active_ids()[1]
        for r in retrieve(q, cid):
            print(f"[{r['score']}] {r['q']} → {r['a']}")
