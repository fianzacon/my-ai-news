#!/bin/bash
# GCP Cloud Run Deployment Script

set -e  # Exit on error

echo "======================================"
echo "🚀 AI News Pipeline - Cloud Deployment"
echo "======================================"

# Configuration
PROJECT_ID="your-gcp-project-id"  # CHANGE THIS
REGION="asia-northeast3"  # Seoul region
SERVICE_NAME="ai-news-pipeline"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Check if required tools are installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not found"
    echo "   Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker not found"
    echo "   Install from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "   Create .env with: GOOGLE_API_KEY, WEBEX_BOT_TOKEN, WEBEX_ROOM_ID"
    exit 1
fi

# Load environment variables
source .env

# Set GCP project
echo ""
echo "📌 Setting GCP project..."
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo ""
echo "🔧 Enabling required GCP APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    --quiet

# Build and push Docker image
echo ""
echo "🐳 Building Docker image..."
gcloud builds submit --tag ${IMAGE_NAME}

# Deploy to Cloud Run
echo ""
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --region ${REGION} \
    --platform managed \
    --memory 2Gi \
    --cpu 2 \
    --timeout 90m \
    --no-allow-unauthenticated \
    --set-env-vars "GOOGLE_API_KEY=${GOOGLE_API_KEY},WEBEX_BOT_TOKEN=${WEBEX_BOT_TOKEN},WEBEX_ROOM_ID=${WEBEX_ROOM_ID}" \
    --quiet

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Next step: Set up Cloud Scheduler"
echo "Run: ./setup-scheduler.sh"
