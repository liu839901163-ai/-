#!/bin/bash
set -eu
cd "$(dirname "$0")"
printf '\n出海工作室 · Mac 本地版\n\n'
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' >/dev/null 2>&1; then
  printf '需要先安装 Python 3.12 或更高版本。\n浏览器将打开 Python 官方 Mac 下载页。安装完成后，重新双击此文件。\n'
  open 'https://www.python.org/downloads/macos/'
  read -r -p '按回车关闭此窗口…' answer
  exit 1
fi
# Restrict this launcher to the user's own computer, irrespective of inherited settings.
export HOST=127.0.0.1
export STUDIO_DATA_DIR="$PWD/.data"
export PORT
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
unset STUDIO_ACCESS_PASSWORD
python3 app.py &
studio_pid=$!
cleanup() { kill "$studio_pid" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 0' INT TERM HUP
if python3 - <<'PY'
import json, os, time, urllib.request
url = 'http://127.0.0.1:' + os.environ['PORT'] + '/api/health'
for attempt in range(30):
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            if json.load(response).get('status') == 'ok':
                break
    except (OSError, ValueError):
        pass
    time.sleep(0.2)
else:
    raise SystemExit(1)
PY
then
  open "http://127.0.0.1:$PORT"
  printf '\n工作室已打开。使用期间请保留这个窗口。\n结束时按 Control+C，或关闭此窗口。\n草稿保存在本文件夹的 .data 目录，请勿删除。\n\n'
  wait "$studio_pid"
else
  printf '\n启动失败，请截图这个窗口寻求帮助。\n'
  read -r -p '按回车关闭…' answer
  exit 1
fi
