; ============================================================
;  ChangeFormatUSB — Inno Setup 6 installer script
;  Requiere Inno Setup 6.x  https://jrsoftware.org/isinfo.php
; ============================================================

#define AppName        "ChangeFormatUSB"
#define AppVersion     "2.0"
#define AppPublisher   "Vicemi"
#define AppURL         "https://github.com/Vicemi/ChangeFormatUsb"
#define AppExeName     "ChangeFormatUSB.exe"
#define AppDescription "Convierte el formato de unidades USB sin perder datos"

[Setup]
AppId={{F3A7C2B1-D8E4-4F9A-BC12-5E6D7A8B9C0D}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=dist\installer
OutputBaseFilename=ChangeFormatUSB-Setup-{#AppVersion}
SetupIconFile=resources\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardResizable=no
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0.17763
ShowLanguageDialog=no
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
DisableProgramGroupPage=auto
UsePreviousAppDir=yes
VersionInfoVersion={#AppVersion}.0.0
VersionInfoDescription={#AppDescription}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.WelcomeLabel1=Bienvenido al asistente de instalacion de [name]
spanish.WelcomeLabel2=Este programa instalara [name/ver] en tu computadora.%n%nConvierte el formato de tus unidades USB (NTFS, FAT32, exFAT, ReFS) sin perder datos.%n%nSe recomienda cerrar todas las demas aplicaciones antes de continuar.
english.WelcomeLabel1=Welcome to the [name] Setup Wizard
english.WelcomeLabel2=This will install [name/ver] on your computer.%n%nConverts USB drive formats (NTFS, FAT32, exFAT, ReFS) without data loss.%n%nClose all other applications before continuing.

[Tasks]
Name: "desktopicon"; \
    Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; \
    Flags: unchecked

[Files]
Source: "dist\{#AppExeName}"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    Comment: "{#AppDescription}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; \
    Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    Tasks: desktopicon; \
    Comment: "{#AppDescription}"

[Run]
Filename: "{app}\{#AppExeName}"; \
    Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent runascurrentuser

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
{ ─── Prevent downgrade ─── }
function InitializeSetup: Boolean;
var
  InstalledVer: String;
begin
  Result := True;
  if RegQueryStringValue(HKLM,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppName}_is1',
    'DisplayVersion', InstalledVer) then
  begin
    if CompareStr(InstalledVer, '{#AppVersion}') > 0 then
    begin
      MsgBox('Ya tienes instalada una version mas reciente (' + InstalledVer + ').'#13#10 +
             'Desinstala la version actual antes de continuar.',
             mbError, MB_OK);
      Result := False;
    end;
  end;
end;
