param(
    [string]$ProjectRoot = "C:\StockApp",
    [string]$BackupPath
)
if (-not $BackupPath) { throw "Provide -BackupPath" }
Copy-Item -Path (Join-Path $BackupPath "*") -Destination $ProjectRoot -Recurse -Force
Write-Host "Rollback complete. Restart Streamlit."
