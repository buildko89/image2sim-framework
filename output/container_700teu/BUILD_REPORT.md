# Vessel Build Report: container_700teu

- **Name**: Genbu Class 700TEU Next-Generation Container Ship
- **Class**: nextgen_container_700teu
- **Provenance**: {
  "principal_dimensions": "public (Nippon Foundation MEGURI2040 Phase 2 announcements)",
  "hydro_coefficients": "estimated (Kijima 1990 standard formula for 130m container)",
  "radar_rcs": "estimated (Large coastal container ~8,000 m^2)"
}

## 1. Principal Dimensions

| Parameter | Value | Unit |
|---|---|---|
| Length Overall ($L_{OA}$) | 134.00 | m |
| Length Between Perpendiculars ($L_{PP}$) | 124.00 | m |
| Beam ($B$) | 21.00 | m |
| Depth ($D$) | 10.50 | m |
| Design Draft ($d$) | 6.00 | m |
| Block Coefficient ($C_b$) | 0.705 | - |
| Displacement | 11500.0 | tonnes |

## 2. Signatures & AIS

- **Radar Cross Section (RCS)**: $\sigma = 8000.0\text{ m}^2$
- **Has AIS**: `True`
- **AIS Class**: `A`
- **MMSI**: `431002700`

## 3. Generated Deliverables

- Blender 3D Scene: `[container_700teu.blend](container_700teu.blend)`
- 3D Model (glTF 2.0): `[container_700teu.glb](container_700teu.glb)`
- MuJoCo Physics Model: `[container_700teu.xml](container_700teu.xml)`
- MMG Hydrodynamics: `[hydro_mmg.json](hydro_mmg.json)`
- Viewer Sync Profile: `[ship_sync.profile.json](ship_sync.profile.json)`
