# Quite-Decent-Folks
This is a game of plants

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

- Camera: raise only the left hand to jump; raise only the right hand to slide;
  raising both hands does not trigger an action
- Up: jump
- Down: slide
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
the camera cannot be opened. Jumping and sliding use the same fast pose profile:
the active wrist may be `0.03` below shoulder height, visibility may be `0.35`,
and one valid frame triggers the action. The course has one floor and no double
or big jump. Each element pair appears at separate high and low positions on
that track. Obstacles and element pairs keep at least `360` horizontal pixels
apart, so an obstacle cannot force one of the two element choices. Camera
capture and pose inference run on background workers; the Pygame loop only
consumes queued action events and remains near its 60 FPS target.
