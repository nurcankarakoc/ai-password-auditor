@echo off
REM Cybzenor - Masaüstü Arayüzünü Başlat (çift tıklayarak da çalıştırılabilir)
cd /d "%~dp0"
pythonw "%~dp0launch_gui.py" || python "%~dp0launch_gui.py"
