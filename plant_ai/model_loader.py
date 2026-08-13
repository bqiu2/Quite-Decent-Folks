"""
plant_ai/model_loader.py

BioCLIP 本地模型加载器。

运行逻辑：
1. 优先检查：
   models/bioclip/open_clip_pytorch_model.bin
2. 如果存在，直接本地加载，不访问 Hugging Face。
3. 如果不存在，第一次自动从 imageomics/bioclip 下载并保存到本地。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import open_clip
import torch

from .config import DEFAULT_DEVICE, VERBOSE

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_MODEL_DIR = PROJECT_ROOT / "models" / "bioclip"
LOCAL_MODEL_PATH = LOCAL_MODEL_DIR / "open_clip_pytorch_model.bin"

HF_REPO_ID = "imageomics/bioclip"
HF_MODEL_FILENAME = "open_clip_pytorch_model.bin"

# BioCLIP v1 的官方 open_clip_config.json 对应 ViT-B/16
OPEN_CLIP_MODEL_NAME = "ViT-B-16"


@dataclass
class BioCLIPBundle:
    model: Any
    preprocess: Any
    tokenizer: Any
    device: str


_MODEL_BUNDLES: dict[str, BioCLIPBundle] = {}


def download_bioclip_model():
    """
    第一次使用时下载 BioCLIP 权重到项目目录。
    之后将直接读取本地文件。
    """
    LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if LOCAL_MODEL_PATH.exists():
        return LOCAL_MODEL_PATH

    print()
    print("=" * 60)
    print("BioCLIP local model was not found.")
    print("Downloading it once from Hugging Face...")
    print(f"Repository : {HF_REPO_ID}")
    print(f"Save to    : {LOCAL_MODEL_PATH}")
    print("=" * 60)
    print()

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required for the first download.\n"
            "Install it with:\n"
            "    pip install huggingface_hub"
        ) from exc

    downloaded_path = hf_hub_download(
        repo_id=HF_REPO_ID,
        filename=HF_MODEL_FILENAME,
        local_dir=str(LOCAL_MODEL_DIR),
    )

    downloaded_path = Path(downloaded_path)

    if not downloaded_path.exists():
        raise RuntimeError(
            "BioCLIP download finished but the model file was not found."
        )

    print()
    print("BioCLIP download completed.")
    print(f"Local model: {downloaded_path.resolve()}")
    print()

    return downloaded_path


def ensure_local_model(allow_download=True):
    """
    确保本地模型存在。

    allow_download=True:
        不存在时自动下载一次。

    allow_download=False:
        严格离线模式，不存在则直接报错。
    """
    if LOCAL_MODEL_PATH.exists():
        return LOCAL_MODEL_PATH

    if allow_download:
        return download_bioclip_model()

    raise FileNotFoundError(
        "\nBioCLIP local model was not found:\n"
        f"    {LOCAL_MODEL_PATH}\n\n"
        "Run once with Internet access to download it."
    )


def load_bioclip(device=None, allow_download=True):
    """
    加载 BioCLIP。

    本地模型存在后，本函数不会访问 Hugging Face。
    """
    selected_device = device or DEFAULT_DEVICE

    if selected_device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA was requested, but torch.cuda.is_available() returned False."
        )

    cached_bundle = _MODEL_BUNDLES.get(str(selected_device))
    if cached_bundle is not None:
        return cached_bundle

    model_path = ensure_local_model(
        allow_download=allow_download
    )

    if VERBOSE:
        print("=" * 60)
        print("Loading BioCLIP from LOCAL FILE")
        print(f"Architecture : {OPEN_CLIP_MODEL_NAME}")
        print(f"Model file   : {model_path.resolve()}")
        print(f"Device       : {selected_device}")
        print("=" * 60)

    model, _, preprocess = open_clip.create_model_and_transforms(
        OPEN_CLIP_MODEL_NAME,
        pretrained=str(model_path),
    )

    # 使用 OpenCLIP 自带的标准 CLIP tokenizer，
    # 避免再通过 Hugging Face 获取 tokenizer。
    tokenizer = open_clip.get_tokenizer(
        OPEN_CLIP_MODEL_NAME
    )

    model = model.to(selected_device)
    model.eval()

    bundle = BioCLIPBundle(
        model=model,
        preprocess=preprocess,
        tokenizer=tokenizer,
        device=selected_device,
    )
    _MODEL_BUNDLES[str(selected_device)] = bundle

    if VERBOSE:
        print("BioCLIP loaded successfully from local storage.")
        print("=" * 60)

    return bundle


def get_bioclip(device=None, allow_download=True):
    """
    推荐对外接口。

    默认：
    - 第一次缺模型 -> 自动下载
    - 之后 -> 完全本地加载
    """
    return load_bioclip(
        device=device,
        allow_download=allow_download,
    )


def get_local_model_path():
    """
    返回本地模型路径。
    """
    return LOCAL_MODEL_PATH


def is_model_downloaded():
    """
    检查模型是否已经下载到项目中。
    """
    return LOCAL_MODEL_PATH.exists()
