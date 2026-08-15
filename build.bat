@echo off
REM QuickCopy build script (PyInstaller)
REM Note: keep this file pure ASCII - cmd.exe parses .bat files with the
REM system codepage (GBK on Chinese Windows), non-ASCII text breaks parsing.

echo ==========================================
echo   QuickCopy Build Script (PyInstaller)
echo ==========================================
echo.

REM 1. Install / upgrade dependencies
REM Note: use CALL - on this machine pip/pyinstaller are pyenv-win .bat shims,
REM and invoking a .bat from another .bat without CALL never returns.
echo [1/2] Installing dependencies: PySide6, pyinstaller ...
call pip install --upgrade PySide6 pyinstaller
if errorlevel 1 (
    echo.
    echo [FAILED] Dependency installation failed. Check your Python / pip.
    pause
    exit /b 1
)

REM 2. Build a single exe via QuickCopy.spec (onefile, windowed, slimmed).
REM Kill any running QuickCopy.exe first, otherwise dist\QuickCopy.exe is
REM locked and PyInstaller fails with PermissionError (WinError 5).
echo.
echo [2/2] Building ...
taskkill /F /IM QuickCopy.exe >nul 2>&1
call pyinstaller --noconfirm --clean QuickCopy.spec
if errorlevel 1 (
    echo.
    echo [FAILED] Build failed. See the log above.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Build complete: dist\QuickCopy.exe
echo   Double-click to run. The data file
echo   quickcopy_data.json will be created
echo   next to the exe.
echo ==========================================
pause
