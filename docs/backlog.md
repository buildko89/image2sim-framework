# Backlog

## MVP Tasks

### Task 0.5: 3D API / Blender Environment Check

- Status: Done
- Priority: High
- Description: Verify Tripo API availability, API key handling, pricing constraints, output formats, and Blender CLI execution policy.
- Notes: Completed scope includes adding `scripts/00_check_environment.py`, safely checking whether API keys are set without exposing values, creating the Blender CLI path check entry point, accepting Windows venv + Windows `blender.exe` + Windows path only for MVP, and accepting the decision that runtime policy must be settled before Blender automation.

### Task 1: Image Inventory Script

- Status: Done
- Priority: High
- Description: Create a script that scans `input/raw_photos/` and records image metadata for review.
- Notes: Implemented as `scripts/01_inventory_images.py`. It writes `output/reports/image_inventory.json` and `output/reports/image_inventory.csv`, records metadata and warnings, and does not perform image selection.

### Task 1.5: Image Selection Flow

- Status: Backlog
- Priority: High
- Description: Define and implement a process for selecting suitable images from the inventory.
- Notes: Next task. Selection criteria should support the `cat_avatar` reference case first and use Task 1 inventory output as input.

### Task 2: Background Removal

- Status: Backlog
- Priority: High
- Description: Add background removal and mask review outputs.
- Notes: `rembg` is intentionally not introduced before this task.

### Task 3: 3D Generation API Prototype

- Status: Backlog
- Priority: High
- Description: Prototype Image-to-3D generation with the selected provider.
- Notes: Tripo is the accepted initial provider. Save raw API responses separately from normalized metadata, for example `output/reports/raw_api_response_tripo_<task_id>.json`, to support debugging and later multi-provider comparisons.

### Task 4: Blender CLI Cleanup

- Status: Backlog
- Priority: High
- Description: Add Blender CLI processing for asset cleanup, normalization, and export.
- Notes: Use Windows `blender.exe` from Windows venv. Unity export policy is `-Z Forward`, `Y Up`, Apply Transform / applied scale, and foot-origin placement.

### Task 5: Unity Import Check

- Status: Backlog
- Priority: Medium
- Description: Verify that generated and cleaned assets can be imported and displayed in Unity.
- Notes: Full Unity automation is outside the early MVP unless required.

## Future / Non-MVP Ideas

### Phase 3: Transfer generated appearance to existing rigged cat model

- Status: Backlog
- Priority: Medium
- Description: Apply generated appearance or texture information to an existing rigged cat model.
- Notes: This is after the basic image-to-asset MVP path is validated.

### Phase 4: View completion using LoRA/DreamBooth or image generation

- Status: Backlog
- Priority: Low
- Description: Use image generation or fine-tuning to compensate for missing views.
- Notes: This is non-MVP because it adds model training and data quality risks.

### Phase 5: Reprojection error loop

- Status: Backlog
- Priority: Low
- Description: Add a loop that compares generated assets against source images using reprojection error.
- Notes: Requires stable camera assumptions and evaluation metrics.

### Multi-provider support for Tripo/Meshy/local OSS

- Status: Deferred
- Priority: Medium
- Description: Support multiple 3D generation providers through a provider abstraction.
- Notes: Do not implement a provider abstraction class in the MVP. Add only after the first provider path proves useful.

### Dockerized execution

- Status: Deferred
- Priority: Low
- Description: Package the pipeline runtime in Docker.
- Notes: Docker is explicitly out of scope for the MVP because Windows venv and Windows Blender are the accepted MVP runtime.

### Vision AI based image quality scoring

- Status: Backlog
- Priority: Medium
- Description: Score source images for sharpness, coverage, occlusion, pose, and suitability.
- Notes: Could support Task 1.5 after a manual baseline exists.

### OpenCV blur detection

- Status: Backlog
- Priority: Low
- Description: Add local blur or sharpness detection using OpenCV.
- Notes: Not part of Task 1. Consider after Task 1.5 defines manual selection criteria and review needs.

### Texture transfer and shape transfer to base model

- Status: Backlog
- Priority: Medium
- Description: Transfer texture or shape from generated assets to a known base model.
- Notes: Related to existing rig and animation workflows.

### Simulation asset evaluation metrics

- Status: Backlog
- Priority: Medium
- Description: Define metrics for whether an asset is usable in simulation.
- Notes: Metrics may include scale, topology, texture quality, axis/origin correctness, and runtime import health.
