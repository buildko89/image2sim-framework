# Backlog

## MVP Tasks

### Task 0.5: Blender Environment Check

- Status: Done
- Priority: High
- Description: Verify local environment readiness for the Blender-first MVP, including Blender CLI execution policy and optional API key visibility checks without requiring paid providers.
- Notes: Completed scope includes adding `scripts/00_check_environment.py`, safely checking whether optional API keys are set without exposing values, creating the Blender CLI path check entry point, accepting Windows venv + Windows `blender.exe` + Windows path only for MVP, and accepting the decision that runtime policy must be settled before Blender automation.

### Task 1: Image Inventory Script

- Status: Done
- Priority: High
- Description: Create a script that scans `input/raw_photos/` and records image metadata for review.
- Notes: Implemented as `scripts/01_inventory_images.py`. It writes `output/reports/image_inventory.json` and `output/reports/image_inventory.csv`, records metadata and warnings, and does not perform image selection.

### Task 1.5: Image Selection Flow

- Status: Done
- Priority: High
- Description: Define and implement a process for selecting suitable images from the inventory.
- Notes: Implemented as `scripts/015_select_images.py`. It supports manual selection, a simple non-interactive fallback, selected image copies under `input/selected_photos/`, and `output/reports/image_selection.json` / `.csv`.

### Task 2: Background Removal

- Status: Done
- Priority: High
- Description: Add background removal and mask review outputs.
- Notes: Implemented as `scripts/02_remove_backgrounds.py`. It uses selected images from `input/selected_photos/`, runs local U2Net-family ONNX background removal, writes transparent cutouts and alpha masks under `input/masks/`, writes checkerboard review images under `input/masks_review/`, and writes `output/reports/background_removal.json` / `.csv`.

### Task 3A: Free/Local Image-to-3D Survey

- Status: Done
- Priority: High
- Description: Survey free/local/OSS image-to-3D options and decide which one to prototype first.
- Candidate tools:
  - TripoSR
  - InstantMesh
  - Hunyuan3D
  - Blender addons/wrappers for local models
- Evaluation criteria:
  - Windows compatibility
  - RTX 4060 feasibility
  - License
  - Offline/local execution
  - Output format OBJ/GLB/PLY
  - Blender importability
  - Setup complexity
  - Texture support
  - Cat/animal suitability
- Notes: Completed in `docs/local_3d_generation_survey.md`. Initial recommendation is to prototype TripoSR first, with Hunyuan3D-2mini shape-only and InstantMesh as fallback candidates.

### Task 3B: Local Image-to-3D Prototype

- Status: Done
- Priority: High
- Description: Run one selected local/OSS image-to-3D method on selected/masked images and output OBJ/GLB/PLY.
- Notes: Completed with Hunyuan3D-2mini shape-only after TripoSR was blocked by `torchmcubes` / CUDA Toolkit / NVCC setup. Generated `output/raw_3d/local/hunyuan3d/side_right_hunyuan3d_shape.glb`. No paid APIs were used. See `docs/progress_task3b_local_image_to_3d_prototype.md`.

### Task 3C: Blender Import and Normalize

- Status: Done
- Priority: High
- Description: Import locally generated asset into Blender, normalize scale/origin/orientation, and export GLB/FBX.
- Notes: Completed using the Hunyuan3D-2mini shape-only GLB from Task 3B. Exported `output/clean_3d/cat_clean.glb` and `output/clean_3d/cat_clean.fbx`; also kept `cat_hunyuan3d_normalized.*` copies. Blender report confirms target height 1.0 and base at Z=0. See `docs/progress_task3c_blender_import_normalize.md`.

### Task 3D: Rigged Cat Base Model Route Survey

- Status: Done
- Priority: High
- Description: Investigate the route for using a clean rigged cat base model as the final animation-capable asset.
- Notes: Completed in `docs/rigged_cat_base_model_survey.md`. Recommended Task 3E route is to use Quaternius Ultimate Animated Animal Pack as the first CC0 animated quadruped pipeline validation asset, then handle cat-like appearance/proportions in Task 3F. Task 3B/3C generated meshes remain reference/shape candidates, not final movable models.
- Requirements:
  - Rigged cat base mesh with armature.
  - License suitable for local prototype use.
  - Exportable to GLB/FBX.
  - Can support basic motions: walk, jump/fly-like movement, sleep/lie-down.
  - Usable in Godot first, then Unity and Unreal.
  - Appearance/proportion adjustment can be done without breaking the rig.
- Evaluation criteria:
  - Blender importability.
  - Bone hierarchy clarity.
  - Weight quality.
  - Animation clip availability.
  - GLB/FBX animation export behavior.
  - Game-engine playback compatibility.
  - License and redistribution constraints.

### Task 3E: Rigged Cat Base Model Preparation

- Status: Done
- Priority: High
- Description: Prepare the selected rigged cat base model in Blender and verify armature, mesh, materials, and basic animation clips.
- Notes: Completed with Quaternius Ultimate Animated Animal Pack `Fox.gltf` as the first CC0 animated quadruped validation asset. This is not the final cat appearance; Task 3F will handle cat-like appearance/proportion transfer. Blender import, Blend save, animated GLB/FBX export, and report generation succeeded. GLB verification found 12 animations and 1 skin. Sleep/lie-down is not present and remains for Task 3G.
- Expected outputs:
  - `output/rigged/cat_base_rigged.blend`
  - `output/rigged/cat_base_rigged.glb`
  - `output/rigged/cat_base_rigged.fbx`
  - `output/reports/rigged_cat_base_model.json`

### Task 3F: Appearance / Shape Transfer Planning

- Status: Done
- Priority: High
- Description: Define how source photos, masks, and generated shape candidates influence the rigged base model's appearance, proportions, or materials.
- Notes: Completed in `docs/appearance_shape_transfer_plan.md`. Use the Task 3E Fox rig as the animation-capable base, use selected photos and masks for color/pattern/proportion reference, and use the Hunyuan3D mesh only as a static shape reference. Directly animating the dense generated mesh is not the default path.
- Candidate approaches:
  - Manual Blender adjustment guided by source images.
  - Proportion matching against generated/static reference mesh.
  - Texture or material approximation from source photos.
  - Later texture baking or projection experiments.

### Task 3G: Basic Cat Animation Set

- Status: Done
- Priority: High
- Description: Prepare or validate a minimum animation set for the rigged cat model.
- Required motions:
  - Idle/stand.
  - Walk.
  - Jump or fly-like upward movement.
  - Sleep or lie-down.
- Notes: Completed as a validation and MVP mapping pass in `docs/progress_task3g_basic_cat_animation_set.md`. Existing clips cover `Idle`, `Walk`, and `Jump_ToIdle`. A true sleep/lie-down clip is not present; `Eating` or `Idle_2_HeadLow` is accepted only as a temporary rest-like placeholder. Natural high-quality animal animation remains a later quality target.

### Task 4: Blender Rig Cleanup and Animation Export

- Status: Done
- Priority: High
- Description: Blenderで作成・生成・編集されたリグ付き猫モデルをゲームエンジン向けに整理し、アニメーション付きGLB/FBXとして出力する。
- Notes: Completed in `docs/progress_task4_blender_rig_cleanup_animation_export.md`. Exported `output/clean_3d/cat_rigged_clean.blend`, `.glb`, and `.fbx`. Output GLB preserves 12 animations, 1 skin, and 1 mesh. A true sleep/lie-down clip is still not present.
- Scope:
  - Origin and foot/base alignment.
  - Scale normalization.
  - Mesh/material cleanup.
  - Armature preservation.
  - Animation clip naming/export.
  - GLB output with animation.
  - FBX output with animation.

### Task 5: Godot Animated Import Check

- Status: Done
- Priority: High
- Description: Verify the cleaned rigged GLB can be imported, displayed, and have basic animations played in Godot.
- Notes: Completed as Godot asset staging, GLB structure validation, and user visual confirmation. Copied `output/clean_3d/cat_rigged_clean.glb` to `output/godot/cat_rigged_clean.glb` and confirmed 12 animations, 1 skin, and 1 mesh remain. User confirmed the model appears in Godot as a fox, which is expected for the current Fox-based rig.

### Task 5.5: Cat Appearance Pass on Fox Rig

- Status: Done
- Priority: High
- Description: Modify the Fox-based rigged model toward a cat-like appearance while preserving armature, skinning, and existing animations.
- Notes: First material-based appearance pass was generated and staged for Godot review. Created `output/rigged/cat_appearance_pass.blend`, `output/clean_3d/cat_appearance_pass.glb`, `output/clean_3d/cat_appearance_pass.fbx`, and `godot/Godot3dcat/MainAppearance.tscn`. GLB validation confirmed 12 animations, 1 skin, and 1 mesh remain. User confirmed in Godot that the color/material pass remains during playback. See `docs/progress_task55_cat_appearance_pass.md`.
- Inputs:
  - `output/clean_3d/cat_rigged_clean.blend`
  - `input/selected_photos/reference_side_right_body_1698975320501.jpg`
  - `input/selected_photos/reference_front_face_1763363798733.jpg`
  - `input/selected_photos/reference_back_top_tail_1755598074234.jpg`
  - `input/masks/reference_*_cutout.png`
  - `output/clean_3d/cat_clean.glb`
- Scope:
  - Adjust material colors toward white / brown / black calico pattern.
  - Reduce fox-like visual impression where possible without breaking the rig.
  - Use selected reference images as Blender reference planes.
  - Keep armature, weights, and animation clips intact.
  - Export updated `.blend`, `.glb`, and `.fbx`.
  - Re-check in Godot.
- Out of scope:
  - Photo-perfect fur texture.
  - Full retopology.
  - Automatic rigging.
  - Real sleep / lie-down animation.

### Task 5.6: Conservative Cat Shape Pass

- Status: Done
- Priority: High
- Description: Apply a conservative shape pass to reduce the Fox visual impression while preserving rigging and animation.
- Notes: Generated `output/rigged/cat_shape_pass.blend`, `output/clean_3d/cat_shape_pass.glb`, `output/clean_3d/cat_shape_pass.fbx`, staged `godot/Godot3dcat/cat_shape_pass.glb`, and updated `MainAppearance.tscn` to use the shape-pass GLB. GLB validation confirmed 12 animations, 1 skin, and 1 mesh remain. User confirmed in Godot that the shape pass is visible and playback has no issue. See `docs/progress_task56_cat_shape_pass.md`.
- Scope:
  - Shorten and narrow tail using existing `Tail*` vertex groups.
  - Slightly lower and narrow ears using existing `Ear*` vertex groups.
  - Lightly compress the front of the head to reduce the fox muzzle impression.
  - Preserve armature, weights, and animation clips.
  - Re-check in Godot.
- Out of scope:
  - Full sculpting.
  - New topology.
  - New rig or animation retargeting.
  - Photo-perfect likeness.

### Task 6: Unity Animated Import Check

- Status: Deferred
- Priority: Medium
- Description: Verify the cleaned rigged GLB/FBX can be imported, displayed, and have basic animations played in Unity.
- Notes: Unity staging script and guide were added. `cat_shape_pass.glb` and `cat_shape_pass.fbx` were copied to `output/unity/`. Unity Editor was found at `C:\Program Files\Unity\Hub\Editor\6000.3.10f1\Editor\Unity.exe`, but the user chose to skip Unity for now and continue only with Godot. See `docs/progress_task6_unity_animated_import_check.md`.

### Task 7: Unreal Animated Import Check

- Status: Deferred
- Priority: Medium
- Description: Verify the cleaned rigged GLB/FBX can be imported, displayed, and have basic animations played in Unreal.
- Notes: Deferred by user request. Continue Godot-only validation for now.

### Task 5.7: Godot Animation Review Scene

- Status: Done
- Priority: High
- Description: Improve the Godot review scene so appearance and motion can be checked without switching engines.
- Notes: Updated `godot/Godot3dcat/play_animation.gd` and `MainAppearance.tscn` so the cat shape pass can be reviewed in Godot with runtime animation switching and rotating preview. Keys: `1` Idle, `2` Walk, `3` Jump_ToIdle, `4` Idle_2_HeadLow, `Space` next animation, `R` toggle rotation.
- Scope:
  - Keep `cat_shape_pass.glb` as the active Godot asset.
  - Keep material override active to avoid color fallback during playback.
  - Allow basic animation review in the main Godot scene.
  - Keep Unity/Unreal out of the active loop.

### Task 5.8: Photo-Based Godot Visual Improvement Pass

- Status: Done
- Priority: High
- Description: Improve the Godot-visible cat asset using the real cat photos as stronger appearance and proportion references before adding more animations.
- Notes: Generated `output/rigged/cat_visual_pass.blend`, `output/clean_3d/cat_visual_pass.glb`, `output/clean_3d/cat_visual_pass.fbx`, staged `godot/Godot3dcat/cat_visual_pass.glb`, and updated `MainAppearance.tscn` to use the visual-pass GLB. GLB validation confirms 12 animations, 1 skin, and 1 mesh remain. User confirmed this pass is much closer to the real photos. See `docs/progress_task58_photo_based_visual_pass.md`.
- Scope:
  - Shift from generic cat appearance to the real long-haired calico reference.
  - Make the body wider/lower to read as long-haired and fluffy.
  - Round the head and reduce the long fox muzzle impression.
  - Use mostly-white calico material placement with black/brown head, back, rump, and tail areas.
  - Restore a longer, fuller tail because the source cat has a plume tail.
  - Preserve armature, weights, and animation clips.
- Out of scope:
  - True fur simulation.
  - Photo-projected texture baking.
  - New topology or custom rig.
  - New animations.

### Task 5.9: Short Legs and Fluffy Fur Silhouette Pass

- Status: Retired
- Priority: High
- Description: Shorten the visible legs and increase fluffy long-hair silhouette after user review of the photo-based pass.
- Notes: Retired in favor of DEC-20260701-011. The Fox-rig based development track is stopped. Future shape and fluffy shell tasks are moved to Task 71 using the new Cat base asset. See `docs/progress_task59_shortleg_fluffy_pass.md` for historical work.

### Task 70: User Cat Asset Inspection and Selection

- Status: Done
- Priority: High
- Description: Inspect the multiple cat 3D models provided in `input/cat` in Blender 5.0 to identify their armature structure, animation clips, and suitability for the base model.
- Notes: Completed. Generated `output/reports/cat_assets_inspection_report.json` and `output/reports/cat_assets_inspection_summary.md`. Decided to use `1903704_FBX` cat assets. See `docs/progress_task70_inspect_cat_assets.md`.

### Task 71: Combine Cat Base Model and Customize Proportions

- Status: Done
- Priority: High
- Description: Import the various `.fbx` files from `1903704_FBX` into a master Blender file, combine their independent animations (walk, run, lazy/sleep, idle) into a single armature, and customize the mesh proportions (short legs, fluffy shape/fur shell, round head) to match the calico reference photos.
- Notes: Completed. Created `output/rigged/cat_master_base.blend` by combining animations and `output/rigged/cat_deformed.blend` by applying leg-shortening (50%), body widening (25%), head rounding, and a fur shell. GLB/FBX exported and staged to Godot. See `docs/progress_task71_cat_base_model_combined_and_deformed.md`.

### Task 71.5: Create and Add Missing Animations (Punch, Wake/Threat)

- Status: Done
- Priority: High
- Description: In `output/rigged/cat_deformed.blend`, create custom animations for "Neko Punch" (swiping with front paw to hit drone) and "Wake Up / Threat" (transition from sleep to standing with a threat pose) using manual keyframing. Integrate these into the master action library.
- Notes: Completed. Generated `Cat_Punch` (30F) and `Cat_WakeUp` (60F, includes threat humpback pose) animations using Blender Python API. Exported to `cat_animated.glb` and staged to Godot. See `docs/progress_task715_custom_animations_created.md`.



### Task 72: UV Mapping and Calico Texture Creation

- Status: Done
- Priority: High
- Description: Optimize UV mapping for the combined cat mesh and create a high-quality calico (white/brown/black) texture sheet. Incorporate fine fur detail baked from Tripo/local references if helpful.
- Notes: Completed. Automatically UV unwrapped using Smart UV Project, generated procedural calico colors based on vertex coordinates (orange-brown spots, dark-black spots, striped tail, white belly/paws, asymmetrical face colors), and baked the colors into a 2D 2048x2048 texture using Cycles CPU emission baking. Set up two materials (solid albedo and alpha-blended fur shell). Staged GLB and texture to Godot.

### Task 73: Godot Animation Playback Validation

- Status: Done
- Priority: High
- Description: Export the customized rigged animated cat model to GLB/FBX, copy to the Godot project, and verify all combined animations (walk, run, sleep, idle) play correctly in `MainAppearance.tscn`.
- Notes: Completed. Updated `play_animation.gd` keybinds to support keys 1-6 representing the 6 animations (Idle, Walk, Run, Sleep, Punch, WakeUp). Updated the `MainAppearance.tscn` configuration, and successfully launched Godot for real-time visualization validation.


## Optional / Deferred

### Task 8A: Cloud API Terms and Credit Check

- Status: Proposed
- Priority: Medium
- Description: Recheck current Tripo and Meshy API access, free-credit availability, pricing, output rights, and credit-consuming submission rules before any real cloud generation.
- Notes: This does not replace Task 5.5 or the local/Blender-first MVP path. See `docs/cloud_api_provider_reconsideration_plan.md`.

### Task 8B: One-Provider Cloud API Dry-Run Integration

- Status: Proposed
- Priority: Medium
- Description: Prepare a dry-run-only request planner for either Tripo or Meshy, using `.env` API keys and explicit submit gating.
- Notes: Prefer reactivating the existing Tripo script first for minimum code change, or add Meshy dry-run if provider comparison is more important.

### Task 8C: Free-Credit Single Cloud Submission

- Status: Proposed
- Priority: Medium
- Description: Run one explicitly approved free-credit cloud generation job and download the resulting static reference mesh.
- Notes: Output belongs under `output/raw_3d/cloud/<provider>/` and must be treated as a reference asset unless later Blender and animation checks prove otherwise.

### Task 8D: Cloud Asset Blender Comparison and Reuse Decision

- Status: Proposed
- Priority: Medium
- Description: Normalize and compare the cloud-generated asset against the Hunyuan3D reference and the rigged base model.
- Notes: Decide whether the cloud output is useful for appearance, shape, texture/material guidance, or should be rejected.

### Tripo API image-to-3D

- Status: Proposed
- Priority: Medium
- Description: Optional experiment for hosted image-to-3D generation.
- Notes: `scripts/03_tripo_image_to_3d.py` is still outside the default MVP path, but can be reactivated as part of Task 8B/8C with dry-run default and explicit submit.

### Meshy API image-to-3D

- Status: Proposed
- Priority: Medium
- Description: Optional experiment for hosted image-to-3D generation.
- Notes: Still outside the default MVP path. Candidate for a new dry-run script if Task 8A confirms API access and free-credit terms are acceptable.

### Paid Blender AI plugins

- Status: Deferred
- Priority: Low
- Description: Evaluate paid Blender AI plugins only after the local-first path works.
- Notes: Paid-credit plugins are not required for the MVP.

### Cloud credit based 3D generation APIs

- Status: Deferred
- Priority: Low
- Description: Evaluate cloud-credit 3D generation services only after the local-first MVP path is validated.
- Notes: Cloud-credit providers must not be required for the MVP.

### LoRA / DreamBooth

- Status: Deferred
- Priority: Low
- Description: Explore fine-tuning or personalization for view completion or texture generation.
- Notes: Deferred because it adds training cost, data quality risk, and operational complexity.

### Fully automatic rigging from generated mesh

- Status: Deferred
- Priority: Low
- Description: Automatically rig dense generated meshes from image-to-3D models.
- Notes: Deferred because generated topology is not reliable for clean deformation. MVP uses a rigged cat base model instead.

### Direct animation of dense generated image-to-3D mesh

- Status: Deferred
- Priority: Low
- Description: Animate the raw Hunyuan3D/TripoSR/InstantMesh output directly.
- Notes: Deferred because dense generated meshes are better used as references than final deformable characters.

## Future / Non-MVP Ideas

### Phase 3: Higher quality appearance transfer to rigged cat model

- Status: Backlog
- Priority: Medium
- Description: Improve transfer of generated appearance, proportions, or texture information to the rigged cat model.
- Notes: Basic rigged model route is now MVP; high-quality transfer remains future work.

### Phase 4: View completion using image generation

- Status: Backlog
- Priority: Low
- Description: Use image generation to compensate for missing views.
- Notes: This is non-MVP because it adds image consistency and data quality risks.

### Phase 5: Reprojection error loop

- Status: Backlog
- Priority: Low
- Description: Add a loop that compares generated assets against source images using reprojection error.
- Notes: Requires stable camera assumptions and evaluation metrics.

### Multi-provider support

- Status: Deferred
- Priority: Medium
- Description: Support optional 3D generation providers through a provider abstraction.
- Notes: Do not implement a provider abstraction class in the MVP. Add only after the Blender-first pipeline proves useful.

### Dockerized execution

- Status: Deferred
- Priority: Low
- Description: Package the pipeline runtime in Docker.
- Notes: Docker is explicitly out of scope for the MVP because Windows venv and Windows Blender are the accepted MVP runtime.

### Vision AI based image quality scoring

- Status: Backlog
- Priority: Medium
- Description: Score source images for sharpness, coverage, occlusion, pose, and suitability.
- Notes: Could support Task 1.5 after a human-reviewed selection baseline exists.

### Vision AI based view hint estimation

- Status: Backlog
- Priority: Medium
- Description: Automatically estimate `view_hint` values such as front, side, back, top, or diagonal.
- Notes: Deferred until manual selection produces enough examples and requirements.

### Vision AI based view hint and quality score estimation

- Status: Backlog
- Priority: Medium
- Description: Automatically estimate both `view_hint` and `quality_score` for selection candidates.
- Notes: Keep manual selection as the MVP baseline before adding model-based estimation.

### Improve selection heuristics using resolution area

- Status: Backlog
- Priority: Medium
- Description: Improve resolution checks using long-side or total-pixel thresholds instead of only per-axis minimums.
- Notes: Do not change the Task 1 `low_resolution` rule until real source image behavior is reviewed.

### Add optional CSV absolute path for review convenience

- Status: Backlog
- Priority: Medium
- Description: Add an optional `absolute_path` field to selection or inventory CSV outputs for local review convenience.
- Notes: Keep relative paths as the portable primary reference.

### Manual selection UI improvements

- Status: Backlog
- Priority: Medium
- Description: Add an optional interactive preview UI for manual image selection.
- Notes: CLI selection is sufficient for the MVP. Consider a local HTML or Streamlit UI after Task 2.

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
