"""seekie-image 的安装脚本。

    pip install .            # 只装程序；Linux 上还需要给 pywebview 一个界面后端
    pip install ".[qt]"      # 连 Qt 后端一起装

Linux 上会同时安装 .desktop 启动器和 hicolor 图标（相对安装前缀的 share/ 目录）。
装在虚拟环境或 pipx 里时桌面环境看不到那个目录，装完再执行一次
`seekie-image --install-desktop` 即可，详见 README。
"""

import re
import sys
from pathlib import Path

from setuptools import setup

ROOT = Path(__file__).parent
ASSETS = "seekie_image/assets"

version = re.search(
    r'^__version__ = "([^"]+)"', (ROOT / "seekie_image" / "__init__.py").read_text("utf-8"), re.M
).group(1)

data_files = []
entry_points = {"console_scripts": ["seekie-image = seekie_image.app:main"]}

if sys.platform.startswith("linux"):
    data_files.append(("share/applications", [f"{ASSETS}/seekie-image.desktop"]))
    for icon in sorted((ROOT / ASSETS / "hicolor").glob("*/apps/seekie-image.png")):
        size = icon.parent.parent.name  # 例如 48x48
        data_files.append((f"share/icons/hicolor/{size}/apps", [icon.relative_to(ROOT).as_posix()]))
elif sys.platform == "win32":
    # 不带控制台窗口的入口，给快捷方式用
    entry_points["gui_scripts"] = ["seekie-imagew = seekie_image.app:main"]

setup(
    name="seekie-image",
    version=version,
    description="接 OpenAI 兼容绘图接口（gpt-image 系列、new-api / one-api 中转站）的桌面绘图工具",
    long_description=(ROOT / "README.md").read_text("utf-8"),
    long_description_content_type="text/markdown",
    license="MIT",
    license_files=["LICENSE"],
    url="https://github.com/shellexy/seekie-image",
    project_urls={
        "Source": "https://github.com/shellexy/seekie-image",
        "Issues": "https://github.com/shellexy/seekie-image/issues",
        "Releases": "https://github.com/shellexy/seekie-image/releases",
    },
    python_requires=">=3.10",
    packages=["seekie_image"],
    package_data={
        "seekie_image": [
            "web/*",
            "assets/*.png",
            "assets/*.ico",
            "assets/*.desktop",
            "assets/hicolor/*/apps/*.png",
        ]
    },
    data_files=data_files,
    install_requires=["pywebview>=5.0", "httpx>=0.26", "Pillow>=10.0"],
    extras_require={
        "qt": ["pywebview[qt]>=5.0"],
        "pyside6": ["pywebview[pyside6]>=5.0"],
        "gtk": ["pywebview[gtk]>=5.0"],
    },
    entry_points=entry_points,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Multimedia :: Graphics",
    ],
)
