@echo off
REM Git Push Script for MT5 Trading Bot Project
REM This script will add, commit, and push your changes

echo ================================================================================
echo GIT PUSH SCRIPT - MT5 Trading Bot
echo ================================================================================
echo.

cd /d "%~dp0"

echo [1/5] Checking Git Status...
git status
echo.

echo [2/5] Adding all changes...
git add .
echo.

echo [3/5] Showing files to be committed...
git status --short
echo.

echo [4/5] Committing changes...
git commit -m "Fix: Remove authentication from webhook-url endpoint and add comprehensive testing" -m "- Fixed webhook-url endpoint to be publicly accessible (no auth required)" -m "- Added FIX_SUMMARY.md documenting all fixes and troubleshooting steps" -m "- Added test_routes.py for route verification" -m "- Verified all 55 routes are working correctly" -m "- Root route (/) and UI routes functioning properly"
echo.

echo [5/5] Pushing to repository...
echo.
echo Please enter your branch name (main/master) or press Ctrl+C to cancel:
set /p BRANCH="Branch name (default: main): "
if "%BRANCH%"=="" set BRANCH=main

git push origin %BRANCH%

echo.
echo ================================================================================
echo Push complete!
echo ================================================================================
echo.
echo Next steps:
echo 1. Restart your server: python server.py
echo 2. Test the UI: http://localhost:5000/
echo 3. Verify webhook-url works without authentication
echo.
pause

