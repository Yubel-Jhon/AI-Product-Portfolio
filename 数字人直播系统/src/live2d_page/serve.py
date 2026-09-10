"""live2d_page 本地静态服务器（零依赖，标准库）

给浏览器 + OBS 浏览器源用。补充 Live2D 相关扩展名的正确 MIME，
避免浏览器把 .moc3 / .model3.json 当错误类型拒载。

跑法：
  cd live2d_page
  ..\venv\Scripts\python.exe serve.py          # 默认 8000
  ..\venv\Scripts\python.exe serve.py 9000     # 指定端口
然后浏览器打开 http://localhost:8000/ ，或 OBS 浏览器源填这个 URL。
"""
import http.server
import mimetypes
import os
import sys

# Live2D 关键扩展名 → 正确 MIME（部分系统里 mimetypes 认不全）
EXTRA_MIME = {
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
for ext, mime in EXTRA_MIME.items():
    mimetypes.add_type(mime, ext)


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **EXTRA_MIME}

    def end_headers(self):
        # 允许跨域，方便将来 WebSocket / 其它端口页面调用
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, fmt, *args):
        # 精简日志，刷屏时看得清
        sys.stderr.write("  %s\n" % (fmt % args))


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"live2d_page 静态服务已启动： http://localhost:{port}/")
    print("浏览器打开上面的地址看嘴型；OBS 浏览器源也填这个地址。Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
