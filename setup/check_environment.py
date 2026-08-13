"""
check_environment.py
====================
三个人都可以运行这个文件，检查自己的开发环境是否和项目统一。

运行：
    python check_environment.py

检查内容：
1. Python 是否为 3.12.13
2. pygame / mediapipe / OpenCV / numpy / Pillow 版本
3. OpenCV 是否可以正常导入
4. MediaPipe Tasks API 是否存在
5. 摄像头是否能被 OpenCV 打开（只做一次快速检查）

注意：
- hand_landmarker.task / pose_landmarker.task 等模型文件不属于 Python 包。
- 模型文件是否存在，应由项目自己的资源检查逻辑负责。
"""

import sys
from importlib.metadata import PackageNotFoundError, version


EXPECTED = {
    "pygame": "2.6.1",
    "mediapipe": "0.10.35",
    "opencv-contrib-python": "4.11.0.86",
    "numpy": "1.26.4",
    "Pillow": "12.3.0",
    "ipykernel": "7.3.0",
    "torch": "2.13.0",
    "transformers": "5.15.0",
    "safetensors": "0.8.0",
    "open_clip_torch": "3.3.0",
}

EXPECTED_PYTHON = (3, 12, 13)


def check_python() -> bool:
    current = sys.version_info[:3]
    ok = current == EXPECTED_PYTHON

    print("=" * 64)
    print("Python")
    print("-" * 64)
    print(
        f"{'OK' if ok else 'ERROR'}  "
        f"当前版本: {current[0]}.{current[1]}.{current[2]}  "
        f"要求版本: 3.12.13"
    )
    return ok


def check_packages() -> bool:
    all_ok = True

    print("\n" + "=" * 64)
    print("Python Packages")
    print("-" * 64)

    for package, expected_version in EXPECTED.items():
        try:
            current_version = version(package)
            ok = current_version == expected_version
        except PackageNotFoundError:
            current_version = "未安装"
            ok = False

        if not ok:
            all_ok = False

        print(
            f"{'OK' if ok else 'ERROR':5}  "
            f"{package:<24} "
            f"当前: {current_version:<12} "
            f"要求: {expected_version}"
        )

    return all_ok


def check_imports() -> bool:
    print("\n" + "=" * 64)
    print("Import / API")
    print("-" * 64)

    all_ok = True

    try:
        import pygame
        print(f"OK     pygame import 成功 ({pygame.version.ver})")
    except Exception as exc:
        print(f"ERROR  pygame import 失败: {exc}")
        all_ok = False

    try:
        import cv2
        print(f"OK     cv2 import 成功 ({cv2.__version__})")
    except Exception as exc:
        print(f"ERROR  cv2 import 失败: {exc}")
        all_ok = False

    try:
        import numpy as np
        print(f"OK     numpy import 成功 ({np.__version__})")
    except Exception as exc:
        print(f"ERROR  numpy import 失败: {exc}")
        all_ok = False

    try:
        from PIL import Image
        print("OK     Pillow import 成功")
    except Exception as exc:
        print(f"ERROR  Pillow import 失败: {exc}")
        all_ok = False

    try:
        import mediapipe as mp
        if hasattr(mp, "tasks"):
            print("OK     MediaPipe Tasks API 可用")
        else:
            print("ERROR  mediapipe 已导入，但找不到 mp.tasks")
            all_ok = False
    except Exception as exc:
        print(f"ERROR  mediapipe import 失败: {exc}")
        all_ok = False

    return all_ok


def check_camera() -> bool:
    print("\n" + "=" * 64)
    print("Camera")
    print("-" * 64)

    try:
        import cv2

        backends = [("默认后端", cv2.CAP_ANY)]
        if sys.platform.startswith("win"):
            backends = [
                ("DirectShow", cv2.CAP_DSHOW),
                ("Media Foundation", cv2.CAP_MSMF),
                ("默认后端", cv2.CAP_ANY),
            ]

        found = None
        for index in range(4):
            for backend_name, backend in backends:
                cap = cv2.VideoCapture(index, backend)
                opened = cap.isOpened()
                ok, _ = cap.read() if opened else (False, None)
                if opened and ok:
                    found = (index, backend_name)
                    cap.release()
                    break
                cap.release()
            if found is not None:
                break

        if found is not None:
            print(f"OK     摄像头 {found[0]} 可通过 {found[1]} 打开并读取画面")
        else:
            print("WARN   使用索引 0~3 和可用后端均未找到可读取的摄像头")

        # 摄像头不可用不代表 Python 环境版本错误，因此不作为硬失败。
        return True

    except Exception as exc:
        print(f"WARN   摄像头检查失败: {exc}")
        return True


def main() -> int:
    results = [
        check_python(),
        check_packages(),
        check_imports(),
        check_camera(),
    ]

    print("\n" + "=" * 64)

    if all(results):
        print("环境检查通过：核心版本与项目约定一致。")
    else:
        print("环境检查未通过：请按照 requirements.txt 重新安装环境。")

    print("=" * 64)
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
