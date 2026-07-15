# Decisions

## Decision Log

Each decision must use this format:

```markdown
### DEC-YYYYMMDD-XXX: Title

- Status: Proposed | Accepted | Rejected | Superseded
- Date: YYYY-MM-DD
- Owner: User | ChatGPT | Codex | Claude | Gemini
- Context:
- Decision:
- Rationale:
- Consequences:
- Related Tasks:
```

### DEC-20260528-001: Repository name is image2sim-framework

- Status: Accepted
- Date: 2026-05-28
- Owner: User
- Context: The project needs a repository name that covers the MVP and the long-term framework direction.
- Decision: リポジトリ名を `image2sim-framework` とする。
- Rationale: 現在のMVPである画像入力と、将来のsimulation-ready asset生成の方向性を両立できるため。
- Consequences: Documentation, configuration, and project references use `image2sim-framework`.
- Related Tasks: Task 0

### DEC-20260528-002: First reference case is cat_avatar

- Status: Accepted
- Date: 2026-05-28
- Owner: User
- Context: The MVP needs a concrete first case to keep implementation and review grounded.
- Decision: 最初のリファレンスケースを猫写真から3D猫モデル生成とする。
- Rationale: 身近な具体例であり、将来的な画像→シミュレーション資産生成の検証対象として扱いやすいため。
- Consequences: Initial input, review, and output examples are organized around `cat_avatar`.
- Related Tasks: Task 0, Task 1, Task 1.5

### DEC-20260528-003: Preferred initial 3D provider is Tripo

- Status: Superseded
- Date: 2026-05-28
- Owner: ChatGPT
- Context: The MVP needs an initial Image-to-3D provider candidate before API verification.
- Decision: 初期3D生成API候補はTripoを優先する。
- Rationale: Image-to-3D、Multi-image、Quad/Retopo系出力の可能性があり、Blender後処理や既存リグ転写に繋げやすいため。
- Consequences: Superseded by DEC-20260622-010. Tripo is now optional, deferred, and experimental, not part of the MVP path.
- Related Tasks: Task 0.5, Task 3

### DEC-20260528-004: Initial game engine target is Unity

- Status: Superseded
- Date: 2026-05-28
- Owner: ChatGPT
- Context: The first generated asset needs a target runtime for display and verification.
- Decision: 初期ゲームエンジン候補はUnityとする。
- Rationale: 既存猫アニメーション、FBX/GLB取り込み、ユーザーの既存経験との相性が良いため。
- Consequences: Superseded by DEC-20260622-010. Godot, Unity, and Unreal are all target engines, with Godot allowed as the first display check.
- Related Tasks: Task 0.5, Task 4, Task 5

### DEC-20260528-005: Runtime environment is undecided

- Status: Accepted
- Date: 2026-05-28
- Owner: ChatGPT
- Context: The project must decide how Python, Blender CLI, paths, and Unity integration will run together.
- Decision: Windows venv / WSL2 venv / Docker のどれで実行するかはTask 0.5で決定する。
- Rationale: Blender CLIとPython実行環境の境界でパス問題が起きやすいため。
- Consequences: No runtime-specific scripts should be added before Task 0.5 decides the execution policy.
- Related Tasks: Task 0.5

### DEC-20260528-006: Runtime and Blender execution policy must be decided before Blender tasks

- Status: Accepted
- Date: 2026-05-28
- Owner: ChatGPT
- Context: Blender CLI and Python scripts may run across Windows, WSL2, or Docker environments. Path handling can break when Python runs in WSL2 and Blender runs as a Windows executable.
- Decision: Before Task 4, decide whether the project uses Windows venv, WSL2 venv, or Docker, and whether Blender is executed as Windows `.exe`, Linux Blender, or containerized Blender.
- Rationale: Avoid path conversion problems such as `/mnt/c/...` vs `C:\...`.
- Consequences: Task 0.5 must record the chosen environment policy before implementing Blender automation.
- Related Tasks:
  - Task 0.5
  - Task 4

### DEC-20260529-007: MVP runtime uses Windows venv and Windows Blender

- Status: Accepted
- Date: 2026-05-29
- Owner: User
- Context: The user works in Windows PowerShell, and Unity is expected to run on Windows. Calling Windows Blender from WSL2 can introduce `/mnt/c/...` vs `C:\...` path conversion issues, while Linux Blender inside WSL2 may fail on missing Linux dependencies.
- Decision: For the MVP, use Windows venv as the Python runtime, execute the Windows `blender.exe`, and use Windows paths only. WSL2 and Docker are not used for the MVP pipeline.
- Rationale: The MVP should prioritize the shortest path through the pipeline and avoid cross-environment path and dependency problems.
- Consequences: `config/pipeline.yaml` records `runtime: windows-venv`, `blender_mode: windows-exe`, and `path_policy: windows-path-only`. Dockerization and WSL2 support remain non-MVP backlog items.
- Related Tasks:
  - Task 0.5
  - Task 1
  - Task 4

### DEC-20260621-008: Task 2 uses local U2Net ONNX background removal

- Status: Accepted
- Date: 2026-06-21
- Owner: Codex
- Context: Task 2 needs a local background removal implementation before Blender reference-scene work.
- Decision: Use local U2Net-family ONNX inference for MVP background removal and write transparent cutouts, alpha masks, checkerboard review images, and JSON/CSV reports.
- Rationale: The direct ONNX path avoids hosted image-processing APIs and avoids importing unrelated background-removal models during startup.
- Consequences: The first run may download model files to `output/model_cache/u2net/`. Mask quality must be manually reviewed before Task 3 uses the images as Blender references.
- Related Tasks: Task 2, Task 3

### DEC-20260621-009: Task 3 Tripo API calls require explicit submit

- Status: Superseded
- Date: 2026-06-21
- Owner: Codex
- Context: Tripo Image-to-3D generation can consume credits and depends on external API state.
- Decision: The Task 3 prototype defaults to dry-run and only calls Tripo when `--submit` is provided and `TRIPO_API_KEY` is set.
- Rationale: The project needs request-shape validation and report generation without accidentally spending API credits.
- Consequences: Superseded by DEC-20260622-010. The script remains experimental, but Task 3 is no longer a Tripo/API task.
- Related Tasks: Task 3, Task 4

### DEC-20260622-010: MVP uses Blender-first local workflow

- Status: Superseded
- Date: 2026-06-22
- Owner: User
- Context: Task 3 had drifted toward a paid API centered implementation, but the project direction is a free/local-first 3D asset pipeline centered on Blender and deployable to Godot, Unity, and Unreal.
- Decision: MVP uses Blender-first local workflow and does not require paid 3D generation APIs.
- Rationale:
  - 無料でできる範囲を優先する
  - Blenderを中心にする当初方針へ戻す
  - Tripo/Meshy APIは有料・クレジット制約がある
  - Godot / Unity / Unreal に展開可能な汎用パイプラインにする
- Consequences: Superseded by DEC-20260622-LOCAL-FIRST-3D. The project remains Blender-centered, but the MVP is now semi-automatic local/OSS image-to-3D first rather than Blender reference-scene/manual-modeling first.
- Related Tasks: Task 3, Task 4, Task 5, Task 6, Task 7

### DEC-20260622-LOCAL-FIRST-3D: MVP uses free/local-first semi-automatic 3D generation instead of paid API-first workflow

- Status: Accepted
- Date: 2026-06-22
- Owner: User
- Context: Task 3 had started to become Tripo/Meshy paid API based. However, the project goal is to build a Blender-centered, free/local-first pipeline that can generate or prepare 3D assets from images and display them in game engines.
- Decision: The MVP will not require paid 3D generation APIs. The project will prioritize free/local/OSS image-to-3D candidates, Blender automated import/cleanup/export, and game engine import checks for Godot, Unity, and Unreal. Paid APIs such as Tripo/Meshy are deferred or experimental.
- Rationale:
  - Avoid dependency on paid API credits
  - Return to the original Blender-centered project direction
  - Keep the pipeline reproducible and locally controllable
  - Preserve the goal of semi-automation rather than fully manual Blender modeling
  - Support multiple target engines including Godot
- Consequences:
  - Existing Tripo API work must be marked as experimental/deferred
  - Task 3 must be redefined as a survey and local prototype path
  - Blender remains central but not purely manual
  - Godot import check is added as an MVP task
- Related Tasks: Task 3A, Task 3B, Task 3C, Task 3D, Task 4, Task 5, Task 6, Task 7

### DEC-20260622-RIGGED-CAT-ANIMATION: MVP target expands from static 3D asset to rigged animated cat model

- Status: Accepted
- Date: 2026-06-22
- Owner: User
- Context: Task 3B and Task 3C produced a static cat-like GLB from local image-to-3D generation. Visual review showed that this path can create a rough static model, but the user's intended goal is a cat model that can move, including walking, jumping or fly-like movement, and sleeping/lying down.
- Decision: The MVP target is changed from a static generated 3D cat asset to a rigged, animation-capable cat model. Local image-to-3D outputs remain useful as reference/shape candidates, but the final movable asset should be based on a clean rigged cat base model. Blender remains the central tool for rig preparation, appearance/proportion adjustment, animation validation, cleanup, and GLB/FBX export. Godot, Unity, and Unreal checks must validate animation playback, not only static display.
- Rationale:
  - A dense generated mesh is not a reliable final character mesh for deformation.
  - Walking, jumping, and sleeping require armature, weights, animation clips, and engine playback validation.
  - A rigged cat base model is a more practical route than fully automatic rigging from generated mesh.
  - The generated Hunyuan3D/other local outputs are still valuable as references for shape and appearance.
  - The project goal is closer to a controllable simulation/game asset than a static display model.
- Consequences:
  - Task 3D becomes the next main task and is promoted to a high-priority rigged base model route survey.
  - Task 3E, Task 3F, and Task 3G are added for rigged model preparation, appearance/shape transfer planning, and basic animation set validation.
  - Task 4 is redefined as Blender rig cleanup and animation export.
  - Task 5 through Task 7 are redefined as animated import/playback checks for Godot, Unity, and Unreal.
  - Fully automatic rigging and direct animation of dense generated meshes are deferred.
- Related Tasks: Task 3D, Task 3E, Task 3F, Task 3G, Task 4, Task 5, Task 6, Task 7

### DEC-20260628-CLOUD-API-OPTIONAL-TRACK: Reconsider Tripo and Meshy as optional cloud reference providers

- Status: Proposed
- Date: 2026-06-28
- Owner: Codex
- Context: Local-only image-to-3D has produced a usable static Hunyuan3D reference, but TripoSR was blocked by local CUDA Toolkit / NVCC setup and generated dense meshes remain unreliable as final deformable character meshes. The current MVP progress already has a rigged animated base route, so cloud APIs should not reset or replace that progress.
- Decision: Keep the current Blender-first rigged animated model plan intact, but add an optional Task 8 track for Tripo/Meshy API experiments within free-credit limits. Cloud outputs are reference or comparison assets unless later Blender and animation checks prove they are useful in the rigged model path.
- Rationale:
  - Tripo/Meshy may reduce local setup friction and provide better textured/static reference meshes.
  - The project still needs a controllable movable model, so a clean rigged base remains the default final asset route.
  - Free-credit experiments can provide useful evidence without making cloud providers mandatory.
  - Credit-consuming API calls must remain explicit and user-approved.
- Consequences:
  - Add `docs/cloud_api_provider_reconsideration_plan.md`.
  - Add proposed Task 8A through Task 8D entries to `docs/backlog.md`.
  - Existing Task 1 through Task 5 progress and Task 5.5 priority remain unchanged.
  - `scripts/03_tripo_image_to_3d.py` can be reactivated as optional dry-run-first work, but not as the default MVP path.
- Related Tasks: Task 5.5, Task 8A, Task 8B, Task 8C, Task 8D

### DEC-20260629-GODOT-ONLY-ACTIVE-LOOP: Continue active validation in Godot only

- Status: Accepted
- Date: 2026-06-29
- Owner: User
- Context: The rigged cat-like asset is now visible and playable in Godot after material and conservative shape passes. Unity staging was prepared, and Unreal was about to be surveyed, but the user chose to skip Unity and Unreal for now.
- Decision: Continue the active MVP review loop in Godot only. Unity and Unreal checks are deferred until the user explicitly resumes them.
- Rationale:
  - Godot already loads and plays the current `cat_shape_pass.glb`.
  - Keeping one engine active reduces context switching while the asset appearance and behavior are still changing.
  - Unity/Unreal compatibility can be revisited after the Godot asset loop is more stable.
- Consequences:
  - Task 6 and Task 7 are deferred.
  - `MainAppearance.tscn` becomes the active review scene.
  - Godot animation switching and rotating preview are added for faster visual checks.
- Related Tasks: Task 5.7, Task 6, Task 7

### DEC-20260701-011: Switch base model from Fox rig to user-provided Cat assets (1903704_FBX)

- Status: Accepted
- Date: 2026-07-01
- Owner: User
- Context: The previous Fox-rig-based automated deformation and projection bake failed to eliminate the "fox-like" appearance and created texture artifacts due to shape mismatches. The user provided multiple rigged cat assets in `input/cat` that were previously unused.
- Decision: Set the new base model route to use the `1903704_FBX` cat assets. Combine their meshes and animations (houseCat, LazyCat, ShustrujCat) into a single master asset.
- Rationale: Starts from a correct cat skeleton and mesh, eliminates "fox-like" proportions naturally, and provides native cat animations (including sleep/lie-down) with identical rig structures.
- Consequences: Fox-rig files (`cat_fluffy_shortleg_pass.glb`, etc.) are retired. Active development shifts to merging and customizing the new cat base asset.
- Related Tasks: Task 70, Task 71, Task 72, Task 73

