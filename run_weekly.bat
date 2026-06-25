@echo off
REM Runs the weekly content-planning pipeline unattended (Scout, Strategist,
REM Analyst, Writer, Substack Specialist) and appends console output to
REM logs\weekly_run.log so John can check what happened without a terminal
REM open. Drafts land in LinkedIn Posts.docx / Substack Essays.docx as usual
REM for manual review and posting - this does not publish anything.
REM
REM Set up once as a weekly Windows Task Scheduler job pointing at this file.
REM See STATUS.md for the exact setup steps.

setlocal
cd /d "%~dp0"
if not exist logs mkdir logs

call venv\Scripts\activate.bat

echo. >> logs\weekly_run.log
echo ==== %date% %time% ==== >> logs\weekly_run.log
python -m agents.orchestrator "What should I publish this week?" >> logs\weekly_run.log 2>&1
echo ---- finished, exit code %errorlevel% ---- >> logs\weekly_run.log

endlocal
