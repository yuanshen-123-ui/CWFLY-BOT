<#
  start-py.ps1 — 启动 CWFLY 飞控机器人（Python 版）

  用法：
    powershell -ExecutionPolicy Bypass -File d:\CWFLY\bot\start-py.ps1
  或直接：
    cd d:\CWFLY\bot
    .\start-py.ps1

  说明：
    - 自动切换到 bot 根目录并设置 PYTHONPATH（使 py 包可导入）
    - 优先使用 bot 目录下的 .venv，否则用系统 python
    - 依赖缺失时自动 pip install
#>
$ErrorActionPreference = 'Stop'

# bot 根目录（本脚本所在目录）
$BotRoot = $PSScriptRoot
Set-Location $BotRoot
$env:PYTHONPATH = $BotRoot

# 选择解释器：优先 .venv，其次系统 python
$VenvPython = Join-Path $BotRoot '.venv\Scripts\python.exe'
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $Python) {
        Write-Error '未找到 python，请先安装 Python 3.10+ 并加入 PATH。'
        exit 1
    }
}
Write-Host "[start-py] 使用解释器: $Python"

# 确保依赖已安装
& $Python -c "import websockets, requests" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[start-py] 依赖缺失，正在安装..."
    & $Python -m pip install -r (Join-Path $BotRoot 'py\requirements.txt')
}

Write-Host "[start-py] 启动 Python 机器人（Ctrl+C 停止）..." -ForegroundColor Cyan
& $Python -m py.main
