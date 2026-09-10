"""glue.py — 串起完整链路，常驻运行（连续出片）

把之前手动的一串步骤（本地出音频 → 传远端 → 跑 SadTalker → 取回视频）
变成一条命令、一个常驻循环：来一条评论就自动出一个小视频，不退出。

评论源（三选一）：
  venv/Scripts/python.exe glue.py                      # 交互：敲一条回车出一条
  venv/Scripts/python.exe glue.py --file comments.txt  # 逐行读（离线批量测试）
  venv/Scripts/python.exe glue.py --http 8000          # 开 HTTP，供弹幕 SDK POST

前置（只做一次）：
  1) venv/Scripts/python.exe kb.py build                  # 建向量索引
  2) venv/Scripts/python.exe -m pip install paramiko      # 让 venv 也能连 AutoDL（否则只能系统 python 连）
  3) 远端已放好 face.png，且实例开机（remote.py / upload.py 里的地址能连）

产物：output/<序号>.mp3 + output/<序号>.mp4
"""
import argparse
import asyncio
import json
import os
import queue
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import kb
from main import ask_deepseek, speak

import remote   # paramiko 跑远端命令（连 AutoDL）
import upload   # SFTP 上传（put 已有）

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "output")
REMOTE_DIR = "/root/autodl-tmp"
FACE = f"{REMOTE_DIR}/face.png"
SADTALKER = f"{REMOTE_DIR}/SadTalker"
PY = "/root/miniconda3/bin/python"


def download(remote_path, local_path):
    """SFTP 下载（upload.py 只有 put，这里补 get）。"""
    import paramiko
    t = paramiko.Transport((upload.HOST, upload.PORT))
    t.connect(username=upload.USER, password=upload.PWD)
    sftp = paramiko.SFTPClient.from_transport(t)
    sftp.get(remote_path, local_path)
    sftp.close()
    t.close()


def lip_sync(audio_local, idx):
    """上传音频 → 远端跑 SadTalker → 下载视频，返回本地 mp4 路径。"""
    audio_remote = f"{REMOTE_DIR}/glue_{idx}.mp3"
    upload.put(audio_local, audio_remote)

    cmd = (
        f"mkdir -p {REMOTE_DIR}/results_glue && cd {SADTALKER} && {PY} inference.py "
        f"--driven_audio {audio_remote} --source_image {FACE} "
        f"--result_dir {REMOTE_DIR}/results_glue --still --preprocess full --size 256"
    )
    o, e = remote.run(cmd, timeout=900)
    if e.strip():
        print("  ! SadTalker stderr:", e[-300:].strip())

    latest = remote.run(f"ls -t {REMOTE_DIR}/results_glue/*.mp4 | head -1")[0].strip()
    if not latest:
        raise RuntimeError("远端没产出 mp4，检查 batch.log / results_glue 目录")
    video_remote = f"{REMOTE_DIR}/glue_{idx}.mp4"
    remote.run(f"cp {latest} {video_remote}")
    mp4_local = os.path.join(OUT_DIR, f"{idx:04d}.mp4")
    download(video_remote, mp4_local)
    print(f"  → 视频已下载 {mp4_local}")
    return mp4_local


def handle(comment, idx):
    contexts = kb.retrieve(comment, top_k=3)
    answer = ask_deepseek(comment, contexts)
    audio_local = os.path.join(OUT_DIR, f"{idx:04d}.mp3")
    asyncio.run(speak(answer, audio_local))
    print(f"[{idx}] 评论: {comment}")
    print(f"    回答: {answer}")
    print(f"    语音: {audio_local}")
    lip_sync(audio_local, idx)
    print(f"--- [{idx}] 完成 ---")


# ---- 评论源：三种实现，都提供 .get() 拿一条评论 ----
class StdinSource:
    def get(self):
        return input("输入评论（Ctrl+C 退出）：").strip()


class FileSource:
    def __init__(self, path):
        self.lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip()]

    def get(self):
        if not self.lines:
            raise StopIteration
        return self.lines.pop(0)


class HttpSource:
    """极简 HTTP 服务：POST body 里 JSON {"text":"评论"} 即可入队。"""

    def __init__(self, port):
        self.q = queue.Queue()

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(n).decode("utf-8", errors="replace")
                try:
                    text = json.loads(body).get("text", "").strip()
                except Exception:
                    text = body.strip()
                if text:
                    self.q.put(text)
                    self.send_response(200)
                else:
                    self.send_response(400)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("0.0.0.0", port), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def get(self):
        return self.q.get().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--http", type=int)
    args = ap.parse_args()

    if args.http:
        src = HttpSource(args.http)
        print(f'HTTP 评论源已开，POST http://localhost:{args.http}/  body: {{"text":"这个多少钱？"}}')
    elif args.file:
        src = FileSource(args.file)
    else:
        src = StdinSource()

    os.makedirs(OUT_DIR, exist_ok=True)
    idx = 0
    while True:
        try:
            comment = src.get()
        except (StopIteration, KeyboardInterrupt):
            print("评论源结束，退出。")
            break
        if not comment:
            continue
        try:
            handle(comment, idx)
            idx += 1
        except Exception as e:
            print(f"!! 处理失败 [{idx}] {comment}: {e}")
            continue


if __name__ == "__main__":
    main()
