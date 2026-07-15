# 打包 UPet.exe（输出到 dist\UPet.exe）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\build.ps1
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m PyInstaller --noconfirm --onefile --windowed --name UPet --icon icon.ico `
    --add-data "spritesheet.webp;." --add-data "icon.ico;." `
    --exclude-module numpy --exclude-module charset_normalizer upet.py
if ($?) { "打包完成: dist\UPet.exe" }
