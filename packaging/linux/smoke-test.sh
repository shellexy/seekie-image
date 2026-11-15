#!/usr/bin/env bash
# 冒烟测试：用浏览器模式起一个实例，确认页面和 /api/state 正常，
# 再启动第二个实例，确认它直接退出且不影响第一个实例。
#
# 用法：bash packaging/linux/smoke-test.sh <可执行文件>
set -euo pipefail

app="${1:?用法: smoke-test.sh <可执行文件>}"
data="$(mktemp -d)"
port="$((20000 + RANDOM % 20000))"
log="$data/app.log"

cleanup() {
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
    done
    kill -KILL "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    rm -rf "$data"
}
pid=""
trap cleanup EXIT

"$app" --browser --no-open --port "$port" --data-dir "$data" >"$log" 2>&1 &
pid=$!

page="$data/page.html"
for _ in $(seq 1 150); do
    if curl -fsS --noproxy '*' "http://127.0.0.1:$port/" >"$page" 2>/dev/null; then
        break
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "应用启动失败：" >&2
        cat "$log" >&2
        exit 1
    fi
    sleep 0.1
done

grep -q '<title>Seekie Image</title>' "$page" || {
    echo "页面标题不是 Seekie Image" >&2
    exit 1
}
token="$(sed -n 's/.*app-token" content="\([^"]*\)".*/\1/p' "$page")"
[ -n "$token" ] || {
    echo "页面里没有接口令牌" >&2
    exit 1
}
curl -fsS --noproxy '*' -H "X-Token: $token" "http://127.0.0.1:$port/api/state" | grep -q '"version"' || {
    echo "/api/state 不可用" >&2
    exit 1
}

# 同一份数据目录的第二个实例应当马上退出
"$app" --browser --no-open --data-dir "$data" >>"$log" 2>&1 || {
    echo "第二个实例退出码不是 0：" >&2
    cat "$log" >&2
    exit 1
}
kill -0 "$pid" || {
    echo "第二个实例把第一个实例挤掉了" >&2
    exit 1
}
curl -fsS --noproxy '*' -o /dev/null "http://127.0.0.1:$port/" || {
    echo "第二个实例启动后，第一个实例不再响应" >&2
    exit 1
}
echo "smoke ok：$app"
