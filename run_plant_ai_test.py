from __future__ import annotations

import argparse
import json
from pathlib import Path

from plant_ai import analyze_plant_with_details
from shared_game_data import plant_to_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="Plant AI V2 test")
    parser.add_argument("image_path", help="Path to one plant image")
    parser.add_argument(
        "--save-crop",
        default="plant_ai_debug/last_crop.jpg",
        help="Where to save the plant auto-crop for debugging",
    )
    args = parser.parse_args()

    image_path = Path(args.image_path)
    print("=" * 68)
    print("Plant AI V2")
    print("=" * 68)
    print(f"Image: {image_path}")
    print("First run may download the SigLIP2 model from Hugging Face.")
    print()

    if not image_path.exists():
        raise FileNotFoundError(f"Image does not exist: {image_path}")

    plant, details = analyze_plant_with_details(
        str(image_path),
        debug_crop_path=args.save_crop,
    )

    print("\n[1] PlantData")
    print(json.dumps(plant_to_dict(plant), ensure_ascii=False, indent=2))

    print("\n[2] Type debug")
    print(f"method           : {details.type_method}")
    print(f"plant_type       : {details.plant_type}")
    print(f"type_scores      : {details.type_scores}")
    print(f"similarities     : {details.type_similarities}")
    print(f"flower_presence  : {details.flower_presence}")
    print(f"reference_counts : {details.reference_counts}")

    print("\n[3] Crop debug")
    print(f"crop_used        : {details.crop_used}")
    print(f"crop_bbox        : {details.crop_bbox}")
    print(f"veg_coverage     : {details.crop_vegetation_coverage}")
    print(f"saved crop       : {args.save_crop}")

    print("\n[4] Health debug")
    for name in ("water", "light", "nitrogen", "phosphorus", "potassium", "pest"):
        print(
            f"{name:10s} final={details.health_final_scores[name]:.4f}  "
            f"raw={details.health_raw_scores[name]:.4f}  "
            f"confidence={details.health_confidence[name]:.4f}  "
            f"levels={details.health_level_scores[name]}"
        )

    if details.warnings:
        print("\n[Warnings]")
        for warning in details.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
