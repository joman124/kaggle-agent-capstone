@echo off
REM Opens the After Work agent dashboard (the Streamlit app in app.py) in
REM your browser. Double-click this file, wait a few seconds, and a browser
REM tab opens automatically at http://localhost:8510.
REM
REM The port is pinned to 8510 on purpose. Streamlit's default is 8501, and
REM the separate Metis project already runs there - launching on the default
REM silently showed the Metis app instead of this one.
REM
REM To stop the app: close this black console window (or press Ctrl+C in it).
REM Closing just the browser tab does NOT stop it - the console window is
REM the app; the browser is only the view.

setlocal
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo Could not find venv\Scripts\activate.bat in this folder.
    echo Is the virtualenv set up here? See README.md Quickstart.
    pause
    endlocal & exit /b 1
)

call venv\Scripts\activate.bat

REM Streamlit's very first launch stops to ask for an email address in the
REM console, which looks like a hang if you double-clicked this file. Writing
REM a blank credentials file once skips that prompt forever.
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    echo [general]> "%USERPROFILE%\.streamlit\credentials.toml"
    echo email = "">> "%USERPROFILE%\.streamlit\credentials.toml"
)

echo Starting the dashboard... a browser tab will open in a few seconds.
echo Leave this window open while you use the app. Close it to stop the app.
python -m streamlit run app.py --server.port 8510

endlocal
