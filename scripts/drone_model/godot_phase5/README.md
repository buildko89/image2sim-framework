# Godot Phase 5 regression test

`run_godot_phase5.py` stages the Phase 4 GLBs and build reports in an isolated
Godot project, imports them with Godot 4, and runs the hierarchy/runtime smoke
test headlessly.

```powershell
python scripts\drone_model\run_godot_phase5.py --godot C:\path\to\godot_console.exe
```

Add `--include-hex6` to exercise the sample template as well as drone2,
drone3, and hula. Results and the two Godot logs are written below
`output/phase5_review/`.

Use `--input-root output --formal-layout` to validate the canonical
`output/*_parametric` artifacts after publishing them.

The test covers imported node names, parent paths, local transforms, meshes,
materials, center of mass and motor-axis transforms, collision-shape creation,
rotor-only visual rotation, and a balanced `RigidBody3D` thrust impulse.

Godot's standard glTF scene importer retains custom properties for import
extensions but does not automatically expose glTF `extras` as Node metadata.
The staged `drone_runtime.gd` therefore maps the GLB extras captured in the
manifest onto the matching imported nodes. The test verifies the mapped
`anchor_type` and `rotation_direction` values against the build report.
