# pubg-
利用电脑像素来做比例尺的原理测量pubg地图距离因为采用像素测距的原理，全程不读取内存，不修改文件，没有封禁的风险
建议先用电脑自带的截图软件测出不同缩放大小一百米所包含的像素量，然后填入对应比例尺。<img width="984" height="437" alt="cee4dea3c0815ddcb5373e061e421646" src="https://github.com/user-attachments/assets/69af1661-f303-4e5f-bfb7-51e3ca5ab34b" />
<img width="410" height="144" alt="image" src="https://github.com/user-attachments/assets/28e528a6-aaf6-47f3-868f-d82425e030c6" />
有图片识别功能，识别阈值越低就越快，但也容易误标，建议50-75
<img width="276" height="65" alt="image" src="https://github.com/user-attachments/assets/73d28f01-2087-412c-802c-57e564c29de8" />

<img width="434" height="271" alt="image" src="https://github.com/user-attachments/assets/ed1a9c3c-05a4-45b1-9904-f160cbd3eea1" />
设置好快捷键后操作方法是，先打开显示点位，打开居中显示，打开图片识别，就能自动锁定标点，从而达到自动测距的功能
<img width="280" height="198" alt="image" src="https://github.com/user-attachments/assets/ef69fb1b-bf42-4ee0-aa6a-9a0464788a26" />
打开地图时点一下空格就能跳转到人物中心视角，可以手动测距也可以开启图像识别自动测距

这是一款基于 Python + Tkinter + OpenCV + pynput + PIL 开发的桌面多点标注、图像识别、实时测距工具，主要实现屏幕多点标记、模板图像匹配识别、像素距离换算实际米数、全局快捷键控制、悬浮数据面板、系统托盘后台运行等功能。
适用于需要在屏幕上标记多个点位、自动识别指定图标 / 画面、实时计算点位间距离的场景，支持自定义点位颜色、大小、全局快捷键、测距比例尺、识别阈值等全部参数，配置自动本地保存。
二、环境依赖 & 安装
1. 运行环境
Python 3.8 及以上版本
Windows 系统（代码依赖屏幕截取、全局键鼠监听、窗口置顶 / 透明，优先适配 Windows）
2. 依赖库安装
打开 CMD / PowerShell / 终端，执行以下命令批量安装依赖：
bash
运行
pip install tkinter numpy opencv-python pillow pynput pystray
依赖说明：
tkinter：图形界面（Python 自带，部分精简系统需手动安装）
numpy：矩阵运算，配合 OpenCV 图像识别
opencv-python：图像模板匹配识别核心
pillow(PIL)：屏幕截图、图片绘制、托盘图标
pynput：全局键盘、鼠标监听，实现全局快捷键
pystray：系统托盘最小化功能（可选，缺失仅无法托盘运行）
提示：若提示 pystray 安装失败，不影响主体功能，只是程序无法最小化到系统托盘。
