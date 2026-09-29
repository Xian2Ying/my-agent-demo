# 一键重启 My Agent：停掉占用 8000/5173 的旧进程 → 启动后端 → 启动前端 → 打开浏览器
# 用法：双击 start.bat，或在本目录执行  powershell -File start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir  = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

Write-Host "==> 1/3 停止旧的 My Agent 进程（按端口 8000/5173 精确匹配）..."
foreach ($port in @(8000, 5173)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        try {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction Stop
            Write-Host ("    端口 " + $port + " 由 PID " + $c.OwningProcess + " 占用，已停止")
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        } catch { }
    }
}
Start-Sleep -Seconds 1

Write-Host "==> 2/3 启动后端 (FastAPI :8000) 与前端 (Vite :5173)..."
Start-Process -FilePath "python"  -ArgumentList "main.py"                          -WorkingDirectory $backendDir
Start-Process -FilePath "node"    -ArgumentList "node_modules\vite\bin\vite.js"    -WorkingDirectory $frontendDir

Write-Host "==> 3/3 等待服务就绪..."
Start-Sleep -Seconds 6

try {
    $h = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -TimeoutSec 5
    if ($h.mock) { Write-Host "    后端 OK（Mock 模式：还没配 API Key）" }
    else         { Write-Host "    后端 OK（已接入真实大模型）" }
} catch {
    Write-Host "    后端仍在启动，稍后手动检查 http://localhost:8000/api/health"
}

Write-Host ""
Write-Host "浏览器将自动打开 http://localhost:5173"
Start-Process "http://localhost:5173"
Write-Host "提示：两个黑色窗口是后端和前端服务，保持别关；本窗口可以关闭。"
