"""入口：启动本机服务，然后用 pywebview 开一个桌面窗口指向它。"""

from __future__ import annotations

from . import kde_native_dialog_patch # 猴子补丁，让 kde 下能使用 kde 文件对话框

import argparse
import inspect
import logging
import logging.handlers
import sys
import threading
import webbrowser
from pathlib import Path

from . import __version__, desktop
from .config import default_data_dir, default_images_dir
from .core import Core
from .instance import InstanceLock
from .server import Server

TITLE = "Seekie Image"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="seekie-image",
        description="接 OpenAI 兼容绘图接口的桌面小工具",
        epilog="同一份数据目录只运行一个实例，再次启动会切换到已有窗口。",
    )
    parser.add_argument("--browser", action="store_true", help="不开桌面窗口，改用系统浏览器")
    parser.add_argument("--no-open", action="store_true", help="浏览器模式下不自动打开页面")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认只限本机")
    parser.add_argument("--port", type=int, default=0, help="监听端口，默认随机")
    parser.add_argument("--data-dir", type=Path,
                        help=f"配置和历史记录所在的目录，默认 {default_data_dir()}")
    parser.add_argument("--images-dir", type=Path, help="生成的图片保存到哪，默认是数据目录下的 images/")
    parser.add_argument("--debug", action="store_true", help="输出调试日志，并打开开发者工具")
    parser.add_argument("--install-desktop", action="store_true",
                        help="Linux：把启动器和图标装进当前用户的应用菜单，然后退出")
    parser.add_argument("--uninstall-desktop", action="store_true", help="Linux：移除上面装的启动器和图标")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    if args.install_desktop:
        return desktop.install()
    if args.uninstall_desktop:
        return desktop.uninstall()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        # 用 pythonw / gui 入口启动时没有 stderr
        handlers=None if sys.stderr else [logging.NullHandler()],
    )
    # httpx 的 INFO 日志会打印完整请求地址，默认不需要
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    log = logging.getLogger("seekie_image")

    data_dir = (args.data_dir or default_data_dir()).expanduser()
    images_dir = (args.images_dir or default_images_dir(args.data_dir and data_dir)).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)

    # 桌面入口/pyw 启动时没有 stderr，出错只能看日志文件
    log_path = data_dir / "app.log"
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=1, encoding="utf-8", delay=True,
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(file_handler)
    except OSError:
        log.warning("没法写日志文件：%s", log_path, exc_info=True)
    log.info("日志文件：%s", log_path)

    # 同一份数据目录只跑一个进程；后来的直接去叫醒已经开着的那个
    instance = InstanceLock(data_dir)
    if not instance.acquire():
        return _wake_running(instance, args)
    try:
        return _run(instance, args, data_dir, images_dir, log)
    finally:
        instance.close()


def _wake_running(instance: InstanceLock, args: argparse.Namespace) -> int:
    """第二次启动：不新建服务，请已有实例把窗口调到前面，然后退出。"""
    log = logging.getLogger("seekie_image")
    if args.browser:
        # 明确要求浏览器模式，就不用打扰桌面窗口了
        info = instance.wait_info()
        if not info:
            log.warning("已经有一个实例在运行，但没找到它的界面地址")
            return 0
        log.info("程序已经在运行，界面地址：%s", info["url"])
        if not args.no_open:
            webbrowser.open(info["url"])
        return 0

    info = instance.wake()
    if not info:
        log.warning("已经有一个实例在运行，但没能连上它（可能正在启动或退出）")
        return 0
    native = info.get("native")
    if native is None:
        log.warning("已经有一个实例在运行，但没能连上它（可能正在启动或退出）")
        return 0
    if native:
        log.info("程序已经在运行，已切换到现有窗口")
        return 0
    log.info("程序已经在运行（浏览器模式）：%s", info["url"])
    if not args.no_open:
        webbrowser.open(info["url"])
    return 0


def _run(instance: InstanceLock, args: argparse.Namespace, data_dir: Path, images_dir: Path, log) -> int:
    core = Core(data_dir, images_dir)
    server = Server(args.host, args.port, core)
    log.info("数据目录：%s", data_dir)
    log.info("图片目录：%s", images_dir)

    webview = None
    if not args.browser:
        try:
            import webview
        except ImportError:
            log.warning("没有安装 pywebview，改用浏览器打开。安装：pip install pywebview")

    if webview is None:
        instance.remember(url=server.url, token=server.token, native=False)
        log.info("界面地址：%s", server.url)
        if not args.no_open:
            threading.Timer(0.3, webbrowser.open, [server.url]).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0

    threading.Thread(target=server.serve_forever, name="http", daemon=True).start()
    try:
        # GTK 和 Qt 都用 argv[0] 给窗口起类名（WM_CLASS / Wayland app_id）。
        # 只在 Linux 上改：Windows 上 pywebview 可能拿 argv[0] 找 DLL。
        if sys.platform.startswith("linux"):
            sys.argv[0] = desktop.APP_ID
        webview.settings["ALLOW_DOWNLOADS"] = True
        core.window = webview.create_window(
            TITLE,
            server.url,
            width=1280,
            height=800,
            min_size=(820, 600),
            background_color="#F5F4FC",
            text_select=True,  # pywebview 默认禁止选中文字，这里需要能选中提示词
        )
        options = {"debug": args.debug}
        # icon 参数在 Windows 上会被 WinForms 当成 .ico 解析，传 png 会直接把进程崩掉；
        # Windows / macOS 的窗口图标本来由可执行文件决定，这里只在 Linux 上传。
        if sys.platform.startswith("linux") and "icon" in inspect.signature(webview.start).parameters:
            options["icon"] = str(desktop.ICON)
        # 窗口还没显示时第二个实例可能就来敲门了：先留下地址，窗口马上出来
        instance.remember(url=server.url, token=server.token, native=True)
        webview.start(**options)
    except Exception as exc:
        log.exception("桌面窗口启动失败")
        _show_error(f"Seekie Image 启动失败：{exc}\n\n详细信息见：{data_dir / 'app.log'}")
        return 1
    finally:
        server.shutdown()
    return 0


def _show_error(message: str) -> None:
    """桌面入口没有控制台时，至少让 Windows 用户看到一个错误框。"""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, TITLE, 0x10)
        except Exception:
            pass
    elif sys.stderr:
        print(message, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
