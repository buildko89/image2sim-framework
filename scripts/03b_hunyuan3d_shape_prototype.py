"""Task 3B local image-to-3D prototype using Hunyuan3D shape generation.

This script is part of the free/local-first MVP path. It does not call paid
3D generation APIs. It runs Hunyuan3D shape-only generation and exports a raw
mesh candidate for later Blender import/cleanup.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from PIL import Image

from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Hunyuan3D mini shape-only prototype.")
    parser.add_argument(
        "--input",
        default="input/masks/side_right_1773200710029_cutout.png",
        help="Input RGBA cutout image path.",
    )
    parser.add_argument(
        "--output",
        default="output/raw_3d/local/hunyuan3d/side_right_hunyuan3d_shape.glb",
        help="Output GLB/OBJ/PLY path.",
    )
    parser.add_argument(
        "--model-path",
        default="tencent/Hunyuan3D-2mini",
        help="Hugging Face model path.",
    )
    parser.add_argument(
        "--subfolder",
        default="hunyuan3d-dit-v2-mini",
        help="Model subfolder to load.",
    )
    parser.add_argument("--steps", type=int, default=30, help="Inference steps.")
    parser.add_argument("--octree-resolution", type=int, default=320, help="Mesh octree resolution.")
    parser.add_argument("--num-chunks", type=int, default=20000, help="Chunk count for mesh extraction.")
    parser.add_argument("--seed", type=int, default=12345, help="Random seed.")
    parser.add_argument(
        "--report",
        default="output/reports/task3b_hunyuan3d_shape_prototype.json",
        help="JSON report path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    report_path = Path(args.report)

    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.time()
    image = Image.open(input_path).convert("RGBA")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        args.model_path,
        subfolder=args.subfolder,
        variant="fp16" if device == "cuda" else None,
        device=device,
    )

    generation_started = time.time()
    mesh = pipeline(
        image=image,
        num_inference_steps=args.steps,
        octree_resolution=args.octree_resolution,
        num_chunks=args.num_chunks,
        generator=torch.manual_seed(args.seed),
        output_type="trimesh",
    )[0]
    generation_seconds = time.time() - generation_started

    mesh.export(output_path)

    report = {
        "task": "Task 3B Local Image-to-3D Prototype",
        "provider": "hunyuan3d",
        "mode": "shape_only",
        "paid_api_used": False,
        "input": str(input_path),
        "output": str(output_path),
        "model_path": args.model_path,
        "subfolder": args.subfolder,
        "device": device,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "steps": args.steps,
        "octree_resolution": args.octree_resolution,
        "num_chunks": args.num_chunks,
        "generation_seconds": generation_seconds,
        "total_seconds": time.time() - started,
        "output_exists": output_path.exists(),
        "output_bytes": output_path.stat().st_size if output_path.exists() else 0,
    }

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
