@echo off
echo Building EA FC 25 Backup Manager...

REM Poistetaan vanhat buildit jos niitä on
rmdir /s /q build
rmdir /s /q dist
del /q EA_FC25_Backup_Manager.spec

REM Ajetaan PyInstaller
pyinstaller --onefile --windowed --icon=new_icon.ico --name "EA FC 25 Backup Manager" --version-file=version_info.txt fc25_backup_gui.py


echo Build completed!
pause
