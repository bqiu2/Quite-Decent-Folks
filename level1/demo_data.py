"""Temporary level-one input used while the plant analyzer is unavailable."""

from __future__ import annotations

from shared_game_data import PlantData, PlantStatus, PlantType, calculate_power


DEMO_STATUS = {
    "water": 0.55,
    "light": 0.62,
    "nitrogen": 0.48,
    "phosphorus": 0.52,
    "potassium": 0.58,
    "pest": 0.80,
}


def create_demo_plant(plant_type: PlantType = "flower") -> PlantData:
    """Create a valid stand-in for ``analyze_plant(image_path)`` output."""
    status = PlantStatus(**DEMO_STATUS)
    power = calculate_power(status)
    return PlantData(
        plant_id="PLANT_LEVEL1_DEMO",
        plant_type=plant_type,
        image_path="uploads/demo_plant.jpg",
        status=status,
        initial_power=power,
        current_power=power,
    )

