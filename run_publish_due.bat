@echo off
REM Publishes any scheduled LinkedIn posts whose time has arrived, then exits.
REM Windows Task Scheduler runs this every 10 minutes, which is what makes a
REM scheduled post go out even when the dashboard is closed. It only ever
REM publishes items you scheduled yourself, and it honors the LIVE / DRY RUN
REM switch in the dashboard sidebar - in dry run it publishes nothing and
REM leaves your scheduled posts untouched.
REM
REM Console output is appended to logs\publish_due.log, and a one-line
REM PASS/FAIL lands in logs\publish_last_status.txt so a silent failure (an
REM expired LinkedIn token, say) is obvious without opening the full log.
REM
REM Set up once with setup_publish_task.bat (double-click it).

setlocal
cd /d "%~dp0"
if not exist logs mkdir logs

echo. >> logs\publish_due.log
echo ==== %date% %time% ==== >> logs\publish_due.log

if not exist venv\Scripts\activate.bat (
    echo [FAILED] %date% %time% - could not find venv\Scripts\activate.bat in this folder. Is the virtualenv set up here?> logs\publish_last_status.txt
    echo venv not found - see logs\publish_last_status.txt >> logs\publish_due.log
    endlocal & exit /b 1
)

call venv\Scripts\activate.bat

python publish_due.py >> logs\publish_due.log 2>&1
set EXITCODE=%errorlevel%
echo ---- finished, exit code %EXITCODE% ---- >> logs\publish_due.log

if "%EXITCODE%"=="0" (
    echo [OK] %date% %time% - publish check ran cleanly.> logs\publish_last_status.txt
) else (
    REM No parentheses in this message, and none in the OK one either: an
    REM unescaped ")" inside a parenthesised if-block closes the block early
    REM and cmd then fails with "- was unexpected at this time."
    echo [FAILED] %date% %time% - exit code %EXITCODE%. See logs\publish_due.log. Most likely cause: the LinkedIn token expired - they last about 60 days - so rerun "python linkedin_auth.py" to get a fresh one.> logs\publish_last_status.txt
)

endlocal & exit /b %EXITCODE%
