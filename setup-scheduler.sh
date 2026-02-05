#!/bin/bash
# Setup Cloud Scheduler for daily 7:30 AM execution

set -e

echo "======================================"
echo "⏰ Setting up TWO-STAGE Cloud Scheduler"
echo "  Stage 1: 00:00 - Collect articles"
echo "  Stage 2: 09:00 - Send to Webex"
echo "======================================"

# Configuration
PROJECT_ID="your-gcp-project-id"  # CHANGE THIS
REGION="asia-northeast3"
SERVICE_NAME="ai-news-pipeline"
COLLECT_JOB_NAME="ai-news-collect-midnight"
SEND_JOB_NAME="ai-news-send-9am"
TIMEZONE="Asia/Seoul"
COLLECT_SCHEDULE="0 0 * * *"  # Midnight
SEND_SCHEDULE="0 9 * * *"     # 9 AM

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')

if [ -z "$SERVICE_URL" ]; then
    echo "❌ Error: Service not found. Deploy first using ./deploy.sh"
    exit 1
fi

# Create service account for scheduler (if not exists)
SERVICE_ACCOUNT="cloud-scheduler-invoker@${PROJECT_ID}.iam.gserviceaccount.com"

echo ""
echo "🔐 Setting up service account..."
gcloud iam service-accounts create cloud-scheduler-invoker \
    --display-name "Cloud Scheduler Invoker" \
    --quiet 2>/dev/null || echo "   Service account already exists"

# Grant permission to invoke Cloud Run
gcloud run services add-iam-policy-binding ${SERVICE_NAME} \
    --region ${REGION} \
    --member "serviceAccount:${SERVICE_ACCOUNT}" \
    --role "roles/run.invoker" \
    --quiet

# Delete existing jobs if exist
echo ""
echo "🗑️  Removing old scheduler jobs (if exist)..."
# Delete old single-stage job
gcloud scheduler jobs delete ai-news-daily-730am \
    --location ${REGION} \
    --quiet 2>/dev/null || echo "   No old single-stage job found"

gcloud scheduler jobs delete ${COLLECT_JOB_NAME} \
    --location ${REGION} \
    --quiet 2>/dev/null || echo "   No collect job found"

gcloud scheduler jobs delete ${SEND_JOB_NAME} \
    --location ${REGION} \
    --quiet 2>/dev/null || echo "   No send job found"

# Cloud Run Jobs URI format
JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${SERVICE_NAME}:run"

# Create Cloud Scheduler jobs
echo ""
echo "📅 Creating scheduler jobs..."

# Stage 1: Collect at midnight (00:00)
echo "   🌙 Stage 1: Midnight collection (00:00)..."
gcloud scheduler jobs create http ${COLLECT_JOB_NAME} \
    --location ${REGION} \
    --schedule "${COLLECT_SCHEDULE}" \
    --time-zone "${TIMEZONE}" \
    --uri "${JOB_URI}" \
    --http-method POST \
    --oauth-service-account-email ${SERVICE_ACCOUNT} \
    --headers "Content-Type=application/json" \
    --message-body '{"args":["--stage","collect"]}' \
    --attempt-deadline 90m \
    --quiet

echo "   ✅ Midnight collection job created"

# Stage 2: Send at 9 AM (09:00)
echo "   ☀️  Stage 2: Morning send (09:00)..."
gcloud scheduler jobs create http ${SEND_JOB_NAME} \
    --location ${REGION} \
    --schedule "${SEND_SCHEDULE}" \
    --time-zone "${TIMEZONE}" \
    --uri "${JOB_URI}" \
    --http-method POST \
    --oauth-service-account-email ${SERVICE_ACCOUNT} \
    --headers "Content-Type=application/json" \
    --message-body '{"args":["--stage","send"]}' \
    --attempt-deadline 90m \
    --quiet

echo "   ✅ Morning send job created"

echo ""
echo "✅ TWO-STAGE Scheduler setup complete!"
echo ""
echo "📋 Schedule Summary:"
echo "  🌙 Stage 1 (Collect): ${COLLECT_JOB_NAME}"
echo "     Schedule: Every day at 00:00 (midnight)"
echo "     Next run: $(gcloud scheduler jobs describe ${COLLECT_JOB_NAME} --location ${REGION} --format 'value(scheduleTime)')"
echo ""
echo "  ☀️  Stage 2 (Send): ${SEND_JOB_NAME}"
echo "     Schedule: Every day at 09:00 (9 AM)"
echo "     Next run: $(gcloud scheduler jobs describe ${SEND_JOB_NAME} --location ${REGION} --format 'value(scheduleTime)')"
echo ""
echo "To test immediately:"
echo "  gcloud scheduler jobs run ${COLLECT_JOB_NAME} --location ${REGION}"
echo "  gcloud scheduler jobs run ${SEND_JOB_NAME} --location ${REGION}"
