#define MyAppName "Manažer BOZP"
#define MyAppVersion "4.0.9"
#define MyAppPublisher "Ing. Vladimír Jindra"
#define MyAppExeName "ManazerBOZP.exe"

[Setup]
AppId={{9D1C4B8E-4A75-49C4-9E3A-BOZP30000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/
AppSupportURL=https://github.com/
AppUpdatesURL=https://github.com/
DefaultDirName={autopf}\Manazer BOZP
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=Manazer_BOZP_4_0_9_Setup
SetupIconFile=core\resources\manager_bozp.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
LicenseFile=LICENSE.txt

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"

[Tasks]
Name: "desktopicon"; Description: "Vytvořit zástupce na ploše"; GroupDescription: "Další možnosti:"; Flags: unchecked

[Files]
Source: "dist\ManazerBOZP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{localappdata}\manazer-bozp"
Name: "{localappdata}\manazer-bozp\databaze"
Name: "{localappdata}\manazer-bozp\ciselniky"
Name: "{localappdata}\manazer-bozp\konfigurace"
Name: "{localappdata}\manazer-bozp\export"
Name: "{localappdata}\manazer-bozp\import"
Name: "{localappdata}\manazer-bozp\logy"
Name: "{localappdata}\manazer-bozp\prilohy"
Name: "{localappdata}\manazer-bozp\templates"
Name: "{localappdata}\manazer-bozp\zalohy"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Spustit Manažer BOZP"; Flags: nowait postinstall skipifsilent
