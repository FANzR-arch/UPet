# UPet —— 桌面宠物小工具

一张精灵图 = 一只桌宠。常驻桌面、始终置顶、会互动、会陪你打字干活。**不需要 Codex。**

<p align="center">
  <img src="exports/wave.gif" alt="挥手">
  <img src="exports/walk-right.gif" alt="走路">
  <img src="exports/jump.gif" alt="跳跃">
  <img src="exports/working.gif" alt="思考">
</p>

<p align="center">
  <a href="https://github.com/FANzR-arch/UPet/releases/latest/download/UPet.exe"><b>⬇ 下载 UPet.exe（最新版）</b></a>
  ·
  <a href="../../releases/latest">全部版本</a>
  ·
  <a href="docs/使用说明.md">📖 使用说明</a>
</p>

<p align="center">
  <sub><b>首次运行会看到蓝色的「Windows 已保护你的电脑」？</b>点「<b>更多信息</b>」→「<b>仍要运行</b>」即可。<br>
  这只是因为没买代码签名证书，不是病毒——介意的话可以直接<a href="#从源码运行--打包">从源码运行</a>。</sub>
</p>

## 三步上手

1. **[下载 UPet.exe](https://github.com/FANzR-arch/UPet/releases/latest/download/UPet.exe)**（单文件，免安装、免运行环境）
2. **双击运行**——内置宠物直接出现在桌面，并弹出宠物画廊供挑选（被 SmartScreen 拦住见上方说明）
3. 右键宠物 → 设置 → 勾选「**开机自启**」，从此它天天在

> **用 Claude Code / AI Agent？** 仓库自带一键安装 skill（[skills/upet-install](skills/upet-install/SKILL.md)），对着 Agent 说「帮我安装 UPet」即可自动完成下载、安装、开机自启；也可直接运行：
> ```powershell
> powershell -ExecutionPolicy Bypass -File skills\upet-install\scripts\install.ps1 -AutoStart
> ```

## 能做什么

- **互动**：单击挥手、双击跳跃、拖动跟着走、Ctrl拖动/滚轮缩放、悬停会看你
- **陪伴**：你打字它思考、你点鼠标它检查、你挂机它打瞌睡、你回来它跳起来欢迎（本地检测，不记录内容，可关闭）
- **换装**：右键 →「选择宠物…」打开动图画廊。换新宠物最省事的是 [CodexPets.net](https://codexpets.net/)（842+，下载 zip → 右键「获取宠物」→ 导入，全程不碰命令行）；想要更大的库可以去 [Petdex](https://petdex.dev/)（3600+）或 [Awesome Codex Pet](https://awesome-codex-pet.pages.dev/)，但它们要复制页面上的 npx / PowerShell 命令执行。Codex 生成的宠物（`~/.codex/pets`）自动识别，无需导入

详细玩法、宠物格式、常见问题 → **[使用说明](docs/使用说明.md)**

## 仓库结构

| 路径 | 说明 |
|------|------|
| `upet.py` | 全部源码（Python + tkinter + Pillow，主题 [sv-ttk](https://github.com/rdbende/Sun-Valley-ttk-theme)） |
| `spritesheet.webp` / `pet.json` | 内置默认宠物 Phil仔 |
| `docs/使用说明.md` | 用户手册（`快速上手.txt` 为 zip 包内附带的精简版） |
| `exports/` | 各动作独立透明动图（WebP + GIF），可用于聊天/PPT/OBS |
| `scripts/build.ps1` | 打包 exe |
| `scripts/package.ps1` | 打包 exe 并生成发布 zip |
| `scripts/export_animations.py` | 把精灵图导出为独立动图 |

## 从源码运行 / 打包

```powershell
pip install pillow sv-ttk darkdetect
python upet.py                                        # 直接运行
powershell -ExecutionPolicy Bypass -File scripts\build.ps1   # 打包 dist\UPet.exe
```

## 宠物格式

8 列 × 9 行（或 11 行）透明 WebP/PNG，行顺序：待机 / 向右走 / 向左走 / 挥手 / 跳跃 / 失落 / 等待 / 思考 / 检查（/ 张望A / 张望B）。每行帧数与格子尺寸自动检测。欢迎把你做的宠物分享到 [Issues](../../issues)。

## License

[MIT](LICENSE)
