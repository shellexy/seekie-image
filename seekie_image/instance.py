"""单实例：同一份数据目录同时只让一个进程跑。

第一个进程先拿到数据目录里的 instance.lock，再把界面地址和令牌写进 instance.json。
后来的进程拿不到锁，就按 instance.json 去找已有进程，请它把窗口调到前面，然后自己退出。

锁是操作系统的文件锁，进程退出（包括崩溃、被 kill）时由内核自动释放，所以不会留下
需要手工清理的「僵尸锁」。instance.json 只是给后来者指路用的，删掉也没关系。
"""

from __future__ import annotations

import errno
import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger("seekie_image")

LOCK_NAME = "instance.lock"
INFO_NAME = "instance.json"
ACTIVATE_TIMEOUT = 5.0   # 请求已有实例的最长等待时间
STARTUP_WAIT = 5.0       # 已有实例可能刚启动还没写 instance.json，等它一会儿


class InstanceLock:
    """数据目录上的独占地盘。acquire() 返回 False 表示已经有别的进程占着。"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.path = data_dir / LOCK_NAME
        self.info_path = data_dir / INFO_NAME
        self._file = None
        self._locked = False
        self._remembered = False

    def acquire(self) -> bool:
        """拿锁。拿到返回 True；已经别的进程拿着返回 False。

        文件系统不支持锁时只记一条警告，按多实例继续跑，不要因为这个小功能打不开程序。
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt

                if handle.seek(0, os.SEEK_END) == 0:  # Windows 上锁区从当前指针算起
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            if exc.errno in (errno.EACCES, errno.EAGAIN, getattr(errno, "EDEADLK", errno.EACCES)):
                return False
            log.warning("没法在数据目录里加单实例锁，这次按多实例运行", exc_info=True)
            return True
        self._file = handle
        self._locked = True
        # 上一次可能是崩溃退出的，留下的地址已经没用了；先清掉，免得后来者找错门
        self.forget()
        return True

    def release(self) -> None:
        handle, self._file = self._file, None
        locked, self._locked = self._locked, False
        if handle is None:
            return
        try:
            if locked:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            handle.close()

    def close(self) -> None:
        """退出时用：删掉自己写的指路信息，再放锁。"""
        if self._remembered:
            self.forget()
            self._remembered = False
        self.release()

    # ---- instance.json ----

    def remember(self, *, url: str, token: str, native: bool) -> None:
        """写下怎么找到这个实例，供后启动的进程唤醒它。"""
        payload = json.dumps({"pid": os.getpid(), "url": url, "token": token, "native": bool(native)})
        tmp = self.info_path.with_suffix(".json.tmp")
        tmp.write_text(payload, "utf-8")
        if os.name == "posix":
            os.chmod(tmp, 0o600)  # 里面有本机接口的令牌，只给自己看
        tmp.replace(self.info_path)
        self._remembered = True

    def info(self) -> dict | None:
        """读 instance.json；文件不在、坏了或格式不对都返回 None。"""
        try:
            data = json.loads(self.info_path.read_text("utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("token"), str):
            return None
        url = data.get("url")
        if not isinstance(url, str):
            return None
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return None
        return data

    def forget(self) -> None:
        try:
            self.info_path.unlink(missing_ok=True)
        except OSError:
            log.debug("删不掉 %s", self.info_path, exc_info=True)

    # ---- 唤醒已有实例 ----

    def wait_info(self, timeout: float = STARTUP_WAIT) -> dict | None:
        """等已有实例把 instance.json 写出来（它可能正在启动）。"""
        deadline = time.monotonic() + timeout
        while True:
            info = self.info()
            if info or time.monotonic() >= deadline:
                return info
            time.sleep(0.2)

    def wake(self, timeout: float = STARTUP_WAIT) -> dict | None:
        """反复尝试请已有实例把窗口调到前面。

        返回最后一次读到的 instance.json，并附加 native 字段：True 表示它有桌面窗口，
        False 表示它跑在浏览器模式（调用方应该去打开那个地址）。
        """
        deadline = time.monotonic() + timeout
        info = None
        while True:
            info = self.info()
            if info:
                native = activate(info)
                if native is not None:
                    return {**info, "native": native}
            if time.monotonic() >= deadline:
                # 读到了地址但一次都没打通：标成 unknown，调用方不要据此打开浏览器
                return {**info, "native": None} if info else None
            time.sleep(0.2)


def activate(info: dict) -> bool | None:
    """请求已有实例激活窗口。返回它是否是桌面窗口；请求失败（还没起来 / 正在退出）返回 None。"""
    url = info["url"].rstrip("/") + "/api/activate"
    request = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={"X-Token": info["token"], "Content-Type": "application/json"},
    )
    # 本机请求不能走代理：环境里的 http_proxy 会让它根本到不了 127.0.0.1
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=ACTIVATE_TIMEOUT) as response:
            data = json.loads(response.read() or b"{}")
    except (OSError, ValueError):
        return None
    return bool(data.get("native")) if isinstance(data, dict) else None
