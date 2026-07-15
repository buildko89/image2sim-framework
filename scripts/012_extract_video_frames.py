from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2


DEFAULT_INPUT_DIR = "input/raw_photos/Movies"
DEFAULT_OUTPUT_DIR = "input/raw_photos/video_frames"
DEFAULT_REPORTS_DIR = "output/reports"
DEFAULT_EXTENSIONS = [".mp4", ".mov", ".m4v"]
DEFAULT_INTERVAL_SECONDS = 1.0
DEFAULT_MAX_FRAMES_PER_VIDEO = 12
DEFAULT_MIN_SHARPNESS = 50.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract candidate still images from cat videos.")
    parser.add_argument("--input", default=DEFAULT_INPUT_DIR, help="Input movie directory.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output frame image directory.")
    parser.add_argument("--reports-dir", default=DEFAULT_REPORTS_DIR, help="Output reports directory.")
    parser.add_argument("--interval-seconds", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--max-frames-per-video", type=int, default=DEFAULT_MAX_FRAMES_PER_VIDEO)
    parser.add_argument("--min-sharpness", type=float, default=DEFAULT_MIN_SHARPNESS)
    parser.add_argument("--dry-run", action="store_true", help="Report planned frames without writing images.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-video progress output.")
    return parser.parse_args()


def repo_relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path.resolve())


def video_files(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in DEFAULT_EXTENSIONS
    )


def sharpness_score(frame: Any) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def select_frame_indices(frame_count: int, fps: float, interval_seconds: float, max_frames: int) -> list[int]:
    if frame_count <= 0 or fps <= 0 or max_frames <= 0:
        return []

    step = max(1, int(round(fps * interval_seconds)))
    indices = list(range(0, frame_count, step))
    if len(indices) <= max_frames:
        return indices

    stride = len(indices) / max_frames
    selected = []
    for i in range(max_frames):
        selected.append(indices[min(len(indices) - 1, int(math.floor(i * stride)))])
    return sorted(set(selected))


def extract_video(
    repo_root: Path,
    video_path: Path,
    output_dir: Path,
    interval_seconds: float,
    max_frames: int,
    min_sharpness: float,
    dry_run: bool,
    video_number: int,
    video_total: int,
    quiet: bool,
) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {
            "video": repo_relative_path(repo_root, video_path),
            "error": "could_not_open_video",
            "frames": [],
        }

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration_seconds = frame_count / fps if fps > 0 else None
    indices = select_frame_indices(frame_count, fps, interval_seconds, max_frames)

    if not quiet:
        duration_text = f"{duration_seconds:.1f}s" if duration_seconds is not None else "unknown duration"
        print(
            f"[{video_number}/{video_total}] {video_path.name}: "
            f"{width}x{height}, {duration_text}, planned frames={len(indices)}"
        )

    frames = []
    try:
        for index_number, frame_index in enumerate(indices, start=1):
            if not quiet and (index_number == 1 or index_number == len(indices) or index_number % 5 == 0):
                print(f"  frame {index_number}/{len(indices)}")

            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                frames.append(
                    {
                        "frame_index": frame_index,
                        "error": "could_not_read_frame",
                    }
                )
                continue

            score = sharpness_score(frame)
            timestamp_seconds = frame_index / fps if fps > 0 else None
            output_name = f"{video_path.stem}_frame_{frame_index:06d}.jpg"
            output_path = output_dir / output_name
            accepted = score >= min_sharpness

            if accepted and not dry_run:
                output_dir.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(output_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

            frames.append(
                {
                    "frame_index": frame_index,
                    "timestamp_seconds": timestamp_seconds,
                    "sharpness": score,
                    "accepted": accepted,
                    "output_file": repo_relative_path(repo_root, output_path) if accepted else None,
                }
            )
    finally:
        cap.release()

    accepted_count = sum(1 for frame in frames if frame.get("accepted"))
    if not quiet:
        print(f"  accepted {accepted_count}/{len(frames)}")

    return {
        "video": repo_relative_path(repo_root, video_path),
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": duration_seconds,
        "width": width,
        "height": height,
        "planned_frame_count": len(indices),
        "accepted_frame_count": accepted_count,
        "frames": frames,
    }


def write_csv(report_path: Path, records: list[dict[str, Any]]) -> None:
    rows = []
    for record in records:
        for frame in record.get("frames", []):
            rows.append(
                {
                    "video": record.get("video"),
                    "width": record.get("width"),
                    "height": record.get("height"),
                    "fps": record.get("fps"),
                    "duration_seconds": record.get("duration_seconds"),
                    "frame_index": frame.get("frame_index"),
                    "timestamp_seconds": frame.get("timestamp_seconds"),
                    "sharpness": frame.get("sharpness"),
                    "accepted": frame.get("accepted"),
                    "output_file": frame.get("output_file"),
                    "error": frame.get("error"),
                }
            )

    fieldnames = [
        "video",
        "width",
        "height",
        "fps",
        "duration_seconds",
        "frame_index",
        "timestamp_seconds",
        "sharpness",
        "accepted",
        "output_file",
        "error",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_reports(
    repo_root: Path,
    reports_dir: Path,
    input_dir: Path,
    output_dir: Path,
    args: argparse.Namespace,
    videos: list[Path],
    records: list[dict[str, Any]],
    interrupted: bool,
) -> tuple[Path, Path, int]:
    accepted_total = sum(record.get("accepted_frame_count", 0) for record in records)
    report = {
        "task": "Video frame extraction for image selection",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "interrupted": interrupted,
        "input_dir": repo_relative_path(repo_root, input_dir),
        "output_dir": repo_relative_path(repo_root, output_dir),
        "interval_seconds": args.interval_seconds,
        "max_frames_per_video": args.max_frames_per_video,
        "min_sharpness": args.min_sharpness,
        "video_count": len(videos),
        "processed_video_count": len(records),
        "accepted_frame_count": accepted_total,
        "videos": records,
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "video_frame_extraction.json"
    csv_path = reports_dir / "video_frame_extraction.csv"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(csv_path, records)
    return json_path, csv_path, accepted_total


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    input_dir = (repo_root / args.input).resolve()
    output_dir = (repo_root / args.output).resolve()
    reports_dir = (repo_root / args.reports_dir).resolve()

    if not input_dir.exists():
        raise FileNotFoundError(f"Video input directory was not found: {input_dir}")

    videos = video_files(input_dir)
    records: list[dict[str, Any]] = []
    interrupted = False

    try:
        for video_number, video_path in enumerate(videos, start=1):
            records.append(
                extract_video(
                    repo_root=repo_root,
                    video_path=video_path,
                    output_dir=output_dir,
                    interval_seconds=args.interval_seconds,
                    max_frames=args.max_frames_per_video,
                    min_sharpness=args.min_sharpness,
                    dry_run=args.dry_run,
                    video_number=video_number,
                    video_total=len(videos),
                    quiet=args.quiet,
                )
            )
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupted by user. Writing partial video frame extraction report...")

    json_path, csv_path, accepted_total = write_reports(
        repo_root=repo_root,
        reports_dir=reports_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        args=args,
        videos=videos,
        records=records,
        interrupted=interrupted,
    )

    print(f"Videos: {len(videos)}")
    print(f"Processed videos: {len(records)}")
    print(f"Accepted frames: {accepted_total}")
    print(f"Output dir: {repo_relative_path(repo_root, output_dir)}")
    print(f"Report JSON: {repo_relative_path(repo_root, json_path)}")
    print(f"Report CSV: {repo_relative_path(repo_root, csv_path)}")
    return 130 if interrupted else 0


if __name__ == "__main__":
    raise SystemExit(main())
