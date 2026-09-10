"""orchestrator.py — 编排层（单进程，一条命令起全部）

同进程提供：
  1) 前端静态服务（http://localhost:8000/ 控制台，/stage.html 直播页）
  2) REST API：列模特/语料、查当前、切换（/api/config /api/active /api/switch）
  3) WebSocket（/ws）：推「字幕 + 情绪 + mp3 二进制」给页面；切换时推 reload
  4) asyncio 主循环：弹幕 → 决策 → 大脑 → 嘴 → 推页面

跑法（在 anime-digital-human 目录下）：
  venv/Scripts/python.exe orchestrator.py --web          # ★ 网页输入（推荐 demo）
  venv/Scripts/python.exe orchestrator.py                # 交互：终端回车 + 网页输入
  venv/Scripts/python.exe orchestrator.py --demo         # 自动：定时引导 + 脚本弹幕
  venv/Scripts/python.exe orchestrator.py --port 9000    # 换端口
"""
import argparse
import asyncio
import json
import mimetypes
import os
import queue
import threading
import time

from aiohttp import web

import brain
import config
import interaction_policy as ip
import kb
import tts

BASE = os.path.dirname(os.path.abspath(__file__))
LIVE2D_DIR = os.path.join(BASE, "live2d_page")

# 正确 MIME（Windows 下 mimetypes 认不全）
MIME = {
    ".moc3": "application/octet-stream",
    ".model3.json": "application/json",
    ".motion3.json": "application/json",
    ".physics3.json": "application/json",
    ".pose3.json": "application/json",
    ".cdi3.json": "application/json",
    ".userdata3.json": "application/json",
    ".json": "application/json",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".png": "image/png",
    ".html": "text/html; charset=utf-8",
}

clients = set()  # 所有已连接的浏览器 / OBS 浏览器源


def guess_mime(path):
    ext = os.path.splitext(path)[1].lower()
    return MIME.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


# ---- WebSocket ----
async def ws_handler(request):
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    clients.add(ws)
    print(f"[ws] 客户端接入，当前 {len(clients)} 个")
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get("type") == "comment":
                        content = (data.get("content") or "").strip()
                        if content:
                            policy = request.app.get("policy")
                            if policy:
                                policy.push(ip.Event("comment", "网页", content))
                                print(f"[网页弹幕] {content}")
                    elif data.get("type") == "done":
                        print("  [ws] 页面播完一段")
                except Exception:
                    pass
            elif msg.type == web.WSMsgType.ERROR:
                break
    finally:
        clients.discard(ws)
        print(f"[ws] 客户端断开，剩 {len(clients)} 个")
    return ws


async def _send_all(payload_text, payload_bytes=None):
    """推给所有客户端：先 text(元信息) 再 binary(mp3)，页面按序配对。"""
    dead = []
    for ws in list(clients):
        try:
            await ws.send_str(payload_text)
            if payload_bytes is not None:
                await ws.send_bytes(payload_bytes)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


async def broadcast(subtitle, emotion, audio: bytes):
    meta = json.dumps(
        {"type": "speak", "subtitle": subtitle, "emotion": emotion},
        ensure_ascii=False,
    )
    await _send_all(meta, audio)


async def broadcast_reload():
    """切换模特/语料后，让直播页重新拉 /api/active 换装。"""
    await _send_all(json.dumps({"type": "reload"}, ensure_ascii=False))


# ---- REST API ----
async def api_config(request):
    """GET /api/config —— 全部模特、语料、当前组合。"""
    return web.json_response({
        "models": config.list_models(),
        "corpora": [{"id": c["id"], "name": c["name"]} for c in config.list_corpora()],
        "active": config.get_active(),
    })


async def api_active(request):
    """GET /api/active —— 当前模特 + 语料的完整配置（直播页渲染用）。"""
    return web.json_response({
        "model": config.get_active_model(),
        "corpus": config.get_active_corpus(),
    })


async def api_switch(request):
    """POST /api/switch {model_id?, corpus_id?} —— 切换并广播 reload。"""
    try:
        data = await request.json()
    except Exception:
        data = {}
    model_id = data.get("model_id")
    corpus_id = data.get("corpus_id")

    ctx = request.app["ctx"]
    policy = ctx["policy"]
    old_corpus = ctx.get("corpus_id")

    active = config.switch(model_id, corpus_id)

    # 语料变了 → 重建该语料的向量索引 + 更新开场白
    if active["corpus_id"] != old_corpus:
        corpus = config.get_corpus(active["corpus_id"])
        if corpus:
            try:
                await asyncio.to_thread(kb.build_index, corpus)
            except Exception as e:
                print(f"[切语料] 建索引失败：{e}")
            policy.set_loop_lines(corpus.get("loop_lines"))
        ctx["corpus_id"] = active["corpus_id"]

    await broadcast_reload()
    print(f"[切换] 模特={active['model_id']} 语料={active['corpus_id']}")
    return web.json_response(active)


# ---- 静态文件 ----
async def static_handler(request):
    rel = request.match_info.get("path", "admin.html")
    if rel in ("", "/"):
        rel = "admin.html"
    fp = os.path.normpath(os.path.join(LIVE2D_DIR, rel))
    # 防目录穿越
    if not fp.startswith(LIVE2D_DIR) or not os.path.isfile(fp):
        raise web.HTTPNotFound()
    return web.FileResponse(fp, headers={"Content-Type": guess_mime(fp)})


def build_app():
    app = web.Application()
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/api/config", api_config)
    app.router.add_get("/api/active", api_active)
    app.router.add_post("/api/switch", api_switch)
    app.router.add_get("/{path:.*}", static_handler)
    return app


# ---- 弹幕源（本地 mock，同一 poll() 接口，将来换 blivedm） ----
class StdinSource:
    def __init__(self):
        self.q = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        while True:
            try:
                line = input("输入弹幕（回车出，Ctrl+C 退出）：")
            except (EOFError, KeyboardInterrupt):
                return
            line = line.strip()
            if line:
                self.q.put(line)

    def poll(self):
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None


class FileSource:
    def __init__(self, path, interval=6.0):
        self.lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip()]
        self.i = 0
        self.interval = interval
        self.next_at = 0.0

    def poll(self):
        if self.i >= len(self.lines):
            return None
        now = time.time()
        if now < self.next_at:
            return None
        self.next_at = now + self.interval
        line = self.lines[self.i]
        self.i += 1
        return line


class DemoSource:
    SCRIPT = [
        "这个多少钱？",
        "是正品吗？",
        "什么时候发货？",
        "隐藏款概率是多少？",
        "主播叫什么名字呀？",
    ]

    def __init__(self, interval=8.0):
        self.i = 0
        self.interval = interval
        self.next_at = time.time() + 3.0

    def poll(self):
        now = time.time()
        if now < self.next_at:
            return None
        self.next_at = now + self.interval
        line = self.SCRIPT[self.i % len(self.SCRIPT)]
        self.i += 1
        return line


class WebSource:
    def poll(self):
        return None


def make_source(args):
    if args.web:
        return WebSource()
    if args.demo:
        return DemoSource()
    if args.file:
        return FileSource(args.file)
    return StdinSource()


# ---- 主循环 ----
async def say(ev):
    """一条评论走完 脑→嘴→推页面。大脑/嘴出错就降级，绝不能崩掉整个服务器。"""
    t0 = time.time()
    corpus = config.get_active_corpus()
    try:
        reply, emo = await asyncio.to_thread(brain.answer, ev.content, corpus)
    except Exception as e:
        print(f"[脑] 出错降级：{e}")
        reply, emo = "这个我得问一下主播哦～", "平静"
    try:
        audio = await tts.synth(reply, config.get_active_model())
    except Exception as e:
        print(f"[嘴] 出错降级（跳过）：{e}")
        return
    await broadcast(reply, emo, audio)
    print(f"[答] {reply}  [{emo}]  端到端{time.time() - t0:.1f}s")


async def run(args):
    corpus = config.get_active_corpus()
    policy = ip.InteractionPolicy(
        cooldown=args.cooldown,
        loop_interval=args.loop_interval,
        loop_lines=corpus.get("loop_lines") if corpus else None,
    )
    source = make_source(args)

    app = build_app()
    app["policy"] = policy
    app["ctx"] = {"policy": policy, "corpus_id": corpus["id"] if corpus else None}
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", args.port)
    await site.start()
    # 启动即建索引（顺带预热 BGE），否则首答会卡、且空库时检索不到
    if corpus:
        await asyncio.to_thread(kb.build_index, corpus)
    print(f"控制台   ： http://localhost:{args.port}/")
    print(f"直播页   ： http://localhost:{args.port}/stage.html")
    print(f"WebSocket： ws://localhost:{args.port}/ws")
    print(f"当前组合 ： 模特「{config.get_active_model()['name']}」+ 语料「{corpus['name']}」")
    if args.web:
        src_name = "网页输入（浏览器里直接打字，回车发送）"
    elif args.demo:
        src_name = "自动演示"
    elif args.file:
        src_name = "文件 " + args.file
    else:
        src_name = "交互输入（终端回车，也可同时网页输入）"
    print(f"弹幕源   ： {src_name}")
    print("Ctrl+C 退出。\n")

    try:
        while True:
            comment = source.poll()
            if comment:
                policy.push(ip.Event("comment", "观众", comment))

            line = policy.loop_line()
            if line:
                try:
                    audio = await tts.synth(line, config.get_active_model())
                    await broadcast(line, "平静", audio)
                    print(f"[引导] {line}")
                except Exception as e:
                    print(f"[引导] 出错：{e}")

            ev = policy.next_event()
            if ev:
                await say(ev)

            await asyncio.sleep(0.2)
    finally:
        await runner.cleanup()


def main():
    ap = argparse.ArgumentParser(description="动漫数字人编排层")
    ap.add_argument("--demo", action="store_true", help="自动演示：定时引导 + 脚本弹幕")
    ap.add_argument("--web", action="store_true", help="纯网页输入：浏览器里打字，数字人回答（推荐 demo）")
    ap.add_argument("--file", help="从文件逐行读弹幕")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--cooldown", type=float, default=4.0, help="两次开口最小间隔（秒）")
    ap.add_argument("--loop-interval", type=float, default=30.0, help="主动引导间隔（秒）")
    args = ap.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()
