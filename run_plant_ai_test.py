"""
run_plant_ai_test.py

最终测试脚本。

直接运行：
    python run_plant_ai_test.py

会自动查找：
    test1.png
    image.png
    test.jpg

也可以手动指定：
    python run_plant_ai_test.py test2.png

查看六维原始概率：
    python run_plant_ai_test.py test2.png --debug-health
"""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path


DEFAULT_IMAGES = (
    "test1.png",
    "image.png",
    "test.jpg",
    "test2.png",
    "test3.jpg",
    "test4.jpg",
)


def find_default_image() -> Path | None:
    """在当前项目目录中自动找一张测试图片。"""
    for name in DEFAULT_IMAGES:
        path = Path(name)
        if path.exists() and path.is_file():
            return path
    return None


def print_status(plant):
    print()
    print("=" * 70)
    print("Plant AI Test Result")
    print("=" * 70)

    print(f"plant_id      : {plant.plant_id}")
    print(f"plant_type    : {plant.plant_type}")
    print(f"image_path    : {plant.image_path}")

    print()
    print("PlantStatus  (0.0 ~ 1.0, higher = healthier)")
    print("-" * 70)

    print(f"water         : {plant.status.water:.4f}")
    print(f"light         : {plant.status.light:.4f}")
    print(f"nitrogen      : {plant.status.nitrogen:.4f}")
    print(f"phosphorus    : {plant.status.phosphorus:.4f}")
    print(f"potassium     : {plant.status.potassium:.4f}")
    print(f"pest          : {plant.status.pest:.4f}")

    print()
    print(f"initial_power : {plant.initial_power:.2f}")
    print(f"current_power : {plant.current_power:.2f}")

    print("=" * 70)


def main():
    # 这行故意放在最前面。
    # 如果连这行都看不到，就不是 AI 代码问题，而是 Python 解释器调用问题。
    print("run_plant_ai_test.py started.", flush=True)

    parser = argparse.ArgumentParser(
        description="Test plant_ai BioCLIP pipeline."
    )

    parser.add_argument(
        "image",
        nargs="?",
        default=None,
        help="Optional plant image path.",
    )

    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default=None,
        help="Force CPU or CUDA.",
    )

    parser.add_argument(
        "--debug-health",
        action="store_true",
        help="Print raw BioCLIP health probabilities.",
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # 1. 确定测试图片
    # ---------------------------------------------------------

    if args.image is not None:
        image_path = Path(args.image)
    else:
        image_path = find_default_image()

        if image_path is None:
            print()
            print("ERROR: No test image was found.")
            print()
            print("Put one of these files in the project root:")
            for name in DEFAULT_IMAGES:
                print(f"  {name}")
            print()
            print("Or run:")
            print("  python run_plant_ai_test.py path_to_image.jpg")
            sys.exit(1)

    if not image_path.exists():
        print(f"ERROR: Image not found: {image_path}")
        sys.exit(1)

    print(f"Input image: {image_path.resolve()}", flush=True)

    # ---------------------------------------------------------
    # 2. 导入项目
    # ---------------------------------------------------------

    print("Importing plant_ai...", flush=True)

    try:
        from plant_ai import (
            analyze_plant,
            analyze_health_debug,
        )
    except Exception as exc:
        print()
        print("ERROR while importing plant_ai")
        print("=" * 70)
        print(f"{type(exc).__name__}: {exc}")
        print()

        print("Python executable:")
        print(sys.executable)
        print()

        raise

    print("plant_ai imported successfully.", flush=True)

    # ---------------------------------------------------------
    # 3. 正式分析
    # ---------------------------------------------------------

    print("Running BioCLIP analysis...", flush=True)

    try:
        plant = analyze_plant(
            str(image_path),
            device=args.device,
        )
    except Exception as exc:
        print()
        print("ERROR while analyzing plant")
        print("=" * 70)
        print(f"{type(exc).__name__}: {exc}")
        print()
        print("Python executable:")
        print(sys.executable)
        print()

        raise

    print_status(plant)

    # ---------------------------------------------------------
    # 4. Debug 六维原始概率
    # ---------------------------------------------------------

    if args.debug_health:
        print()
        print("=" * 70)
        print("BioCLIP Health Debug")
        print("=" * 70)

        debug = analyze_health_debug(
            str(image_path),
            device=args.device,
        )

        for name, item in debug.items():
            print(
                f"{name:<12} "
                f"final={item['value']:.4f}  "
                f"raw_health={item['raw_healthy_probability']:.4f}  "
                f"raw_stress={item['raw_stress_probability']:.4f}  "
                f"confidence={item['confidence']:.4f}"
            )

    print()
    print("PlantData as dict:")
    print(asdict(plant))

    print()
    print("Test finished successfully.", flush=True)


if __name__ == "__main__":
    main()
