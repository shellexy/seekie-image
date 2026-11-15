#!/usr/bin/env python3
"""一个假的 OpenAI 兼容绘图接口，用来不花钱地试界面和排查问题。

    python mock_api.py --port 8787 --delay 3

然后在 seekie-image 的设置里添加服务商：接口地址 http://127.0.0.1:8787，API Key 随便填。
它画的是按提示词随机配色的山和太阳，不是真的模型输出。

触发特殊情况：
    提示词包含 [error]   -> 返回 400 和一段错误信息
    提示词包含 [timeout] -> 返回 524（模拟中转站网关超时）
    API Key 填 bad       -> 返回 401
    API Key 填 nostream  -> 请求体里带 stream 就返回 400（模仿不支持流式的中转站）
    请求体带 "n": 3         -> 一次返回 3 张（最多 10 张）
    请求体带 "stream": true -> 以 SSE 返回：先是越来越清楚的 partial_image，再是 completed；
                               "partial_images" 控制每张图有几张中间图（0–3，不写按 2）
    请求体带 "response_format": "url" -> 返回图片链接而不是 b64_json
"""

from __future__ import annotations

import argparse
import base64
import email
import hashlib
import io
import json
import math
import random
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, ImageDraw, ImageFilter


def say(text: str) -> None:
    print(f"[mock] {text}", flush=True)


MODELS = ["gpt-image-2.6-sunburst", "gpt-image-2.6-flare", "gpt-image-2", "gpt-4o", "text-embedding-3-small"]
PALETTES = [
    ((84, 160, 232), (232, 244, 255), (255, 214, 120), [(120, 170, 220), (70, 120, 190), (38, 70, 130)]),
    ((255, 170, 120), (255, 232, 200), (255, 244, 220), [(214, 120, 130), (150, 80, 120), (80, 50, 96)]),
    ((150, 200, 180), (240, 250, 240), (255, 250, 230), [(110, 170, 130), (60, 120, 100), (30, 76, 76)]),
    ((190, 170, 240), (246, 238, 255), (255, 226, 240), [(150, 130, 210), (100, 90, 170), (56, 52, 110)]),
]


def paint(prompt: str, size: str, refs: list[bytes], note: str = "") -> bytes:
    try:
        width, height = (int(v) for v in size.split("x"))
    except ValueError:
        width, height = 1536, 1024
    rng = random.Random(hashlib.sha256(f"{prompt}{time.time()}".encode()).digest())
    top, bottom, sun, hills = rng.choice(PALETTES)
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / height
        draw.line([(0, y), (width, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    radius = min(width, height) * rng.uniform(0.08, 0.13)
    cx, cy = width * rng.uniform(0.2, 0.8), height * rng.uniform(0.22, 0.42)
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=sun)
    for index, color in enumerate(hills):
        base = height * (0.58 + index * 0.13)
        amp = height * rng.uniform(0.04, 0.09)
        freq, phase = rng.uniform(1.2, 2.6), rng.uniform(0, math.tau)
        points = [(0, height)]
        for x in range(0, width + 16, 16):
            wave = math.sin(x / width * math.tau * freq + phase) + 0.4 * math.sin(x / width * math.tau * freq * 2.3)
            points.append((x, base + amp * wave))
        points.append((width, height))
        draw.polygon(points, fill=color)
    # 把收到的参考图贴在左下角，方便确认参考图确实传上来了
    x = int(width * 0.03)
    for ref in refs[:4]:
        try:
            thumb = Image.open(io.BytesIO(ref)).convert("RGB")
        except Exception:
            continue
        thumb.thumbnail((width // 6, height // 6))
        y = height - thumb.height - int(height * 0.04)
        draw.rectangle([x - 4, y - 4, x + thumb.width + 3, y + thumb.height + 3], fill="white")
        image.paste(thumb, (x, y))
        x += thumb.width + 16
    draw.text((12, 10), f"mock {width}x{height} {note}".strip(), fill=(255, 255, 255))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def rough(final: bytes, index: int, total: int) -> bytes:
    """把成品图弄糊，假装是生成到一半的样子；index 越大越清楚。"""
    image = Image.open(io.BytesIO(final))
    small = image.resize((max(64, image.width // 3), max(64, image.height // 3)))
    blur = (14, 7, 3)[max(0, 3 - total) + index] if total else 0
    small = small.filter(ImageFilter.GaussianBlur(blur))
    out = io.BytesIO()
    small.save(out, "PNG")
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    delay = 2.0
    hosted: dict[str, bytes] = {}  # 以 url 形式返回的图片
    last_params: dict = {}  # 最近一次绘图请求的参数，测试里用来看发出去的是什么

    def log_message(self, fmt, *args):
        say(fmt % args)

    def _json(self, status: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str, code: str = "invalid_request_error"):
        self._json(status, {"error": {"message": message, "type": code, "code": code}})

    def _authorized(self) -> bool:
        key = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        if key == "bad":
            self._error(401, "Incorrect API key provided.", "invalid_api_key")
            return False
        return True

    def do_GET(self):
        if self.path.startswith("/hosted/"):
            image = self.hosted.get(self.path.rsplit("/", 1)[-1])
            if image is None:
                return self._error(404, "Image expired")
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(image)))
            self.end_headers()
            self.wfile.write(image)
            return
        if not self._authorized():
            return
        if self.path.rstrip("/").endswith("/models"):
            return self._json(200, {"object": "list", "data": [{"id": m, "object": "model"} for m in MODELS]})
        self._error(404, f"Unknown path {self.path}")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not self._authorized():
            return
        path = self.path.rstrip("/")
        refs: list[bytes] = []
        if path.endswith("/images/generations"):
            params = json.loads(body)
        elif path.endswith("/images/edits"):
            params, refs = self._multipart(body)
            if not refs:
                return self._error(400, "Missing required parameter: 'image'.")
        elif path.endswith("/chat/completions"):
            return self._chat(json.loads(body))
        else:
            return self._error(404, f"Unknown path {self.path}")

        Handler.last_params = params
        prompt = str(params.get("prompt") or "")
        shown = {key: value for key, value in params.items() if key != "prompt"}
        say(f"参数 {shown}，参考图 {len(refs)} 张")
        if "[error]" in prompt:
            return self._error(400, "Your request was rejected by the safety system.", "moderation_blocked")
        if "[timeout]" in prompt:
            time.sleep(self.delay)
            return self._error(524, "")
        size = str(params.get("size") or "1536x1024")
        size = "1536x1024" if size == "auto" else size
        note = " ".join(str(params[k]) for k in ("quality", "complexity") if params.get(k))

        key = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        if key == "nostream" and "stream" in params:
            return self._error(400, "Unknown parameter: 'stream'.")
        try:
            count = min(max(int(params.get("n") or 1), 1), 10)
        except (TypeError, ValueError):
            return self._error(400, "Invalid value for 'n'.")
        if str(params.get("stream")).lower() == "true":
            try:
                partials = min(max(int(params.get("partial_images", 2)), 0), 3)
            except (TypeError, ValueError):
                partials = 2
            return self._stream(prompt, size, refs, note, count, partials)
        time.sleep(self.delay)
        items = []
        for _ in range(count):
            image = paint(prompt, size, refs, note)
            if params.get("response_format") == "url":
                name = hashlib.sha256(image).hexdigest()[:16]
                self.hosted[name] = image
                items.append({"url": f"http://{self.headers.get('Host')}/hosted/{name}"})
            else:
                items.append({"b64_json": base64.b64encode(image).decode()})
        self._json(200, {"created": int(time.time()), "data": items})

    def _multipart(self, body: bytes) -> tuple[dict, list[bytes]]:
        header = f"Content-Type: {self.headers.get('Content-Type')}\r\n\r\n".encode()
        params, refs = {}, []
        for part in email.message_from_bytes(header + body).walk():
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            payload = part.get_payload(decode=True)
            if name in ("image", "image[]"):
                refs.append(payload)
            else:
                params[name] = payload.decode("utf-8", "replace")
        return params, refs

    def _stream(self, prompt: str, size: str, refs: list[bytes], note: str, count: int, partials: int):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def emit(event: dict):
            self.wfile.write(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode())
            self.wfile.flush()

        finals = [paint(prompt, size, refs, (note + " stream").strip()) for _ in range(count)]
        steps = partials + 1
        for index in range(partials):
            time.sleep(self.delay / steps)
            for slot, final in enumerate(finals):
                event = {
                    "type": "image_generation.partial_image",
                    "partial_image_index": index,
                    "b64_json": base64.b64encode(rough(final, index, partials)).decode(),
                }
                if count > 1:
                    # 官方文档没写一次多张时中间图怎么区分；这里借用 Responses 事件里的 output_index
                    event["output_index"] = slot
                emit(event)
        time.sleep(self.delay / steps)
        for final in finals:
            emit({"type": "image_generation.completed", "b64_json": base64.b64encode(final).decode()})

    def _chat(self, params: dict):
        content = params["messages"][-1]["content"]
        refs, prompt = [], content
        if isinstance(content, list):
            prompt = " ".join(p.get("text", "") for p in content if p.get("type") == "text")
            for part in content:
                if part.get("type") == "image_url":
                    refs.append(base64.b64decode(part["image_url"]["url"].split(",", 1)[1]))
        time.sleep(self.delay)
        if "[error]" in prompt:
            text = "抱歉，我无法生成这张图片。"
        else:
            image = base64.b64encode(paint(prompt, "1024x1024", refs, "chat")).decode()
            text = f"好的，图片在这里：\n\n![image](data:image/png;base64,{image})"
        self._json(200, {"choices": [{"index": 0, "message": {"role": "assistant", "content": text}}]})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--delay", type=float, default=2.0, help="每次生成假装花多少秒")
    args = parser.parse_args()
    Handler.delay = args.delay
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    say(f"假接口在 http://{args.host}:{args.port}/v1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
