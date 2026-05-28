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

The execution policy for Windows venv, WSL2 venv, or Docker will be decided in Task 0.5.

## Task 0.5 Environment Check

Task 0.5 checks local external dependencies without generating a 3D model.

Run the check with this process:

1. Copy `.env.example` to `.env`.
2. Set `BLENDER_PATH` in `.env` when Blender CLI should be checked.
3. Run `python scripts/00_check_environment.py` in PowerShell.
4. Review `output/reports/environment_check.json`.
5. Record the chosen runtime policy in `docs/decisions.md`.

## Blender CLI

The Blender CLI execution policy, including whether to call Windows Blender or Linux Blender inside WSL2, will be decided in Task 0.5.
