@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo 플레이오토 수집기 EXE 빌드
echo ========================================
echo.

:: PyInstaller로 빌드
pyinstaller --onefile --name PlayautoCollector --icon=NONE --add-data "config.json;." playauto_collector_exe.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [성공] 빌드 완료!
    echo 실행 파일: dist\PlayautoCollector.exe
    echo.
    echo 배포 시 필요한 파일:
    echo   1. dist\PlayautoCollector.exe
    echo   2. config.json (로그인 정보)
) else (
    echo.
    echo [실패] 빌드 실패
)

pause
