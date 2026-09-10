"""brain.py — 大脑：评论 → 回复文本 + 情绪标签（人设从语料库 corpus.json 读，不写死）

跑法（单测）：venv/Scripts/python.exe brain.py "这个多少钱？"
"""
import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

import config
import kb

load_dotenv()

# 前端能消费的情绪标签（「平静」做默认）
EMOTIONS = ["开心", "惊讶", "卖萌", "平静"]


def _context_text(contexts):
    lines = ["【知识库】"]
    for c in contexts:
        lines.append(f"问：{c['q']}\n答：{c['a']}")
    return "\n".join(lines)


def _parse(raw):
    """从回复末尾拆出情绪标签；拆不出就默认平静。"""
    text = (raw or "").strip()
    for tag in EMOTIONS:
        if text.endswith(tag):
            body = text[: -len(tag)].strip()
            return (body or tag), tag
    return text or "这个我得问一下主播哦～", "平静"


def ask_deepseek_with_emotion(comment, contexts, persona):
    """脑：检索结果当上下文，调 DeepSeek 生成 (回复, 情绪)。没 key 时降级用标准答案。"""
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        a = contexts[0]["a"] if contexts else "这个我得问一下主播哦～"
        return a, "平静"
    # trust_env=False：不读系统代理（10809 常死）。DeepSeek 国内直连，走代理反而超时。
    client = OpenAI(
        api_key=key,
        base_url="https://api.deepseek.com",
        http_client=httpx.Client(trust_env=False, timeout=30.0),
    )
    sys = persona + "\n\n" + _context_text(contexts)
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": comment},
        ],
        temperature=0.7,
    )
    return _parse(resp.choices[0].message.content)


def answer(comment, corpus):
    """同步接口：评论 → (回复文本, 情绪)。RAG + LLM 都是阻塞调用，放线程池跑。"""
    contexts = kb.retrieve(comment, corpus["id"], top_k=3)
    return ask_deepseek_with_emotion(comment, contexts, corpus.get("persona", ""))


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "这个多少钱？"
    corpus = config.get_active_corpus()
    reply, emo = answer(q, corpus)
    print(f"[语料] {corpus['name']}\n[评论] {q}\n[回复] {reply}\n[情绪] {emo}")
