# Level 2: Plant Guardian

Level 2 is a five-lane pixel-art defense game. The detected plant moves along
the vertical rail and attacks two zombie waves before they reach the house.
MediaPipe Hand Landmarker can move the plant with an index-finger gesture.

## Integration

```python
from level2 import run_level2
from shared_game_data import DIFFICULTIES

level2_result = run_level2(
    plant,
    DIFFICULTIES["normal"],
)
```

The integration uses the shared `PlantData`, `DifficultyConfig`, `Level2Result`,
and `ATTACK_CONFIG` data structures. Plant type, current power, and difficulty
affect the plant form, attack style, damage, zombie health, speed, and count.

## Controls

Run the standalone demo with:

```powershell
python -m level2.demo
```

Keyboard controls are always available:

- `Up` / `Down` or `W` / `S`: move the plant between rails
- `H`: enable or disable hand control
- `Escape`: quit the level

When hand control is enabled, extend only the index finger. Point up or down to
move one rail. Relax or hold the finger horizontally before triggering again.
