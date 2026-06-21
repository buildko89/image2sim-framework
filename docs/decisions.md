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

- Status: Accepted
- Date: 2026-05-28
- Owner: ChatGPT
- Context: The MVP needs an initial Image-to-3D provider candidate before API verification.
- Decision: 初期3D生成API候補はTripoを優先する。
- Rationale: Image-to-3D、Multi-image、Quad/Retopo系出力の可能性があり、Blender後処理や既存リグ転写に繋げやすいため。
- Consequences: Task 0.5でAPIキー、料金、出力形式、Quad対応を確認する。
- Related Tasks: Task 0.5, Task 3

### DEC-20260528-004: Initial game engine target is Unity

- Status: Accepted
- Date: 2026-05-28
- Owner: ChatGPT
- Context: The first generated asset needs a target runtime for display and verification.
- Decision: 初期ゲームエンジン候補はUnityとする。
- Rationale: 既存猫アニメーション、FBX/GLB取り込み、ユーザーの既存経験との相性が良いため。
- Consequences: Task 4以降でUnity向け軸設定や足元原点化を考慮する。
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
- Context: Task 2 needs a local background removal implementation before 3D generation API prototyping.
- Decision: Use local U2Net-family ONNX inference for MVP background removal and write transparent cutouts, alpha masks, checkerboard review images, and JSON/CSV reports.
- Rationale: The direct ONNX path avoids hosted image-processing APIs and avoids importing unrelated background-removal models during startup.
- Consequences: The first run may download model files to `output/model_cache/u2net/`. Mask quality must be manually reviewed before Task 3 uses the images for 3D generation.
- Related Tasks: Task 2, Task 3
