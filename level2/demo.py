"""Standalone launcher for teammates who want to test Level 2 directly."""

from shared_game_data import DIFFICULTIES, PlantData, PlantStatus, calculate_power

from .level2 import run_level2


def make_demo_plant() -> PlantData:
    status = PlantStatus(
        water=0.75,
        light=0.75,
        nitrogen=0.70,
        phosphorus=0.70,
        potassium=0.70,
        pest=0.90,
    )
    power = calculate_power(status)
    return PlantData(
        plant_id="LEVEL2_DEMO",
        plant_type="flower",
        image_path="",
        status=status,
        initial_power=power,
        current_power=power,
    )


if __name__ == "__main__":
    result = run_level2(make_demo_plant(), DIFFICULTIES["normal"])
    print(result)
