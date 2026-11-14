"""Ctrl+Shift+I：不用 --debug 启动也能打开内核自带的开发者工具。

pywebview 只在 debug 模式下才启用开发者工具，而 debug 模式还会顺带恢复内核自带的右键菜单、
一启动就弹出检查器。这里改成按需打开：收到快捷键时再去启用并显示，再按一次关闭。
"""

from __future__ import annotations

import sys

from .clipboard import _on_gui_thread, _qt_call

_qt_inspector = None  # Qt 的检查器窗口，留着引用以免被回收


def toggle(window) -> None:
    if "webview.platforms.gtk" in sys.modules:
        _toggle_gtk(window)
    elif "webview.platforms.qt" in sys.modules:
        _toggle_qt(window)
    else:
        raise RuntimeError("这个系统上要加 --debug 参数启动才能用开发者工具")


def _toggle_gtk(window) -> None:
    from gi.repository import GLib
    from webview.platforms.gtk import BrowserView

    def work():
        view = BrowserView.instances[window.uid].webview
        view.get_settings().set_enable_developer_extras(True)
        inspector = view.get_inspector()
        if inspector.get_web_view() is not None:  # 检查器已经开着
            inspector.close()
        else:
            inspector.show()

    _on_gui_thread(GLib.idle_add, work)


def _toggle_qt(window) -> None:
    from qtpy.QtWebEngineWidgets import QWebEngineView

    def work(_app):
        global _qt_inspector
        if _qt_inspector is not None and _qt_inspector.isVisible():
            _qt_inspector.close()
            return
        if _qt_inspector is None:
            _qt_inspector = QWebEngineView()
            _qt_inspector.setWindowTitle("seekie-image 开发者工具")
            _qt_inspector.resize(1000, 680)
            window.native.webview.page().setDevToolsPage(_qt_inspector.page())
        _qt_inspector.show()
        _qt_inspector.raise_()

    _qt_call(work)
