#!/usr/bin/env bash
# deploy.sh — AIRE full deployment script
# Usage: ./deploy/deploy.sh [--project PROJECT_ID] [--region REGION] [--skip-tests]
set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
IMAGE_REPO="gcr.io"
SERVICE_NAME="aire-backend"
SERVICE_ACCOUNT="aire-backend"
SKIP_TESTS=false

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --project) PROJECT_ID="$2"; shift 2 ;;
    --region)  REGION="$2";  shift 2 ;;
    --skip-tests) SKIP_TESTS=true; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$PROJECT_ID" ]]; then
  echo "❌  GCP_PROJECT_ID is not set. Pass --project or export GCP_PROJECT_ID."
  exit 1
fi

IMAGE="${IMAGE_REPO}/${PROJECT_ID}/${SERVICE_NAME}:$(git rev-parse --short HEAD 2>/dev/null || echo latest)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AIRE Deployment"
echo "  Project : $PROJECT_ID"
echo "  Region  : $REGION"
echo "  Image   : $IMAGE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Step 1: Tests ─────────────────────────────────────────────────────────────
if [[ "$SKIP_TESTS" == "false" ]]; then
  echo ""
  echo "▶ Step 1/5: Running tests..."
  USE_SECRET_MANAGER=false python -m pytest tests/ -v --tb=short --ignore=tests/test_integration.py
  echo "✅  Tests passed"
else
  echo "⚠️  Skipping tests (--skip-tests)"
fi

# ── Step 2: Build & push image ────────────────────────────────────────────────
echo ""
echo "▶ Step 2/5: Building Docker image..."
docker build \
  -t "$IMAGE" \
  -t "${IMAGE_REPO}/${PROJECT_ID}/${SERVICE_NAME}:latest" \
  -f services/Dockerfile \
  .
echo "✅  Image built"

echo ""
echo "▶ Step 3/5: Pushing image to Artifact Registry..."
docker push "$IMAGE"
docker push "${IMAGE_REPO}/${PROJECT_ID}/${SERVICE_NAME}:latest"
echo "✅  Image pushed"

# ── Step 3: Deploy Cloud Run ──────────────────────────────────────────────────
echo ""
echo "▶ Step 4/5: Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="$IMAGE" \
  --platform=managed \
  --allow-unauthenticated \
  --service-account="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},USE_SECRET_MANAGER=true,GCP_REGION=${REGION}" \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=1 \
  --max-instances=10 \
  --concurrency=80 \
  --timeout=300

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="value(status.url)")

echo "✅  Cloud Run deployed at: $SERVICE_URL"

# ── Step 4: Health check ──────────────────────────────────────────────────────
echo ""
echo "▶ Step 5/5: Health check..."
sleep 5
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/health")
if [[ "$HTTP_STATUS" == "200" ]]; then
  echo "✅  Health check passed (HTTP $HTTP_STATUS)"
else
  echo "❌  Health check failed (HTTP $HTTP_STATUS)"
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  AIRE deployed successfully"
echo "  URL: $SERVICE_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
