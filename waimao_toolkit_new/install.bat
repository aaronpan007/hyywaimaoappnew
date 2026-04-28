@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: waimao_toolkit_new installer for Windows
:: Usage: install.bat [--target-dir DIR] [--skip-chromium]

set "TARGET_DIR=.claude\skills"
set "SKIP_CHROMIUM=0"

:: Parse arguments
:parse_args
if "%~1"=="" goto :done_args
if "%~1"=="--target-dir" (
    set "TARGET_DIR=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--skip-chromium" (
    set "SKIP_CHROMIUM=1"
    shift
    goto :parse_args
)
echo Unknown option: %~1
echo Usage: install.bat [--target-dir DIR] [--skip-chromium]
exit /b 1
:done_args

set "SCRIPT_DIR=%~dp0"
:: Remove trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: Determine absolute target path
cd /d "%CD%"
set "TARGET_ABS=%CD%\%TARGET_DIR%"

echo === Waimao Toolkit Installer ===
echo Source:  %SCRIPT_DIR%\skills\
echo Target:  %TARGET_ABS%\
echo.

:: Create target directory
if not exist "%TARGET_ABS%" mkdir "%TARGET_ABS%"

:: Copy skills
set "SKILLS=_shared company-profile customer-acquisition email-craft email-blast"

for %%S in (%SKILLS%) do (
    set "SRC=%SCRIPT_DIR%\skills\%%S"
    set "DST=%TARGET_ABS%\%%S"

    if not exist "!SRC!" (
        echo WARNING: %%S not found in source, skipping
    ) else (
        echo Copying %%S ...
        if not exist "!DST!" mkdir "!DST!"

        :: Use robocopy to copy, excluding unwanted items
        robocopy "!SRC!" "!DST!" /E /NFL /NDL /NJH /NJS ^
            /XD __pycache__ .agents sources output ^
            /XF *.pyc profile.json profile.md *.csv config.json skills-lock.json >nul 2>&1

        :: robocopy returns 1 on success (files copied), 0 if nothing to copy
        if errorlevel 8 (
            echo   ERROR copying %%S
        )
    )
)

:: Replace __SKILL_DIR__ placeholder in all SKILL.md files
echo.
echo Replacing path placeholders ...

for /r "%TARGET_ABS%" %%F in (SKILL.md) do (
    :: Use PowerShell for text replacement (reliable on Windows)
    powershell -Command "(Get-Content '%%F' -Raw) -replace '__SKILL_DIR__', '%TARGET_ABS:\=/%' | Set-Content '%%F' -NoNewline" 2>nul
    echo   Updated: %%~nxF in %%~dpF
)

:: -------------------------------------------------------
:: Step 3: Install dependencies
:: -------------------------------------------------------
call :check_and_install_deps
if errorlevel 1 goto :eof

goto :skip_deps_function

:check_and_install_deps
echo.
echo === Checking Dependencies ===

:: --- Step 1: Check toolchain ---
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+ first.
    exit /b 1
)

where pip >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip not found. Please install pip first.
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found. Please install Node.js first.
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm not found. Please install npm first.
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   Python: python ^(%%v^)
echo   pip:    pip
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo   Node:   %%v
for /f "tokens=*" %%v in ('npm --version 2^>^&1') do echo   npm:    %%v

:: --- Step 2: Install missing Python packages ---
echo.
echo Checking Python packages ...

:: requests
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo   [Installing] requests ...
    pip install requests --quiet
    echo   [OK] requests (installed)
) else (
    echo   [OK] requests
)

:: beautifulsoup4 (import as bs4)
python -c "import bs4" >nul 2>&1
if errorlevel 1 (
    echo   [Installing] beautifulsoup4 ...
    pip install beautifulsoup4 --quiet
    echo   [OK] beautifulsoup4 (installed)
) else (
    echo   [OK] beautifulsoup4
)

:: python-dotenv (import as dotenv)
python -c "import dotenv" >nul 2>&1
if errorlevel 1 (
    echo   [Installing] python-dotenv ...
    pip install python-dotenv --quiet
    echo   [OK] python-dotenv (installed)
) else (
    echo   [OK] python-dotenv
)

:: replicate
python -c "import replicate" >nul 2>&1
if errorlevel 1 (
    echo   [Installing] replicate ...
    pip install replicate --quiet
    echo   [OK] replicate (installed)
) else (
    echo   [OK] replicate
)

:: playwright
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo   [Installing] playwright ...
    pip install playwright --quiet
    echo   [OK] playwright (installed)
) else (
    echo   [OK] playwright
)

:: --- Step 3: Playwright Chromium browser ---
if "%SKIP_CHROMIUM%"=="1" (
    echo.
    echo Skipping Chromium browser (--skip-chromium).
) else (
    echo.
    echo Checking Playwright Chromium browser ...
    python -c "from playwright.sync_api import sync_playwright; import os; p=sync_playwright().start(); print(os.path.exists(p.chromium.executable_path)); p.stop()" >nul 2>&1
    if errorlevel 1 (
        echo   [Installing] Playwright Chromium (~150MB) ...
        python -m playwright install chromium
        echo   [OK] Chromium browser installed
    ) else (
        echo   [OK] Chromium browser already installed
    )
)

:: --- Step 4: lark-cli (optional) ---
echo.
echo Checking lark-cli (optional) ...
npx lark-cli --version >nul 2>&1
if errorlevel 1 (
    echo   [SKIP] lark-cli not found.
    echo          If you need Feishu/Lark spreadsheet support,
    echo          install it with: npm install -g @larksuite/cli
) else (
    echo   [OK] lark-cli available via npx
)

echo.
echo === Dependencies Ready ===
exit /b 0

:skip_deps_function

:: Copy .env.example to project root if .env doesn't exist
set "ENV_FILE=%CD%\.env"
if not exist "%ENV_FILE%" (
    if exist "%SCRIPT_DIR%\.env.example" (
        copy "%SCRIPT_DIR%\.env.example" "%ENV_FILE%" >nul
        echo.
        echo Created .env file. Please fill in your API keys:
        echo   %ENV_FILE%
    )
) else (
    echo.
    echo .env already exists, skipping creation.
)

echo.
echo === Installation Complete ===
echo Skills installed to: %TARGET_ABS%
echo.
echo Next steps:
echo   1. Edit .env and add your API keys
echo   2. Restart your AI agent to load the new skills
echo.

endlocal
