"""本机 HTTP 服务：给界面提供页面、图片和一组 JSON 接口。

只监听 127.0.0.1（除非启动时另行指定）。/api/* 需要带上页面里注入的令牌，
并且检查 Host 头，这样别的网页没法借浏览器来调用这些接口。
"""

from __future__ import annotations

import hmac
import json
import logging
import re
import secrets
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

from .core import MAX_UPLOAD, ApiError, Core
from .provider import ProviderError, normalize_base_url

log = logging.getLogger("seekie_image")
# 不用 mimetypes 模块：Windows 上它会读注册表，.js 可能被认成 text/plain，页面就起不来了
CONTENT_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}
WEB_DIR = Path(__file__).parent / "web"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
# script-src 里的 'unsafe-eval' 是给 pywebview 留的：它自己往页面里注入脚本时用的是 eval。
PAGE_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-eval'; img-src 'self' data: blob:; "
    "style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'"
)
# 生成的图片（尤其是 SVG）被直接打开时不允许执行任何东西
FILE_CSP = "default-src 'none'; style-src 'unsafe-inline'; sandbox"


class Request:
    def __init__(self, match: re.Match, body: bytes, query: dict):
        self.args = match.groups()
        self.body = body
        self.query = query

    def json(self) -> dict:
        try:
            data = json.loads(self.body or b"{}")
        except ValueError as exc:
            raise ApiError(400, "请求体不是合法的 JSON") from exc
        if not isinstance(data, dict):
            raise ApiError(400, "请求体需要是一个 JSON 对象")
        return data


def _resolve(core: Core, req: Request) -> dict:
    data = req.json()
    try:
        base = normalize_base_url(str(data.get("base_url") or ""))
    except ProviderError:
        return {"url": None}
    path = "/chat/completions" if data.get("api_mode") == "chat" else "/images/generations"
    return {"url": base + path}


ROUTES = [
    ("GET", r"/api/state", lambda c, r: c.state()),
    ("PUT", r"/api/providers", lambda c, r: c.save_providers(r.json().get("providers"))),
    ("POST", r"/api/providers/probe", lambda c, r: c.probe(r.json())),
    ("POST", r"/api/providers/resolve", _resolve),
    ("GET", r"/api/sessions", lambda c, r: c.store.sessions()),
    ("PATCH", r"/api/sessions/(\w+)", lambda c, r: c.rename_session(r.args[0], r.json().get("title"))),
    ("DELETE", r"/api/sessions/(\w+)", lambda c, r: c.delete_session(r.args[0])),
    ("GET", r"/api/sessions/(\w+)/messages", lambda c, r: c.messages(r.args[0])),
    ("GET", r"/api/messages", lambda c, r: c.messages_by_id(r.query.get("ids", [""])[0].split(","))),
    ("POST", r"/api/messages/(\w+)/cancel", lambda c, r: c.cancel(r.args[0])),
    ("DELETE", r"/api/messages/(\w+)", lambda c, r: c.delete_message(r.args[0])),
    ("POST", r"/api/generate", lambda c, r: c.generate(r.json())),
    ("POST", r"/api/upload", lambda c, r: c.upload(r.body)),
    ("POST", r"/api/clipboard", lambda c, r: c.paste(images=r.json().get("images") is not False)),
    ("POST", r"/api/files/([\w.-]+)/copy", lambda c, r: c.copy_image(r.args[0])),
    ("POST", r"/api/activate", lambda c, r: c.activate()),
    ("POST", r"/api/window-title", lambda c, r: c.set_window_title(r.json().get("title"))),
    ("POST", r"/api/devtools", lambda c, r: c.toggle_devtools()),
    ("POST", r"/api/files/([\w.-]+)/export", lambda c, r: c.export(r.args[0])),
    ("POST", r"/api/files/([\w.-]+)/reveal", lambda c, r: c.reveal(r.args[0])),
]
ROUTES = [(method, re.compile(pattern), handler) for method, pattern, handler in ROUTES]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "seekie-image"

    def log_message(self, fmt, *args):  # 默认会把每个请求打到 stderr，太吵
        log.debug("%s %s", self.address_string(), fmt % args)

    def do_GET(self):
        self._handle()

    do_POST = do_PUT = do_PATCH = do_DELETE = do_GET

    # ---- 响应 ----

    def _send(self, status: int, body: bytes, content_type: str, headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self._send(status, body, "application/json; charset=utf-8", {"Cache-Control": "no-store"})

    # ---- 分发 ----

    def _host_allowed(self) -> bool:
        if self.server.server_address[0] not in LOOPBACK:
            return True  # 用户显式要求监听其它地址时不做限制
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in LOOPBACK

    def _handle(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_UPLOAD + 1024:
                self.close_connection = True
                raise ApiError(413, "请求体太大")
            body = self.rfile.read(length) if length else b""
            if not self._host_allowed():
                raise ApiError(403, "不接受这个来源的请求")

            url = urlsplit(self.path)
            path = unquote(url.path)
            if path.startswith("/api/"):
                self._api(path, body, parse_qs(url.query))
            elif self.command == "GET":
                self._static(path, parse_qs(url.query))
            else:
                raise ApiError(405, "不支持的请求方法")
        except ApiError as exc:
            self._json(exc.status, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:
            log.error("处理 %s %s 时出错\n%s", self.command, self.path, traceback.format_exc())
            self._json(500, {"error": f"程序内部出错：{exc!r}"})

    def _api(self, path: str, body: bytes, query: dict):
        token = self.headers.get("X-Token") or ""
        if not hmac.compare_digest(token.encode(), self.server.token.encode()):
            raise ApiError(403, "页面已过期，请重新打开")
        for method, pattern, handler in ROUTES:
            match = pattern.fullmatch(path)
            if match and method == self.command:
                return self._json(200, handler(self.server.core, Request(match, body, query)))
        raise ApiError(404, "没有这个接口")

    def _static(self, path: str, query: dict):
        if path in ("/", "/index.html"):
            html = (WEB_DIR / "index.html").read_text("utf-8").replace("__TOKEN__", self.server.token)
            return self._send(200, html.encode(), "text/html; charset=utf-8", {
                "Cache-Control": "no-store",
                "Content-Security-Policy": PAGE_CSP,
            })
        if path.startswith("/static/"):
            name = path[len("/static/"):]
            target = WEB_DIR / name
            if not re.fullmatch(r"[\w.-]+", name) or not target.is_file():
                raise ApiError(404, "找不到页面资源")
            ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
            return self._send(200, target.read_bytes(), ctype, {"Cache-Control": "no-cache"})
        if path.startswith("/previews/"):
            # 和 /files/ 一样不验令牌（<img> 带不了请求头），靠记录 id 猜不到来保护
            mid, _, slot = path[len("/previews/"):].partition("/")
            data, mime = self.server.core.preview(mid, slot)
            return self._send(200, data, mime, {
                "Cache-Control": "private, max-age=300",
                "Content-Security-Policy": FILE_CSP,
            })
        if path.startswith("/files/"):
            target = self.server.core.file_path(path[len("/files/"):])
            headers = {
                "Cache-Control": "private, max-age=31536000, immutable",
                "Content-Security-Policy": FILE_CSP,
            }
            download = query.get("download", [""])[0]
            if download:
                headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(download)}"
            ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
            return self._send(200, target.read_bytes(), ctype, headers)
        raise ApiError(404, "找不到这个页面")


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, host: str, port: int, core: Core):
        super().__init__((host, port), Handler)
        self.core = core
        self.token = secrets.token_urlsafe(24)

    @property
    def url(self) -> str:
        host, port = self.server_address[:2]
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"
        return f"http://{host}:{port}/"
