# Workflow

## Basic Workflow

The intended long-term asset pipeline is:

1. Collect raw image observations.
2. Create an image inventory.
3. Select usable input images.
4. Remove backgrounds and review masks.
5. Generate raw 3D assets through a 3D generation provider.
6. Clean and normalize assets with Blender.
7. Export Unity-ready assets.
8. Review reports and iterate.

## Development Workflow

Each implementation task follows this governance flow:

1. ChatGPT creates the task specification.
2. Codex performs the primary implementation.
3. Claude reviews design and code.
4. Gemini reviews API, tool, and implementation concerns.
5. ChatGPT integrates review feedback and classifies it as accepted, deferred, or rejected.
6. The user makes the final decision.
7. Codex implements the next fix or the next task.

## Task Completion Criteria

A task is complete when:

- Implementation is finished.
- `README.md` or files under `docs/` are updated as needed.
- The change summary is explained.
- The next task is stated.
- Review findings are recorded in `docs/review_log.md`.
- Adoption decisions are recorded in `docs/decisions.md`.

## Documentation Rules

- MVP scope, task flow, and execution process belong in `docs/workflow.md`.
- Runtime environment choices, API selections, Blender policy, Unity policy, and other durable decisions belong in `docs/decisions.md`.
- Review findings from ChatGPT, Claude, Gemini, Codex, and the user belong in `docs/review_log.md`.
- MVP tasks and future proposals belong in `docs/backlog.md`.
- Proposals outside the MVP must be moved to `docs/backlog.md` instead of being implemented immediately.

## Task 0 Scope

Task 0 only creates the initial repository structure, configuration files, minimal dependencies, and documentation skeleton.

Task 0 does not implement scripts, external API calls, Blender CLI processing, Unity import processing, or background removal.

Task 0.2 adds GitHub and documentation operation rules. It still does not implement API connectivity, image inventory scripts, image selection, background removal, Blender CLI, or Unity import processing.

## Runtime Environment

The MVP execution policy is Windows venv, Windows `blender.exe`, and Windows paths only. WSL2 and Docker are not used for the MVP pipeline.

## Task 0.5 Environment Check

Task 0.5 checks local external dependencies without generating a 3D model.

Run the check with this process:

1. Copy `.env.example` to `.env`.
2. Set `BLENDER_PATH` in `.env` when Blender CLI should be checked.
3. Run `python scripts/00_check_environment.py` in PowerShell.
4. Review `output/reports/environment_check.json`.
5. Record the chosen runtime policy in `docs/decisions.md`.

`scripts/00_check_environment.py` resolves the repository root from the script location, not from the current working directory. This keeps `.env`, `config/`, and `output/reports/` anchored to this repository even when the script is launched from another directory.

## Task 1 Image Inventory

Task 1 creates an inventory of source images before any selection or image processing.

Run the inventory process with this flow:

1. Put source images under `input/raw_photos/`.
2. Run `python scripts/01_inventory_images.py` in PowerShell.
3. Review `output/reports/image_inventory.json` and `output/reports/image_inventory.csv`.
4. Use Task 1.5 to select suitable images from the inventory.

Task 1 does not copy, move, delete, classify, or edit images. It only records basic metadata, warnings, and read errors for supported image files.

## Task 1.5 Image Selection

Task 1.5 selects candidate images for downstream processing through a human-in-the-loop workflow.

Run the selection process with this flow:

1. Put source images under `input/raw_photos/`.
2. Run `python scripts/01_inventory_images.py` in PowerShell.
3. Review `output/reports/image_inventory.json`.
4. Run `python scripts/015_select_images.py`.
5. For each candidate image, enter `select`, `view_hint`, `quality_score`, and `reason`.
6. Review `input/selected_photos/`, `output/reports/image_selection.json`, and `output/reports/image_selection.csv`.
7. Continue to Task 2 for background removal.

Task 1.5 copies selected images into `input/selected_photos/`. It does not move or delete source images, edit pixels, remove backgrounds, call 3D APIs, run Blender, or import into Unity.

Important selection decisions should use manual mode or human review. Non-interactive mode is only a fallback for pipeline smoke checks and keeps more candidates than it rejects. To reduce path and encoding issues in later API, Blender, and Unity steps, filenames copied into `input/selected_photos/` are converted to ASCII-safe names while source filenames remain unchanged.

## Task 2 Background Removal

Task 2 removes image backgrounds from the selected image set and creates review artifacts before any 3D API calls.

Run the background removal process with this flow:

1. Complete Task 1.5 so selected images exist under `input/selected_photos/`.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run `python scripts/02_remove_backgrounds.py` in PowerShell.
4. Review transparent cutouts and masks under `input/masks/`.
5. Review checkerboard composites under `input/masks_review/`.
6. Review `output/reports/background_removal.json` and `output/reports/background_removal.csv`.
7. Continue to Task 3 for 3D generation API prototyping.

Task 2 writes transparent cutouts as `*_cutout.png`, alpha masks as `*_mask.png`, and review images as `*_review.jpg`. It supports `u2net` and `u2netp` ONNX models, and the first run may download model files to `output/model_cache/u2net/`. Task 2 does not call 3D APIs, run Blender, or import into Unity.

## Task 3 Tripo Image-to-3D Prototype

Task 3 submits a selected background-removed image to Tripo and records both raw API responses and normalized metadata.

Run the prototype process with this flow:

1. Complete Task 2 so cutout images exist under `input/masks/`.
2. Run `python scripts/03_tripo_image_to_3d.py --config config/pipeline.yaml` to inspect the dry-run request plan.
3. Set `TRIPO_API_KEY` in `.env` when a real API call is intended.
4. Run `python scripts/03_tripo_image_to_3d.py --config config/pipeline.yaml --submit --poll`.
5. Review `output/reports/tripo_image_to_3d.json`.
6. Review `output/reports/raw_api_response_tripo_<task_id>.json`.
7. If output URLs are needed locally, rerun or use `--download` before the URLs expire.

Task 3 defaults to dry-run because real Tripo submission can consume credits. It does not run Blender cleanup or import into Unity.

## Blender CLI

Task 4 should call Windows `blender.exe` from the Windows venv. Blender checks should run in background mode with `-b`.

## Task 3 API Response Policy

Task 3 must save raw 3D provider API responses separately from normalized metadata, for example:

```text
output/reports/raw_api_response_tripo_<task_id>.json
```

Raw API response logs are used for debugging provider behavior and future multi-provider comparisons.
