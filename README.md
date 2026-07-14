# UPet —— 独立桌面宠物小工具

一张精灵图 = 一只桌宠。导入 Codex 格式的宠物精灵图，
它就会常驻你的桌面：始终置顶、会打瞌睡、陪你打字干活。**不需要 Codex。**

<p align="center">
  <img src="exports/wave.gif" alt="挥手">
  <img src="exports/walk-right.gif" alt="走路">
  <img src="exports/jump.gif" alt="跳跃">
  <img src="exports/working.gif" alt="思考">
</p>

## 快速开始

从 [Releases](../../releases) 下载 `UPet.exe`（单文件，免安装、免 Python 环境），
**双击即出宠物**——内置了默认宠物 Phil仔，无需任何配置。
首次运行会弹一次「选择宠物」窗口：可以换成本机已有的宠物、导入文件，或直达宠物站下载；
之后随时右键宠物 →「选择宠物…」再换。

从源码运行：`pip install pillow sv-ttk darkdetect` 后 `python upet.py`。

> 首次运行 exe 时 Windows SmartScreen 可能会拦截（因为 exe 未做代码签名），
> 点「更多信息」→「仍要运行」即可。介意的话可直接从源码运行。

「安装」方式：把 `UPet.exe` 和宠物精灵图 `spritesheet.webp` 放到同一个目录
（比如 `D:\Tools\UPet\`），双击 exe，右键宠物勾选「开机自启」即完成安装。

- exe 启动时会自动加载**同目录下的 `spritesheet.webp`**；
- 找不到时会弹出文件选择框，手动导入任意宠物精灵图；
- 导入过一次后路径会记住（配置存在 `%APPDATA%\UPet\config.json`）。

## 互动方式

| 操作 | 效果 |
|------|------|
| 单击 | 挥手 |
| 双击 | 跳跃 |
| 左右拖动 | 跟随拖动方向播放走路动画，松手落位（位置会记住） |
| Ctrl + 上下拖动 | 连续放大/缩小（25%~300%，脚底位置不动，大小会记住） |
| 鼠标滚轮 | 逐级放大/缩小 |
| 鼠标悬停 | 张望或挥手（有冷却，不会太频繁） |
| 右键 | 菜单：动作 / 大小 / 速度 / 导入精灵图 / 自由走动 / 感知键鼠活动 / 移到屏幕顶部 / 开机自启 / 退出 |

平时它会待机呼吸，每隔一会儿随机挥手、张望、思考，或在屏幕上走两步（可在菜单里关掉「自由走动」）。

## 感知键鼠活动

开启时（默认开，右键菜单可关），宠物会对你的电脑操作做出反应：

| 你的行为 | 宠物反应 |
|------|------|
| 连续打字 | 进入「思考工作」，停止打字后回到待机 |
| 连续点击鼠标 | 做「检查」动作 |
| 键鼠 2 分钟没动 | 失落打瞌睡 |
| 打瞌睡后你回来了 | 跳一下欢迎 |

实现只调用 Windows API 判断「是否有按键/点击」，不记录任何按键内容，不联网。

## 宠物从哪里来

UPet 是播放器，不负责造宠物。右键宠物 →「**获取宠物**」可直达这些宠物站：

| 站点 | 规模 | 怎么用 |
|------|------|------|
| [Petdex](https://petdex.dev/) | 3600+ | 复制页面上的 npx / PowerShell 命令安装，装完出现在「我的宠物」菜单里 |
| [Awesome Codex Pet](https://awesome-codex-pet.pages.dev/) | 中文社区精选 | 同上，一条命令安装 |
| [CodexPets.net](https://codexpets.net/) | 842+ | 直接下载 zip，右键 →「获取宠物」→「导入下载的宠物」选中即可 |

自己用 **Codex** 生成的宠物也会被自动识别：所有位于 `C:\Users\<你>\.codex\pets\` 下的宠物
都会出现在右键菜单「**我的宠物**」里，一键切换，切换后 Codex 开不开都无所谓。

也可以导入任何符合格式的精灵图：**8 列 × 9 或 11 行**的透明 WebP/PNG（行数自动识别），行顺序为
待机 / 向右走 / 向左走 / 挥手 / 跳跃 / 失落 / 等待 / 思考 / 检查（/ 张望 A / 张望 B）。
每行实际帧数按透明度自动检测，格子尺寸按图片大小自动推算。

欢迎把你做的宠物分享到本仓库的 Issues。

## 目录说明

| 文件 | 说明 |
|------|------|
| `upet.py` | 工具源码（Python + tkinter + Pillow，界面主题 [sv-ttk](https://github.com/rdbende/Sun-Valley-ttk-theme)） |
| `spritesheet.webp` / `pet.json` | 内置默认宠物 Phil仔 的素材 |
| `export_animations.py` | 把每个动作导出为独立动图的脚本 |
| `exports/` | 已导出的各动作透明动态 WebP + GIF（可用于网页、PPT、聊天、OBS） |
| `icon.ico` | exe 图标（Phil仔头像） |

## 重新打包

改了 `upet.py` 之后重新生成 exe：

```
python -m PyInstaller --noconfirm --onefile --windowed --name UPet --icon icon.ico --add-data "spritesheet.webp;." --add-data "icon.ico;." --exclude-module numpy --exclude-module charset_normalizer upet.py
```

## 重新导出动图

```
python export_animations.py            # 原始尺寸 8fps
python export_animations.py --scale 2  # 放大 2 倍
```
