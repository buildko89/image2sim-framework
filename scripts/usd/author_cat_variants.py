"""
scripts/usd/author_cat_variants.py

猫モデル (root_cat.usda) に対し、VariantSets (CoatColor, LOD) を
プログラマブルにオーサリングするスクリプト。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from pxr import Usd, Sdf

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAT_STAGE = REPO_ROOT / "output_v2" / "usd" / "root_cat.usda"


def setup_cat_variants(stage_path: Path | str) -> bool:
    stage_path = Path(stage_path)
    if not stage_path.is_file():
        raise FileNotFoundError(f"USD stage not found: {stage_path}")

    stage = Usd.Stage.Open(str(stage_path))
    if not stage:
        raise RuntimeError(f"Failed to open USD stage: {stage_path}")

    root_prim = stage.GetPrimAtPath("/KohaCat")
    if not root_prim.IsValid():
        raise RuntimeError(f"Root prim /KohaCat not found in {stage_path}")

    groom_prim = stage.GetPrimAtPath("/KohaCat/Groom")

    # 1. LOD VariantSet の構築
    vset_lod = root_prim.GetVariantSets().AddVariantSet("LOD")
    vset_lod.AddVariant("Full_Groom")
    vset_lod.AddVariant("Simple_Mesh")

    vset_lod.SetVariantSelection("Full_Groom")
    with vset_lod.GetVariantEditContext():
        if groom_prim.IsValid():
            groom_prim.SetActive(True)

    vset_lod.SetVariantSelection("Simple_Mesh")
    with vset_lod.GetVariantEditContext():
        if groom_prim.IsValid():
            groom_prim.SetActive(False)

    # 既定値に戻す
    vset_lod.SetVariantSelection("Full_Groom")
    print("[USD Cat Variants] Configured VariantSet 'LOD' (Full_Groom / Simple_Mesh)")

    # 2. CoatColor VariantSet の構築
    vset_coat = root_prim.GetVariantSets().AddVariantSet("CoatColor")
    vset_coat.AddVariant("Koha_Calico")
    vset_coat.AddVariant("Brown_Tabby")
    vset_coat.AddVariant("White")

    vset_coat.SetVariantSelection("Koha_Calico")
    with vset_coat.GetVariantEditContext():
        root_prim.CreateAttribute("cat:coat_style", Sdf.ValueTypeNames.String).Set("Calico_TriColor")
        root_prim.CreateAttribute("cat:palette_source", Sdf.ValueTypeNames.String).Set("raw_photos_calico")

    vset_coat.SetVariantSelection("Brown_Tabby")
    with vset_coat.GetVariantEditContext():
        root_prim.CreateAttribute("cat:coat_style", Sdf.ValueTypeNames.String).Set("Brown_Tabby_Striped")
        root_prim.CreateAttribute("cat:palette_source", Sdf.ValueTypeNames.String).Set("procedural_tabby")

    vset_coat.SetVariantSelection("White")
    with vset_coat.GetVariantEditContext():
        root_prim.CreateAttribute("cat:coat_style", Sdf.ValueTypeNames.String).Set("Solid_White")
        root_prim.CreateAttribute("cat:palette_source", Sdf.ValueTypeNames.String).Set("solid_white_rgb")

    # 既定値に戻す
    vset_coat.SetVariantSelection("Koha_Calico")
    print("[USD Cat Variants] Configured VariantSet 'CoatColor' (Koha_Calico / Brown_Tabby / White)")

    stage.GetRootLayer().Save()
    print(f"[USD Cat Variants] Successfully saved variants to {stage_path}")
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Author VariantSets to Koha cat master stage.")
    parser.add_argument("--stage", default=str(DEFAULT_CAT_STAGE), help="Path to root_cat.usda")
    return parser.parse_args()


def main():
    args = parse_args()
    setup_cat_variants(Path(args.stage))


if __name__ == "__main__":
    main()
