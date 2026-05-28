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

No external API connectivity is verified in Task 0 or Task 0.2.

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

- Task 1: Input image inventory creation
- Task 1.5: Image selection
- Task 2: Background removal

The next implementation task should be Task 1. Task 0.5 created the environment check entry point, and runtime policy details should be recorded in `docs/decisions.md` before Task 4.

## Git Safety

Do not commit:

- API keys or secrets
- `.env`
- raw photos
- selected photos
- masks and mask review outputs
- generated 3D assets such as `.glb`, `.fbx`, `.obj`, `.blend`
- generated reports and intermediate artifacts
