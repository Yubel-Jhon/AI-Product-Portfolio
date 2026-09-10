"""tts.py — 嘴：文本 → mp3 字节（edge-tts，内存里直接出，不落盘）

音色/语速/音调优先读模特配置（model.json 的 voice/pitch/rate），没有就回退 .env，再回退默认。

跑法（单测）：venv/Scripts/python.exe tts.py "大家好" out.mp3
"""
import asyncio
import os

import edge_tts
from dotenv import load_dotenv

load_dotenv()


def _param(model, key, env_key, default):
    """模特配置 → 环境变量 → 默认值。"""
    if model and model.get(key):
        return model[key]
    return os.getenv(env_key, default)


async def synth(text, model=None) -> bytes:
    """文本 → mp3 字节流。edge-tts stream 里 type=='audio' 的 data 就是 mp3 分片。"""
    voice = _param(model, "voice", "TTS_VOICE", "zh-CN-XiaoxiaoNeural")
    rate = _param(model, "rate", "TTS_RATE", "+8%")
    pitch = _param(model, "pitch", "TTS_PITCH", "+25Hz")
    chunks = []
    async for ch in edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).stream():
        if ch["type"] == "audio":
            chunks.append(ch["data"])
    return b"".join(chunks)


if __name__ == "__main__":
    import sys
    text = sys.argv[1] if len(sys.argv) > 1 else "大家好呀"
    out = sys.argv[2] if len(sys.argv) > 2 else "out.mp3"
    data = asyncio.run(synth(text))
    with open(out, "wb") as f:
        f.write(data)
    print(f"已合成 {len(data)} 字节 → {out}")
