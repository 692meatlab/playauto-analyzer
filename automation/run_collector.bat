@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo 플레이오토 데이터 수집기 실행
echo %date% %time%
echo ========================================

:: Python 실행
python playauto_collector_exe.py

if %ERRORLEVEL% EQU 0 (
    echo [성공] 데이터 수집 완료
) else (
    echo [실패] 데이터 수집 실패 - 로그 확인 필요
)

echo ========================================
