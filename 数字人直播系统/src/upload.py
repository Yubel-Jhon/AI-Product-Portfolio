"""SFTP 上传文件到 AutoDL 实例。

用法：
    python upload.py "本地路径=远端路径" ["本地=远端" ...]
例：
    python upload.py "C:/x/正面1.png=/root/autodl-tmp/face.png"

敏感信息从环境变量读取；没有环境变量时，会尝试读同目录的 .env（见 remote.py）。
"""
import os
import sys

import paramiko


def _load_env():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.isfile(path):
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k, v.strip())


_load_env()

HOST = os.getenv("AUTODL_HOST", "connect.nmb2.seetacloud.com")
PORT = int(os.getenv("AUTODL_PORT", "38427"))
USER = os.getenv("AUTODL_USER", "root")
PWD = os.getenv("AUTODL_PWD", "")


def put(local, remote):
    t = paramiko.Transport((HOST, PORT))
    t.connect(username=USER, password=PWD)
    sftp = paramiko.SFTPClient.from_transport(t)
    sftp.put(local, remote)
    sftp.close()
    t.close()
    print(f"OK  {local}  ->  {remote}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python upload.py \"本地=远端\" ...")
        sys.exit(1)
    for pair in sys.argv[1:]:
        lo, re = pair.split("=", 1)
        put(lo, re)
