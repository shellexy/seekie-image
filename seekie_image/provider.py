"""和 OpenAI 兼容接口打交道的部分：拼地址、发请求、从各种形状的响应里把图片取出来。

中转站（new-api / one-api 一类）的行为不完全一致，这里兼容的差异有：
- 图片以 b64_json 返回，或以 url 返回；
- 绘图模型挂在 /images/* 上，或挂在 /chat/completions 上；
- 普通 JSON 响应，或 SSE 流式响应（在额外参数里加 "stream": true 时）。
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import threading
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ENDPOINT_SUFFIXES = ("/images/generations", "/images/edits", "/chat/completions", "/models")
_NO_PROXY_SEP = re.compile(r"[,\s]+")
MIME_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}
GATEWAY_TIMEOUT_HINT = (
    "中转站在图片生成完之前就断开了。可以降低质量或复杂度；"
    "如果中转站支持流式，在服务商的「额外参数」里加上 "
    '{"stream": true, "partial_images": 2} 能让连接保持活跃。'
)


class ProviderError(Exception):
    """可以直接展示给用户看的错误。status 是接口返回的 HTTP 状态码（没有就是 None）。"""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class Cancelled(Exception):
    pass


def clean_no_proxy() -> None:
    """把 NO_PROXY 里带方括号的 IPv6 项改成 httpx 认得的写法。

    httpx 0.28 解析 no_proxy 模式时会直接拒绝 ``[::1]``（InvalidURL），
    而带方括号恰好是 NO_PROXY 里写 IPv6 的常见写法。这里只动方括号：
    ``[::1]`` -> ``::1``，``[2001:db8::1]:8080`` -> ``2001:db8::1``。
    程序发请求时靠的就是这个环境变量，所以在模块加载时顺手做一次。
    """
    for name in ("NO_PROXY", "no_proxy"):
        value = os.environ.get(name)
        if not value or "[" not in value:
            continue
        items = []
        for item in _NO_PROXY_SEP.split(value):
            item = item.strip()
            if not item:
                continue
            if item.startswith("["):
                host = item[1:].split("]", 1)[0]
                if host:
                    items.append(host)
            else:
                items.append(item)
        os.environ[name] = ",".join(items)


clean_no_proxy()


def normalize_base_url(url: str) -> str:
    """把用户填的地址整理成 API 根地址。

    https://host                      -> https://host/v1
    https://host/v1/                  -> https://host/v1
    https://host/v1/images/generations-> https://host/v1
    https://host/api/v3               -> 原样（已带版本号）
    https://host/custom#              -> https://host/custom（以 # 结尾表示不要自动补 /v1）
    """
    url = (url or "").strip()
    if not url:
        raise ProviderError("还没有填接口地址")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    if url.endswith("#"):
        return url[:-1].rstrip("/")
    url = url.rstrip("/")
    for suffix in ENDPOINT_SUFFIXES:
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    if not re.search(r"/v\d+[a-z0-9]*(/|$)", urlsplit(url).path):
        url += "/v1"
    return url


def sniff_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    head = data[:512].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head):
        return "image/svg+xml"
    return None


def _decode_b64(text: str) -> bytes:
    if text.startswith("data:"):
        text = text.split(",", 1)[-1]
    text = re.sub(r"\s+", "", text)
    try:
        return base64.b64decode(text + "=" * (-len(text) % 4))
    except ValueError as exc:
        raise ProviderError("接口返回的图片数据不是合法的 base64") from exc


def _error_text(status: int, body: bytes) -> str:
    message = ""
    try:
        payload = json.loads(body)
    except ValueError:
        message = body.decode("utf-8", "replace").strip()
        if message.lstrip().lower().startswith(("<!doctype", "<html")):
            message = ""  # 网关的 HTML 错误页没有阅读价值
    else:
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("msg") or error.get("code") or "")
        else:
            message = str(error)
    message = message[:500]
    if status < 400:  # 有的中转站用 200 状态码返回错误体
        return message or "接口返回了一个没有说明的错误"
    if status in (504, 524) or (status == 502 and not message):
        return f"网关超时（HTTP {status}）。{GATEWAY_TIMEOUT_HINT}"
    if status == 401:
        return f"API Key 无效或已过期（HTTP 401）{'：' + message if message else ''}"
    if status == 404 and not message:
        return "接口地址不存在（HTTP 404）。检查接口地址，或在设置里换一种接口类型。"
    return f"HTTP {status}：{message}" if message else f"接口返回了 HTTP {status}"


def _raise_transport(exc: Exception, timeout: float) -> None:
    if isinstance(exc, httpx.TimeoutException):
        raise ProviderError(f"等了 {int(timeout)} 秒没有等到结果。可以在服务商设置里调大超时时间。") from exc
    if isinstance(exc, httpx.ConnectError):
        raise ProviderError(f"连不上接口：{exc}".rstrip("：")) from exc
    if isinstance(exc, httpx.RemoteProtocolError):
        raise ProviderError(f"连接被对方中断。{GATEWAY_TIMEOUT_HINT}") from exc
    raise ProviderError(f"网络错误：{exc}") from exc


def _headers(provider: dict) -> dict:
    headers = {"Accept": "application/json, text/event-stream"}
    if provider.get("api_key"):
        headers["Authorization"] = f"Bearer {provider['api_key']}"
    return headers


def list_models(provider: dict) -> list[str]:
    """GET /models，用来在设置里测试连通性并挑模型。"""
    url = normalize_base_url(provider.get("base_url", "")) + "/models"
    try:
        response = httpx.get(url, headers=_headers(provider), timeout=20, follow_redirects=True)
    except httpx.HTTPError as exc:
        _raise_transport(exc, 20)
    if response.status_code >= 400:
        raise ProviderError(_error_text(response.status_code, response.content))
    try:
        items = response.json().get("data", [])
        return sorted({str(item["id"]) for item in items if item.get("id")})
    except (ValueError, AttributeError, TypeError, KeyError) as exc:
        raise ProviderError("接口通了，但返回的不是模型列表") from exc


class Job:
    """一次生成请求。在调用 run() 的线程里起一个事件循环，cancel() 可以从别的线程调用。

    用 asyncio 而不是同步客户端，是因为等待响应头的那一两分钟里，同步的 socket 读取
    没有可靠的办法从另一个线程打断；取消任务则能立刻断开连接。
    """

    def __init__(self, provider: dict):
        self.provider = provider
        self.timeout = float(provider.get("timeout") or 300)
        self.base = normalize_base_url(provider.get("base_url", ""))
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._on_partial = None

    def cancel(self) -> None:
        self._cancelled.set()
        with self._lock:
            loop, task = self._loop, self._task
        if loop and task:
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass  # 事件循环已经结束，说明请求刚好跑完

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def run(self, *, model: str, prompt: str, size: str, quality: str, complexity: str,
            refs: list[Path], n: int = 1, image_format: dict | None = None,
            frame_count: int = 0, frame_duration_ms: int = 0, on_partial=None) -> list[tuple[bytes, str]]:
        """返回 [(图片字节, mime), ...]。失败抛 ProviderError，被取消抛 Cancelled。

        on_partial(slot, data, mime)：流式生成时每收到一张中间预览图就调用一次，
        slot 是它属于第几张图（从 0 开始）。在事件循环所在的线程里调用，不要在里面做慢的事。
        """
        self._on_partial = on_partial
        try:
            images = asyncio.run(self._main(
                model, prompt, size, quality, complexity, refs, max(1, int(n)),
                image_format, frame_count, frame_duration_ms,
            ))
        except asyncio.CancelledError:
            raise Cancelled() from None
        except httpx.HTTPError as exc:
            _raise_transport(exc, self.timeout)
        if self.cancelled:
            raise Cancelled()
        return images

    async def _main(self, model, prompt, size, quality, complexity, refs, n,
                    image_format=None, frame_count=0, frame_duration_ms=0) -> list[tuple[bytes, str]]:
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._task = asyncio.current_task()
        if self.cancelled:  # 在事件循环建好之前就被取消了
            raise asyncio.CancelledError()
        async with httpx.AsyncClient(
            headers=_headers(self.provider),
            timeout=httpx.Timeout(self.timeout, connect=20),
            follow_redirects=True,
        ) as client:
            if self.provider.get("api_mode") == "chat":
                sources = await self._chat_sources(client, model, prompt, refs, n)
            else:
                payload = await self._post_images(
                    client, model, prompt, size, quality, complexity, refs, n,
                    image_format, frame_count, frame_duration_ms,
                )
                sources = _sources_from_images(payload)
        return [await self._load(source) for source in sources]

    async def _chat_sources(self, client, model, prompt, refs, n) -> list[str]:
        """对话接口没有「一次几张」的参数，要几张就同时发几次请求。"""
        async def once() -> list[str]:
            return _sources_from_chat(await self._post_chat(client, model, prompt, refs))

        if n == 1:
            return await once()
        results = await asyncio.gather(*(once() for _ in range(n)), return_exceptions=True)
        sources = [source for result in results if isinstance(result, list) for source in result]
        failures = [result for result in results if isinstance(result, BaseException)]
        if not sources:
            raise failures[0]
        # 有几次成功就先把成功的交出去，已经花了钱的图不该因为别的请求失败而丢掉
        return sources

    # ---- 请求 ----

    async def _post_images(self, client, model, prompt, size, quality, complexity, refs, n,
                           image_format=None, frame_count=0, frame_duration_ms=0) -> dict:
        body: dict = {"model": model, "prompt": prompt, "n": n}
        if size and size != "auto":
            body["size"] = size
        if quality and quality != "auto":
            body["quality"] = quality
        if complexity and complexity != "default":
            body["complexity"] = complexity
        if image_format:
            body["output_format"] = image_format["output"]
            # 透明格式明确要透明背景；普通格式明确要实心背景，免得模型自己发挥
            body["background"] = "transparent" if image_format.get("transparent") else "opaque"
            if image_format.get("frames"):
                body["frame_count"] = max(1, int(frame_count or 1))
                body["frame_duration_ms"] = max(1, int(frame_duration_ms or 1))
        streaming = bool(self.provider.get("stream"))
        if streaming:
            body.update({"stream": True, "partial_images": 2})
        body.update(self.provider.get("extra") or {})

        try:
            return await self._submit_images(client, body, refs)
        except ProviderError as exc:
            # 不认识流式参数的中转站会直接拒绝请求（这时还没出图、不计费），去掉这两个参数再试一次
            rejected = exc.status in (400, 422) and re.search(r"stream|partial_images", str(exc), re.I)
            if not (streaming and rejected):
                raise
            body.pop("stream", None)
            body.pop("partial_images", None)
            return await self._submit_images(client, body, refs)

    async def _submit_images(self, client, body: dict, refs) -> dict:
        if not refs:
            return await self._send(client, self.base + "/images/generations", json=body)

        # 带参考图走 /images/edits，multipart 表单里的值只能是字符串
        fields = {
            key: value if isinstance(value, str) else json.dumps(value)
            for key, value in body.items()
        }
        field_name = "image" if len(refs) == 1 else "image[]"
        files = []
        for path in refs:
            data = path.read_bytes()
            files.append((field_name, (path.name, data, sniff_mime(data) or "image/png")))
        return await self._send(client, self.base + "/images/edits", data=fields, files=files)

    async def _post_chat(self, client, model, prompt, refs) -> dict:
        content: list | str = prompt
        if refs:
            content = [{"type": "text", "text": prompt}]
            for path in refs:
                data = path.read_bytes()
                mime = sniff_mime(data) or "image/png"
                uri = f"data:{mime};base64,{base64.b64encode(data).decode()}"
                content.append({"type": "image_url", "image_url": {"url": uri}})
        body = {"model": model, "messages": [{"role": "user", "content": content}], "stream": False}
        body.update(self.provider.get("extra") or {})
        return await self._send(client, self.base + "/chat/completions", json=body)

    async def _send(self, client: httpx.AsyncClient, url: str, **kwargs) -> dict:
        async with client.stream("POST", url, **kwargs) as response:
            if response.status_code >= 400:
                raise ProviderError(_error_text(response.status_code, await response.aread()), response.status_code)
            if "text/event-stream" in response.headers.get("content-type", ""):
                return await self._read_sse(response)
            raw = await response.aread()
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise ProviderError("接口返回的不是 JSON。检查接口地址是否正确。") from exc
        if isinstance(payload, dict) and payload.get("error"):
            raise ProviderError(_error_text(200, raw))
        return payload

    async def _read_sse(self, response: httpx.Response) -> dict:
        """把流式事件收拢成和非流式一样的形状。

        images 接口：取不是 partial 的、带 b64_json 的事件。
        chat 接口：把各个 delta.content 拼起来。
        """
        final_images: list[dict] = []
        text_parts: list[str] = []
        extra_images: list = []
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("error"):
                raise ProviderError(_error_text(200, data.encode()))
            if "partial" in str(event.get("type", "")):
                self._take_partial(event)
                continue
            if event.get("b64_json") or event.get("url"):
                final_images.append(event)
            for item in event.get("data") or []:
                if isinstance(item, dict) and (item.get("b64_json") or item.get("url")):
                    final_images.append(item)
            for choice in event.get("choices") or []:
                delta = choice.get("delta") or choice.get("message") or {}
                if isinstance(delta.get("content"), str):
                    text_parts.append(delta["content"])
                extra_images.extend(delta.get("images") or [])
        if final_images:
            return {"data": final_images}
        if text_parts or extra_images:
            message = {"content": "".join(text_parts), "images": extra_images}
            return {"choices": [{"message": message}]}
        raise ProviderError("流式响应结束了，但里面没有最终图片。")

    def _take_partial(self, event: dict) -> None:
        """中间预览图。Images API 用 b64_json，Responses 风格的事件用 partial_image_b64。"""
        if not self._on_partial:
            return
        encoded = event.get("b64_json") or event.get("partial_image_b64")
        if not isinstance(encoded, str) or not encoded:
            return
        # 一次请求多张图时，文档没写中间图怎么区分属于哪一张；有 output_index 就用，没有就都算第一张
        slot = event.get("output_index")
        slot = slot if isinstance(slot, int) and 0 <= slot < 16 else 0
        try:
            data = _decode_b64(encoded)
            mime = sniff_mime(data)
            if mime:
                self._on_partial(slot, data, mime)
        except Exception:  # 预览图坏了不影响最终结果
            pass

    async def _load(self, source: str) -> tuple[bytes, str]:
        if source.startswith(("http://", "https://")):
            # 图片链接通常指向 CDN，所以另起一个不带 API Key 的客户端去下载
            try:
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as downloader:
                    response = await downloader.get(source)
            except httpx.HTTPError as exc:
                raise ProviderError(f"图片生成了，但下载失败：{exc}") from exc
            if response.status_code >= 400:
                raise ProviderError(f"图片生成了，但下载失败（HTTP {response.status_code}）")
            data = response.content
        else:
            data = _decode_b64(source)
        mime = sniff_mime(data)
        if not mime:
            raise ProviderError("接口返回的数据不是可识别的图片格式")
        return data, mime


# ---- 从响应里找图片 ----

def _sources_from_images(payload: dict) -> list[str]:
    items = payload.get("data") if isinstance(payload, dict) else None
    sources = []
    for item in items or []:
        if isinstance(item, dict):
            source = item.get("b64_json") or item.get("url")
            if source:
                sources.append(source)
    if not sources:
        raise ProviderError("接口返回成功，但里面没有图片。可能需要在设置里换成 Chat Completions 接口类型。")
    return sources


_DATA_URI = re.compile(r"data:image/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+", re.I)
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)")
_BARE_IMAGE = re.compile(r"https?://[^\s)\"'<>]+\.(?:png|jpe?g|webp|gif)(?:\?[^\s)\"'<>]*)?", re.I)


def _sources_from_chat(payload: dict) -> list[str]:
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("对话接口返回的结构无法识别") from exc

    sources: list[str] = []
    text = ""

    def take_part(part) -> None:
        if not isinstance(part, dict):
            return
        image_url = part.get("image_url")
        url = image_url.get("url") if isinstance(image_url, dict) else image_url
        if url:
            sources.append(url)

    for part in message.get("images") or []:
        take_part(part)
    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            take_part(part)
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                text += part["text"]
    elif isinstance(content, str):
        text = content

    if not sources:
        sources = [match.group(0) for match in _DATA_URI.finditer(text)]
    if not sources:
        sources = _MD_IMAGE.findall(text)
    if not sources:
        sources = [match.group(0) for match in _BARE_IMAGE.finditer(text)]
    if not sources:
        excerpt = text.strip().replace("\n", " ")[:200]
        raise ProviderError(f"模型没有返回图片{'，它的回复是：' + excerpt if excerpt else '。'}")
    return sources
