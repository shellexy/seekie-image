"""读写系统剪贴板（文字、图片）。

为什么不让页面自己读：pywebview 关掉了原生右键菜单，页面里的「粘贴」只能靠脚本读剪贴板，
而各个内核在这件事上都不可靠——WebKitGTK 的粘贴事件里拿不到图片，Qt WebEngine 的
Clipboard API 会一直挂起。所以桌面窗口模式下统一由 Python 这边去读。

read() 返回 (text, images)：images 是若干张图片的原始字节；剪贴板里有图片时 text 为 None。
write_image() 把一张图片放进剪贴板，供「复制图片」使用。
"""

from __future__ import annotations

import io
import logging
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import unquote, urlsplit

log = logging.getLogger("seekie_image")

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGES = 10
MAX_FILE_BYTES = 50 * 1024 * 1024


def _backend() -> str:
    if "webview.platforms.gtk" in sys.modules:
        return "gtk"
    if "webview.platforms.qt" in sys.modules:
        return "qt"
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "other"


def read() -> tuple[str | None, list[bytes]]:
    reader = {
        "gtk": _read_gtk, "qt": _read_qt, "windows": _read_windows, "macos": _read_macos,
    }.get(_backend(), _read_with_pillow)
    text, images = reader()
    return (None if images else text or None), images[:MAX_IMAGES]


def write_image(data: bytes) -> None:
    """把图片放进剪贴板。统一转成 PNG 再交给系统，省得各平台对 WebP 之类的支持不一。"""
    from PIL import Image

    image = Image.open(io.BytesIO(data))  # 打不开（比如 SVG）会抛异常，由调用方转成提示
    image.load()
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")
    out = io.BytesIO()
    image.save(out, "PNG")
    writer = {
        "gtk": _write_gtk, "qt": _write_qt, "windows": _write_windows, "macos": _write_macos,
    }.get(_backend())
    if writer is None:
        raise RuntimeError("当前环境不支持")
    writer(out.getvalue(), image)


# ---- 通用的小工具 ----

def _on_gui_thread(schedule, work, timeout: float = 5.0):
    """GTK 和 Qt 的剪贴板都只能在界面线程里访问；这里把 work 丢过去并等结果。"""
    done = threading.Event()
    box: dict = {}

    def run():
        try:
            box["value"] = work()
        except Exception as exc:  # 带回调用线程再抛
            box["error"] = exc
        finally:
            done.set()
        return False  # GLib.idle_add：只执行一次

    schedule(run)
    if not done.wait(timeout):
        raise TimeoutError("界面线程没有响应")
    if "error" in box:
        raise box["error"]
    return box["value"]


def _images_from_paths(paths: list[str]) -> list[bytes]:
    """在文件管理器里「复制」的文件，剪贴板里放的是路径；把其中的图片读出来。"""
    images = []
    for raw in paths:
        if raw.startswith("file://"):
            raw = unquote(urlsplit(raw).path)
        path = Path(raw)
        try:
            if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file() and path.stat().st_size <= MAX_FILE_BYTES:
                images.append(path.read_bytes())
        except OSError:
            log.debug("读不了剪贴板里的文件：%s", raw, exc_info=True)
    return images


def _pillow_images() -> list[bytes]:
    from PIL import Image, ImageGrab

    grabbed = ImageGrab.grabclipboard()
    if isinstance(grabbed, list):  # 复制的是文件
        return _images_from_paths([str(item) for item in grabbed])
    if isinstance(grabbed, Image.Image):
        out = io.BytesIO()
        grabbed.save(out, "PNG")
        return [out.getvalue()]
    return []


# ---- Linux：直接用 pywebview 正在用的那套界面库 ----

def _read_gtk():
    from gi.repository import Gdk, GLib, Gtk

    def work():
        board = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        images = _images_from_paths(list(board.wait_for_uris() or []))
        if not images and board.wait_is_image_available():
            pixbuf = board.wait_for_image()
            if pixbuf is not None:
                ok, data = pixbuf.save_to_bufferv("png", [], [])
                if ok:
                    images.append(bytes(data))
        return (None if images else board.wait_for_text()), images

    return _on_gui_thread(GLib.idle_add, work)


def _write_gtk(png: bytes, _image) -> None:
    from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

    def work():
        loader = GdkPixbuf.PixbufLoader.new_with_type("png")
        loader.write(png)
        loader.close()
        board = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        board.set_image(loader.get_pixbuf())
        board.store()  # 交给剪贴板管理器，应用退出后内容还在

    _on_gui_thread(GLib.idle_add, work)


def _qt_call(work):
    """在 Qt 的界面线程里执行 work 并取回结果。"""
    from qtpy import QtCore, QtWidgets  # pywebview 的 Qt 后端本身就依赖 qtpy

    app = QtWidgets.QApplication.instance()

    class Invoker(QtCore.QObject):
        call = QtCore.Signal(object)

        def __init__(self):
            super().__init__()
            self.call.connect(self.run)

        @QtCore.Slot(object)
        def run(self, fn):
            fn()

    # 对象归属界面线程后，从别的线程发信号会排进界面线程的事件队列里执行
    invoker = Invoker()
    invoker.moveToThread(app.thread())
    try:
        return _on_gui_thread(invoker.call.emit, lambda: work(app))
    finally:
        invoker.deleteLater()


def _read_qt():
    from qtpy import QtCore

    def work(app):
        board = app.clipboard()
        mime = board.mimeData()
        images = _images_from_paths([url.toString() for url in mime.urls()]) if mime.hasUrls() else []
        if not images and mime.hasImage():
            image = board.image()
            if not image.isNull():
                buffer = QtCore.QBuffer()
                buffer.open(QtCore.QIODevice.WriteOnly)
                image.save(buffer, "PNG")
                images.append(bytes(buffer.data().data()))
        return (None if images else (mime.text() if mime.hasText() else None)), images

    return _qt_call(work)


def _write_qt(png: bytes, _image) -> None:
    from qtpy import QtGui

    def work(app):
        picture = QtGui.QImage.fromData(png, "PNG")
        if picture.isNull():
            raise RuntimeError("图片解码失败")
        app.clipboard().setImage(picture)

    _qt_call(work)


# ---- Windows / macOS ----

def _read_windows():
    images = _pillow_images()
    return (None if images else _windows_text()), images


def _windows_text() -> str | None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _write_windows(png: bytes, image) -> None:
    import ctypes
    from ctypes import wintypes

    # CF_DIB 是所有程序都认的格式（不带透明）；另外再放一份 PNG，认它的程序能保留透明
    flat = io.BytesIO()
    if image.mode == "RGBA":
        from PIL import Image

        canvas = Image.new("RGB", image.size, "white")
        canvas.paste(image, mask=image.getchannel("A"))
        canvas.save(flat, "BMP")
    else:
        image.save(flat, "BMP")
    dib = flat.getvalue()[14:]  # 去掉 BMP 文件头，剩下的就是 DIB

    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT

    def put(fmt: int, payload: bytes) -> None:
        handle = kernel32.GlobalAlloc(0x0002, len(payload))  # GMEM_MOVEABLE
        if not handle:
            raise MemoryError("GlobalAlloc 失败")
        pointer = kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, payload, len(payload))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(fmt, handle):  # 成功后内存归系统所有
            kernel32.GlobalFree(handle)
            raise OSError("SetClipboardData 失败")

    if not user32.OpenClipboard(None):
        raise OSError("剪贴板正被别的程序占用")
    try:
        user32.EmptyClipboard()
        put(8, dib)  # CF_DIB
        put(user32.RegisterClipboardFormatW("PNG"), png)
    finally:
        user32.CloseClipboard()


def _write_macos(png: bytes, _image) -> None:
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".png")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(png)
        script = 'on run argv\nset the clipboard to (read (POSIX file (item 1 of argv)) as «class PNGf»)\nend run'
        subprocess.run(["osascript", "-e", script, path], check=True, capture_output=True, timeout=10)
    finally:
        os.unlink(path)


def _read_macos():
    images = _pillow_images()
    if images:
        return None, images
    result = subprocess.run(["pbpaste"], capture_output=True, timeout=3)
    return result.stdout.decode("utf-8", "replace"), []


def _read_with_pillow():
    return None, _pillow_images()
