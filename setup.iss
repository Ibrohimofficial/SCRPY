; Inno Setup skripti — Ajib Ekran Ulagich o'rnatuvchisi (Setup.exe)
; Bu skript GitHub Actions ichida avtomatik ishlatiladi.
; O'rnatuvchi: dasturni Program Files'ga joylaydi, Desktop'ga shortcut yaratadi.

#define MyAppName "Ajib Ekran Ulagich"
#define MyAppVersion "1.0"
#define MyAppPublisher "Ajib Studio"
#define MyAppURL "https://ajibstudio.uz/"
#define MyAppExeName "ScrcpyConnect.exe"

[Setup]
AppId={{8F2A1C4E-7B3D-4A91-9C5E-1234567890AB}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=AjibEkranUlagich-Setup
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Ish stolida (Desktop) yorliq yaratish"; GroupDescription: "Qo'shimcha:"; Flags: checkedonce

[Files]
Source: "dist\ScrcpyConnect.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} ni hozir ishga tushirish"; Flags: nowait postinstall skipifsilent
