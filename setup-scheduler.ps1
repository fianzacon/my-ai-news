# Cloud Scheduler 설정 스크립트 (Windows PowerShell)

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [string]$Region = "asia-northeast3",
    [string]$ServiceName = "ai-news-pipeline",
    [string]$CollectJobName = "ai-news-collect-midnight",
    [string]$SendJobName = "ai-news-send-9am",
    [string]$CollectSchedule = "0 0 * * *",
    [string]$SendSchedule = "0 9 * * *",
    [string]$TimeZone = "Asia/Seoul"
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "⏰ Setting up TWO-STAGE Cloud Scheduler" -ForegroundColor Cyan
Write-Host "  Stage 1: 00:00 - Collect articles" -ForegroundColor Cyan
Write-Host "  Stage 2: 09:00 - Send to Webex" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if Cloud Run Job exists
$JobExists = gcloud run jobs describe $ServiceName --region $Region --format "value(metadata.name)" 2>$null

if (-not $JobExists) {
    Write-Host "❌ Error: Cloud Run Job not found. Deploy first using .\deploy.ps1" -ForegroundColor Red
    exit 1
}

Write-Host "Cloud Run Job: $ServiceName" -ForegroundColor Cyan
Write-Host ""

# Create service account (if not exists)
$ServiceAccount = "cloud-scheduler-invoker@$ProjectId.iam.gserviceaccount.com"

Write-Host "🔐 Setting up service account..." -ForegroundColor Yellow
gcloud iam service-accounts create cloud-scheduler-invoker `
    --display-name "Cloud Scheduler Invoker" `
    --quiet 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Service account created" -ForegroundColor Green
} else {
    Write-Host "   ℹ️  Service account already exists" -ForegroundColor Gray
}

# Grant permission to invoke Cloud Run Jobs
Write-Host ""
Write-Host "🔑 Granting Cloud Run Jobs invoker permission..." -ForegroundColor Yellow
gcloud run jobs add-iam-policy-binding $ServiceName `
    --region $Region `
    --member "serviceAccount:$ServiceAccount" `
    --role "roles/run.invoker" `
    --quiet

# Delete existing jobs if exist
Write-Host ""
Write-Host "🗑️  Removing old scheduler jobs (if exist)..." -ForegroundColor Yellow

# Delete old single-stage job
gcloud scheduler jobs delete "ai-news-daily-730am" `
    --location $Region `
    --quiet 2>$null

gcloud scheduler jobs delete $CollectJobName `
    --location $Region `
    --quiet 2>$null

gcloud scheduler jobs delete $SendJobName `
    --location $Region `
    --quiet 2>$null

Write-Host "   ✅ Old jobs cleaned up" -ForegroundColor Green

# Create Cloud Scheduler jobs to trigger Cloud Run Jobs
Write-Host ""
Write-Host "📅 Creating scheduler jobs..." -ForegroundColor Yellow

# Cloud Run Jobs URI format
$JobUri = "https://$Region-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$ProjectId/jobs/$ServiceName`:run"

# Stage 1: Collect at midnight (00:00)
Write-Host "   🌙 Stage 1: Midnight collection (00:00)..." -ForegroundColor Cyan
gcloud scheduler jobs create http $CollectJobName `
    --location $Region `
    --schedule $CollectSchedule `
    --time-zone $TimeZone `
    --uri $JobUri `
    --http-method POST `
    --oauth-service-account-email $ServiceAccount `
    --headers "Content-Type=application/json" `
    --message-body '{"args":["--stage","collect"]}' `
    --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Midnight collection job created" -ForegroundColor Green
} else {
    Write-Host "   ❌ Failed to create midnight job" -ForegroundColor Red
}

# Stage 2: Send at 9 AM (09:00)
Write-Host "   ☀️  Stage 2: Morning send (09:00)..." -ForegroundColor Cyan
gcloud scheduler jobs create http $SendJobName `
    --location $Region `
    --schedule $SendSchedule `
    --time-zone $TimeZone `
    --uri $JobUri `
    --http-method POST `
    --oauth-service-account-email $ServiceAccount `
    --headers "Content-Type=application/json" `
    --message-body '{"args":["--stage","send"]}' `
    --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Morning send job created" -ForegroundColor Green
} else {
    Write-Host "   ❌ Failed to create morning job" -ForegroundColor Red
}

# Get next run times
$CollectNextRun = gcloud scheduler jobs describe $CollectJobName --location $Region --format "value(scheduleTime)" 2>$null
$SendNextRun = gcloud scheduler jobs describe $SendJobName --location $Region --format "value(scheduleTime)" 2>$null

Write-Host ""
Write-Host "✅ TWO-STAGE Scheduler setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Schedule Summary:" -ForegroundColor Cyan
Write-Host "  🌙 Stage 1 (Collect): $CollectJobName" -ForegroundColor White
Write-Host "     Schedule: Every day at 00:00 (midnight)" -ForegroundColor Gray
Write-Host "     Next run: $CollectNextRun" -ForegroundColor Gray
Write-Host ""
Write-Host "  ☀️  Stage 2 (Send): $SendJobName" -ForegroundColor White
Write-Host "     Schedule: Every day at 09:00 (9 AM)" -ForegroundColor Gray
Write-Host "     Next run: $SendNextRun" -ForegroundColor Gray
Write-Host ""
Write-Host "To test immediately:" -ForegroundColor Yellow
Write-Host "  gcloud scheduler jobs run $CollectJobName --location $Region" -ForegroundColor White
Write-Host "  gcloud scheduler jobs run $SendJobName --location $Region" -ForegroundColor White
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  gcloud logs read --limit 50 --format json" -ForegroundColor White
