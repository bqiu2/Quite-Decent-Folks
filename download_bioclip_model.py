"""
download_bioclip_model.py

Download Imageomics BioCLIP into the local project.

Expected final path:
    <project_root>/models/bioclip/open_clip_pytorch_model.bin

Recommended location for this script:
    project root, next to plant_ai/ and shared_game_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HF_REPO_ID = "imageomics/bioclip"
MODEL_FILENAME = "open_clip_pytorch_model.bin"
CONFIG_FILENAME = "open_clip_config.json"


def find_project_root() -> Path:
    """
    Find the nearest parent directory containing both:
        plant_ai/
        shared_game_data.py

    This makes the script independent of the terminal's current directory.
    """
    script_dir = Path(__file__).resolve().parent

    for candidate in (script_dir, *script_dir.parents):
        if (
            (candidate / "plant_ai").is_dir()
            and (candidate / "shared_game_data.py").is_file()
        ):
            return candidate

    # Fallback: script directory itself.
    return script_dir


def get_hf_download():
    try:
        from huggingface_hub import hf_hub_download
        return hf_hub_download
    except ImportError:
        print()
        print("ERROR: huggingface_hub is not installed.")
        print("Current Python:")
        print(f"  {sys.executable}")
        print()
        print("Install it into THIS Python environment with:")
        print(f'  "{sys.executable}" -m pip install huggingface_hub')
        print()
        raise SystemExit(1)


def valid_model_file(path: Path) -> bool:
    if not path.is_file():
        return False

    size_mb = path.stat().st_size / (1024 * 1024)

    # BioCLIP weights are far larger than this.
    return size_mb >= 100


def main() -> None:
    project_root = find_project_root()
    model_dir = project_root / "models" / "bioclip"
    model_path = model_dir / MODEL_FILENAME
    config_path = model_dir / CONFIG_FILENAME

    print()
    print("=" * 72)
    print("BioCLIP local downloader")
    print("=" * 72)
    print(f"Python executable : {sys.executable}")
    print(f"Script path       : {Path(__file__).resolve()}")
    print(f"Project root      : {project_root}")
    print(f"Target directory  : {model_dir}")
    print(f"Target model      : {model_path}")
    print("=" * 72)
    print()

    if valid_model_file(model_path):
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print("BioCLIP is already downloaded.")
        print(f"Model: {model_path.resolve()}")
        print(f"Size : {size_mb:.2f} MB")
        print()
        print("No Hugging Face request is needed.")
        return

    if model_path.exists():
        print("WARNING: An incomplete/suspicious model file already exists.")
        print(f"Path: {model_path}")
        print("The downloader will repair/re-download it.")
        print()

    model_dir.mkdir(parents=True, exist_ok=True)

    hf_hub_download = get_hf_download()

    print(f"Downloading from {HF_REPO_ID} ...")
    print("The first download may take some time.")
    print()

    try:
        downloaded_model = Path(
            hf_hub_download(
                repo_id=HF_REPO_ID,
                filename=MODEL_FILENAME,
                local_dir=str(model_dir),
            )
        ).resolve()

        # Optional but useful for keeping the official config beside the weights.
        try:
            hf_hub_download(
                repo_id=HF_REPO_ID,
                filename=CONFIG_FILENAME,
                local_dir=str(model_dir),
            )
        except Exception as exc:
            print(
                "WARNING: open_clip_config.json could not be downloaded, "
                "but the model weights may still be usable."
            )
            print(f"{type(exc).__name__}: {exc}")
            print()

    except Exception as exc:
        print()
        print("=" * 72)
        print("DOWNLOAD FAILED")
        print("=" * 72)
        print(f"{type(exc).__name__}: {exc}")
        print()
        print("Check network access, disk space, and the Python environment.")
        raise

    if not valid_model_file(model_path):
        print()
        print("ERROR: Download returned but expected local model is invalid.")
        print(f"Expected path : {model_path}")
        print(f"Returned path : {downloaded_model}")
        raise SystemExit(1)

    size_mb = model_path.stat().st_size / (1024 * 1024)

    print()
    print("=" * 72)
    print("SUCCESS")
    print("=" * 72)
    print(f"Model path : {model_path.resolve()}")
    print(f"Model size : {size_mb:.2f} MB")
    if config_path.exists():
        print(f"Config path: {config_path.resolve()}")
    print()
    print("Expected project structure:")
    print(f"{project_root.name}/")
    print("├── plant_ai/")
    print("├── models/")
    print("│   └── bioclip/")
    print("│       ├── open_clip_pytorch_model.bin")
    print("│       └── open_clip_config.json")
    print("├── shared_game_data.py")
    print("└── download_bioclip_model.py")
    print()
    print("Your existing model_loader.py can now load BioCLIP locally.")


if __name__ == "__main__":
    main()
