#!/usr/bin/env bash
# ── deploy.sh ──────────────────────────────────────────────────────────────────
# Deploy the Bhubaneswar Change Detection backend to Google Cloud Run.
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated (`gcloud auth login`)
#   2. A service account that has:
#        - roles/earthengine.writer   (or roles/earthengine.admin)
#      on the GEE project
#   3. Docker (only if building locally; Cloud Build handles it otherwise)
#
# Usage:
#   bash deploy.sh
#
# After deployment, copy the Cloud Run URL and set it in:
#   - frontend/app.js            (API_BASE)
#   - frontend/analysis.html     (API_BASE)
# ───────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

PROJECT_ID="change-detection-494607"
REGION="asia-south1"                           # Mumbai — closest to Bhubaneswar
SERVICE_NAME="bhubaneswar-cd-api"
SERVICE_ACCOUNT="bhubaneswar-change-backend@change-detection-494607.iam.gserviceaccount.com"

# Vercel production URL (update after first Vercel deploy)
VERCEL_ORIGIN="https://bhubaneshwar-change-detection.vercel.app"

# ── Set active project ────────────────────────────────────────────────────────

echo "[1/4] Setting project to ${PROJECT_ID} ..."
gcloud config set project "${PROJECT_ID}"

# ── Build container via Cloud Build ───────────────────────────────────────────

IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "[2/4] Building container image via Cloud Build ..."
gcloud builds submit \
    --tag "${IMAGE}" \
    --timeout 600 \
    ./backend

# ── Deploy to Cloud Run ───────────────────────────────────────────────────────

echo "[3/4] Deploying to Cloud Run (${REGION}) ..."
gcloud run deploy "${SERVICE_NAME}" \
    --image       "${IMAGE}" \
    --region      "${REGION}" \
    --platform    managed \
    --allow-unauthenticated \
    --service-account "${SERVICE_ACCOUNT}" \
    --set-env-vars  "GEE_PROJECT_ID=${PROJECT_ID},CORS_ORIGIN=${VERCEL_ORIGIN}" \
    --memory      1Gi \
    --cpu         1 \
    --timeout     300 \
    --max-instances 3 \
    --min-instances 0

# ── Print service URL ─────────────────────────────────────────────────────────

echo ""
echo "[4/4] Deployment complete."
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --region "${REGION}" \
    --format "value(status.url)")
echo ""
echo "======================================================="
echo " Cloud Run URL:  ${SERVICE_URL}"
echo "======================================================="
echo ""
echo "Next steps:"
echo "  1. Set API_BASE in frontend/app.js to:       ${SERVICE_URL}"
echo "  2. Set API_BASE in frontend/analysis.html to: ${SERVICE_URL}"
echo "  3. Deploy frontend to Vercel:  vercel --prod"
echo ""
