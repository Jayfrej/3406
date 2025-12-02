# Git Push Script for MT5 Trading Bot Project
# This script will add, commit, and push your changes

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "GIT PUSH SCRIPT - MT5 Trading Bot" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to project directory
Set-Location "C:\Users\usEr\PycharmProjects\3406"

Write-Host "[1/6] Checking Git Status..." -ForegroundColor Yellow
git status
Write-Host ""

Write-Host "[2/6] Adding all changes..." -ForegroundColor Yellow
git add .
Write-Host "✅ Files added" -ForegroundColor Green
Write-Host ""

Write-Host "[3/6] Showing files to be committed..." -ForegroundColor Yellow
git status --short
Write-Host ""

Write-Host "[4/6] Committing changes..." -ForegroundColor Yellow
git commit -m "Fix: Remove authentication from webhook-url endpoint and add comprehensive testing" `
           -m "- Fixed webhook-url endpoint to be publicly accessible (no auth required)" `
           -m "- Added FIX_SUMMARY.md documenting all fixes and troubleshooting steps" `
           -m "- Added test_routes.py for route verification" `
           -m "- Added GIT_PUSH_GUIDE.md with detailed git instructions" `
           -m "- Verified all 55 routes are working correctly" `
           -m "- Root route (/) and UI routes functioning properly"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Commit successful" -ForegroundColor Green
} else {
    Write-Host "⚠️ Commit failed or nothing to commit" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "[5/6] Checking remote repository..." -ForegroundColor Yellow
$remotes = git remote -v
if ($remotes) {
    Write-Host "Remote repository configured:" -ForegroundColor Green
    git remote -v
} else {
    Write-Host "⚠️ WARNING: No remote repository configured!" -ForegroundColor Red
    Write-Host "Please add your remote repository first:" -ForegroundColor Yellow
    Write-Host "  git remote add origin <your-repository-url>" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Example:" -ForegroundColor Cyan
    Write-Host "  git remote add origin https://github.com/yourusername/your-repo.git" -ForegroundColor Cyan
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

Write-Host "[6/6] Pushing to repository..." -ForegroundColor Yellow
$branch = Read-Host "Enter branch name (default: main)"
if ([string]::IsNullOrWhiteSpace($branch)) {
    $branch = "main"
}

Write-Host "Pushing to origin/$branch..." -ForegroundColor Yellow
git push origin $branch

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "✅ PUSH SUCCESSFUL!" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Restart your server: python server.py" -ForegroundColor White
    Write-Host "2. Test the UI: http://localhost:5000/" -ForegroundColor White
    Write-Host "3. Verify webhook-url works without authentication" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Red
    Write-Host "❌ PUSH FAILED!" -ForegroundColor Red
    Write-Host "================================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common solutions:" -ForegroundColor Yellow
    Write-Host "1. Pull first: git pull origin $branch --rebase" -ForegroundColor White
    Write-Host "2. Check authentication (use Personal Access Token)" -ForegroundColor White
    Write-Host "3. Verify remote URL: git remote -v" -ForegroundColor White
    Write-Host ""
    Write-Host "For detailed help, see: GIT_PUSH_GUIDE.md" -ForegroundColor Cyan
}

Write-Host ""
Read-Host "Press Enter to exit"

