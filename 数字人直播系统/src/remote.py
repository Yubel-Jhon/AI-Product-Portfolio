"""通过 paramiko 连 AutoDL 实例跑命令（非交互，密码登录）。

用法：
    python remote.py "nvidia-smi"          # 跑一条命令
    python remote.py "cd /root && ls"      # 复合命令用引号包住

敏感信息从环境变量读取；没有环境变量时，会尝试读同目录的 .env（不依赖 dotenv）。
需要在 .env 里配：AUTODL_HOST / AUTODL_PORT / AUTODL_USER / AUTODL_PWD
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


def run(cmd, timeout=600):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30)
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode(errors="replace")
    e = err.read().decode(errors="replace")
    c.close()
    return o, e


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python remote.py '<命令>'")
        sys.exit(1)
    o, e = run(sys.argv[1])
    print(o)
    if e.strip():
        print("--- STDERR ---")
        print(e)
