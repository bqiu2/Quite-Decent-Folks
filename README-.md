# Plant AI V2 替换说明

## 一、哪些旧文件删除

在项目根目录 `plant_game_environment` 中：

**删除：**
- `plant_ai/` 整个旧文件夹
- `run_plant_ai_test.py` 旧测试脚本

**不要删除：**
- `shared_game_data.py`
- `data/`
- `setup/`
- 第一关、第二关、MediaPipe 等其他游戏代码

如果 Git 已经正常使用，先备份一次：

```powershell
git add .
git commit -m "backup before plant ai v2"
```

然后：

```powershell
Remove-Item -Recurse -Force .\plant_ai
Remove-Item -Force .\run_plant_ai_test.py
```

如果提示文件不存在，可以忽略对应那一条。

## 二、复制新文件

把压缩包中的：

- `plant_ai/`
- `run_plant_ai_test.py`
- `build_reference_cache.py`

复制到项目根目录。

`shared_game_data.py` 使用你项目当前已有版本，不要用别的文件覆盖它。

## 三、requirements.txt

你截图里同时有项目根目录 `requirements.txt` 和 `setup/requirements.txt`。如果 `setup/requirements.txt` 仍用于环境安装/检查，两个文件应保持同一套版本，避免环境检查与实际安装不一致。

建议把项目根目录 requirements.txt 改成：

```text
pygame==2.6.1
mediapipe==0.10.35
opencv-contrib-python==4.11.0.86
numpy==1.26.4
Pillow==12.3.0
torch==2.13.0
transformers==5.15.0
safetensors==0.8.0
```

如果你已经确认原来的 pygame / mediapipe / opencv / numpy / Pillow 都正常，只想补齐 AI 包，可以先执行：

```powershell
python -m pip install -r requirements_ai_only.txt
```

需要把整个项目严格对齐到同一版本时再执行：

```powershell
python -m pip install -r requirements.txt
python -m pip check
```

## 四、准备三类参考图片

目录已经创建：

```text
plant_ai/
└── reference_images/
    ├── grass/
    ├── shrub/
    └── flower/
```

每类最低 5 张，建议 15~30 张。

这里的 `flower` 是游戏类别，不是植物学定义：**照片里必须明显看到花或花瓣**。
如果一棵植物理论上会开花，但当前照片只有叶子，应根据外观放到 grass/shrub，而不是 flower。

参考图准备好后：

```powershell
python build_reference_cache.py
```

第一次会加载模型并生成 `plant_ai/.cache/type_prototypes.npz`。
以后参考图不变就直接使用缓存。

## 五、测试

```powershell
python -u run_plant_ai_test.py ".\image.png"
```

输出会包含：
- `plant_type`
- 三类原型得分
- flower_presence
- 六维最终状态
- 六维原始状态
- 模型置信度
- 自动裁剪结果

并生成：

```text
plant_ai_debug/last_crop.jpg
```

先打开这张裁剪图，确认 AI 实际看到的植物主体是否正确。

## 六、游戏中正式调用

```python
from plant_ai import analyze_plant

plant = analyze_plant("uploads/plant.jpg")
```

返回仍然是原来的 `PlantData`，因此第一关和第二关接口不用改。
