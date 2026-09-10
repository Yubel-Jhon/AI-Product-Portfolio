"""批量生成 demo 音频：不同评论 → RAG+DeepSeek 回答 → edge-tts 语音。
输出 demo_0.mp3 ~ demo_3.mp3（edge-tts 实际输出 MP3，后缀用 .mp3 更规范）。
"""
import asyncio

import kb
from main import ask_deepseek, speak

COMMENTS = [
    "这个多少钱？",
    "是正品吗？",
    "隐藏款概率是多少？",
    "什么时候发货？",
]


def main():
    for i, c in enumerate(COMMENTS):
        contexts = kb.retrieve(c, top_k=3)
        answer = ask_deepseek(c, contexts)
        out = f"demo_{i}.mp3"
        asyncio.run(speak(answer, out))
        print(f"[{i}] 评论: {c}")
        print(f"    回答: {answer}")
        print(f"    已合成 -> {out}")


if __name__ == "__main__":
    main()
