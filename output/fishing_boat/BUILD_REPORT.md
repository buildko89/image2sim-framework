# Vessel Build Report: fishing_boat

- **Name**: Small Coastal Fishing Boat (Non-AIS Target Vessel)
- **Class**: coastal_fishing_boat
- **Provenance**: {
  "principal_dimensions": "public (Standard Japanese 19GT coastal fishing boat hulls)",
  "hydro_coefficients": "estimated (Empirical formula for small high-speed fishing vessel)",
  "radar_rcs": "measured/benchmark (Small FRP fishing boat with radar reflector ~5.0 m^2)"
}

## 1. Principal Dimensions

| Parameter | Value | Unit |
|---|---|---|
| Length Overall ($L_{OA}$) | 12.00 | m |
| Length Between Perpendiculars ($L_{PP}$) | 10.50 | m |
| Beam ($B$) | 3.20 | m |
| Depth ($D$) | 1.80 | m |
| Design Draft ($d$) | 1.10 | m |
| Block Coefficient ($C_b$) | 0.420 | - |
| Displacement | 15.5 | tonnes |

## 2. Signatures & AIS

- **Radar Cross Section (RCS)**: $\sigma = 5.0\text{ m}^2$
- **Has AIS**: `False`
- **AIS Class**: `NONE`
- **MMSI**: `0`

## 3. Generated Deliverables

- Blender 3D Scene: `[fishing_boat.blend](fishing_boat.blend)`
- 3D Model (glTF 2.0): `[fishing_boat.glb](fishing_boat.glb)`
- MuJoCo Physics Model: `[fishing_boat.xml](fishing_boat.xml)`
- MMG Hydrodynamics: `[hydro_mmg.json](hydro_mmg.json)`
- Viewer Sync Profile: `[ship_sync.profile.json](ship_sync.profile.json)`
