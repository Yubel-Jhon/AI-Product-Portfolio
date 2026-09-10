"""动漫数字人 · 音频闭环（脑 + 记忆 + 嘴）
评论 → RAG 检索知识库 → DeepSeek(脑) 回答 → edge-tts(嘴) 合成 → wav

跑法：venv/Scripts/python.exe main.py "这个多少钱？"
依赖：先跑一次 kb.build_index()（即 venv/Scripts/python.exe kb.py build）建好索引。
没配 DEEPSEEK_API_KEY 时，会自动降级为「直接用检索到的标准答案」（FAQ-only 版，也能出声）。
"""
import asyncio
import os
import sys

import edge_tts
from dotenv import load_dotenv
from openai import OpenAI

import kb

load_dotenv()

VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")

SYSTEM_PROMPT = """你是直播间里的动漫数字人主播，正对着观众回答问题。
要求：
1. 口语化、亲切，1~3 句话，可带"宝子们""～"这类语气词。
2. 优先根据下面【知识库】里的标准答案回答；命中的话照抄不改写。
3. 知识库里没有的，就说"这个我得问一下主播哦～"，绝不编造价格、库存、材质、售后等事实。
"""


def _context_text(contexts):
    lines = ["【知识库】"]
    for c in contexts:
        lines.append(f"问：{c['q']}\n答：{c['a']}")
    return "\n".join(lines)


def ask_deepseek(comment, contexts):
    """脑：把检索结果当上下文，调 DeepSeek 生成回答。没 key 时降级用标准答案。"""
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        return contexts[0]["a"] if contexts else "这个我得问一下主播哦～"
    client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    sys = SYSTEM_PROMPT + "\n\n" + _context_text(contexts)
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": comment},
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


async def speak(text, out):
    await edge_tts.Communicate(text, VOICE).save(out)


def main():
    comment = sys.argv[1] if len(sys.argv) > 1 else input("输入一条观众评论（回车用默认）：").strip()
    comment = comment or "这个多少钱？"
    contexts = kb.retrieve(comment, top_k=3)
    answer = ask_deepseek(comment, contexts)
    print(f"【评论】{comment}")
    print(f"【答】{answer}")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "answer.wav")
    asyncio.run(speak(answer, out))
    print(f"已合成 → {out}")


if __name__ == "__main__":
    main()
