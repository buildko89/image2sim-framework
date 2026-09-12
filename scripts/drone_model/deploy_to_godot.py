from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path


DEFAULT_SOURCE = Path("output/origin_01_parametric")
DEFAULT_TARGET = Path(r"D:\work_godot\hakoniwa-godot-drone\Models\origin-01")

SYNC_FILES = [
    "origin-01.glb",
    "origin_01_body.glb",
    "origin_01_transporter.glb",
    "propeller_origin_01.glb",
    "origin_01_camera.glb",
    "origin_01_lidar.glb",
    "origin_01_lidar2.glb",
    "parts_param.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Origin-01成果物をhakoniwa-godot-droneへデプロイします。")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--target", default=str(DEFAULT_TARGET))
    parser.add_argument("--dry-run", action="store_true", help="コピーを行わず差分のみ確認します。")
    parser.add_argument("--backup", action="store_true", help="コピー先既存ファイルを.bakとしてバックアップします。")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = Path(args.source).resolve()
    target_dir = Path(args.target).resolve()

    if not source_dir.is_dir():
        print(f"Error: ソースディレクトリが存在しません: {source_dir}", file=sys.stderr)
        return 1
    if not target_dir.is_dir():
        print(f"Error: ターゲットディレクトリが存在しません: {target_dir}", file=sys.stderr)
        return 1

    print(f"=== Origin-01 デプロイ ===")
    print(f"Source: {source_dir}")
    print(f"Target: {target_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY'}")
    print()

    updated_count = 0
    identical_count = 0
    missing_source = 0

    for fname in SYNC_FILES:
        src = source_dir / fname
        dst = target_dir / fname

        if not src.is_file():
            print(f"  [MISSING] {fname} (ソースに存在しません)")
            missing_source += 1
            continue

        src_hash = sha256_file(src)
        dst_exists = dst.is_file()
        dst_hash = sha256_file(dst) if dst_exists else None

        if dst_exists and src_hash == dst_hash:
            print(f"  [IDENTICAL] {fname} ({src.stat().st_size:,} bytes)")
            identical_count += 1
            continue

        status = "NEW" if not dst_exists else "UPDATE"
        print(f"  [{status}] {fname}")
        print(f"           Source: {src.stat().st_size:,} bytes, hash={src_hash[:12]}")
        if dst_exists:
            print(f"           Target: {dst.stat().st_size:,} bytes, hash={dst_hash[:12]}")

        if not args.dry_run:
            if dst_exists and args.backup:
                bak = dst.with_suffix(dst.suffix + ".bak")
                shutil.copy2(dst, bak)
                print(f"           -> Backup: {bak.name}")
            shutil.copy2(src, dst)
            print(f"           -> Deployed to {dst}")
        updated_count += 1

    print()
    print(f"結果サマリ: 更新={updated_count}, 一致={identical_count}, 不足={missing_source}")
    if args.dry_run and updated_count > 0:
        print("※--dry-run のため実際のファイルコピーはスキップされました。反映するには --dry-run なしで実行してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
