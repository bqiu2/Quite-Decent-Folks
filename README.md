# Quite-Decent-Folks
This is a game of plants

## Run the complete game

The end-to-end launcher connects plant analysis, Level 1, Level 2, and final
score saving:

```powershell
python main.py path\to\plant.jpg
```

With no image path, the launcher opens a file picker. For a model-free demo:

```powershell
python main.py --demo --difficulty normal
```

Useful development options are `--device cpu`, `--no-camera`, `--no-wait`, and
`--output data\my_result.json`. The final result is saved as JSON under `data/`
by default.

## Pixel-art analysis flow

After the plant image is analyzed, the game pauses on an analysis card showing
the generated plant ID, plant type, six-dimension health radar, initial battle
power, and the matching pixel plant form. Press `Enter` or `Space` to start
Level 1.

Level 1 keeps a live version of the same radar in the upper-right status panel.
Collecting water, light, nitrogen, phosphorus, or potassium updates the radar
and current power immediately; the starting power and power delta remain visible
for comparison. The runner, plant forms, background, collectibles, and HUD use
the same block-based pixel palette across both levels.

plant_game/
│
├── main.py
│
├── game_data.py
│
├── config.py
│
├── scoring.py
│
│
├── plant_ai/
│   ├── __init__.py
│   ├── classifier.py
│   ├── diagnosis.py
│   └── plant_analyzer.py
│
├── level1/
│   ├── __init__.py
│   ├── level1.py
│   ├── player.py
│   ├── map.py
│   ├── items.py
│   └── collision.py
│
├── level2/
│   ├── __init__.py
│   ├── level2.py
│   ├── plant_player.py
│   ├── zombie.py
│   ├── projectile.py
│   └── wave_manager.py
│
├── vision/
│   ├── pose_control.py
│   └── hand_control.py
│
├── ui/
│   ├── menu.py
│   ├── tutorial.py
│   ├── hud.py
│   └── result.py
│
├── assets/
│   ├── plants/
│   │   ├── grass/
│   │   ├── shrub/
│   │   └── flower/
│   │
│   ├── player/
│   ├── zombies/
│   ├── elements/
│   ├── level1/
│   ├── level2/
│   ├── ui/
│   └── fonts/
│
├── uploads/
│
└── data/

## Level 1 development

While the plant analyzer is not providing data, run the keyboard-playable
level-one demo with explicit temporary `PlantData` values:

```powershell
& "D:\tool\conda\envs\plant-game\python.exe" -m tools.run_level1_demo
```

The temporary values live in `level1/demo_data.py`. The demo prints the input,
the returned `Level1Result`, and the mutated plant data. Production code does
not silently fall back to these values: `run_level1(plant)` still requires the
real object from `analyze_plant(image_path)`. Level one lasts 40 seconds.

Controls:

- At the start of Level 1, choose Keyboard or Camera Pose control.
- Keyboard: W jump/up, S crouch on the ground or drop/down from a floating platform, A crouch, D big jump
- Camera Pose: raise only the left hand to jump; raise only the right hand to
  crouch; raising both hands does not trigger an action
- M: mute / unmute sound effects and background music
- Escape: return an incomplete result and close the level

Run the automated checks:

```powershell
& "D:\tool\conda\envs\plant-game\python.exe" -m unittest discover -s tests -v
```

Probe camera hardware and preview pose actions independently from the game:

```powershell
& "D:\tool\conda\envs\plant-game\python.exe" -m tools.run_camera_diagnostic
```

The analyzer converts the uploaded plant photo into `PlantData`; it does not
provide live control frames. Level one opens and closes the first readable
camera itself, displays a mirrored preview, and keeps keyboard controls
available. The integration API remains:

```python
level1_result = run_level1(plant)
```

Tests may disable camera access with `run_level1(plant, use_camera=False)` or
inject an alternate callable through `action_provider`.

Pose input uses the MediaPipe Lite model at
`assets/models/pose_landmarker.task`. Keyboard control remains available when
the camera cannot be opened. Each live element pair now offers one running-lane
pickup and one air-route pickup; platform pickups are attached to the passing
floating platforms. Air pickups can only be collected while jumping, while
ground/platform pickups can only be collected while standing on their route.
Collected elements briefly break into pixel shards; untouched pair members stay
visible. The runner also has moving air platforms that can be landed on and
dropped through with S. Jumping and sliding use the same fast pose profile:
the active wrist may be `0.03` below shoulder height, visibility may be `0.35`,
and one valid frame triggers the action. Obstacles and element pairs keep at
least `360` horizontal pixels apart, so an obstacle cannot force one of the two element choices. Camera
capture and pose inference run on background workers; the Pygame loop only
consumes queued action events and remains near its 60 FPS target.
