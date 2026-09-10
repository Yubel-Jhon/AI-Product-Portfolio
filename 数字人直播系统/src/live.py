"""live.py — 阶段1：本地实时应答闭环（先不接 Live2D、不接 B站）

评论 → RAG → DeepSeek → edge-tts → 立即播放

目标：验证「来一条评论，几秒内自动回答出声」的实时管线，
     并测出端到端延迟（脑 vs 嘴各占多少）。
后面阶段再往上叠：Live2D 嘴型 → OBS → B站弹幕。

跑法（首次先装播放库）：
  venv/Scripts/python.exe -m pip install pygame
  venv/Scripts/python.exe live.py                 # 交互：敲一条回车出一条
  venv/Scripts/python.exe live.py --file comments.txt
"""
import argparse
import asyncio
import os
import time

import kb
from main import ask_deepseek, speak

BASE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(BASE, "_live_tts.mp3")


def play_audio(path):
    """播放 mp3，阻塞到播完。"""
    import pygame
    pygame.mixer.init()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)


def handle(comment):
    t0 = time.time()
    contexts = kb.retrieve(comment, top_k=3)
    answer = ask_deepseek(comment, contexts)
    t1 = time.time()
    asyncio.run(speak(answer, TMP))
    t2 = time.time()
    print(f"[评论] {comment}")
    print(f"[回答] {answer}")
    print(f"  脑 {t1 - t0:.1f}s | 嘴(合成) {t2 - t1:.1f}s | 累计 {t2 - t0:.1f}s")
    play_audio(TMP)  # 出声（阻塞到播完再接下一条）


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    args = ap.parse_args()

    if args.file:
        lines = [l.strip() for l in open(args.file, encoding="utf-8") if l.strip()]
        for c in lines:
            handle(c)
    else:
        while True:
            c = input("输入评论（Ctrl+C 退出）：").strip()
            if c:
                handle(c)


if __name__ == "__main__":
    main()
