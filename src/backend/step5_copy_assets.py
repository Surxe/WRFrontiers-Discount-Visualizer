"""
step5_copy_assets.py

Step 5: Copy referenced images to src/frontend/public/assets/ (preserving paths)
        and copy discounts.json to src/frontend/public/data/discounts.json.
"""

import sys
import json
import shutil
from config import TEXTURES_DIR, REPO_ROOT, FRONTEND_ASSETS_DIR, FRONTEND_DATA_DIR

def copy_assets(discounts: list[dict]):
    """
    For each item in discounts, copies its image from the textures directory
    to src/frontend/public/assets/, preserving the original directory structure.

    The image_path from Module.json looks like:
        WRFrontiers/Content/Sparrow/UI/Textures/Modules/T_Module_ChassisAres

    The actual file on disk is at:
        WRFrontiersDB-Data/textures/WRFrontiers/Content/.../T_Module_ChassisAres.png
    """
    print("[5/5] Copying images to frontend assets...")

    FRONTEND_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    missing = []

    for item in discounts:
        image_path = item.get("image_path", "")
        if not image_path:
            continue

        # Source: look for .png file in textures directory
        src_file = TEXTURES_DIR / (image_path + ".png")

        if not src_file.exists():
            missing.append(image_path)
            print(f"  [!] Image not found: {src_file.relative_to(REPO_ROOT) if src_file.is_relative_to(REPO_ROOT) else src_file}")
            continue

        # Destination: same relative path under frontend/public/assets/
        dst_file = FRONTEND_ASSETS_DIR / (image_path + ".png")
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        copied += 1
        print(f"  -> Copied: {image_path}.png")

    print(f"  -> {copied} images copied, {len(missing)} missing.")


def copy_discounts_to_frontend(discounts: list[dict]):
    """Writes the final discounts.json to the frontend public/data directory."""
    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    dst = FRONTEND_DATA_DIR / "discounts.json"
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(discounts, f, indent=2, ensure_ascii=False)
    print(f"  -> Copied discounts.json to {dst.relative_to(REPO_ROOT) if dst.is_relative_to(REPO_ROOT) else dst}")


def run_step(discounts: list[dict]):
    copy_assets(discounts)
    copy_discounts_to_frontend(discounts)


if __name__ == "__main__":
    # If run standalone, read the discounts file first
    from step4_read_output import load_discounts
    discounts = load_discounts()
    run_step(discounts)
