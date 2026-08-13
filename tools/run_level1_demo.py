"""Run level one with temporary data instead of the unfinished AI input."""

from __future__ import annotations

from dataclasses import asdict
import json

from level1.demo_data import create_demo_plant
from level1.level1 import run_level1
from shared_game_data import plant_to_dict


def main() -> None:
    plant = create_demo_plant()
    print("Level 1 demo input:")
    print(json.dumps(plant_to_dict(plant), ensure_ascii=False, indent=2))

    result = run_level1(plant)

    print("\nLevel 1 demo output:")
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    print("\nUpdated plant data:")
    print(json.dumps(plant_to_dict(plant), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
