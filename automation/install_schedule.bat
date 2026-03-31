@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo 플레이오토 자동 수집 스케줄러 설치
echo ========================================
echo.

:: 현재 디렉토리 경로
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_PATH=%SCRIPT_DIR%run_collector.bat"

:: 관리자 권한 확인
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [오류] 관리자 권한으로 실행해주세요.
    echo        이 파일을 우클릭 후 "관리자 권한으로 실행" 선택
    pause
    exit /b 1
)

:: 기존 작업 삭제 (있으면)
schtasks /delete /tn "PlayautoCollector" /f >nul 2>&1

:: 새 작업 등록 (매일 오전 8시)
schtasks /create /tn "PlayautoCollector" /tr "\"%SCRIPT_PATH%\"" /sc daily /st 08:00 /rl highest /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [성공] 스케줄러 등록 완료!
    echo.
    echo 설정 내용:
    echo   - 작업 이름: PlayautoCollector
    echo   - 실행 시간: 매일 오전 8:00
    echo   - 실행 파일: %SCRIPT_PATH%
    echo.
    echo 스케줄러 확인: 작업 스케줄러 ^> PlayautoCollector
) else (
    echo.
    echo [실패] 스케줄러 등록 실패
)

echo.
pause
