# 打包 exe 并生成发布包（dist\UPet.exe + dist\UPet-win64.zip）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\package.ps1
& "$PSScriptRoot\build.ps1"
Set-Location (Split-Path $PSScriptRoot -Parent)
Copy-Item docs\快速上手.txt dist\使用说明.txt -Force
# 刚生成的 exe 可能被杀软短暂锁定，压缩失败时重试
for ($i = 1; $i -le 3; $i++) {
    try {
        Compress-Archive -Path dist\UPet.exe, dist\使用说明.txt `
            -DestinationPath dist\UPet-win64.zip -Force -ErrorAction Stop
        break
    } catch {
        if ($i -eq 3) { throw }
        Start-Sleep -Seconds 3
    }
}
"发布包: dist\UPet-win64.zip"
