@echo off
REM Runs the weekly content-planning pipeline unattended (Scout, Strategist,
REM Analyst, Writer, Substack Specialist) and appends console output to
REM logs\weekly_run.log. After each run it also writes a one-line PASS/FAIL
REM to logs\weekly_last_status.txt so a silent failure (e.g. depleted Gemini
REM credits) is obvious at a glance without opening the full log, and it
REM returns the real exit code so Task Scheduler's "Last Run Result" column
REM reflects success/failure too. Drafts land in LinkedIn Posts.docx /
REM Substack Essays.docx for manual review and posting - this does not
REM publish anything.
REM
REM Set up once as a weekly Windows Task Scheduler job pointing at this file.
REM See STATUS.md for the exact setup steps.

setlocal
cd /d "%~dp0"
if not exist logs mkdir logs

echo. >> logs\weekly_run.log
echo ==== %date% %time% ==== >> logs\weekly_run.log

if not exist venv\Scripts\activate.bat (
    echo [FAILED] %date% %time% - could not find venv\Scripts\activate.bat in this folder. Is the virtualenv set up here?> logs\weekly_last_status.txt
    echo venv not found - see logs\weekly_last_status.txt >> logs\weekly_run.log
    endlocal & exit /b 1
)

call venv\Scripts\activate.bat

python -m agents.orchestrator "What should I publish this week?" >> logs\weekly_run.log 2>&1
set EXITCODE=%errorlevel%
echo ---- finished, exit code %EXITCODE% ---- >> logs\weekly_run.log

if "%EXITCODE%"=="0" (
    echo [OK] %date% %time% - weekly run succeeded. New drafts are in LinkedIn Posts.docx / Substack Essays.docx, ready to review and post.> logs\weekly_last_status.txt
) else (
    echo [FAILED] %date% %time% - exit code %EXITCODE%. See logs\weekly_run.log for the full error. Most likely cause: depleted Gemini prepaid credits - top up at https://ai.studio/projects, then rerun.> logs\weekly_last_status.txt
)

endlocal & exit /b %EXITCODE%
