# image2sim-framework

`image2sim-framework` is a semi-automated pipeline project for generating simulation-ready 3D assets from image observation data.

The first reference case is `cat_avatar`: generating a Unity-displayable 3D cat model from cat photos. The current target is cat photos, but the long-term goal is a reusable framework that can turn images into 3D assets for simulation, games, robotics, and digital twin workflows.

## MVP Goal

The MVP verifies a practical path from input images to a 3D asset that can be reviewed and used in Unity.

Task 0 only creates the initial repository structure. It does not yet implement image inventory, background removal, 3D generation API calls, Blender CLI processing, or Unity import automation.

## Setup

The examples below assume Windows PowerShell.

Check Python:

```powershell
python --version
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a local environment file from the template:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` locally and set API keys or tool paths as needed. Do not commit `.env`.

## Repository Layout

```text
image2sim-framework/
  config/
    pipeline.yaml
  input/
    raw_photos/
    selected_photos/
    masks/
    masks_review/
  output/
    raw_3d/
    clean_3d/
    unity/
    reports/
  scripts/
  blender/
  unity/
  docs/
```

Input images, masks, generated 3D files, Unity exports, reports, API keys, and other local artifacts are excluded from Git. Empty working directories are preserved with `.gitkeep`.

## Current Status

Task 0 is complete: the initial repository structure, configuration template, minimal Python dependencies, and documentation skeleton are present.

Task 0.2 adds documentation governance for multi-agent review and Codex implementation.

Task 0.5 adds local environment checking and records the MVP runtime policy.

Task 1 adds image inventory reports for source photos. It does not perform image selection.

Task 1.5 adds a human-in-the-loop image selection flow and a simple non-interactive fallback.

Task 2 adds background removal and mask review outputs for selected images.

## Task 0.5 Environment Check

Task 0.5 verifies local environment readiness for later 3D generation and Blender CLI tasks. It does not call Tripo, Meshy, rembg, Blender cleanup scripts, or Unity import automation.

Create a local `.env` file:

```powershell
copy .env.example .env
```

Set `BLENDER_PATH` in `.env` if Blender CLI should be checked. Leave API keys empty until they are needed; the environment check only reports `set` or `not set` and never prints key values.

Run the check:

```powershell
python scripts/00_check_environment.py
```

The script resolves the repository root from its own file location, so `.env` and `output/reports/environment_check.json` are still read and written under this repository even when the command is launched from another directory.

When using the project virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/00_check_environment.py
```

The check writes:

```text
output/reports/environment_check.json
```

Use the report to decide and record the runtime policy in `docs/decisions.md` before implementing Blender automation in Task 4.

## Task 1 Image Inventory

Task 1 scans `input/raw_photos/` and writes an inventory report before image selection. It does not select, copy, move, edit, classify, or score images.

Run with default paths:

```powershell
python scripts/01_inventory_images.py
```

Run with explicit input and output paths:

```powershell
python scripts/01_inventory_images.py --input input/raw_photos --output output/reports
```

Run with pipeline config:

```powershell
python scripts/01_inventory_images.py --config config/pipeline.yaml
```

The script writes:

```text
output/reports/image_inventory.json
output/reports/image_inventory.csv
```

Warning rules:

- `low_resolution`: width or height is below 1024 pixels.
- `extreme_aspect_ratio`: aspect ratio is below 0.5 or above 2.0.
- `small_file_size`: file size is below 100000 bytes.
- `has_alpha_channel`: Pillow mode is `RGBA` or `LA`.
- `missing_exif`: no EXIF metadata is present.

Task 1.5 uses the inventory to select suitable images. Selection criteria, angle classification, background removal, API calls, Blender processing, and Unity import are outside Task 1.

## Task 1.5 Image Selection

Task 1.5 reads `output/reports/image_inventory.json`, records human selection decisions, and copies selected images to `input/selected_photos/`. Source images are never deleted or moved.

Run the manual selection flow:

```powershell
python scripts/015_select_images.py
```

Run with explicit paths:

```powershell
python scripts/015_select_images.py --inventory output/reports/image_inventory.json --selected-dir input/selected_photos --output output/reports
```

Run with pipeline config:

```powershell
python scripts/015_select_images.py --config config/pipeline.yaml
```

Run the non-interactive fallback:

```powershell
python scripts/015_select_images.py --non-interactive
```

The non-interactive mode is a simple MVP fallback for CI or batch smoke checks. It prioritizes keeping candidates so the pipeline can keep moving. It selects valid images with no warnings, also allowing `missing_exif`, `has_alpha_channel`, and `low_resolution`. It rejects images with `extreme_aspect_ratio` or `small_file_size`. Manual review is recommended for real selection.

The script writes:

```text
input/selected_photos/
output/reports/image_selection.json
output/reports/image_selection.csv
```

Selected copies include the view hint in the filename, for example `input/selected_photos/side_left_cat001.jpg`. Filenames copied into `input/selected_photos/` are converted to ASCII-safe names for later API, Blender, and Unity steps. Source filenames are not changed. Filename collisions are avoided with numeric suffixes.

Valid `view_hint` values:

- `front`
- `front_left`
- `front_right`
- `side_left`
- `side_right`
- `back`
- `back_left`
- `back_right`
- `top`
- `diagonal`
- `unknown`

`quality_score` values:

- `1`: do not use
- `2`: weak
- `3`: normal
- `4`: good
- `5`: very good

In manual mode, `reason` can be left blank. Blank reasons are saved as `manual selection` for selected images and `manual rejection` for rejected images.

Task 1.5 only selects and copies images. Image editing, background removal, Vision AI classification, API calls, Blender processing, and Unity import are outside this task. Task 2 performs background removal on selected images.

## Task 2 Background Removal

Task 2 reads selected images from `input/selected_photos/`, removes backgrounds, and writes review artifacts. Source images and selected images are not modified.

Run with default paths:

```powershell
python scripts/02_remove_backgrounds.py
```

Run with explicit paths:

```powershell
python scripts/02_remove_backgrounds.py --input input/selected_photos --masks-dir input/masks --review-dir input/masks_review --output output/reports
```

Run with pipeline config:

```powershell
python scripts/02_remove_backgrounds.py --config config/pipeline.yaml
```

Use a specific U2Net-family model:

```powershell
python scripts/02_remove_backgrounds.py --model u2netp
```

The script writes:

```text
input/masks/*_cutout.png
input/masks/*_mask.png
input/masks_review/*_review.jpg
output/model_cache/u2net/
output/reports/background_removal.json
output/reports/background_removal.csv
```

Review images are checkerboard composites for quick visual inspection of edge quality and missing foreground. The report records foreground coverage and warns on very low or very high alpha coverage. The first run may download U2Net model files to `output/model_cache/u2net/`.

Task 2 only removes backgrounds and creates mask review outputs. It supports `u2net` and `u2netp` ONNX models. 3D API calls, Blender processing, and Unity import are outside this task.

## Development Workflow

This project uses multiple AI roles plus final user approval:

- ChatGPT: PM and architect. Creates task specs, integrates reviews, and organizes accepted/deferred/rejected decisions.
- Codex: Primary implementation agent. Edits the repository and reports changed files and next tasks.
- Claude: Secondary design and code reviewer.
- Gemini: Secondary reviewer for APIs, tools, runtime boundaries, and implementation risks.
- User: Final decision maker.

Documentation is the source of truth for project operation:

- `docs/workflow.md`: development workflow, task completion criteria, and execution policy notes.
- `docs/decisions.md`: durable decisions such as runtime environment, API provider, Blender policy, and Unity policy.
- `docs/review_log.md`: review findings and action classification from ChatGPT, Claude, Gemini, Codex, and the user.
- `docs/backlog.md`: MVP tasks and future/non-MVP ideas.
- `docs/task_template.md`: template for future task specifications.
- `docs/review_template.md`: template for future review records.
- `docs/decision_template.md`: template for future decision records.

## Upcoming Tasks

- Task 3: 3D generation API prototype
- Task 4: Blender CLI cleanup

The next implementation task should be Task 3. Task 2 creates the background-removed image set used as input for 3D generation.

## Git Safety

Do not commit:

- API keys or secrets
- `.env`
- raw photos
- selected photos
- masks and mask review outputs
- generated 3D assets such as `.glb`, `.fbx`, `.obj`, `.blend`
- generated reports and intermediate artifacts
