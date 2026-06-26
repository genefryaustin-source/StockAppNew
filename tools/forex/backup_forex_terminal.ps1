param(
    [string]$ProjectRoot = "C:\StockApp",
    [string]$BackupRoot = "C:\StockApp\backups"
)
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dest = Join-Path $BackupRoot "forex_terminal_$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$files = @(
"modules\forex\forex_portfolio_engine.py",
"modules\forex\forex_terminal_dashboard.py",
"modules\forex\forex_terminal_api.py",
"modules\forex\forex_terminal_execution_service.py",
"modules\forex\forex_order_management_engine.py",
"ui\admin\forex_terminal_validation_center.py"
)
foreach ($file in $files) {
    $src = Join-Path $ProjectRoot $file
    if (Test-Path $src) {
        $target = Join-Path $dest $file
        New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
        Copy-Item $src $target -Force
    }
}
Write-Host "Backup created: $dest"
