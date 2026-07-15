"""Deferred/experimental cloud API prototype; not part of the MVP path.

The MVP now uses free/local/OSS-first semi-automatic 3D generation plus
Blender import/cleanup/export. This Tripo script is retained only for
optional paid/cloud provider experiments and must not run by default.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml


DEFAULT_INPUT_DIR = "input/masks"
DEFAULT_RAW_3D_DIR = "output/raw_3d"
DEFAULT_REPORTS_DIR = "output/reports"
DEFAULT_API_BASE_URL = "https://api.tripo3d.ai/v2/openapi"
DEFAULT_MODEL_VERSION = "v2.5-20250123"
DEFAULT_POLLING_INTERVAL_SEC = 10
DEFAULT_TIMEOUT_SEC = 600
DEFAULT_SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]
FINAL_STATUSES = {"success", "failed", "banned", "expired", "cancelled", "unknown"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deprecated/experimental Tripo image-to-3D generation.")
    parser.add_argument("--input", dest="input_path", help="Input image file or directory.")
    parser.add_argument("--raw-3d-dir", dest="raw_3d_dir", help="Directory for downloaded raw 3D assets.")
    parser.add_argument("--output", dest="reports_dir", help="Output reports directory.")
    parser.add_argument("--config", dest="config_path", help="Pipeline config YAML path.")
    parser.add_argument("--model-version", dest="model_version", help="Tripo model_version.")
    parser.add_argument("--face-limit", dest="face_limit", type=int, help="Optional output face limit.")
    parser.add_argument("--no-texture", action="store_true", help="Set texture=false.")
    parser.add_argument("--no-pbr", action="store_true", help="Set pbr=false.")
    parser.add_argument("--poll", action="store_true", help="Poll until the task reaches a final status.")
    parser.add_argument("--download", action="store_true", help="Download output model URLs after success.")
    parser.add_argument("--submit", action="store_true", help="Actually call Tripo. Without this, only dry-run.")
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


def load_env_file(repo_root: Path) -> None:
    env_path = repo_root / ".env"
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
        return
    except ImportError:
        pass

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(repo_root: Path, config_path: str | None) -> dict[str, Any]:
    if not config_path:
        return {}

    path = resolve_path(repo_root, config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file was not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")

    return data


def settings_from_config(config: dict[str, Any]) -> dict[str, Any]:
    api_config = config.get("api") or {}
    if not isinstance(api_config, dict):
        api_config = {}

    tripo_config = api_config.get("tripo") or {}
    if not isinstance(tripo_config, dict):
        tripo_config = {}

    background_removal = config.get("background_removal") or {}
    if not isinstance(background_removal, dict):
        background_removal = {}

    return {
        "input_dir": tripo_config.get("input_dir", background_removal.get("masks_dir", DEFAULT_INPUT_DIR)),
        "raw_3d_dir": tripo_config.get("raw_3d_dir", "output/raw_3d"),
        "reports_dir": tripo_config.get("reports_dir", config.get("reports_dir", DEFAULT_REPORTS_DIR)),
        "api_base_url": str(tripo_config.get("api_base_url", DEFAULT_API_BASE_URL)).rstrip("/"),
        "model_version": tripo_config.get("model_version", DEFAULT_MODEL_VERSION),
        "polling_interval_sec": int(api_config.get("polling_interval_sec", DEFAULT_POLLING_INTERVAL_SEC)),
        "timeout_sec": int(api_config.get("timeout_sec", DEFAULT_TIMEOUT_SEC)),
        "supported_extensions": sorted(
            {str(ext).lower() for ext in tripo_config.get("supported_extensions", DEFAULT_SUPPORTED_EXTENSIONS)}
        ),
        "texture": bool(tripo_config.get("texture", True)),
        "pbr": bool(tripo_config.get("pbr", True)),
        "download_outputs": bool(tripo_config.get("download_outputs", False)),
    }


def find_input_image(input_path: Path, supported_extensions: list[str]) -> Path | None:
    if input_path.is_file():
        return input_path
    if not input_path.exists():
        return None

    candidates = [
        path
        for path in input_path.rglob("*")
        if path.is_file()
        and path.suffix.lower() in supported_extensions
        and (path.stem.endswith("_cutout") or "_cutout" in path.stem)
    ]
    if not candidates:
        candidates = [
            path
            for path in input_path.rglob("*")
            if path.is_file() and path.suffix.lower() in supported_extensions
        ]

    return sorted(candidates, key=lambda path: str(path).lower())[0] if candidates else None


def file_type_for_tripo(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix == "jpeg":
        return "jpg"
    return suffix


def auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def request_json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Response was not JSON: HTTP {response.status_code}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {payload}")
    if payload.get("code") != 0:
        raise RuntimeError(f"Tripo API error: {payload}")
    return payload


def upload_image(api_base_url: str, api_key: str, image_path: Path) -> tuple[dict[str, Any], str | None]:
    mime_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    with image_path.open("rb") as handle:
        response = requests.post(
            f"{api_base_url}/upload/sts",
            headers=auth_headers(api_key),
            files={"file": (image_path.name, handle, mime_type)},
            timeout=60,
        )
    payload = request_json(response)
    return payload, response.headers.get("X-Tripo-Trace-ID")


def build_generation_payload(image_path: Path, image_token: str, settings: dict[str, Any], face_limit: int | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "image_to_model",
        "model_version": settings["model_version"],
        "file": {
            "type": file_type_for_tripo(image_path),
            "file_token": image_token,
        },
        "texture": settings["texture"],
        "pbr": settings["pbr"],
    }
    if face_limit is not None:
        payload["face_limit"] = face_limit
    return payload


def create_task(api_base_url: str, api_key: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    response = requests.post(
        f"{api_base_url}/task",
        headers={**auth_headers(api_key), "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    return request_json(response), response.headers.get("X-Tripo-Trace-ID")


def get_task(api_base_url: str, api_key: str, task_id: str) -> tuple[dict[str, Any], str | None]:
    response = requests.get(
        f"{api_base_url}/task/{task_id}",
        headers=auth_headers(api_key),
        timeout=60,
    )
    return request_json(response), response.headers.get("X-Tripo-Trace-ID")


def poll_task(api_base_url: str, api_key: str, task_id: str, interval_sec: int, timeout_sec: int) -> list[dict[str, Any]]:
    started = time.monotonic()
    responses: list[dict[str, Any]] = []

    while True:
        payload, trace_id = get_task(api_base_url, api_key, task_id)
        payload["_trace_id"] = trace_id
        responses.append(payload)
        status = (payload.get("data") or {}).get("status")
        if status in FINAL_STATUSES:
            return responses
        if time.monotonic() - started >= timeout_sec:
            return responses
        time.sleep(interval_sec)


def output_urls(task_payload: dict[str, Any]) -> dict[str, str]:
    data = task_payload.get("data") or {}
    output = data.get("output") or {}
    return {
        key: value
        for key, value in output.items()
        if key in {"model", "base_model", "pbr_model", "rendered_image", "generated_image"}
        and isinstance(value, str)
        and value.startswith(("http://", "https://"))
    }


def download_outputs(raw_3d_dir: Path, task_id: str, urls: dict[str, str]) -> dict[str, str]:
    raw_3d_dir.mkdir(parents=True, exist_ok=True)
    downloaded: dict[str, str] = {}
    for key, url in urls.items():
        suffix = Path(url.split("?", 1)[0]).suffix or ".bin"
        output_path = raw_3d_dir / f"tripo_{task_id}_{key}{suffix}"
        response = requests.get(url, timeout=120)
        if response.status_code >= 400:
            continue
        output_path.write_bytes(response.content)
        downloaded[key] = str(output_path)
    return downloaded


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    args = parse_args()
    print("WARNING: This Tripo prototype is deprecated for the MVP and experimental only.")
    print("The default MVP path is Blender-first and does not require paid 3D generation APIs.")
    repo_root = Path(__file__).resolve().parent.parent
    load_env_file(repo_root)

    try:
        config = load_config(repo_root, args.config_path)
        settings = settings_from_config(config)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}")
        return 1

    if args.model_version:
        settings["model_version"] = args.model_version
    if args.no_texture:
        settings["texture"] = False
    if args.no_pbr:
        settings["pbr"] = False

    input_path = resolve_path(repo_root, args.input_path or settings["input_dir"])
    raw_3d_dir = resolve_path(repo_root, args.raw_3d_dir or settings["raw_3d_dir"])
    reports_dir = resolve_path(repo_root, args.reports_dir or settings["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)

    image_path = find_input_image(input_path, settings["supported_extensions"])
    if image_path is None:
        print(f"ERROR: No input image was found: {input_path}")
        return 1

    api_key = os.environ.get("TRIPO_API_KEY", "")
    dry_run = not args.submit
    planned_payload = build_generation_payload(image_path, "DRY_RUN_IMAGE_TOKEN", settings, args.face_limit)
    report: dict[str, Any] = {
        "project": "image2sim-framework",
        "task": "Optional/Deferred - Tripo Image-to-3D Prototype",
        "schema_version": "0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run" if dry_run else "submit",
        "provider": "tripo",
        "api_base_url": settings["api_base_url"],
        "input_image": repo_relative_path(repo_root, image_path),
        "planned_request": planned_payload,
        "task_id": None,
        "status": None,
        "output_urls": {},
        "downloaded_files": {},
        "raw_response_files": [],
        "trace_ids": [],
        "errors": [],
    }

    if dry_run:
        report_path = reports_dir / "tripo_image_to_3d_dry_run.json"
        write_json(report_path, report)
        print("Deprecated/experimental Tripo image-to-3D prototype")
        print("- Mode: dry-run")
        print(f"- Input image: {repo_relative_path(repo_root, image_path)}")
        print(f"- Planned task endpoint: {settings['api_base_url']}/task")
        print(f"- Report: {report_path}")
        return 0

    if not api_key:
        print("ERROR: TRIPO_API_KEY is not set. Add it to .env or the environment, then rerun with --submit.")
        return 1

    try:
        upload_payload, upload_trace_id = upload_image(settings["api_base_url"], api_key, image_path)
        if upload_trace_id:
            report["trace_ids"].append(upload_trace_id)
        image_token = (upload_payload.get("data") or {}).get("image_token")
        if not image_token:
            raise RuntimeError(f"Upload response did not include image_token: {upload_payload}")

        generation_payload = build_generation_payload(image_path, image_token, settings, args.face_limit)
        create_payload, create_trace_id = create_task(settings["api_base_url"], api_key, generation_payload)
        if create_trace_id:
            report["trace_ids"].append(create_trace_id)
        task_id = (create_payload.get("data") or {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"Task response did not include task_id: {create_payload}")

        raw_response_path = reports_dir / f"raw_api_response_tripo_{task_id}.json"
        raw_report = {
            "upload": upload_payload,
            "create_task": create_payload,
            "poll": [],
        }
        report["task_id"] = task_id
        report["planned_request"] = generation_payload

        final_payload = create_payload
        if args.poll:
            poll_payloads = poll_task(
                settings["api_base_url"],
                api_key,
                task_id,
                settings["polling_interval_sec"],
                settings["timeout_sec"],
            )
            raw_report["poll"] = poll_payloads
            final_payload = poll_payloads[-1] if poll_payloads else create_payload
            for payload in poll_payloads:
                trace_id = payload.get("_trace_id")
                if trace_id:
                    report["trace_ids"].append(trace_id)

        data = final_payload.get("data") or {}
        report["status"] = data.get("status")
        report["output_urls"] = output_urls(final_payload)
        if args.download or settings["download_outputs"]:
            downloaded = download_outputs(raw_3d_dir, task_id, report["output_urls"])
            report["downloaded_files"] = {
                key: repo_relative_path(repo_root, Path(path))
                for key, path in downloaded.items()
            }

        write_json(raw_response_path, raw_report)
        report["raw_response_files"].append(repo_relative_path(repo_root, raw_response_path))
    except (RuntimeError, OSError, requests.RequestException) as exc:
        report["errors"].append(str(exc))

    report_path = reports_dir / "tripo_image_to_3d.json"
    write_json(report_path, report)

    print("Deprecated/experimental Tripo image-to-3D prototype")
    print("- Mode: submit")
    print(f"- Input image: {repo_relative_path(repo_root, image_path)}")
    print(f"- Task ID: {report['task_id'] or 'none'}")
    print(f"- Status: {report['status'] or 'unknown'}")
    print(f"- Errors: {len(report['errors'])}")
    print(f"- Report: {report_path}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
