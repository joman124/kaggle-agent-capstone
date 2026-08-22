@echo off
REM ONE-TIME SETUP. Double-click this file once to teach Windows to check for
REM due scheduled posts every 10 minutes, in the background, forever (it
REM survives restarts). Nothing is published until you turn on live posting in
REM the dashboard sidebar - this only sets up the checker.
REM
REM To undo it later, double-click remove_publish_task.bat.

setlocal
cd /d "%~dp0"

set TASKNAME=After Work - publish scheduled posts

echo Registering the background publisher...
echo.

schtasks /create /TN "%TASKNAME%" /TR "wscript.exe \"%~dp0run_publish_due_hidden.vbs\"" /SC MINUTE /MO 10 /F

if errorlevel 1 (
    echo.
    echo Could not register the task. If it says "Access is denied", right-click
    echo this file and choose "Run as administrator", then try again.
    pause
    endlocal & exit /b 1
)

echo.
echo Done. Windows will now check every 10 minutes for scheduled posts.
echo.
echo   Check it ran:      logs\publish_last_status.txt
echo   Full history:      logs\publish_due.log
echo   Remove it later:   remove_publish_task.bat
echo.
pause
endlocal
