把参考图片分别放到：

reference_images/grass/
reference_images/shrub/
reference_images/flower/

最低：每类 5 张（只用于让程序能够构建原型）
建议：每类 15~30 张

图片要求：
1. 尽量只拍植物主体。
2. 背景、拍摄角度、光照尽量多样。
3. grass：以细长、线形、草状叶为主要特征。
4. shrub：以灌木/灌丛、分枝、较宽叶片为主要特征；照片中尽量不要有明显花朵。
5. flower：照片中必须明显看到花、花瓣或花序。
6. 不要把同一张图复制多份。
7. 不要把“会开花但当前没有花”的植物放入 flower；按照片当下外观分。

加入/删除参考图后，程序会自动检测变化并重建缓存。
也可以手动执行：
    python build_reference_cache.py
