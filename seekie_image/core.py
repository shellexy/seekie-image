"""应用逻辑：把配置、数据库、图片文件和后台生成任务串起来。"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from . import __version__, clipboard, config as cfg, devtools
from .provider import MIME_EXT, Cancelled, Job, ProviderError, list_models, normalize_base_url, sniff_mime
from .store import Store

log = logging.getLogger("seekie_image")

FILE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,120}$")
SIZE_VALUE = re.compile(r"^(auto|\d{2,5}x\d{2,5})$")
MAX_UPLOAD = 50 * 1024 * 1024
THUMB_EDGE = 480
THUMB_SUFFIX = "_t.webp"
REF_PREFIX = "ref_"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class Core:
    def __init__(self, data_dir: Path, images_dir: Path | None = None):
        self.data_dir = data_dir
        # 生成的图片和同名 .txt 放在 images_dir，这是给用户自己翻看的地方（Linux 上在「图片」目录里）；
        # 缩略图和上传的参考图只有应用自己用，留在数据目录里，不去打扰那个文件夹。
        self.images_dir = images_dir or data_dir / "images"
        self.thumbs_dir = data_dir / "thumbs"
        self.refs_dir = data_dir / "refs"
        for folder in (self.images_dir, self.thumbs_dir, self.refs_dir):
            folder.mkdir(parents=True, exist_ok=True)
        self.config = cfg.Config(data_dir)
        self.store = Store(data_dir / "history.db")
        self.window = None  # pywebview 窗口；浏览器模式下保持 None
        self._jobs: dict[str, Job] = {}
        self._jobs_lock = threading.Lock()
        # 流式生成的中间预览图，只放在内存里：{记录 id: {第几张: (版本号, 图片字节, mime)}}
        self._previews: dict[str, dict[int, tuple[int, bytes, str]]] = {}
        self._previews_lock = threading.Lock()
        self.store.fail_stale_pending("上次退出时这张图还没生成完，请求已中断。")
        self._sweep_stale_uploads()

    def close(self) -> None:
        with self._jobs_lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            job.cancel()
        self.store.close()

    # ---- 状态与配置 ----

    def state(self) -> dict:
        return {
            "version": __version__,
            "native": self.window is not None,
            "config": self.config.data,
            "options": cfg.OPTIONS,
            "defaults": {"models": cfg.DEFAULT_MODELS, "timeout": cfg.DEFAULT_TIMEOUT},
            "sessions": self.store.sessions(),
        }

    def save_providers(self, providers) -> dict:
        if not isinstance(providers, list):
            raise ApiError(400, "配置格式不对")
        try:
            for provider in providers:
                normalize_base_url(str((provider or {}).get("base_url", "")))
            self.config.set_providers(providers)
        except (ValueError, ProviderError) as exc:
            raise ApiError(400, str(exc)) from exc
        return self.config.data

    def probe(self, provider: dict) -> dict:
        try:
            return {"models": list_models(provider)}
        except ProviderError as exc:
            raise ApiError(502, str(exc)) from exc

    # ---- 文件 ----

    def _home_of(self, name: str) -> Path:
        """按文件名决定它该放在哪个目录。"""
        if name.endswith(THUMB_SUFFIX):
            return self.thumbs_dir
        if name.startswith(REF_PREFIX):
            return self.refs_dir
        return self.images_dir

    def _find(self, name: str) -> Path | None:
        home = self._home_of(name)
        # 早先的版本把三类文件都放在 images/ 里，找不到时再去那儿看一眼
        for folder in dict.fromkeys((home, self.images_dir)):
            path = folder / name
            if path.is_file():
                return path
        return None

    def file_path(self, name: str) -> Path:
        if not FILE_NAME.match(name) or ".." in name or not name.lower().endswith(IMAGE_SUFFIXES):
            raise ApiError(404, "文件不存在")
        path = self._find(name)
        if path is None:
            raise ApiError(404, "文件不存在")
        return path

    def _save_image(self, data: bytes, mime: str, prefix: str = "") -> dict:
        if prefix:
            stem = prefix + uuid.uuid4().hex
        else:
            # 生成的图片会出现在用户的图片文件夹里，文件名带上时间方便翻找；后面几位随机字符防重名
            stem = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        name = stem + MIME_EXT[mime]
        (self._home_of(name) / name).write_bytes(data)
        item = {"file": name, "thumb": name, "w": None, "h": None}
        if mime == "image/svg+xml":
            return item
        try:
            from PIL import Image

            with Image.open(io.BytesIO(data)) as image:
                item["w"], item["h"] = image.size
                image.seek(0)
                thumb = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
                thumb.thumbnail((THUMB_EDGE, THUMB_EDGE))
                thumb.save(self.thumbs_dir / f"{stem}{THUMB_SUFFIX}", "WEBP", quality=82)
            item["thumb"] = f"{stem}{THUMB_SUFFIX}"
        except Exception:  # 缩略图只是锦上添花，失败就直接用原图
            log.warning("生成缩略图失败：%s", name, exc_info=True)
        return item

    def upload(self, data: bytes) -> dict:
        if not data:
            raise ApiError(400, "没有收到图片")
        if len(data) > MAX_UPLOAD:
            raise ApiError(413, "参考图不能超过 50 MB")
        mime = sniff_mime(data)
        if mime not in ("image/png", "image/jpeg", "image/webp"):
            raise ApiError(400, "参考图只支持 PNG、JPEG 和 WebP")
        item = self._save_image(data, mime, prefix=REF_PREFIX)
        return {"file": item["file"], "thumb": item["thumb"]}

    def paste(self, images: bool = True) -> dict:
        """读系统剪贴板：图片直接存成参考图，文字原样交回页面。只在桌面窗口模式下可用。

        images=False 时只要文字（给接口设置里的那些输入框用）。
        """
        if self.window is None:
            raise ApiError(400, "浏览器模式下由页面自己读剪贴板")
        try:
            text, blobs = clipboard.read()
        except Exception as exc:
            log.warning("读剪贴板失败", exc_info=True)
            raise ApiError(500, f"读不到剪贴板：{exc}") from exc
        if not images:
            return {"text": text, "images": []}
        images = []
        for data in blobs:
            mime = sniff_mime(data)
            if mime in ("image/png", "image/jpeg", "image/webp") and len(data) <= MAX_UPLOAD:
                item = self._save_image(data, mime, prefix=REF_PREFIX)
                images.append({"file": item["file"], "thumb": item["thumb"]})
        return {"text": None if images else text, "images": images}

    def copy_image(self, name: str) -> dict:
        """把一张图片放进系统剪贴板。只在桌面窗口模式下可用。"""
        if self.window is None:
            raise ApiError(400, "浏览器模式下由页面自己写剪贴板")
        data = self.file_path(name).read_bytes()
        try:
            clipboard.write_image(data)
        except Exception as exc:
            log.warning("复制图片失败", exc_info=True)
            raise ApiError(500, f"复制图片失败：{exc}") from exc
        return {"ok": True}

    def toggle_devtools(self) -> dict:
        """打开或关闭内核的开发者工具。只在桌面窗口模式下可用。"""
        if self.window is None:
            raise ApiError(400, "浏览器模式下请用浏览器自己的开发者工具")
        try:
            devtools.toggle(self.window)
        except Exception as exc:
            log.warning("打开开发者工具失败", exc_info=True)
            raise ApiError(500, f"打不开开发者工具：{exc}") from exc
        return {"ok": True}

    def _remove_unreferenced(self, names: set[str]) -> None:
        for name in names - self.store.referenced_files():
            try:
                path = self._find(name)
                if path is not None:
                    path.unlink(missing_ok=True)
                if self._home_of(name) == self.images_dir:
                    # 图片旁边的说明文件一起删；即使图片本身已经被用户拿走了也要删
                    (self.images_dir / name).with_suffix(".txt").unlink(missing_ok=True)
            except OSError:
                log.warning("删除文件失败：%s", name, exc_info=True)

    def _sweep_stale_uploads(self) -> None:
        """清掉上传后没有用上的参考图（只动 ref_ 开头、超过一天的文件）。"""
        cutoff = time.time() - 86400
        stale = {
            path.name
            for folder in (self.refs_dir, self.thumbs_dir)
            for path in folder.glob(f"{REF_PREFIX}*")
            if path.stat().st_mtime < cutoff
        }
        if stale:
            self._remove_unreferenced(stale)

    def _write_note(self, image: dict, message: dict, provider: dict, index: int = 0, total: int = 1) -> None:
        """在图片旁边写一个同名 .txt，记下这张图是怎么来的。"""
        params = message["params"]

        def shown(group: str, key: str, unset: str) -> str:
            value = params[key]
            return (cfg.option_label(group, value) or value) if value == unset else value

        lines = ["提示词：", message["prompt"], ""]
        lines.append(f"模型：{params['model']}")
        lines.append(f"服务商：{params['provider_name']}")
        style = cfg.style_prompt(params["style"])
        if style:
            lines.append(f"风格：{cfg.option_label('styles', params['style'])}（在提示词后追加了「画面风格：{style}」）")
        else:
            lines.append("风格：不指定")
        lines.append(f"比例：{shown('sizes', 'size', 'auto')}")
        lines.append(f"质量：{shown('qualities', 'quality', 'auto')}")
        lines.append(f"复杂度：{shown('complexities', 'complexity', 'default')}")
        asked = params.get("n") or 1
        if asked > 1 or total > 1:
            lines.append(f"数量：请求 {asked} 张，这是返回的 {total} 张里的第 {index + 1} 张")
        extra = provider.get("extra") or {}
        if extra:
            lines.append(f"额外参数：{json.dumps(extra, ensure_ascii=False)}")
        if message["refs"]:
            lines.append(f"参考图：{len(message['refs'])} 张")
        if image.get("w") and image.get("h"):
            lines.append(f"图片尺寸：{image['w']}×{image['h']}")
        lines.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            (self.images_dir / image["file"]).with_suffix(".txt").write_text("\n".join(lines) + "\n", "utf-8")
        except OSError:  # 说明文件写不了不该让这次生成算失败
            log.warning("写说明文件失败：%s", image["file"], exc_info=True)

    def export(self, name: str) -> dict:
        """弹出系统的「另存为」对话框。浏览器模式下由前端自己走下载。"""
        path = self.file_path(name)
        if self.window is None:
            return {"native": False}
        import webview

        dialog = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        ext = path.suffix.lstrip(".")
        chosen = self.window.create_file_dialog(
            dialog,
            save_filename=time.strftime(f"image-%Y%m%d-%H%M%S.{ext}"),
            file_types=(f"{ext.upper()} 图片 (*.{ext})", "所有文件 (*.*)"),
        )
        if not chosen:
            return {"native": True, "saved": None}
        target = Path(chosen if isinstance(chosen, str) else chosen[0])
        if not target.suffix:
            target = target.with_suffix(path.suffix)
        try:
            target.write_bytes(path.read_bytes())
        except OSError as exc:
            raise ApiError(500, f"保存失败：{exc}") from exc
        return {"native": True, "saved": str(target)}

    def reveal(self, name: str) -> dict:
        path = self.file_path(name)
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
        except OSError as exc:
            raise ApiError(500, f"打不开文件夹：{path.parent}") from exc
        return {"ok": True}

    # ---- 对话 ----

    def rename_session(self, sid: str, title) -> dict:
        title = str(title or "").strip()[:60]
        if not title:
            raise ApiError(400, "标题不能为空")
        if not self.store.session(sid):
            raise ApiError(404, "这组绘画不存在，可能已经被删除")
        self.store.rename_session(sid, title)
        return self.store.session(sid)

    def delete_session(self, sid: str) -> dict:
        names: set[str] = set()
        for message in self.store.messages(sid):
            self._cancel_job(message["id"])
            names |= _files_of(message)
        self.store.delete_session(sid)
        self._remove_unreferenced(names)
        return {"ok": True}

    def messages(self, sid: str) -> list[dict]:
        return [self._with_previews(message) for message in self.store.messages(sid)]

    def messages_by_id(self, ids: list[str]) -> list[dict]:
        found = (self.store.message(mid) for mid in ids[:100])
        return [self._with_previews(message) for message in found if message]

    # ---- 中间预览图 ----

    def _with_previews(self, message: dict) -> dict:
        """给还在生成的记录带上目前有哪些预览图；v 每换一张图加一，前端据此决定要不要重新加载。"""
        previews = []
        if message["status"] == "pending":
            with self._previews_lock:
                slots = self._previews.get(message["id"]) or {}
                previews = [{"slot": slot, "v": slots[slot][0]} for slot in sorted(slots)]
        return {**message, "previews": previews}

    def _set_preview(self, mid: str, slot: int, data: bytes, mime: str) -> None:
        with self._previews_lock:
            slots = self._previews.setdefault(mid, {})
            slots[slot] = (slots[slot][0] + 1 if slot in slots else 1, data, mime)

    def preview(self, mid: str, slot: str) -> tuple[bytes, str]:
        with self._previews_lock:
            found = (self._previews.get(mid) or {}).get(int(slot)) if slot.isdigit() else None
        if not found:
            raise ApiError(404, "预览图已经不在了")
        return found[1], found[2]

    def delete_message(self, mid: str) -> dict:
        message = self.store.message(mid)
        if message:
            self._cancel_job(mid)
            self.store.delete_message(mid)
            self._remove_unreferenced(_files_of(message))
        return {"ok": True}

    # ---- 生成 ----

    def generate(self, payload: dict) -> dict:
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            raise ApiError(400, "先写点画面描述")
        provider = self.config.provider(str(payload.get("provider_id") or ""))
        if not provider:
            raise ApiError(400, "这个服务商已经不在设置里了，请重新选择模型")
        model = str(payload.get("model") or "").strip()
        if not model:
            raise ApiError(400, "还没有选择模型")
        size = str(payload.get("size") or "auto").lower().replace("×", "x")
        if not SIZE_VALUE.match(size):
            raise ApiError(400, "尺寸要写成 宽x高，比如 1536x864")

        refs = []
        for ref in payload.get("refs") or []:
            name = str((ref or {}).get("file") or "")
            self.file_path(name)
            thumb = str(ref.get("thumb") or name)
            refs.append({"file": name, "thumb": thumb if FILE_NAME.match(thumb) else name})

        try:
            count = int(payload.get("n") or 1)
        except (TypeError, ValueError):
            count = 1
        params = {
            "provider_id": provider["id"],
            "provider_name": provider["name"],
            "model": model,
            "style": str(payload.get("style") or "none"),
            "size": size,
            "quality": str(payload.get("quality") or "auto"),
            "complexity": str(payload.get("complexity") or "default"),
            "n": min(max(count, 1), cfg.MAX_COUNT),
        }

        session = self.store.session(str(payload.get("session_id") or ""))
        if not session:
            session = self.store.create_session(_title_from(prompt))
        message = self.store.add_message(session["id"], prompt, params, refs)
        self.config.remember(**{k: params[k] for k in cfg.DEFAULT_LAST})

        try:
            job = Job(provider)
        except ProviderError as exc:
            self.store.finish_message(message["id"], "error", error=str(exc))
        else:
            with self._jobs_lock:
                self._jobs[message["id"]] = job
            threading.Thread(
                target=self._run_job, args=(job, message, provider), name="generate", daemon=True
            ).start()
        return {
            "session": self.store.session(session["id"]),
            "message": self._with_previews(self.store.message(message["id"])),
        }

    def _run_job(self, job: Job, message: dict, provider: dict) -> None:
        mid, params = message["id"], message["params"]
        prompt = message["prompt"]
        style = cfg.style_prompt(params["style"])
        if style:
            prompt = f"{prompt}\n\n画面风格：{style}"
        try:
            results = job.run(
                model=params["model"],
                prompt=prompt,
                size=params["size"],
                quality=params["quality"],
                complexity=params["complexity"],
                refs=[self.file_path(ref["file"]) for ref in message["refs"]],
                n=params.get("n") or 1,
                on_partial=lambda slot, data, mime: self._set_preview(mid, slot, data, mime),
            )
            images = [self._save_image(data, mime) for data, mime in results]
            for index, image in enumerate(images):
                self._write_note(image, message, provider, index, len(images))
            if not self.store.finish_message(mid, "done", images=images):
                # 结果回来之前记录已被取消或删除，文件不留
                self._remove_unreferenced({n for i in images for n in (i["file"], i["thumb"])})
        except Cancelled:
            self.store.finish_message(mid, "cancelled")
        except ProviderError as exc:
            self.store.finish_message(mid, "error", error=str(exc))
        except Exception as exc:
            log.exception("生成任务出错")
            self.store.finish_message(mid, "error", error=f"程序内部出错：{exc!r}")
        finally:
            with self._jobs_lock:
                self._jobs.pop(mid, None)
            with self._previews_lock:
                self._previews.pop(mid, None)

    def _cancel_job(self, mid: str) -> None:
        with self._jobs_lock:
            job = self._jobs.get(mid)
        if job:
            job.cancel()

    def cancel(self, mid: str) -> dict:
        # 先改状态再断连接：这样界面立刻有反应，迟到的结果也不会覆盖回来
        self.store.finish_message(mid, "cancelled")
        self._cancel_job(mid)
        message = self.store.message(mid)
        if not message:
            raise ApiError(404, "记录不存在")
        return self._with_previews(message)


def _files_of(message: dict) -> set[str]:
    names = set()
    for item in message["refs"] + message["images"]:
        names.add(item["file"])
        names.add(item["thumb"])
    return names


def _title_from(prompt: str) -> str:
    line = prompt.strip().splitlines()[0].strip()
    line = re.sub(r"^(请|帮我|给我)?(生成|画|绘制|做)(一张|一幅|一个|个|张)?", "", line).strip(" ，,。.:：") or line
    return line[:16] + ("…" if len(line) > 16 else "")
