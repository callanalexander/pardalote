; Inno Setup script for the pardalote Windows installer.
; Installs per-user (no admin rights needed), adds Start menu and desktop shortcuts.
; Build after PyInstaller, from the desktop/ folder:
;   ISCC.exe /DAppVersion=1.0.0 pardalote.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{46D7346C-47A2-4156-84A7-6605FC686D29}
AppName=pardalote
AppVersion={#AppVersion}
AppPublisher=Callan Alexander
AppPublisherURL=https://github.com/callanalexander/pardalote
DefaultDirName={localappdata}\Programs\pardalote
DefaultGroupName=pardalote
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=pardalote-setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\pardalote.exe
UninstallDisplayName=pardalote
#if FileExists(AddBackslash(SourcePath) + "pardalote.ico")
SetupIconFile=pardalote.ico
#endif

[Tasks]
Name: "desktopicon"; Description: "Put a pardalote icon on the desktop"; GroupDescription: "Shortcuts:"

[InstallDelete]
; Clear out the previous version's libraries when upgrading
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\pardalote\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\pardalote"; Filename: "{app}\pardalote.exe"
Name: "{autodesktop}\pardalote"; Filename: "{app}\pardalote.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\pardalote.exe"; Description: "Start pardalote now"; Flags: nowait postinstall skipifsilent
