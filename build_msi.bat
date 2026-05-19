@echo off
echo Building MSI...

wix build -o EquityResearchTerminal.msi installer.wxs

echo MSI built successfully.
pause