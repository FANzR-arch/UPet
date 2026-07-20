# UPet 一键安装 / 更新 / 卸载脚本
# 用法：
#   安装/更新：    powershell -ExecutionPolicy Bypass -File install.ps1
#   安装+开机自启：powershell -ExecutionPolicy Bypass -File install.ps1 -AutoStart
#   卸载：         powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall
#   卸载并清数据： powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall -RemoveData
param(
    [switch]$AutoStart,
    [switch]$Uninstall,
    [switch]$RemoveData,
    [switch]$NoLaunch,
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\UPet"),
    [string]$SourceExe = ""   # 留空则从 GitHub 下载最新版；给本地路径则离线安装
)

$ErrorActionPreference = "Stop"
$DownloadUrl = "https://github.com/FANzR-arch/UPet/releases/latest/download/UPet.exe"
$ExePath     = Join-Path $InstallDir "UPet.exe"
$StartMenu   = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\UPet.lnk"
$StartupBat  = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\UPet.bat"
$DataDir     = Join-Path $env:APPDATA "UPet"

function Stop-UPet {
    $procs = Get-Process -Name "UPet" -ErrorAction SilentlyContinue
    if ($procs) {
        Write-Host "停止正在运行的 UPet..."
        $procs | Stop-Process -Force
        Start-Sleep -Milliseconds 500
    }
}

if ($Uninstall) {
    Stop-UPet
    if (Test-Path $StartupBat) { Remove-Item $StartupBat -Force; Write-Host "已移除开机自启" }
    if (Test-Path $StartMenu)  { Remove-Item $StartMenu -Force;  Write-Host "已移除开始菜单快捷方式" }
    if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force; Write-Host "已删除 $InstallDir" }
    if ($RemoveData -and (Test-Path $DataDir)) {
        Remove-Item $DataDir -Recurse -Force
        Write-Host "已删除配置和已导入的宠物（$DataDir）"
    } elseif (Test-Path $DataDir) {
        Write-Host "配置和已导入的宠物保留在 $DataDir（加 -RemoveData 可一并删除）"
    }
    Write-Host "UPet 已卸载。"
    exit 0
}

# ---------- 安装 / 更新 ----------
New-Item -ItemType Directory -Force $InstallDir | Out-Null
Stop-UPet   # 正在运行会锁住 exe，无法覆盖更新

if ($SourceExe) {
    Write-Host "从本地复制：$SourceExe"
    Copy-Item $SourceExe $ExePath -Force
} else {
    Write-Host "下载最新版 UPet.exe（约 20 MB）..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $ExePath -UseBasicParsing
}
Unblock-File $ExePath   # 去掉“来自网络”标记，减少 SmartScreen 弹窗

# 开始菜单快捷方式
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($StartMenu)
$lnk.TargetPath = $ExePath
$lnk.WorkingDirectory = $InstallDir
$lnk.Description = "UPet 桌面宠物"
$lnk.Save()

# 开机自启：写与程序内「设置 → 开机自启」相同的 UPet.bat，两边状态保持一致
if ($AutoStart) {
    Set-Content -Path $StartupBat -Value "@echo off`r`nstart `"`" `"$ExePath`"`r`n" -Encoding Default
    Write-Host "已启用开机自启"
}

Write-Host "已安装到 $ExePath"
if (-not $NoLaunch) {
    Start-Process $ExePath -WorkingDirectory $InstallDir
    Write-Host "UPet 已启动，宠物马上出现在桌面。"
}
