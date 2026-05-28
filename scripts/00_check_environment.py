from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ENV_KEYS = [
    "TRIPO_API_KEY",
    "MESHY_API_KEY",
    "BLENDER_PATH",
    "UNITY_PROJECT_PATH",
]


def load_env_file(env_path: Path) -> None:
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


def env_status(key: str) -> str:
    return "set" if os.environ.get(key) else "not set"


def check_blender(blender_path: str | None) -> dict:
    result = {
        "path_status": "not set",
        "path_exists": False,
        "executable": False,
        "version": None,
        "warning": None,
        "error": None,
    }

    if not blender_path:
        result["warning"] = "BLENDER_PATH is not set; Blender CLI check was skipped."
        return result

    blender_file = Path(blender_path)
    result["path_status"] = "set"
    result["path_exists"] = blender_file.exists()

    if not blender_file.exists():
        result["warning"] = "BLENDER_PATH is set but the file does not exist."
        return result

    try:
        completed = subprocess.run(
            [blender_path, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except OSError as exc:
        result["error"] = f"Failed to execute Blender: {exc.__class__.__name__}"
        return result
    except subprocess.TimeoutExpired:
        result["error"] = "Blender --version timed out after 30 seconds."
        return result

    result["executable"] = completed.returncode == 0
    output = (completed.stdout or completed.stderr or "").splitlines()
    if output:
        result["version"] = output[0].strip()
    if completed.returncode != 0:
        result["error"] = f"Blender --version returned exit code {completed.returncode}."

    return result


def main() -> int:
    repo_root = Path.cwd()
    env_path = repo_root / ".env"
    reports_dir = repo_root / "output" / "reports"
    report_path = reports_dir / "environment_check.json"

    load_env_file(env_path)

    env_vars = {key: env_status(key) for key in ENV_KEYS}
    blender_result = check_blender(os.environ.get("BLENDER_PATH"))

    warnings = []
    if not env_path.exists():
        warnings.append(".env was not found. Copy .env.example to .env when local settings are needed.")
    for key, status in env_vars.items():
        if status == "not set":
            warnings.append(f"{key} is not set.")
    if blender_result.get("warning"):
        warnings.append(blender_result["warning"])
    if blender_result.get("error"):
        warnings.append(blender_result["error"])

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
        },
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "current_directory": str(repo_root),
        "env_file": {
            "path": str(env_path),
            "exists": env_path.exists(),
        },
        "environment_variables": env_vars,
        "blender": blender_result,
        "warnings": warnings,
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Environment check")
    print(f"- Python: {report['python']['version']}")
    print(f"- OS: {report['os']['system']} {report['os']['release']} ({report['os']['machine']})")
    print(f"- Current directory: {report['current_directory']}")
    print(f"- .env: {'exists' if env_path.exists() else 'not found'}")
    for key in ENV_KEYS:
        print(f"- {key}: {env_vars[key]}")
    print(f"- BLENDER_PATH file exists: {blender_result['path_exists']}")
    print(f"- Blender executable: {blender_result['executable']}")
    if blender_result["version"]:
        print(f"- Blender version: {blender_result['version']}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    print(f"- Report: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
