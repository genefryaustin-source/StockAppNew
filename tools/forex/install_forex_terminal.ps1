param(
    [string]$ZipDirectory = ".",
    [string]$ProjectRoot = "C:\StockApp"
)
$patterns = @(
"forex_portfolio_engine_terminal_*.zip",
"forex_terminal_dashboard_phase2_*.zip",
"forex_terminal_phase3_execution_*.zip",
"forex_terminal_phase4_validation_*.zip",
"forex_terminal_phase5_workstation_*.zip",
"forex_terminal_phase6_bloomberg_*.zip",
"forex_terminal_phase7_dashboard_ui_*.zip",
"forex_phase9_hardened_validation_*.zip"
)
foreach ($pattern in $patterns) {
    $zip = Get-ChildItem -Path $ZipDirectory -Filter $pattern | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($zip) {
        Write-Host "Installing $($zip.Name)" -ForegroundColor Green
        Expand-Archive -Path $zip.FullName -DestinationPath $ProjectRoot -Force
    } else {
        Write-Warning "Missing $pattern"
    }
}
Write-Host "Install complete. Restart Streamlit." -ForegroundColor Cyan
