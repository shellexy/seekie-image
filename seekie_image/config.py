"""数据目录、配置文件，以及界面上那几个下拉菜单的选项。"""

from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from pathlib import Path

APP_DIR_NAME = "seekie-image"

# 菜单选项由后端给出，前端只负责渲染；label 用在菜单里，short 用在按钮上。
STYLES = [
    {"id": "none", "label": "不指定", "short": "风格", "prompt": ""},
    {"id": "anime", "label": "动漫", "short": "动漫", "prompt": "日系动画风格，干净的线条，赛璐璐上色"},
    {"id": "photo", "label": "写实摄影", "short": "写实", "prompt": "写实摄影风格，自然光，真实的材质与景深"},
    {"id": "watercolor", "label": "水彩", "short": "水彩", "prompt": "水彩画风格，柔和的晕染与纸张肌理"},
    {"id": "flat", "label": "扁平插画", "short": "扁平", "prompt": "扁平矢量插画风格，大色块，简洁的几何造型"},
    {"id": "oil", "label": "油画", "short": "油画", "prompt": "油画风格，可见的笔触与厚涂质感"},
    {"id": "pixel", "label": "像素", "short": "像素", "prompt": "像素艺术风格，有限色板，清晰的像素边缘"},
    {"id": "3d", "label": "3D 渲染", "short": "3D", "prompt": "3D 渲染风格，柔和的全局光照，细腻的材质"},
]

SIZES = [
    {"id": "auto", "label": "自动", "short": "比例", "hint": "由模型决定"},
    {"id": "1024x1024", "label": "方形 1:1", "short": "1:1", "hint": "1024×1024"},
    {"id": "1536x1024", "label": "横版 3:2", "short": "3:2", "hint": "1536×1024"},
    {"id": "1024x1536", "label": "竖版 2:3", "short": "2:3", "hint": "1024×1536"},
    {"id": "1536x864", "label": "宽屏 16:9", "short": "16:9", "hint": "1536×864"},
    {"id": "864x1536", "label": "竖屏 9:16", "short": "9:16", "hint": "864×1536"},
]

QUALITIES = [
    {"id": "auto", "label": "自动", "short": "质量", "hint": "由模型决定"},
    {"id": "low", "label": "快速", "short": "快速", "hint": "low"},
    {"id": "medium", "label": "标准", "short": "标准", "hint": "medium"},
    {"id": "high", "label": "高清", "short": "高清", "hint": "high"},
    {"id": "xhigh", "label": "超清", "short": "超清", "hint": "xhigh"},
    {"id": "max", "label": "极致", "short": "极致", "hint": "max"},
]

COMPLEXITIES = [
    {"id": "default", "label": "默认", "short": "复杂度", "hint": "不发送该参数"},
    {"id": "low", "label": "低", "short": "复杂度 低", "hint": "low"},
    {"id": "medium", "label": "中", "short": "复杂度 中", "hint": "medium"},
    {"id": "high", "label": "高", "short": "复杂度 高", "hint": "high"},
]

# 输出格式：只对 gpt-image 系列显示，请求里用 output_format / background 表达
FORMATS = [
    {"id": "png", "label": "PNG", "short": "PNG", "hint": "不透明背景",
     "output": "png", "transparent": False, "frames": False},
    {"id": "png-transparent", "label": "透明 PNG", "short": "透明 PNG", "hint": "背景透明",
     "output": "png", "transparent": True, "frames": False},
    {"id": "webp", "label": "WebP", "short": "WebP", "hint": "不透明背景",
     "output": "webp", "transparent": False, "frames": False},
    {"id": "webp-transparent", "label": "透明 WebP", "short": "透明 WebP", "hint": "背景透明",
     "output": "webp", "transparent": True, "frames": False},
    {"id": "gif", "label": "GIF 动画", "short": "GIF", "hint": "动态 GIF",
     "output": "gif", "transparent": False, "frames": True},
    {"id": "gif-transparent", "label": "透明 GIF", "short": "透明 GIF", "hint": "动态、背景透明",
     "output": "gif", "transparent": True, "frames": True},
]

MAX_FRAMES = 16
MIN_FRAME_DURATION_MS = 20
MAX_FRAME_DURATION_MS = 2000
DEFAULT_FRAME_COUNT = 9
DEFAULT_FRAME_DURATION_MS = 200

MAX_COUNT = 10  # Images API 的 n 最多到 10
COUNTS = [
    {"id": 1, "label": "1 张", "short": "数量"},
    {"id": 2, "label": "2 张", "short": "2 张"},
    {"id": 3, "label": "3 张", "short": "3 张"},
    {"id": 4, "label": "4 张", "short": "4 张"},
]

OPTIONS = {
    "styles": STYLES,
    "sizes": SIZES,
    "qualities": QUALITIES,
    "complexities": COMPLEXITIES,
    "counts": COUNTS,
    "formats": FORMATS,
}

API_MODES = ("images", "chat")
DEFAULT_MODELS = ["gpt-image-2.6-sunburst", "gpt-image-2.6-flare"]
DEFAULT_TIMEOUT = 300

DEFAULT_LAST = {
    "provider_id": None,
    "model": None,
    "style": "none",
    "size": "auto",
    "quality": "auto",
    "complexity": "default",
    "n": 1,
    "format": "png",
    "frame_count": DEFAULT_FRAME_COUNT,
    "frame_duration_ms": DEFAULT_FRAME_DURATION_MS,
}


def default_data_dir() -> Path:
    """放 config.json、history.db、缩略图和上传的参考图的目录。Linux 上是 ~/.config/seekie-image。"""
    env = os.environ.get("SEEKIE_IMAGE_HOME")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP_DIR_NAME


def default_images_dir(data_dir: Path | None = None) -> Path:
    """生成的图片（和同名 .txt）放在哪：数据目录的 images/ 里。可以用 --images-dir 另外指定。"""
    return (data_dir or default_data_dir()) / "images"


def option_label(group: str, option_id: str) -> str | None:
    for item in OPTIONS[group]:
        if item["id"] == option_id:
            return item["label"]
    return None


def format_option(option_id: str) -> dict:
    for item in FORMATS:
        if item["id"] == option_id:
            return item
    return FORMATS[0]


def supports_format(model: str) -> bool:
    """输出格式、透明背景和 GIF 帧参数只对 gpt-image 系列发送。"""
    return "gpt-image" in (model or "").lower()


def style_prompt(style_id: str) -> str:
    for style in STYLES:
        if style["id"] == style_id:
            return style["prompt"]
    return ""


def clean_provider(raw: dict) -> dict:
    """把前端交来的服务商配置整理成固定形状；格式不对的字段抛 ValueError。"""
    if not isinstance(raw, dict):
        raise ValueError("服务商配置格式不对")
    name = str(raw.get("name") or "").strip()
    base_url = str(raw.get("base_url") or "").strip()
    if not name:
        raise ValueError("服务商需要一个名称")
    if not base_url:
        raise ValueError(f"「{name}」还没有填接口地址")

    models: list[str] = []
    for model in raw.get("models") or []:
        model = str(model).strip()
        if model and model not in models:
            models.append(model)

    extra = raw.get("extra") or {}
    if not isinstance(extra, dict):
        raise ValueError(f"「{name}」的额外参数需要是一个 JSON 对象")

    mode = raw.get("api_mode")
    try:
        timeout = int(raw.get("timeout") or DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT

    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:12]),
        "name": name,
        "base_url": base_url,
        "api_key": str(raw.get("api_key") or "").strip(),
        "api_mode": mode if mode in API_MODES else "images",
        "models": models,
        "extra": extra,
        "stream": bool(raw.get("stream")),
        "timeout": max(30, min(timeout, 1800)),
    }


class Config:
    """config.json 的读写。API Key 以明文保存在用户目录下。"""

    def __init__(self, data_dir: Path):
        self.path = data_dir / "config.json"
        self._lock = threading.Lock()
        self.data = {"providers": [], "last": dict(DEFAULT_LAST)}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text("utf-8"))
            except (OSError, ValueError):
                # 配置损坏时留个备份再用默认值，不直接覆盖掉用户的文件
                self.path.replace(self.path.with_suffix(".json.broken"))
            else:
                if isinstance(loaded.get("providers"), list):
                    self.data["providers"] = loaded["providers"]
                if isinstance(loaded.get("last"), dict):
                    self.data["last"].update(loaded["last"])

    def save(self) -> None:
        with self._lock:
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), "utf-8")
            if os.name == "posix":
                os.chmod(tmp, 0o600)
            tmp.replace(self.path)

    def provider(self, provider_id: str) -> dict | None:
        for provider in self.data["providers"]:
            if provider["id"] == provider_id:
                return provider
        return None

    def set_providers(self, providers: list) -> None:
        self.data["providers"] = [clean_provider(p) for p in providers]
        self.save()

    def remember(self, **last) -> None:
        self.data["last"].update(last)
        self.save()
