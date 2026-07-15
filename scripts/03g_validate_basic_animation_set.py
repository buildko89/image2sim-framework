from __future__ import annotations

import argparse
import json
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT_GLB = "output/rigged/cat_base_rigged.glb"
DEFAULT_REPORT = "output/reports/task3g_basic_animation_set.json"

REQUIRED_MOTIONS = {
    "idle": ["Idle", "Idle_2"],
    "walk": ["Walk"],
    "jump": ["Jump_ToIdle", "Gallop_Jump"],
    "sleep_or_lie_down": ["Sleep", "LieDown", "Lie_Down", "Rest", "Down"],
}

FALLBACK_MOTIONS = {
    "sleep_or_lie_down": ["Eating", "Idle_2_HeadLow"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the basic animation set in a GLB asset.")
    parser.add_argument("--input", default=DEFAULT_INPUT_GLB, help="Input animated GLB path.")
    parser.add_argument("--report", default=DEFAULT_REPORT, help="Output JSON report path.")
    return parser.parse_args()


def read_glb_json(glb_path: Path) -> dict[str, Any]:
    data = glb_path.read_bytes()
    if len(data) < 20:
        raise ValueError(f"GLB is too small: {glb_path}")
    magic, version, _length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2:
        raise ValueError(f"Unsupported GLB header: {glb_path}")
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError(f"First GLB chunk is not JSON: {glb_path}")
    return json.loads(data[20 : 20 + chunk_length].decode("utf-8"))


def choose_motion(animation_names: list[str], candidates: list[str]) -> str | None:
    existing = set(animation_names)
    for candidate in candidates:
        if candidate in existing:
            return candidate
    return None


def build_motion_map(animation_names: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for motion, candidates in REQUIRED_MOTIONS.items():
        selected = choose_motion(animation_names, candidates)
        fallback = None
        if selected is None:
            fallback = choose_motion(animation_names, FALLBACK_MOTIONS.get(motion, []))
        result[motion] = {
            "required_candidates": candidates,
            "selected_clip": selected,
            "fallback_clip": fallback,
            "status": "available" if selected else "fallback" if fallback else "missing",
        }
    return result


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    input_path = (repo_root / args.input).resolve()
    report_path = (repo_root / args.report).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Animated GLB not found: {input_path}")

    gltf = read_glb_json(input_path)
    animations = gltf.get("animations", [])
    animation_names = [animation.get("name") or f"animation_{index}" for index, animation in enumerate(animations)]
    motion_map = build_motion_map(animation_names)
    missing = [motion for motion, entry in motion_map.items() if entry["status"] == "missing"]
    fallback = [motion for motion, entry in motion_map.items() if entry["status"] == "fallback"]

    report = {
        "task": "Task 3G: Basic Cat Animation Set",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_glb": args.input,
        "animation_count": len(animation_names),
        "skin_count": len(gltf.get("skins", [])),
        "mesh_count": len(gltf.get("meshes", [])),
        "animation_names": animation_names,
        "required_motions": motion_map,
        "summary": {
            "available_count": sum(1 for entry in motion_map.values() if entry["status"] == "available"),
            "fallback_count": len(fallback),
            "missing_count": len(missing),
            "fallback_motions": fallback,
            "missing_motions": missing,
        },
        "mvp_decision": {
            "idle": "Use Idle.",
            "walk": "Use Walk.",
            "jump": "Use Jump_ToIdle first; Gallop_Jump can be reviewed as an energetic jump/gallop variant.",
            "sleep_or_lie_down": "No true sleep/lie-down clip exists. Use Eating or Idle_2_HeadLow only as a temporary rest-like placeholder, then create or source a lie-down clip later.",
        },
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Animations: {len(animation_names)}")
    print(f"Available motions: {report['summary']['available_count']}")
    print(f"Fallback motions: {report['summary']['fallback_count']}")
    print(f"Missing motions: {report['summary']['missing_count']}")
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
