# Plant Guardian

Plant Guardian is a pixel-art adventure in which a real plant becomes the
player's character. The game analyzes an uploaded plant image, classifies it as
`grass`, `shrub`, or `flower`, estimates six health dimensions, and carries the
result into two playable levels.

The project is a local Python/Pygame application. The interface and in-game
text are in English.

## Game flow

```text
Plant photo
    │
    ▼
BioCLIP classification + six-dimension health analysis
    │
    ▼
Plant ID, radar chart, plant sprite, and initial power
    │
    ▼
Level 1: collect what the plant needs
    │
    ▼
Level 2: defend the farmhouse
    │
    ▼
Final score + JSON result
```

### Plant analysis

The analyzer produces a shared `PlantData` object containing:

- a generated ID such as `PLANT_0025`;
- one of three visual classes: `grass`, `shrub`, or `flower`;
- six normalized health values in the range `0.0` to `1.0`:
  `water`, `light`, `nitrogen`, `phosphorus`, `potassium`, and `pest`;
- initial and current battle power.

Power uses a weak-link calculation: the minimum of the five nutrient values has
the largest influence, the nutrient average has a smaller influence, and the
`pest` health value multiplies the result.

### Level 1 — Plant Runner

The player runs through a forest field for up to 40 seconds with three health
points. Collectible icons represent water, light, nitrogen, phosphorus,
potassium, and pesticide. Nutrient pickups improve the matching status value;
pesticide improves the `pest` health value. The live radar and power readout
update immediately.

The level includes ground routes, floating platforms, air-only pickups, ground
or platform pickups, obstacles, pickup break animations, and an animated farmer
carrying the selected potted plant.

Before the run, choose a control method:

- Keyboard: `W` jump/up, `S` drop from a platform/down, `A` crouch, `D` big jump.
- Camera pose: raise the left hand to jump and the right hand to crouch. Raising
  both hands does not trigger an action.
- `M`: mute or unmute Level 1 audio.
- `Escape`: leave the level.

The camera mode uses MediaPipe Pose Landmarker. Keyboard mode remains available
when no camera can be opened.

### Level 2 — Plant Guardian

The second level is a five-lane farmhouse defense game with two pest waves.
The plant moves on the perspective rail and attacks pests in its current lane.
Keyboard controls are always available:

- `W` / `Up`: move up one lane;
- `S` / `Down`: move down one lane;
- `H`: enable or disable MediaPipe hand control;
- `R`: restart after a result screen;
- `Escape` or `Q`: leave the level.

With hand control enabled, point the index finger up or down to move one lane.
The level BGM is stored at `assets/level2/level2_bgm.mp3`, loops until the level
ends, and stops on victory, defeat, or exit.

The pest roster is:

- Locust: descends vertically from the upper-right, is immune while flying, then
  lands and crawls toward the farmhouse.
- Aphid: adult → two eggs → nymph → adult. Each stage transition stays at the
  same world position; eggs hatch in place and nymphs mature in place.
- Caterpillar: slow ground pest with ordinary health and movement.
- Leafhopper: fast ground pest with repeated hop steps.

Plant attack styles are data-driven:

| Plant class | Attack | Gameplay profile |
| --- | --- | --- |
| `grass` | Sword wave | Fast, single target |
| `shrub` | Earthquake wave | Slower, penetrates multiple pests |
| `flower` | Petal shot | Fires three projectiles |

The plant's current power affects projectile damage. The player wins after both
waves and all spawned lifecycle pests are cleared; the player loses if a pest
reaches the farmhouse.

## Requirements

- Windows, macOS, or Linux with a working Python installation;
- Python `3.12.13` is the tested project version;
- a display and audio device for interactive play;
- a camera only when using camera or hand controls.

The pinned packages are listed in [setup/requirements.txt](setup/requirements.txt):

- Pygame 2.6.1;
- MediaPipe 0.10.35;
- OpenCV contrib 4.11.0.86;
- NumPy 1.26.4;
- Pillow 12.3.0;
- PyTorch 2.13.0;
- Transformers 5.15.0;
- Safetensors 0.8.0;
- OpenCLIP 3.3.0.

## Installation

The maintained setup is a Conda environment on Python 3.12.13:

```powershell
conda create -n plant-game python=3.12.13 -y
conda activate plant-game
python -m pip install --upgrade pip
python -m pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python-headless
python -m pip install -r setup/requirements.txt
python setup/check_environment.py
```

The same dependency set is also described in [setup/environment.yml](setup/environment.yml).

### Required model files

The two MediaPipe models are stored in `assets/models/`:

- `pose_landmarker.task` for Level 1 pose control;
- `hand_landmarker.task` for Level 2 hand control.

If they are missing, download the hand model with:

```powershell
powershell -ExecutionPolicy Bypass -File setup/download_hand_model.ps1
```

The pose model is documented in [assets/models/README.txt](assets/models/README.txt).
Camera controls can be disabled with `--no-camera`, but the plant analyzer still
requires the BioCLIP model unless demo mode is used.

### BioCLIP model

The local BioCLIP weights are expected at:

```text
models/bioclip/open_clip_pytorch_model.bin
```

Download or repair that file with:

```powershell
python download_bioclip_model.py
```

The downloader uses the `imageomics/bioclip` Hugging Face repository and may
require `huggingface_hub` in the active environment:

```powershell
python -m pip install huggingface_hub
```

The current project checkout contains the large weight file, but keeping model
weights outside version control is recommended for normal collaboration.

## Run the game

Analyze a supplied image and run the complete game:

```powershell
python main.py path\to\plant.jpg
```

If no image path is supplied, the launcher opens a native file picker:

```powershell
python main.py
```

Useful options:

```text
--demo                    use the built-in demo PlantData and skip BioCLIP
--device cpu|cuda         choose the analyzer device
--difficulty easy|normal|hard
                          skip the Level 2 difficulty picker
--no-camera               use keyboard controls in Level 1
--output path\result.json save to an explicit JSON path
--no-wait                 skip interactive analysis/tutorial/result waits
```

Examples:

```powershell
python main.py --demo --difficulty normal --no-camera
python main.py uploads\my_plant.jpg --device cpu --no-camera
python main.py --demo --no-wait --output data\demo_result.json
```

The default final result path is:

```text
data/result_<plant_id>.json
```

## Run individual levels

Level 1's integration API accepts a `PlantData` instance:

```python
from level1 import run_level1

result = run_level1(plant, use_camera=False)
```

For a standalone keyboard demo:

```powershell
python -m tools.run_level1_demo
```

Level 2's integration API accepts a plant and difficulty configuration:

```python
from level2 import run_level2
from shared_game_data import DIFFICULTIES

result = run_level2(plant, DIFFICULTIES["normal"])
```

For the standalone Level 2 demo:

```powershell
python -m level2.demo
```

## Plant AI utilities

Analyze a test image without starting the game:

```powershell
python run_plant_ai_test.py test1.png
python run_plant_ai_test.py test1.png --debug-health
```

The public AI API is lazy-loaded so importing `plant_ai` does not load the
large model immediately:

```python
from plant_ai import analyze_plant, analyze_health, classify_plant

plant = analyze_plant("test1.png", device="cpu")
plant_class = classify_plant(image, device="cpu")
status = analyze_health(image, device="cpu")
```

`classify_plant` returns one of `grass`, `shrub`, or `flower`; health values are
normalized to `0.0`–`1.0`.

## Tests and diagnostics

Run the complete automated test suite:

```powershell
python -m unittest discover -s tests -v
```

The suite covers shared scoring, Level 1 movement and collisions, Level 2
configuration and playthroughs, hand/pose control, and main-flow result saving.

Run the camera diagnostic independently:

```powershell
python -m tools.run_camera_diagnostic
```

For headless smoke checks, the code recognizes these environment variables:

```powershell
$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"
$env:PLANT_GAME_SMOKE_TEST = "1"
$env:PLANT_GAME_SKIP_TUTORIAL = "1"
python -m unittest discover -s tests -q
```

## Project layout

```text
PlantGuardian/
├── main.py                         Complete game launcher
├── shared_game_data.py             Shared data classes, scoring, and rules
├── plant_ai/                       BioCLIP class and health analysis
├── level1/                         Runner gameplay, map, items, audio
├── level2/                         Farm defense, pests, waves, projectiles
├── vision/                         MediaPipe pose and hand controllers
├── ui/                             Shared pixel-art drawing helpers
├── assets/
│   ├── level1/                     Level 1 background
│   ├── level2/                     Level 2 background and looping BGM
│   │   └── pests/                   Locust, aphid, caterpillar, leafhopper sheets
│   ├── models/                     MediaPipe `.task` files
│   ├── plants/                     Grass, shrub, and flower sprites
│   ├── runner/                     Farmer run, jump, and crouch sprites
│   └── ui/                         Shared menu background
├── models/bioclip/                 Local BioCLIP weights
├── data/                            Plant ID counter and saved results
├── uploads/                         Optional user image workspace
├── setup/                           Requirements and environment helpers
├── tools/                           Demos and diagnostics
└── tests/                           Automated tests
```

## Shared data contract

`shared_game_data.py` is the integration boundary between the analyzer, both
levels, and the final result screen. The main objects are:

- `PlantStatus`: six normalized health dimensions;
- `PlantData`: plant identity, class, image path, status, and power;
- `Level1Result`: pickups, damage, health, power change, and Level 1 score;
- `Level2Result`: victory state, waves, pests, battle time, and Level 2 score;
- `FinalResult`: final score, difficulty multiplier, and victory state.

Keep shared names and scoring rules in this file when changing the integration
between modules.

## Troubleshooting

**The game opens but camera actions do nothing**

Check that the relevant `.task` model exists in `assets/models/`, close other
camera applications, or start with `--no-camera` and use keyboard controls.

**BioCLIP cannot be loaded**

Confirm that `models/bioclip/open_clip_pytorch_model.bin` exists and that the
active Python environment contains PyTorch, OpenCLIP, and `huggingface_hub`.
Use `python download_bioclip_model.py` to repair the local model.

**No audio is available**

The levels are designed to remain playable without audio. Level 1 falls back to
its procedural audio manager; Level 2 skips its MP3 if Pygame cannot initialize
the mixer or decode the file.

**The game appears frozen during first analysis**

The first BioCLIP load is expensive. Use `--device cpu` for compatibility or
`--demo` to verify the game without model inference.

## License and asset note

This repository is a project workspace containing code, generated pixel-art
assets, local model files, and test images. Check the license and redistribution
terms of any third-party model, font, sound, or reference asset before sharing
the complete bundle.
