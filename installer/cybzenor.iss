; Cybzenor - Windows Kurulum Betiği (Inno Setup)
; dist\Cybzenor.exe'yi (build_exe.py çıktısı) gerçek bir Windows kurulum sihirbazına
; sarar: kullanıcı Başlat Menüsü + isteğe bağlı Masaüstü kısayolu seçebilir, standart
; "Program Ekle/Kaldır" girişi ve düzgün bir kaldırıcı (uninstaller) alır.
;
; Yönetici hakkı GEREKMEZ: uygulama kendi verisini (üretilen wordlist'ler, hedef
; profilleri, loglar) .exe'nin bulunduğu klasöre yazıyor (bkz. config/settings.py::
; _detect_base_dir) — bu yüzden kurulum dizini kasıtlı olarak Program Files DEĞİL,
; kullanıcıya özel %LocalAppData%\Programs\Cybzenor klasörüdür; aksi halde normal
; (yönetici olmayan) bir kullanıcı uygulamayı her açtığında yazma izni hatası alırdı.
;
; Derleme:
;   1) python build_exe.py               (önce dist\Cybzenor.exe üretilmeli)
;   2) ISCC installer\cybzenor.iss /DMyAppVersion=1.0.1
;   Çıktı: installer\output\CybzenorKurulum.exe

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#define MyAppName "Cybzenor"
#define MyAppPublisher "Cybzenor"
#define MyAppURL "https://github.com/nurcankarakoc/ai-password-auditor"
#define MyAppExeName "Cybzenor.exe"

[Setup]
AppId={{7AAEC039-4FA6-4EFD-B0A3-F658627FECA5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Yönetici gerektirmez; her kullanıcı kendi profiline kurar (bkz. yukarıdaki not).
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=CybzenorKurulum
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; .exe zaten Qt/CTk gibi büyük binary'ler içerdiğinden ek bir sıkıştırma katmanı
; kurulum dosyasını gereksiz büyütmesin diye orta seviye sıkıştırma yeterli.
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist\Cybzenor.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
