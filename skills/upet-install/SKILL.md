---
name: upet-install
description: 一键安装、更新或卸载 UPet 桌面宠物（Windows）。自动下载最新版 UPet.exe、创建开始菜单快捷方式、可选开机自启，并直接启动。用户提到安装 UPet、装桌宠、桌面宠物、更新 UPet、卸载 UPet、install UPet、desktop pet 时使用；即使用户只说「帮我装那个桌面宠物」「把 UPet 弄到我电脑上」也应使用本 skill，不要手动摸索安装步骤。
---

# UPet 一键安装

UPet 是一个 Windows 桌面宠物（单文件 exe，免安装依赖）。本 skill 用一个脚本完成下载、安装、快捷方式、开机自启和启动，避免用户手动跑流程或被 SmartScreen 卡住。

仓库：https://github.com/FANzR-arch/UPet

## 前提

- Windows 10/11
- 能访问 GitHub（下载约 20 MB）。访问不了时用 `-SourceExe` 离线安装（见下）

## 安装 / 更新

先问用户是否需要开机自启（如果用户已在请求里说明，直接照办，不必再问）。然后运行：

```powershell
# 普通安装（装到 %LOCALAPPDATA%\Programs\UPet 并启动）
powershell -ExecutionPolicy Bypass -File scripts/install.ps1

# 安装并开机自启
powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -AutoStart
```

更新就是重新运行同一命令：脚本会先停掉运行中的 UPet，再用最新版覆盖。

脚本做了什么（用户问起时照此解释）：

1. 从 GitHub Releases 下载最新 `UPet.exe` 到 `%LOCALAPPDATA%\Programs\UPet\`
2. `Unblock-File` 去掉网络标记，避免 SmartScreen 弹窗
3. 创建开始菜单快捷方式
4. `-AutoStart` 时在启动文件夹写 `UPet.bat` —— 与程序内「右键 → 设置 → 开机自启」是同一个文件，两边勾选状态互通
5. 启动 UPet（加 `-NoLaunch` 可跳过）

## 验证

安装后检查进程在跑即算成功：

```powershell
Get-Process -Name UPet -ErrorAction SilentlyContinue
```

有输出即安装成功，告诉用户：宠物已出现在桌面，首次会弹出画廊选宠物；单击挥手、双击跳跃、拖动跟走、滚轮缩放；右键是一切功能的入口。

## 离线 / 手动指定 exe

用户已经自己下载了 UPet.exe，或网络不通时：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -SourceExe "C:\path\to\UPet.exe"
```

## 卸载

```powershell
# 卸载，保留配置和已导入的宠物
powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -Uninstall

# 连配置和宠物一起删（%APPDATA%\UPet）——先向用户确认再执行
powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -Uninstall -RemoveData
```

## 常见问题

- **下载失败 / 超时**：GitHub 直连不稳定时，让用户手动从 Releases 页下载 exe，再走 `-SourceExe` 路径
- **杀毒软件拦截**：exe 未购买代码签名证书，个别杀软会误报；源码完全开源可查（仓库里 `upet.py` 即全部源码），让用户自行决定是否加白名单
- **想换宠物**：右键宠物 →「选择宠物」→「更多宠物」，从 CodexPets.net 下载 zip 后右键「获取宠物」导入
