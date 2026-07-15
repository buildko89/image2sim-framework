from __future__ import annotations

import argparse
import io
import json
import os
import random
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps


DEFAULT_INPUT_BLEND = "output/rigged/cat_tripo_reference_visual_pass.blend"
DEFAULT_TRIPO_GLB = "output/raw_3d/cloud_manual/tripo/calico_cat_v25/calico_cat_v25.glb"
DEFAULT_TEXTURE_DIR = "output/textures/task65_cat_tripo_retexture"
DEFAULT_OUTPUT_BLEND = "output/rigged/cat_tripo_retexture_pass.blend"
DEFAULT_OUTPUT_GLB = "output/clean_3d/cat_tripo_retexture_pass.glb"
DEFAULT_OUTPUT_FBX = "output/clean_3d/cat_tripo_retexture_pass.fbx"
DEFAULT_REPORT = "output/reports/task65_cat_tripo_retexture_pass.json"

TEXTURE_SPECS = {
    "white_fur.png": {
        "base": (236, 226, 205),
        "light": (254, 248, 232),
        "dark": (145, 134, 119),
        "source_mix": 0.22,
        "contrast": 1.35,
    },
    "warm_calico_fur.png": {
        "base": (182, 86, 24),
        "light": (236, 148, 54),
        "dark": (70, 34, 18),
        "source_mix": 0.38,
        "contrast": 1.45,
    },
    "dark_calico_fur.png": {
        "base": (40, 30, 23),
        "light": (105, 78, 56),
        "dark": (8, 7, 6),
        "source_mix": 0.42,
        "contrast": 1.55,
    },
    "cream_shadow_fur.png": {
        "base": (174, 154, 120),
        "light": (226, 204, 166),
        "dark": (88, 76, 62),
        "source_mix": 0.30,
        "contrast": 1.35,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Tripo-derived material textures and apply them to the rigged cat.")
    parser.add_argument("--input", default=DEFAULT_INPUT_BLEND)
    parser.add_argument("--tripo-glb", default=DEFAULT_TRIPO_GLB)
    parser.add_argument("--texture-dir", default=DEFAULT_TEXTURE_DIR)
    parser.add_argument("--output-blend", default=DEFAULT_OUTPUT_BLEND)
    parser.add_argument("--output-glb", default=DEFAULT_OUTPUT_GLB)
    parser.add_argument("--output-fbx", default=DEFAULT_OUTPUT_FBX)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--blender", help="Path to blender executable. Defaults to BLENDER_PATH.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root / path


def repo_relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path.resolve())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_glb_chunks(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError(f"GLB is too small: {path}")
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2:
        raise ValueError(f"Unsupported GLB header: {path}")
    offset = 12
    gltf: dict[str, Any] | None = None
    bin_chunk = b""
    while offset < min(length, len(data)):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset : offset + chunk_length]
        offset += chunk_length
        if chunk_type == 0x4E4F534A:
            gltf = json.loads(chunk.decode("utf-8"))
        elif chunk_type == 0x004E4942:
            bin_chunk = chunk
    if gltf is None:
        raise ValueError(f"GLB JSON chunk not found: {path}")
    return gltf, bin_chunk


def extract_first_base_color_texture(glb_path: Path, output_dir: Path) -> Path:
    gltf, bin_chunk = read_glb_chunks(glb_path)
    materials = gltf.get("materials", [])
    images = gltf.get("images", [])
    textures = gltf.get("textures", [])
    buffer_views = gltf.get("bufferViews", [])

    texture_index = None
    for material in materials:
        pbr = material.get("pbrMetallicRoughness", {})
        if "baseColorTexture" in pbr:
            texture_index = pbr["baseColorTexture"].get("index")
            break
    if texture_index is None:
        raise ValueError("No baseColorTexture found in Tripo GLB.")

    texture = textures[texture_index]
    image_index = texture.get("source")
    if image_index is None:
        raise ValueError("Tripo texture has no source image.")
    image_info = images[image_index]
    output_dir.mkdir(parents=True, exist_ok=True)

    if "bufferView" in image_info:
        view = buffer_views[image_info["bufferView"]]
        offset = int(view.get("byteOffset", 0))
        length = int(view["byteLength"])
        payload = bin_chunk[offset : offset + length]
        ext = ".png" if image_info.get("mimeType") == "image/png" else ".jpg"
        output_path = output_dir / f"tripo_base_color{ext}"
        output_path.write_bytes(payload)
        return output_path

    if "uri" in image_info:
        uri = image_info["uri"]
        source = glb_path.parent / uri
        if not source.exists():
            raise FileNotFoundError(f"External Tripo texture not found: {source}")
        output_path = output_dir / source.name
        output_path.write_bytes(source.read_bytes())
        return output_path

    raise ValueError("Unsupported Tripo image entry.")


def crop_square(image: Image.Image) -> Image.Image:
    width, height = image.size
    size = min(width, height)
    left = (width - size) // 2
    top = (height - size) // 2
    return image.crop((left, top, left + size, top + size))


def blend_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(a[i] * (1.0 - t) + b[i] * t))) for i in range(3))


def colorize_luminance(source: Image.Image, spec: dict[str, Any]) -> Image.Image:
    source = crop_square(source.convert("RGB")).resize((1024, 1024), Image.Resampling.LANCZOS)
    source = ImageEnhance.Contrast(source).enhance(float(spec["contrast"]))
    source_blur = source.filter(ImageFilter.GaussianBlur(radius=0.35))
    gray = ImageOps.autocontrast(ImageOps.grayscale(source_blur), cutoff=1)
    detail = ImageChops.subtract(gray, gray.filter(ImageFilter.GaussianBlur(radius=10)), scale=2.0, offset=128)
    detail = ImageOps.autocontrast(detail, cutoff=2)

    base = spec["base"]
    light = spec["light"]
    dark = spec["dark"]
    source_mix = float(spec["source_mix"])
    output = Image.new("RGB", gray.size, base)
    src_pixels = source.load()
    gray_pixels = gray.load()
    detail_pixels = detail.load()
    out_pixels = output.load()

    for y in range(output.height):
        for x in range(output.width):
            lum = gray_pixels[x, y] / 255.0
            detail_lum = (detail_pixels[x, y] - 128) / 255.0
            t = max(0.0, min(1.0, lum * 0.78 + 0.11 + detail_lum * 0.65))
            color = blend_color(dark, light, t)
            out_pixels[x, y] = blend_color(color, src_pixels[x, y], source_mix)

    return output.filter(ImageFilter.UnsharpMask(radius=1.2, percent=90, threshold=3))


def add_directional_fur(image: Image.Image, spec: dict[str, Any], seed: int) -> Image.Image:
    rng = random.Random(seed)
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    for _ in range(520):
        x = rng.randint(-60, width + 60)
        y = rng.randint(-20, height)
        length = rng.randint(90, 320)
        slant = rng.randint(-35, 35)
        color = spec["light"] if rng.random() < 0.45 else spec["dark"]
        alpha = rng.randint(16, 48)
        draw.line((x, y, x + slant, y + length), fill=(*color, alpha), width=rng.choice([1, 1, 2]))
    return image.filter(ImageFilter.GaussianBlur(radius=0.18))


def generate_tripo_retextures(tripo_texture: Path, texture_dir: Path) -> list[str]:
    source = Image.open(tripo_texture).convert("RGB")
    outputs = []
    for index, (filename, spec) in enumerate(TEXTURE_SPECS.items()):
        image = colorize_luminance(source, spec)
        image = add_directional_fur(image, spec, 6500 + index)
        output_path = texture_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        outputs.append(str(output_path))
    return outputs


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    input_blend = resolve_path(repo_root, args.input)
    tripo_glb = resolve_path(repo_root, args.tripo_glb)
    texture_dir = resolve_path(repo_root, args.texture_dir)
    output_blend = resolve_path(repo_root, args.output_blend)
    output_glb = resolve_path(repo_root, args.output_glb)
    output_fbx = resolve_path(repo_root, args.output_fbx)
    report = resolve_path(repo_root, args.report)
    blender_script = repo_root / "blender" / "cat_texture_experiment_pass.py"
    blender_path = args.blender or os.environ.get("BLENDER_PATH") or r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"

    extracted_texture = extract_first_base_color_texture(tripo_glb, texture_dir)
    texture_outputs = generate_tripo_retextures(extracted_texture, texture_dir)
    plan = {
        "task": "Task 6.5: Tripo Retexture Pass",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "input": repo_relative_path(repo_root, input_blend),
        "tripo_glb": repo_relative_path(repo_root, tripo_glb),
        "extracted_tripo_texture": repo_relative_path(repo_root, extracted_texture),
        "texture_dir": repo_relative_path(repo_root, texture_dir),
        "generated_textures": [repo_relative_path(repo_root, Path(path)) for path in texture_outputs],
        "output_blend": repo_relative_path(repo_root, output_blend),
        "output_glb": repo_relative_path(repo_root, output_glb),
        "output_fbx": repo_relative_path(repo_root, output_fbx),
        "report": repo_relative_path(repo_root, report),
        "blender": blender_path,
        "steps": [
            "extract Tripo v2.5 embedded base color texture from GLB",
            "derive per-material fur textures using Tripo texture luminance and color variation",
            "reuse the texture experiment Blender pass to add UVs and connect textures",
            "export the animated rigged GLB/FBX",
        ],
    }
    write_json(report.with_name("task65_cat_tripo_retexture_pass_plan.json"), plan)

    print("Task 6.5 Tripo retexture pass")
    print(f"- Input Blend: {input_blend}")
    print(f"- Tripo GLB: {tripo_glb}")
    print(f"- Extracted texture: {extracted_texture}")
    print(f"- Texture dir: {texture_dir}")
    print(f"- Output GLB: {output_glb}")
    print(f"- Blender: {blender_path}")

    if args.dry_run:
        print("- Dry-run: Blender was not executed.")
        return 0 if input_blend.exists() and tripo_glb.exists() else 2
    if not input_blend.exists():
        print(f"ERROR: Required input not found: {input_blend}")
        return 2
    if not tripo_glb.exists():
        print(f"ERROR: Tripo GLB not found: {tripo_glb}")
        return 2
    if not Path(blender_path).exists():
        print(f"ERROR: Blender executable not found: {blender_path}")
        return 2

    command = [
        blender_path,
        "--background",
        "--python",
        str(blender_script),
        "--",
        "--input",
        str(input_blend),
        "--texture-dir",
        str(texture_dir),
        "--output-blend",
        str(output_blend),
        "--output-glb",
        str(output_glb),
        "--output-fbx",
        str(output_fbx),
        "--report",
        str(report),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)
    if completed.stdout:
        print(completed.stdout)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr)
    if completed.returncode != 0:
        print(f"ERROR: Blender returned exit code {completed.returncode}.")
        return completed.returncode
    generated_report = json.loads(report.read_text(encoding="utf-8"))
    generated_report["task"] = "Task 6.5: Tripo Retexture Pass"
    generated_report["tripo_source"] = {
        "glb": str(tripo_glb),
        "extracted_base_color_texture": str(extracted_texture),
        "method": "Tripo v2.5 GLB embedded base-color texture extraction, material-specific recolor, UV apply, GLB bake/export",
    }
    generated_report["notes"] = [
        "This pass uses the downloaded Tripo v2.5 model texture as the source texture signal.",
        "It is a retexture/bake experiment on the existing animated rig, not a full surface-to-surface projection transfer.",
        "The exported GLB keeps the rig, skin, and animation set while adding embedded base color textures.",
    ]
    write_json(report, generated_report)
    print(f"- Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
