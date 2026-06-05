"""
Download Qwen2.5-VL-3B-Instruct to local storage.

Run:
    python download_model.py
    python download_model.py --model Qwen/Qwen2.5-VL-7B-Instruct   # different model
    python download_model.py --dir D:/models/qwen                   # custom save path
"""

import argparse
from pathlib import Path

DEFAULT_MODEL = "Qwen/Qwen2.5-VL-3B-Instruct"
DEFAULT_DIR   = Path(__file__).parent / "models"


def download(model_id: str, save_dir: Path):
    from huggingface_hub import snapshot_download
    import os

    save_dir = Path(save_dir) / model_id.replace("/", "--")
    save_dir.mkdir(parents=True, exist_ok=True)

    print(f"Model   : {model_id}")
    print(f"Save to : {save_dir}")
    print(f"This may take 5-15 minutes depending on connection speed.")
    print(f"Model size: ~7 GB (weights + tokenizer + processor)\n")

    # Files to skip — not needed for inference or fine-tuning
    ignore = [
        "*.msgpack", "flax_model*", "tf_model*",
        "rust_model*", "*.ot", "*.h5",
    ]

    path = snapshot_download(
        repo_id        = model_id,
        local_dir      = str(save_dir),
        ignore_patterns = ignore,
    )

    print(f"\nDownload complete.")
    print(f"Saved to: {path}")

    # Show what was downloaded
    files = sorted(Path(path).rglob("*"))
    total_gb = sum(f.stat().st_size for f in files if f.is_file()) / 1e9
    print(f"Files: {sum(1 for f in files if f.is_file())}  |  Total size: {total_gb:.2f} GB")
    print()
    print("To use in train_config.yaml, set:")
    print(f'  model:')
    print(f'    name: "{path}"')
    print(f"  (local path — no HuggingFace download needed during training)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"HuggingFace model ID (default: {DEFAULT_MODEL})")
    p.add_argument("--dir",   default=str(DEFAULT_DIR),
                   help=f"Local save directory (default: {DEFAULT_DIR})")
    args = p.parse_args()
    download(args.model, args.dir)
