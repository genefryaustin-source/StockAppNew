[Setup]
AppName=Equity Research Terminal
AppVersion=1.0
DefaultDirName={pf}\EquityResearchTerminal
DefaultGroupName=Equity Research Terminal
OutputDir=installer
OutputBaseFilename=EquityResearchTerminalSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\EquityResearchTerminal\*"; DestDir: "{app}"; Flags: recursesubdirs
Source: "installer_assets\secrets.toml"; DestDir: "{userprofile}\.streamlit"; Flags: onlyifdoesntexist

[Dirs]
Name: "{userprofile}\.streamlit"; Flags: uninsneveruninstall

[Icons]
Name: "{group}\Equity Research Terminal"; Filename: "{app}\EquityResearchTerminal.exe"
Name: "{commondesktop}\Equity Research Terminal"; Filename: "{app}\EquityResearchTerminal.exe"

[Run]
Filename: "{app}\EquityResearchTerminal.exe"; Description: "Launch App"; Flags: nowait postinstall skipifsilent