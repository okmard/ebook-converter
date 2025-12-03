@echo off
cd /d "%~dp0"

echo Checking PyInstaller...
pip show pyinstaller > nul
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo.
echo Cleaning up...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist EbookConverterWeb.spec del EbookConverterWeb.spec

echo.
echo Building Web App...
echo This may take a while...

pyinstaller --noconfirm --onefile --windowed --add-data "templates;templates" --add-data "static;static" --name "EbookConverterWeb" --hidden-import=ebooklib --hidden-import=bs4 --clean app.py

echo.
if exist dist\EbookConverterWeb.exe (
    echo ==========================================
    echo Build SUCCESS!
    echo EXE file: %~dp0dist\EbookConverterWeb.exe
    echo.
    echo You can send this EXE file to other users.
    echo No Python installation required.
    echo ==========================================
) else (
    echo Build FAILED. Check errors above.
)
pause
