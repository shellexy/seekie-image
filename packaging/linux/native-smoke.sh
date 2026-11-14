#!/usr/bin/env bash
# 在 Xvfb 里起一个原生窗口，确认 PyInstaller 包里的 GTK / WebKit 能加载，
# 再启动第二个实例，确认它会唤醒第一个窗口后退出。
#
# 用法：bash packaging/linux/native-smoke.sh <可执行文件>
set -euo pipefail

app="${1:?用法: native-smoke.sh <可执行文件>}"
data="$(mktemp -d)"
runtime="$data/runtime"
mkdir -m 700 "$runtime"
port="$((20000 + RANDOM % 20000))"
log="$data/app.log"
pid=""

cleanup() {
    if [ -n "$pid" ]; then
        kill -TERM -- "-$pid" 2>/dev/null || true
        for _ in $(seq 1 30); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.1
        done
        kill -KILL -- "-$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi
    rm -rf "$data"
}
trap cleanup EXIT

setsid xvfb-run -a -s "-screen 0 1280x800x24" env \
    GDK_BACKEND=x11 WAYLAND_DISPLAY= \
    XDG_RUNTIME_DIR="$runtime" GSETTINGS_BACKEND=memory \
    WEBKIT_DISABLE_COMPOSITING_MODE=1 LIBGL_ALWAYS_SOFTWARE=1 NO_AT_BRIDGE=1 \
    "$app" --port "$port" --data-dir "$data" >"$log" 2>&1 &
pid=$!

for _ in $(seq 1 200); do
    if curl -fsS --noproxy '*' "http://127.0.0.1:$port/" >/dev/null 2>&1; then
        break
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "原生窗口启动失败：" >&2
        cat "$log" >&2
        exit 1
    fi
    sleep 0.1
done

kill -0 "$pid"
curl -fsS --noproxy '*' -o /dev/null "http://127.0.0.1:$port/" || {
    echo "原生窗口的 HTTP 服务没有响应" >&2
    cat "$log" >&2
    exit 1
}

# 第二个实例：同一份数据目录，应当唤醒已有窗口后退出
"$app" --no-open --data-dir "$data" >>"$log" 2>&1 || {
    echo "第二个实例退出码不是 0：" >&2
    cat "$log" >&2
    exit 1
}
grep -q '已切换到现有窗口' "$log" || {
    echo "第二个实例没有走唤醒窗口的路径：" >&2
    cat "$log" >&2
    exit 1
}
kill -0 "$pid"
curl -fsS --noproxy '*' -o /dev/null "http://127.0.0.1:$port/"
echo "native smoke ok：$app"
