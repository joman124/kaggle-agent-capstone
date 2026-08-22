@echo off
REM Undoes setup_publish_task.bat: stops Windows checking for due scheduled
REM posts. Your scheduled posts stay in the dashboard, they just will not fire
REM on their own any more. Nothing else is affected.

setlocal
schtasks /delete /TN "After Work - publish scheduled posts" /F
if errorlevel 1 (
    echo.
    echo Could not remove it - it may already be gone.
) else (
    echo.
    echo Removed. Scheduled posts will no longer publish automatically.
)
echo.
pause
endlocal
