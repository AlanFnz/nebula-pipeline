#!/usr/bin/env python3
"""
generate.py
generate source video via Kling on Replicate (text-to-video or image-to-video)

verify model IDs at replicate.com/kwaivgi before running — slugs change with versions
"""

import argparse
import os
import sys
from pathlib import Path

import replicate
import requests

MODELS = {
    "text":  "kwaivgi/kling-v1.6-standard-text2video",   # verify slug
    "image": "kwaivgi/kling-v1.6-standard-image2video",  # verify slug
}


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, stream=True)
    r.raise_for_status()
    total = 0
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
            total += len(chunk)
    print(f"  saved {total / 1_000_000:.1f} MB → {dest}")


def run_model(model: str, inputs: dict) -> str:
    result = replicate.run(model, input=inputs)
    return result if isinstance(result, str) else result[0]


def text_to_video(prompt: str, duration: int, aspect: str, output: Path) -> None:
    print(f"text-to-video  model={MODELS['text']}")
    print(f"  prompt : {prompt[:80]}")
    url = run_model(MODELS["text"], {
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect,
    })
    download(url, output)


def image_to_video(image: Path, prompt: str, duration: int, output: Path) -> None:
    print(f"image-to-video  model={MODELS['image']}")
    print(f"  image  : {image}")
    print(f"  prompt : {prompt[:80]}")
    with open(image, "rb") as f:
        url = run_model(MODELS["image"], {
            "image": f,
            "prompt": prompt,
            "duration": duration,
        })
    download(url, output)


def main() -> None:
    p = argparse.ArgumentParser(
        description="generate source video via Kling on Replicate",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mode", choices=["text", "image"], required=True,
                   help="text-to-video or image-to-video")
    p.add_argument("--prompt", required=True, help="generation/motion prompt")
    p.add_argument("--image", type=Path,
                   help="source still image (required for --mode image)")
    p.add_argument("--output", type=Path, required=True,
                   help="output video path, e.g. project/source/clip.mp4")
    p.add_argument("--duration", type=int, default=5,
                   help="clip duration in seconds")
    p.add_argument("--aspect", default="1:1",
                   help="aspect ratio, text mode only (1:1, 16:9, 9:16)")
    args = p.parse_args()

    if not os.environ.get("REPLICATE_API_TOKEN"):
        raise SystemExit("error: REPLICATE_API_TOKEN environment variable not set")

    if args.mode == "image":
        if not args.image:
            raise SystemExit("error: --image is required for --mode image")
        if not args.image.exists():
            raise SystemExit(f"error: image not found: {args.image}")
        image_to_video(args.image, args.prompt, args.duration, args.output)
    else:
        text_to_video(args.prompt, args.duration, args.aspect, args.output)

    print("done")


if __name__ == "__main__":
    main()
