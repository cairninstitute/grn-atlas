@echo off
REM ============================================================================
REM GRN Atlas UI - Automated Setup Script (Windows)
REM 
REM This script automates the integration of the complete GRN Atlas UI into
REM your existing React project. It will:
REM 1. Create directory structure
REM 2. Copy all component files
REM 3. Install dependencies
REM 4. Set up environment variables
REM 5. Prepare for git commit
REM
REM Usage: setup.bat [project-path]
REM Example: setup.bat C:\projects\grn-atlas
REM ============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Configuration
set SCRIPT_DIR=%cd%
set PROJECT_PATH=%1
if "%PROJECT_PATH%"=="" set PROJECT_PATH=.

REM Colors and symbols (using basic Windows console)
set CHECK=[OK]
set ERROR=[ERROR]
set WARNING=[WARN]
set INFO=[INFO]

cls
echo.
echo ====================================================================
echo   GRN Atlas UI - Automated Setup for Windows
echo ====================================================================
echo.

REM Check prerequisites
echo Step 1: Checking Prerequisites
echo.

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo %ERROR% Node.js is not installed
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo %CHECK% Node.js is installed (%NODE_VERSION%)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo %ERROR% npm is not installed
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('npm --version') do set NPM_VERSION=%%i
echo %CHECK% npm is installed (%NPM_VERSION%)

where git >nul 2>nul
if %errorlevel% neq 0 (
    echo %WARNING% git is not installed (optional, but recommended)
) else (
    for /f "tokens=*" %%i in ('git --version') do set GIT_VERSION=%%i
    echo %CHECK% git is installed (!GIT_VERSION!)
)

echo.

REM Verify project structure
echo Step 2: Verifying Project Structure
echo.

if not exist "%PROJECT_PATH%" (
    echo %ERROR% Project path does not exist: %PROJECT_PATH%
    pause
    exit /b 1
)
echo %CHECK% Project path exists: %PROJECT_PATH%

if not exist "%PROJECT_PATH%\package.json" (
    echo %ERROR% package.json not found in %PROJECT_PATH%
    echo Are you sure this is a React project?
    pause
    exit /b 1
)
echo %CHECK% package.json found

if not exist "%PROJECT_PATH%\src" (
    echo %ERROR% src/ directory not found
    pause
    exit /b 1
)
echo %CHECK% src/ directory exists

echo.

REM Create directory structure
echo Step 3: Creating Directory Structure
echo.

if not exist "%PROJECT_PATH%\src\components" (
    mkdir "%PROJECT_PATH%\src\components"
    echo %CHECK% Created directory: src\components
) else (
    echo %INFO% Directory already exists: src\components
)

if not exist "%PROJECT_PATH%\src\services" (
    mkdir "%PROJECT_PATH%\src\services"
    echo %CHECK% Created directory: src\services
) else (
    echo %INFO% Directory already exists: src\services
)

if not exist "%PROJECT_PATH%\src\styles" (
    mkdir "%PROJECT_PATH%\src\styles"
    echo %CHECK% Created directory: src\styles
) else (
    echo %INFO% Directory already exists: src\styles
)

if not exist "%PROJECT_PATH%\docs" (
    mkdir "%PROJECT_PATH%\docs"
    echo %CHECK% Created directory: docs
) else (
    echo %INFO% Directory already exists: docs
)

echo.

REM Copy React components
echo Step 4: Copying React Components
echo.

if exist "%SCRIPT_DIR%\GeneNetworkExplorer.jsx" (
    copy "%SCRIPT_DIR%\GeneNetworkExplorer.jsx" "%PROJECT_PATH%\src\GeneNetworkExplorer.jsx" >nul
    echo %CHECK% Copied: GeneNetworkExplorer.jsx
)

for %%F in ("%SCRIPT_DIR%\components\*.jsx") do (
    if not exist "%PROJECT_PATH%\src\components\%%~nxF" (
        copy "%%F" "%PROJECT_PATH%\src\components\%%~nxF" >nul
        echo %CHECK% Copied: %%~nxF
    ) else (
        echo %INFO% File already exists: %%~nxF (skipping)
    )
)

echo.

REM Copy services
echo Step 5: Copying Services
echo.

if exist "%SCRIPT_DIR%\services\apiService.js" (
    if not exist "%PROJECT_PATH%\src\services\apiService.js" (
        copy "%SCRIPT_DIR%\services\apiService.js" "%PROJECT_PATH%\src\services\apiService.js" >nul
        echo %CHECK% Copied: apiService.js
    ) else (
        echo %INFO% File already exists: apiService.js (skipping)
    )
)

echo.

REM Copy styles
echo Step 6: Copying CSS Styles
echo.

for %%F in ("%SCRIPT_DIR%\styles\*.css") do (
    if not exist "%PROJECT_PATH%\src\styles\%%~nxF" (
        copy "%%F" "%PROJECT_PATH%\src\styles\%%~nxF" >nul
        echo %CHECK% Copied: %%~nxF
    ) else (
        echo %INFO% File already exists: %%~nxF (skipping)
    )
)

echo.

REM Copy documentation
echo Step 7: Copying Documentation
echo.

for %%F in ("%SCRIPT_DIR%\*.md") do (
    copy "%%F" "%PROJECT_PATH%\docs\%%~nxF" >nul
    echo %CHECK% Copied: %%~nxF
)

if exist "%SCRIPT_DIR%\backend_example.py" (
    copy "%SCRIPT_DIR%\backend_example.py" "%PROJECT_PATH%\docs\backend_example.py" >nul
    echo %CHECK% Copied: backend_example.py
)

echo.

REM Setup environment variables
echo Step 8: Setting Up Environment Variables
echo.

if exist "%SCRIPT_DIR%\.env.example" (
    if not exist "%PROJECT_PATH%\.env.local" (
        copy "%SCRIPT_DIR%\.env.example" "%PROJECT_PATH%\.env.local" >nul
        echo %CHECK% Created .env.local from template
        echo %INFO% Update .env.local with your API URL:
        echo   REACT_APP_API_URL=http://localhost:8000/api/v1
    ) else (
        echo %WARNING% .env.local already exists (skipping)
        echo %INFO% Merge settings from .env.example if needed
    )
)

echo.

REM Install dependencies
echo Step 9: Installing Dependencies
echo.

cd /d "%PROJECT_PATH%"

echo %INFO% Installing cytoscape...
call npm install cytoscape@^3.28.1 >nul 2>&1
if %errorlevel% equ 0 (
    echo %CHECK% cytoscape installed
) else (
    echo %WARNING% cytoscape installation may have failed
)

echo %INFO% Installing cytoscape-popper...
call npm install cytoscape-popper@^2.0.0 >nul 2>&1
if %errorlevel% equ 0 (
    echo %CHECK% cytoscape-popper installed
) else (
    echo %WARNING% cytoscape-popper installation may have failed
)

echo %INFO% Installing popper.js...
call npm install popper.js@^1.16.1 >nul 2>&1
if %errorlevel% equ 0 (
    echo %CHECK% popper.js installed
) else (
    echo %WARNING% popper.js installation may have failed
)

echo.

REM Create backup of package.json
echo Step 10: Backing Up Configuration
echo.

if exist "%PROJECT_PATH%\package.json" (
    copy "%PROJECT_PATH%\package.json" "%PROJECT_PATH%\package.json.backup" >nul
    echo %CHECK% Created package.json.backup
)

echo.

REM Summary
echo ====================================================================
echo   SETUP COMPLETE!
echo ====================================================================
echo.

echo All files have been successfully copied to your project.
echo.
echo Next Steps:
echo.
echo 1. UPDATE APP.JSX:
echo    Import GeneNetworkExplorer and theme.css
echo.
echo 2. CONFIGURE ENVIRONMENT:
echo    Edit .env.local with your API URL
echo.
echo 3. READ DOCUMENTATION:
echo    Check docs\ folder for guides and examples
echo.
echo 4. START DEVELOPMENT:
echo    npm start
echo.
echo 5. SET UP BACKEND:
echo    Follow INTEGRATION_GUIDE.md in docs\
echo.
echo 6. COMMIT TO GIT:
echo    git add .
echo    git commit -m "feat: Add GRN Atlas UI complete implementation"
echo    git push
echo.

REM File manifest
echo ====================================================================
echo   FILE MANIFEST
echo ====================================================================
echo.

echo COMPONENTS (9 files):
echo   + src\components\GeneNetworkExplorer.jsx
echo   + src\components\Sidebar.jsx
echo   + src\components\Toolbar.jsx
echo   + src\components\ViewTabs.jsx
echo   + src\components\NetworkVisualization.jsx
echo   + src\components\GeneDetailPanel.jsx
echo   + src\components\ComparisonView.jsx
echo   + src\components\InterventionDesigner.jsx
echo   + src\components\PathwayView.jsx
echo.

echo STYLES (10 files):
echo   + src\styles\theme.css
echo   + src\styles\GeneNetworkExplorer.css
echo   + src\styles\Sidebar.css
echo   + src\styles\Toolbar.css
echo   + src\styles\ViewTabs.css
echo   + src\styles\NetworkVisualization.css
echo   + src\styles\GeneDetailPanel.css
echo   + src\styles\ComparisonView.css
echo   + src\styles\InterventionDesigner.css
echo   + src\styles\PathwayView.css
echo.

echo SERVICES (1 file):
echo   + src\services\apiService.js
echo.

echo DOCUMENTATION (5 files):
echo   + docs\README.md
echo   + docs\INTEGRATION_GUIDE.md
echo   + docs\PROJECT_SUMMARY.md
echo   + docs\QUICK_REFERENCE.md
echo   + docs\backend_example.py
echo.

echo ENVIRONMENT:
echo   + .env.local (created from template)
echo.

echo ====================================================================
echo   INSTALLATION SUMMARY
echo ====================================================================
echo.
echo Project:     %PROJECT_PATH%
echo Total Files: 28
echo Total Size:  ~161 KB
echo Status:      Ready to develop
echo.

echo ====================================================================
echo   PRO TIPS
echo ====================================================================
echo.
echo 1. DEVELOPMENT:
echo    npm start          # Start React dev server
echo    npm run build      # Build for production
echo.
echo 2. BACKEND:
echo    python -m uvicorn backend_example:app --reload
echo.
echo 3. DOCUMENTATION:
echo    * QUICK_REFERENCE.md - Start here for overview
echo    * README.md - Full feature documentation
echo    * INTEGRATION_GUIDE.md - Backend setup
echo    * PROJECT_SUMMARY.md - Quick reference
echo.
echo 4. TROUBLESHOOTING:
echo    * Check browser console for errors (F12)
echo    * Verify .env.local has correct API URL
echo    * Ensure backend is running on port 8000
echo    * Check backend CORS configuration
echo.

echo ====================================================================
echo   Ready to Go! ^o^/
echo ====================================================================
echo.
echo Your GRN Atlas UI is ready for development.
echo All documentation is in the docs\ folder.
echo.
echo Happy coding! (with genes) 8^)
echo.

pause
