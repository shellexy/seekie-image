"""后端冒烟测试：起一个假接口，把生成的各条路径跑一遍。

    python -m unittest discover -s tests -v
"""

import io
import os
import socket
import stat
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mock_api  # noqa: E402
from seekie_image import app, clipboard, config, desktop  # noqa: E402
from seekie_image.core import ApiError, Core  # noqa: E402
from seekie_image.instance import InstanceLock, activate  # noqa: E402
from seekie_image.provider import normalize_base_url  # noqa: E402
from seekie_image.server import Server  # noqa: E402


def fake_window(shown: bool = True) -> SimpleNamespace:
    """够 Core.activate() 用的假窗口，记下它被要求做了什么。"""
    window = SimpleNamespace(calls=[])
    window.events = SimpleNamespace(shown=SimpleNamespace(is_set=lambda: shown))
    window.restore = lambda: window.calls.append("restore")
    window.show = lambda: window.calls.append("show")
    return window


class BackendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mock_api.Handler.delay = 0.3
        mock_api.say = lambda *args: None
        cls.mock = ThreadingHTTPServer(("127.0.0.1", 0), mock_api.Handler)
        cls.mock.handle_error = lambda *args: None  # 取消请求时客户端会主动断开
        cls.mock.daemon_threads = True
        threading.Thread(target=cls.mock.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.mock.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.mock.shutdown()
        cls.mock.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = Core(Path(self.tmp.name))
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.core.close)

    def provider(self, **overrides) -> str:
        provider = {"name": "mock", "base_url": self.base, "api_key": "k", "models": ["m"], **overrides}
        providers = self.core.config.data["providers"] + [provider]
        return self.core.save_providers(providers)["providers"][-1]["id"]

    def generate(self, provider_id: str, prompt="一座山", wait=True, **extra) -> dict:
        result = self.core.generate({"provider_id": provider_id, "model": "m", "prompt": prompt, **extra})
        message = result["message"]
        deadline = time.time() + 10
        while wait and message["status"] == "pending" and time.time() < deadline:
            time.sleep(0.05)
            message = self.core.store.message(message["id"])
        return message

    def image_files(self) -> set[str]:
        """应用存下来的所有图片文件（原图、缩略图、参考图），不含说明用的 .txt。"""
        folders = (self.core.images_dir, self.core.thumbs_dir, self.core.refs_dir)
        return {p.name for folder in folders for p in folder.iterdir() if p.suffix != ".txt"}

    def notes(self) -> set[str]:
        return {p.name for p in self.core.images_dir.glob("*.txt")}

    def test_base_url(self):
        self.assertEqual(normalize_base_url("api.example.com"), "https://api.example.com/v1")
        self.assertEqual(normalize_base_url("https://a.b/v1/images/generations"), "https://a.b/v1")
        self.assertEqual(normalize_base_url("https://a.b/api/v3/"), "https://a.b/api/v3")
        self.assertEqual(normalize_base_url("https://a.b/raw#"), "https://a.b/raw")

    def test_generate_and_params(self):
        message = self.generate(self.provider(), size="1024x1536", quality="high", complexity="low")
        self.assertEqual(message["status"], "done", message["error"])
        image = message["images"][0]
        self.assertEqual((image["w"], image["h"]), (1024, 1536))
        self.assertTrue(image["thumb"].endswith("_t.webp"))
        self.assertEqual(self.image_files(), {image["file"], image["thumb"]})
        session = self.core.store.sessions()[0]
        self.assertEqual(session["thumb"], image["thumb"])
        self.assertEqual(self.core.config.data["last"]["quality"], "high")

    def test_edit_with_references(self):
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), "red").save(buffer, "PNG")
        ref = self.core.upload(buffer.getvalue())
        message = self.generate(self.provider(), refs=[ref, ref])
        self.assertEqual(message["status"], "done", message["error"])
        self.assertEqual(len(message["refs"]), 2)

    def test_stream_chat_and_url_responses(self):
        streamed = self.generate(self.provider(extra={"stream": True, "partial_images": 2}), size="1024x1024")
        self.assertEqual(streamed["status"], "done", streamed["error"])
        self.assertEqual(streamed["images"][0]["w"], 1024)  # 拿到的是最终图，不是 256 宽的 partial
        chat = self.generate(self.provider(api_mode="chat"))
        self.assertEqual(chat["status"], "done", chat["error"])
        by_url = self.generate(self.provider(extra={"response_format": "url"}), size="1024x1024")
        self.assertEqual(by_url["status"], "done", by_url["error"])
        self.assertEqual(by_url["images"][0]["w"], 1024)

    def test_errors_are_readable(self):
        provider_id = self.provider()
        rejected = self.generate(provider_id, prompt="[error]")
        self.assertEqual(rejected["status"], "error")
        self.assertIn("safety system", rejected["error"])
        timeout = self.generate(provider_id, prompt="[timeout]")
        self.assertIn("网关超时", timeout["error"])
        unauthorized = self.generate(self.provider(api_key="bad"))
        self.assertIn("API Key", unauthorized["error"])
        no_image = self.generate(self.provider(api_mode="chat"), prompt="[error]")
        self.assertIn("没有返回图片", no_image["error"])
        unreachable = self.generate(self.provider(base_url="http://127.0.0.1:9"))
        self.assertIn("连不上", unreachable["error"])
        with self.assertRaises(ApiError):
            self.core.generate({"provider_id": provider_id, "model": "m", "prompt": "  "})

    def test_cancel_keeps_status_and_leaves_no_files(self):
        mock_api.Handler.delay = 1.0
        self.addCleanup(setattr, mock_api.Handler, "delay", 0.3)
        message = self.generate(self.provider(), wait=False)
        self.assertEqual(message["status"], "pending")
        self.assertEqual(self.core.cancel(message["id"])["status"], "cancelled")
        time.sleep(0.3)
        self.assertEqual(self.core._jobs, {}, "取消后连接应当立刻断开，而不是等接口返回")
        time.sleep(1.2)  # 假接口这时才会把结果发回来
        self.assertEqual(self.core.store.message(message["id"])["status"], "cancelled")
        self.assertEqual(self.image_files(), set())

    def test_delete_removes_only_unshared_files(self):
        provider_id = self.provider()
        first = self.generate(provider_id)
        image = first["images"][0]
        second = self.generate(provider_id, session_id=first["session_id"],
                               refs=[{"file": image["file"], "thumb": image["thumb"]}])
        self.assertEqual(second["status"], "done", second["error"])
        self.core.delete_message(first["id"])
        self.assertIn(image["file"], self.image_files())  # 还被第二条当参考图用着
        self.core.delete_session(first["session_id"])
        self.assertEqual(self.image_files(), set())
        self.assertEqual(self.core.store.sessions(), [])

    def test_probe_lists_models(self):
        models = self.core.probe({"base_url": self.base, "api_key": "k"})["models"]
        self.assertIn("gpt-image-2.6-sunburst", models)
        with self.assertRaises(ApiError):
            self.core.probe({"base_url": self.base, "api_key": "bad"})

    def test_paste_from_system_clipboard(self):
        from PIL import Image

        with self.assertRaises(ApiError) as caught:  # 浏览器模式下页面自己读，后台不代劳
            self.core.paste()
        self.assertEqual(caught.exception.status, 400)

        self.core.window = object()  # 假装开着桌面窗口
        png = io.BytesIO()
        Image.new("RGB", (40, 30), "orange").save(png, "PNG")
        with mock.patch.object(clipboard, "read", return_value=(None, [png.getvalue(), b"not an image"])):
            pasted = self.core.paste()
        self.assertIsNone(pasted["text"])
        self.assertEqual(len(pasted["images"]), 1)  # 认不出的内容被跳过
        self.assertTrue(pasted["images"][0]["file"].startswith("ref_"))
        self.assertIn(pasted["images"][0]["file"], self.image_files())

        with mock.patch.object(clipboard, "read", return_value=("一只猫", [])):
            self.assertEqual(self.core.paste(), {"text": "一只猫", "images": []})

        before = self.image_files()
        with mock.patch.object(clipboard, "read", return_value=(None, [png.getvalue()])):
            self.assertEqual(self.core.paste(images=False)["images"], [])  # 只要文字时不落盘
        self.assertEqual(self.image_files(), before)

        with mock.patch.object(clipboard, "read", side_effect=RuntimeError("boom")):
            with self.assertLogs("seekie_image", "WARNING"), self.assertRaises(ApiError) as caught:
                self.core.paste()
        self.assertEqual(caught.exception.status, 500)

    def test_copy_image_hands_png_to_clipboard(self):
        from PIL import Image

        webp = io.BytesIO()
        Image.new("RGB", (40, 30), "teal").save(webp, "WEBP")
        name = self.core.upload(webp.getvalue())["file"]
        with self.assertRaises(ApiError):
            self.core.copy_image(name)  # 浏览器模式

        self.core.window = object()
        seen = {}
        with mock.patch.object(clipboard, "_backend", return_value="gtk"), \
                mock.patch.object(clipboard, "_write_gtk", lambda png, image: seen.update(png=png)):
            self.assertEqual(self.core.copy_image(name), {"ok": True})
        self.assertTrue(seen["png"].startswith(b"\x89PNG"))  # 不管原图什么格式，交出去的都是 PNG
        with self.assertRaises(ApiError):
            self.core.copy_image("nope.png")

    def test_files_go_to_their_own_folders_with_a_note(self):
        from PIL import Image

        png = io.BytesIO()
        Image.new("RGB", (40, 30), "orange").save(png, "PNG")
        ref = self.core.upload(png.getvalue())
        pid = self.provider(extra={"output_format": "png"})
        message = self.generate(pid, prompt="一只戴草帽的猫\n坐在防波堤上", style="anime", size="1536x1024",
                                quality="high", refs=[ref])
        self.assertEqual(message["status"], "done", message["error"])
        image = message["images"][0]

        # 图片文件夹里只有原图和同名 .txt；缩略图和参考图留在数据目录
        stem = Path(image["file"]).stem
        self.assertRegex(stem, r"^\d{8}-\d{6}-[0-9a-f]{6}$")
        self.assertEqual({p.name for p in self.core.images_dir.iterdir()}, {image["file"], f"{stem}.txt"})
        self.assertTrue((self.core.thumbs_dir / image["thumb"]).is_file())
        self.assertTrue((self.core.refs_dir / ref["file"]).is_file())
        self.assertEqual(self.core.file_path(image["thumb"]).parent, self.core.thumbs_dir)

        note = (self.core.images_dir / f"{stem}.txt").read_text("utf-8")
        self.assertTrue(note.startswith("提示词：\n一只戴草帽的猫\n坐在防波堤上\n\n模型：m\n服务商：mock\n"))
        for line in ("风格：动漫（", "比例：1536x1024", "质量：high", "复杂度：默认",
                     '额外参数：{"output_format": "png"}', "参考图：1 张", "生成时间："):
            self.assertIn(line, note)
        self.assertNotIn("api_key", note)

        with self.assertRaises(ApiError):  # 说明文件不通过 /files 对外提供
            self.core.file_path(f"{stem}.txt")

        self.core.delete_message(message["id"])
        self.assertEqual(list(self.core.images_dir.iterdir()), [])  # 删记录时 .txt 一起删
        self.assertEqual(self.image_files(), set())

        # 图片被用户从文件夹里拿走以后再删记录，剩下的 .txt 也要清掉
        message = self.generate(pid)
        (self.core.images_dir / message["images"][0]["file"]).unlink()
        self.core.delete_message(message["id"])
        self.assertEqual(list(self.core.images_dir.iterdir()), [])

    def test_several_images_in_one_go(self):
        pid = self.provider()
        message = self.generate(pid, n=3)
        self.assertEqual(message["status"], "done", message["error"])
        self.assertEqual(message["params"]["n"], 3)
        self.assertEqual(len(message["images"]), 3)
        self.assertEqual(len(self.notes()), 3)
        note = (self.core.images_dir / message["images"][1]["file"]).with_suffix(".txt").read_text("utf-8")
        self.assertIn("数量：请求 3 张，这是返回的 3 张里的第 2 张", note)
        self.assertEqual(self.core.config.data["last"]["n"], 3)  # 下次打开还是这个数量

        self.assertEqual(self.generate(pid, n=99)["params"]["n"], 10)  # 超出上限就按上限
        self.assertEqual(self.generate(pid, n="x")["params"]["n"], 1)

        # 对话接口没有 n，要几张就发几次请求
        chat = self.provider(api_mode="chat")
        message = self.generate(chat, n=2)
        self.assertEqual(message["status"], "done", message["error"])
        self.assertEqual(len(message["images"]), 2)

    def test_stream_previews(self):
        mock_api.Handler.delay = 1.2
        self.addCleanup(setattr, mock_api.Handler, "delay", 0.3)
        pid = self.provider(stream=True)
        message = self.generate(pid, n=2, wait=False)
        mid = message["id"]
        self.assertEqual(message["previews"], [])

        seen = {}
        deadline = time.time() + 10
        while time.time() < deadline:
            message = self.core.messages_by_id([mid])[0]
            for preview in message["previews"]:
                data, mime = self.core.preview(mid, str(preview["slot"]))
                self.assertEqual(mime, "image/png")
                seen.setdefault(preview["slot"], set()).add(preview["v"])
            if message["status"] != "pending":
                break
            time.sleep(0.05)
        self.assertEqual(message["status"], "done", message["error"])
        self.assertEqual(len(message["images"]), 2)
        self.assertEqual(seen, {0: {1, 2}, 1: {1, 2}})  # 两张图各有两张中间图，版本号递增
        self.assertEqual(message["previews"], [])  # 生成完就不再带预览
        with self.assertRaises(ApiError):
            self.core.preview(mid, "0")  # 内存里的预览图也清掉了
        with self.assertRaises(ApiError):
            self.core.preview(mid, "../x")

    def test_stream_falls_back_when_rejected(self):
        # 中转站不认识 stream：自动去掉再发一次，照样出图
        pid = self.provider(stream=True, api_key="nostream")
        message = self.generate(pid)
        self.assertEqual(message["status"], "done", message["error"])
        self.assertEqual(len(message["images"]), 1)
        # 没开流式时不会带 stream 参数；用户自己在额外参数里写的 stream 被拒绝则如实报错
        self.assertEqual(self.generate(self.provider(api_key="nostream"))["status"], "done")
        message = self.generate(self.provider(api_key="nostream", extra={"stream": True}))
        self.assertEqual(message["status"], "error")
        self.assertIn("stream", message["error"])

    def test_separate_images_dir_and_old_layout(self):
        with tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as pictures:
            core = Core(Path(data), Path(pictures) / "seekie-image")
            self.addCleanup(core.close)
            self.assertTrue((Path(pictures) / "seekie-image").is_dir())
            # 早先的版本把缩略图和参考图也放在 images/ 里，这些文件还要能找到
            (core.images_dir / "ref_old.png").write_bytes(b"x")
            (core.images_dir / "old_t.webp").write_bytes(b"x")
            self.assertEqual(core.file_path("ref_old.png").parent, core.images_dir)
            self.assertEqual(core.file_path("old_t.webp").parent, core.images_dir)


class InstanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.core = Core(self.dir)
        self.addCleanup(self.core.close)

    def start_server(self) -> Server:
        server = Server("127.0.0.1", 0, self.core)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def hold_lock(self, *, native: bool) -> tuple[InstanceLock, Server]:
        server = self.start_server()
        lock = InstanceLock(self.dir)
        self.assertTrue(lock.acquire())
        self.addCleanup(lock.release)
        lock.remember(url=server.url, token=server.token, native=native)
        return lock, server

    def test_lock_is_exclusive_per_directory(self):
        first, second = InstanceLock(self.dir), InstanceLock(self.dir)
        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())  # 第二个进程（这里用另一个 fd 模拟）拿不到
        first.release()
        self.assertTrue(second.acquire())
        second.release()

    def test_instance_info_is_private_and_validated(self):
        lock = InstanceLock(self.dir)
        self.assertTrue(lock.acquire())
        self.addCleanup(lock.release)
        lock.remember(url="http://127.0.0.1:1234/", token="secret", native=True)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(lock.info_path.stat().st_mode), 0o600)
        self.assertEqual(lock.info()["token"], "secret")

        lock.info_path.write_text('{"url": "ftp://x", "token": "t"}', "utf-8")
        self.assertIsNone(lock.info())  # 不认识地址格式就当作没有
        lock.info_path.write_text("不是 JSON", "utf-8")
        self.assertIsNone(lock.info())

    def test_activate_raises_window(self):
        self.core.window = fake_window()
        self.assertEqual(self.core.activate(), {"native": True})
        self.assertEqual(self.core.window.calls, ["restore", "show"])

    def test_activate_in_browser_mode(self):
        self.core.window = None
        self.assertEqual(self.core.activate(), {"native": False})

    def test_close_removes_info_and_releases_lock(self):
        lock = InstanceLock(self.dir)
        self.assertTrue(lock.acquire())
        lock.remember(url="http://127.0.0.1:1234/", token="t", native=True)
        lock.close()
        self.assertFalse(lock.info_path.exists())
        again = InstanceLock(self.dir)
        self.assertTrue(again.acquire())  # 锁确实放掉了
        again.release()

    def test_activate_does_not_wait_for_starting_window(self):
        self.core.window = fake_window(shown=False)
        self.assertEqual(self.core.activate(), {"native": True})
        self.assertEqual(self.core.window.calls, [])  # 窗口还在启动，等它自己出来

    def test_activate_returns_none_when_nothing_listens(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.assertIsNone(activate({"url": f"http://127.0.0.1:{port}/", "token": "t"}))

    def test_second_launch_wakes_native_window(self):
        self.core.window = fake_window()
        self.hold_lock(native=True)
        self.assertEqual(app.main(["--data-dir", str(self.dir), "--no-open"]), 0)
        self.assertEqual(self.core.window.calls, ["restore", "show"])

    def test_second_launch_opens_browser_when_first_is_browser_mode(self):
        _lock, server = self.hold_lock(native=False)
        with mock.patch("seekie_image.app.webbrowser.open") as opened:
            self.assertEqual(app.main(["--data-dir", str(self.dir), "--browser"]), 0)
        opened.assert_called_once_with(server.url)

    def test_second_launch_no_open_does_nothing(self):
        self.hold_lock(native=False)
        with mock.patch("seekie_image.app.webbrowser.open") as opened:
            self.assertEqual(app.main(["--data-dir", str(self.dir), "--browser", "--no-open"]), 0)
        opened.assert_not_called()

    def test_second_launch_does_not_open_browser_when_unreachable(self):
        self.hold_lock(native=True)
        with mock.patch.object(InstanceLock, "wake", return_value={
            "url": "http://127.0.0.1:1/", "token": "t", "native": None,
        }), mock.patch("seekie_image.app.webbrowser.open") as opened:
            self.assertEqual(app.main(["--data-dir", str(self.dir)]), 0)
        opened.assert_not_called()


class DirectoriesTest(unittest.TestCase):
    def env(self, home: str, **extra):
        return mock.patch.dict(os.environ, {"HOME": home, **extra}, clear=True)

    @unittest.skipUnless(sys.platform.startswith("linux"), "只针对 Linux 的目录约定")
    def test_linux_defaults(self):
        with tempfile.TemporaryDirectory() as home:
            with self.env(home):
                self.assertEqual(config.default_data_dir(), Path(home, ".config", "seekie-image"))
                self.assertEqual(config.default_images_dir(), Path(home, ".config", "seekie-image", "images"))
            with self.env(home, XDG_CONFIG_HOME=f"{home}/cfg"):
                self.assertEqual(config.default_data_dir(), Path(home, "cfg", "seekie-image"))

    def test_explicit_data_dir(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(config.default_images_dir(Path(home, "portable")), Path(home, "portable", "images"))
            with self.env(home, SEEKIE_IMAGE_HOME=f"{home}/custom"):
                self.assertEqual(config.default_data_dir(), Path(home, "custom"))
                self.assertEqual(config.default_images_dir(), Path(home, "custom", "images"))


@unittest.skipUnless(sys.platform.startswith("linux"), "启动器只在 Linux 上安装")
class DesktopEntryTest(unittest.TestCase):
    def test_install_and_uninstall(self):
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.dict(os.environ, {"XDG_DATA_HOME": home}), \
                mock.patch.object(desktop, "launch_command", return_value=["/opt/my apps/bin/seekie-image"]), \
                mock.patch.object(desktop, "_refresh_caches"), \
                mock.patch("builtins.print"):
            self.assertEqual(desktop.install(), 0)
            entry = Path(home, "applications", "seekie-image.desktop").read_text("utf-8")
            self.assertIn('Exec="/opt/my apps/bin/seekie-image"\n', entry)  # 带空格的路径要加引号
            self.assertIn("TryExec=/opt/my apps/bin/seekie-image\n", entry)
            self.assertIn("Icon=seekie-image\n", entry)
            icons = sorted(p.parent.parent.name for p in Path(home, "icons", "hicolor").glob("*/apps/seekie-image.png"))
            self.assertIn("48x48", icons)
            self.assertIn("256x256", icons)

            self.assertEqual(desktop.uninstall(), 0)
            self.assertEqual([p for p in Path(home).rglob("*") if p.is_file()], [])


if __name__ == "__main__":
    unittest.main()
