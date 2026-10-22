# Vessel Build Report: ferry_seto

- **Name**: Seto Inland Sea Passenger Car Ferry
- **Class**: coastal_passenger_ferry
- **Provenance**: {
  "principal_dimensions": "public (Ryobi Ferry public fleet specifications)",
  "hydro_coefficients": "estimated (Twin-screw twin-rudder ferry empirical formula)",
  "radar_rcs": "estimated (~1,200 m^2 with vehicle deck and passenger cabin)"
}

## 1. Principal Dimensions

| Parameter | Value | Unit |
|---|---|---|
| Length Overall ($L_{OA}$) | 65.86 | m |
| Length Between Perpendiculars ($L_{PP}$) | 60.00 | m |
| Beam ($B$) | 14.00 | m |
| Depth ($D$) | 4.80 | m |
| Design Draft ($d$) | 3.10 | m |
| Block Coefficient ($C_b$) | 0.635 | - |
| Displacement | 1680.0 | tonnes |

## 2. Signatures & AIS

- **Radar Cross Section (RCS)**: $\sigma = 1200.0\text{ m}^2$
- **Has AIS**: `True`
- **AIS Class**: `A`
- **MMSI**: `431003942`

## 3. Generated Deliverables

- Blender 3D Scene: `[ferry_seto.blend](ferry_seto.blend)`
- 3D Model (glTF 2.0): `[ferry_seto.glb](ferry_seto.glb)`
- MuJoCo Physics Model: `[ferry_seto.xml](ferry_seto.xml)`
- MMG Hydrodynamics: `[hydro_mmg.json](hydro_mmg.json)`
- Viewer Sync Profile: `[ship_sync.profile.json](ship_sync.profile.json)`
