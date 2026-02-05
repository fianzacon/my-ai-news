# GCP Cloud Run 배포 스크립트 (Windows PowerShell)

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [string]$Region = "asia-northeast3",
    [string]$ServiceName = "ai-news-pipeline"
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "🚀 AI News Pipeline - Cloud Deployment" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "❌ Error: .env file not found" -ForegroundColor Red
    Write-Host "   Create .env with: GOOGLE_API_KEY, WEBEX_BOT_TOKEN, WEBEX_ROOM_ID"
    exit 1
}

# Load environment variables from .env
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

$GOOGLE_API_KEY = $env:GOOGLE_API_KEY
$WEBEX_BOT_TOKEN = $env:WEBEX_BOT_TOKEN
$WEBEX_ROOM_ID = $env:WEBEX_ROOM_ID
$NAVER_CLIENT_ID = $env:NAVER_CLIENT_ID
$NAVER_CLIENT_SECRET = $env:NAVER_CLIENT_SECRET
$GOOGLE_NEWS_API_KEY = $env:GOOGLE_NEWS_API_KEY

if (-not $GOOGLE_API_KEY -or -not $WEBEX_BOT_TOKEN -or -not $WEBEX_ROOM_ID) {
    Write-Host "❌ Error: Missing required environment variables in .env" -ForegroundColor Red
    exit 1
}

if (-not $NAVER_CLIENT_ID -or -not $NAVER_CLIENT_SECRET) {
    Write-Host "⚠️  Warning: Naver API credentials not found. News collection will be limited." -ForegroundColor Yellow
}

if (-not $GOOGLE_NEWS_API_KEY) {
    Write-Host "⚠️  Warning: Google News API key not found. Only Naver news will be collected." -ForegroundColor Yellow
}

# Set GCP project
Write-Host "📌 Setting GCP project..." -ForegroundColor Yellow
gcloud config set project $ProjectId

# Enable required APIs
Write-Host ""
Write-Host "🔧 Enabling required GCP APIs..." -ForegroundColor Yellow
gcloud services enable `
    cloudbuild.googleapis.com `
    run.googleapis.com `
    cloudscheduler.googleapis.com `
    --quiet

# Build and push Docker image
Write-Host ""
Write-Host "🐳 Building and pushing Docker image..." -ForegroundColor Yellow
$ImageName = "gcr.io/$ProjectId/$ServiceName"
gcloud builds submit --tag $ImageName

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Build failed" -ForegroundColor Red
    exit 1
}

# Deploy to Cloud Run Jobs (24-hour timeout support)
Write-Host ""
Write-Host "☁️  Deploying to Cloud Run Jobs..." -ForegroundColor Yellow
gcloud run jobs deploy $ServiceName `
    --image $ImageName `
    --region $Region `
    --memory 2Gi `
    --cpu 2 `
    --task-timeout 2h `
    --max-retries 1 `
    --set-env-vars "GOOGLE_API_KEY=$GOOGLE_API_KEY,WEBEX_BOT_TOKEN=$WEBEX_BOT_TOKEN,WEBEX_ROOM_ID=$WEBEX_ROOM_ID,NAVER_CLIENT_ID=$NAVER_CLIENT_ID,NAVER_CLIENT_SECRET=$NAVER_CLIENT_SECRET,GOOGLE_NEWS_API_KEY=$GOOGLE_NEWS_API_KEY,GOOGLE_APPLICATION_CREDENTIALS=/app/service_account/lpoint-ai-initiative-aa739c71cc48.json" `
    --service-account lpoint-ai-initiative@lpoint-ai-initiative.iam.gserviceaccount.com `
    --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Deployment failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Job Name: $ServiceName" -ForegroundColor Cyan
Write-Host "Max Timeout: 2 hours" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Run: .\setup-scheduler.ps1 -ProjectId $ProjectId" -ForegroundColor White
Write-Host "2. Test: gcloud run jobs execute $ServiceName --region $Region" -ForegroundColor White
