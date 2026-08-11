# Level 2：植物守卫

第二关使用 Pygame 实现五条滑轨上的植物打僵尸玩法，并使用 MediaPipe Hand Landmarker 识别食指朝上、朝下手势。

## 接入主程序

```python
from level2 import run_level2
from shared_game_data import DIFFICULTIES

level2_result = run_level2(
    plant,
    DIFFICULTIES["normal"],
)
```

输入和输出严格使用 `shared_game_data.py` 中的：

- `PlantData`
- `DifficultyConfig`
- `Level2Result`
- `ATTACK_CONFIG`

植物类型、当前战力和难度会影响外观、攻击方式、伤害、僵尸生命、速度和数量。

## 单独测试

先下载官方手部模型：

```powershell
powershell -ExecutionPolicy Bypass -File setup\download_hand_model.ps1
```

然后运行：

```powershell
python -m level2.demo
```

按 `H` 开启或关闭摄像头。握起中指、无名指和小指，只伸出食指：

- 食指朝上：植物上移一格
- 食指朝下：植物下移一格
- 收回或横放食指后，才能再次触发同一方向

方向键、`W/S` 始终可以作为备用控制。
