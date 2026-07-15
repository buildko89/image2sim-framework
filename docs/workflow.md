# Workflow

## Basic Workflow

The intended MVP asset pipeline is now an animation-capable rigged cat workflow:

1. Task 1: image inventory.
2. Task 1.5: image selection.
3. Task 2: background removal.
4. Task 3A: free/local image-to-3D survey.
5. Task 3B: local image-to-3D prototype for a static reference/shape candidate.
6. Task 3C: Blender import and normalize for the generated static reference model.
7. Task 3D: rigged cat base model route survey.
8. Task 3E: rigged cat base model preparation.
9. Task 3F: appearance / shape transfer planning.
10. Task 3G: basic cat animation set.
11. Task 4: Blender rig cleanup and animation export.
12. Task 5: Godot animated import/playback check.
13. Task 5.7: Godot animation review scene.
14. Task 6: Unity animated import/playback check. Deferred for now.
15. Task 7: Unreal animated import/playback check. Deferred for now.

Blender remains central, but it is not defined as a fully manual modeling-only step. Blender is responsible for automated import, cleanup, normalization, optional human correction, rig preparation, animation validation, and GLB/FBX export. Paid APIs are not a required MVP path.

重要な方針:

- Task 3B/3C の生成メッシュは、最終可動モデルではなく参照モデルとして扱う。
- 最終成果物は、リグ付き猫ベースモデルを使った可動モデルにする。
- MVPで必要な動作は、最低限の idle/stand、walk、jumpまたは飛ぶような上下移動、sleepまたはlie-down。
- 完全自動リギングや高品質な自然アニメーションは後続改善とし、まずは可動するモデルの成立を優先する。
- 当面はGodotだけで静的表示とアニメーション再生を確認する。
- Unity / Unreal の確認は後で必要になった時点まで保留する。

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
- Runtime environment choices, optional API provider policy, Blender policy, game-engine policy, and other durable decisions belong in `docs/decisions.md`.
- Review findings from ChatGPT, Claude, Gemini, Codex, and the user belong in `docs/review_log.md`.
- MVP tasks and future proposals belong in `docs/backlog.md`.
- Proposals outside the MVP must be moved to `docs/backlog.md` instead of being implemented immediately.

## Task 0 Scope

Task 0 only creates the initial repository structure, configuration files, minimal dependencies, and documentation skeleton.

Task 0 does not implement scripts, external API calls, Blender CLI processing, game-engine import processing, or background removal.

Task 0.2 adds GitHub and documentation operation rules. It still does not implement API connectivity, image inventory scripts, image selection, background removal, Blender CLI, or game-engine import processing.

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

Task 1.5 copies selected images into `input/selected_photos/`. It does not move or delete source images, edit pixels, remove backgrounds, call 3D APIs, run Blender, or import into game engines.

Important selection decisions should use manual mode or human review. Non-interactive mode is only a fallback for pipeline smoke checks and keeps more candidates than it rejects. To reduce path and encoding issues in later Blender and game-engine steps, filenames copied into `input/selected_photos/` are converted to ASCII-safe names while source filenames remain unchanged.

## Task 2 Background Removal

Task 2 removes image backgrounds from the selected image set and creates review artifacts before local image-to-3D survey/prototype work.

Run the background removal process with this flow:

1. Complete Task 1.5 so selected images exist under `input/selected_photos/`.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run `python scripts/02_remove_backgrounds.py` in PowerShell.
4. Review transparent cutouts and masks under `input/masks/`.
5. Review checkerboard composites under `input/masks_review/`.
6. Review `output/reports/background_removal.json` and `output/reports/background_removal.csv`.
7. Continue to Task 3A for free/local image-to-3D survey.

Task 2 writes transparent cutouts as `*_cutout.png`, alpha masks as `*_mask.png`, and review images as `*_review.jpg`. It supports `u2net` and `u2netp` ONNX models, and the first run may download model files to `output/model_cache/u2net/`. Task 2 does not call 3D APIs, run Blender, or import into game engines.

## Task 3A Free/Local Image-to-3D Survey

Task 3A surveys free/local/OSS image-to-3D options and decides which one to prototype first. It does not run paid APIs or generate production assets.

Candidate tools:

- TripoSR
- InstantMesh
- Hunyuan3D
- Blender addons/wrappers for local models

Evaluation criteria:

- Windows compatibility
- RTX 4060 feasibility
- License
- Offline/local execution
- Output format OBJ/GLB/PLY
- Blender importability
- Setup complexity
- Texture support
- Cat/animal suitability

Survey notes belong in `docs/local_3d_generation_survey.md`.

Task 3A result: TripoSR was the first Task 3B prototype candidate, but TripoSR setup was blocked by CUDA Toolkit/NVCC requirements. Hunyuan3D-2mini shape-only was used successfully as the fallback.

## Task 3B Local Image-to-3D Prototype

Task 3B runs one selected local/OSS image-to-3D method on selected/masked images and outputs OBJ/GLB/PLY.

Task 3B must not call Tripo, Meshy, paid Blender AI plugins, or cloud-credit 3D generation APIs.

Task 3B completed with Hunyuan3D-2mini shape-only. The output is a static reference/shape candidate, not the final animation-ready model.

## Task 3C Blender Import and Normalize

Task 3C imports a locally generated asset into Blender, normalizes scale/origin/orientation, and exports GLB/FBX.

Blender should automate import, cleanup, normalization, and export where practical. Human Blender editing is allowed as a correction path, not as the only MVP path.

The Task 3C output is useful for visual reference and scale/origin validation. It is not assumed to be suitable for direct rigging or high-quality deformation.

## Task 3D Rigged Cat Base Model Route Survey

Task 3D surveys the practical route for creating the final animation-capable cat model.

Task 3D must answer:

- Which rigged cat base model route should be used?
- What license constraints apply?
- Can the model be imported into Blender?
- Does it have a usable armature and weights?
- Are walk, jump/fly-like movement, and sleep/lie-down animations available or practical to create?
- Can the model export to GLB/FBX with animation?
- Can Godot play the exported animation first?

The generated Hunyuan3D model from Task 3B/3C should be treated as a reference for shape and appearance, not as the default mesh to animate.

## Task 3E Rigged Cat Base Model Preparation

Task 3E prepares the selected rigged cat base model in Blender.

Expected work:

- Import or create the rigged base model.
- Check armature hierarchy.
- Check mesh weights.
- Check materials.
- Add or verify basic animation clips.
- Export a first animated GLB/FBX for Task 4 and Task 5.

## Task 3F Appearance / Shape Transfer Planning

Task 3F defines how source photos, masks, and generated static candidates influence the rigged base model.

The first version may be manual or semi-automatic. The priority is preserving a usable rig while making the cat resemble the source photos more closely.

## Task 3G Basic Cat Animation Set

Task 3G prepares or validates a minimal animation set:

- Idle/stand.
- Walk.
- Jump or fly-like upward movement.
- Sleep or lie-down.

The animation set can be simple at first. Natural animal motion quality is a later improvement target.

## Blender CLI

Blender tasks should call Windows `blender.exe` from the Windows venv. Blender checks should run in background mode with `-b` when automation is needed.

## Task 4 Blender Rig Cleanup and Animation Export

Task 4 normalizes Blender-created, locally generated, or semi-automatically edited rigged assets and exports them for game engines.

Task 4 scope:

- Adjust origin.
- Place the origin at the feet/base.
- Set a consistent scale.
- Remove unnecessary objects.
- Preserve armature.
- Preserve or export animation clips.
- Export animated GLB.
- Export animated FBX.
- Document export policy for Godot / Unity / Unreal.

Run the cleanup/export process with this flow:

1. Complete Task 3D/3E/3G or provide another supported rigged input asset.
2. Set `BLENDER_PATH` in `.env`.
3. Run `python scripts/04_blender_cleanup_export.py --config config/pipeline.yaml --dry-run` to inspect the plan.
4. Run `python scripts/04_blender_cleanup_export.py --config config/pipeline.yaml` to export GLB/FBX.
5. Add `--remove-reference-objects` when exporting a production asset from a scene that still contains reference images.
6. Review `output/reports/blender_cleanup_export.json`.

Expected outputs:

```text
output/clean_3d/cat_clean.glb
output/clean_3d/cat_clean.fbx
output/reports/blender_cleanup_export_plan.json
output/reports/blender_cleanup_export.json
```

Game-engine export policy is documented in `docs/game_engine_export_policy.md`.

## Task 5 Godot Animated Import Check

Task 5 verifies that generated/cleaned rigged GLB assets can be imported, displayed, and animated in Godot.

Task 5 deliverables:

- `godot/GodotImportGuide.md`
- `output/godot/`
- Godot-oriented GLB placement and animation playback procedure

Godot is the active display and animation playback confirmation target. Unity and Unreal checks are deferred unless the user resumes them later.

Run the Godot preparation process with this flow:

1. Complete Task 4 so `output/clean_3d/cat_clean.glb` exists.
2. Run `python scripts/05_godot_import_check.py --config config/pipeline.yaml --dry-run` to inspect the plan.
3. Run `python scripts/05_godot_import_check.py --config config/pipeline.yaml` to copy the GLB into `output/godot/`.
4. Follow `godot/GodotImportGuide.md` to place the GLB in a Godot project and instantiate it in a 3D scene.
5. Check visibility, scale, origin, floor contact, orientation, material appearance, armature import, and animation playback.

Expected outputs:

```text
output/godot/cat_clean.glb
output/reports/godot_import_check_plan.json
output/reports/godot_import_check.json
```

## Task 5.7 Godot Animation Review Scene

Task 5.7 keeps the current review loop inside Godot.

The active review scene is `godot/Godot3dcat/MainAppearance.tscn`, using `godot/Godot3dcat/cat_shape_pass.glb`.

Runtime controls:

- `1`: Idle
- `2`: Walk
- `3`: Jump_ToIdle
- `4`: Idle_2_HeadLow
- `Space`: next animation in the review sequence
- `R`: toggle rotating preview

## Task 6 Unity Animated Import Check

Task 6 verifies that exported GLB/FBX assets can be imported, displayed, and animated in Unity.

Task 6 is deferred for now by user request.

## Task 7 Unreal Animated Import Check

Task 7 verifies that exported GLB/FBX assets can be imported, displayed, and animated in Unreal.

Task 7 is deferred for now by user request.

## Optional Provider Experiments

Tripo, Meshy, paid Blender AI plugins, and cloud-credit 3D generation APIs are optional/deferred. They are not required for the MVP and should not be part of the default pipeline.

Tripo and Meshy can be reconsidered as a separate optional Task 8 track after the current rigged model progress is preserved:

1. Task 8A: check current API access, free-credit availability, pricing, output rights, and submission rules.
2. Task 8B: prepare one provider dry-run integration.
3. Task 8C: run one explicitly approved free-credit submission.
4. Task 8D: compare the cloud-generated asset in Blender and decide whether it helps the rigged model path.

See `docs/cloud_api_provider_reconsideration_plan.md`.

If optional provider experiments are resumed later, raw 3D provider API responses should be saved separately from normalized metadata, for example:

```text
output/reports/raw_api_response_tripo_<task_id>.json
```

Raw API response logs are only for debugging provider behavior and future multi-provider comparisons.
