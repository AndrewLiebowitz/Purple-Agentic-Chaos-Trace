#!/bin/bash

# ==============================================================================
# AI RED TEAM SIMULATION - DEPLOYMENT SCRIPT
# ==============================================================================

# Exit immediately if a command exits with a non-zero status
set -e

# --- PHASE 0: Pre-Flight Checks & Authentication ---
echo "🛫 Performing pre-flight checks..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: 'gcloud' is not installed."
    exit 1
fi

# Ensure user is logged in
CURRENT_USER=$(gcloud config get-value account 2>/dev/null)
if [[ -z "$CURRENT_USER" ]]; then
    echo "⚠️  No active Google Cloud account detected."
    echo "🔑 Launching authentication..."
    gcloud auth login
    CURRENT_USER=$(gcloud config get-value account)
fi
echo "✅ Authenticated as: $CURRENT_USER"

# --- PHASE 1: Configuration ---
echo "--- 1. Configuration ---"

# Auto-detect Project ID, but allow override
DETECTED_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ -n "$DETECTED_PROJECT" ]; then
    echo "🌍 Detected active project: $DETECTED_PROJECT"
    PROJECT_ID=$DETECTED_PROJECT
else
    read -p "Enter your GCP Project ID: " PROJECT_ID
fi

# Verify Project ID is set
if [[ -z "$PROJECT_ID" ]]; then
    echo "❌ Error: No Project ID set."
    exit 1
fi

gcloud config set project $PROJECT_ID
REGION="us-central1"
REPO_NAME="agents-repo"

# --- PHASE 2: Enable APIs ---
echo "--- 2. Enabling Google Cloud APIs ---"
# Explicitly enabling Cloud Trace to fix the "Storage not initialized" warning
gcloud services enable \
    aiplatform.googleapis.com \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudtrace.googleapis.com \
    logging.googleapis.com \
    --project $PROJECT_ID

echo "✅ APIs Enabled."

# --- PHASE 3: Configuring IAM & Permissions ---
echo "--- 3. Configuring Service Account Permissions ---"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "🤖 Service Account: $COMPUTE_SA"

# Grant permissions needed for the agents to run and log
for ROLE in roles/aiplatform.user roles/cloudtrace.agent roles/storage.admin roles/artifactregistry.writer roles/logging.logWriter; do
    echo "   -> Granting $ROLE..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member=serviceAccount:${COMPUTE_SA} \
        --role=$ROLE \
        --condition=None \
        --quiet > /dev/null
done

# --- PHASE 4: Infrastructure (Artifact Registry) ---
echo "--- 4. Setting up Artifact Registry ---"
if ! gcloud artifacts repositories describe $REPO_NAME --location=$REGION --project=$PROJECT_ID > /dev/null 2>&1; then
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="Docker repository for AI Red Team agents" \
        --project $PROJECT_ID
else
    echo "✅ Repository '$REPO_NAME' already exists."
fi

# --- PHASE 5: Build & Push Images ---
echo "--- 5. Building Container Images ---"
# Assumes script is run from /scripts/ folder, so context is ../
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/agent-beta ../agent_beta
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/agent-alpha ../agent_alpha

# --- PHASE 6: Deploy Services ---
echo "--- 6. Deploying to Cloud Run ---"

echo "🔵 Deploying Agent Beta (Target)..."
gcloud run deploy agent-beta \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/agent-beta \
  --region $REGION \
  --platform managed \
  --project $PROJECT_ID \
  --quiet

echo "🔴 Deploying Agent Alpha (Attacker)..."
gcloud run deploy agent-alpha \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/agent-alpha \
  --region $REGION \
  --platform managed \
  --project $PROJECT_ID \
  --quiet

# --- PHASE 7: Fix Permissions (The 403 Killer) ---
echo "--- 7. Applying Explicit Access Permissions ---"
# This step explicitly authorizes the Service Account and YOU (the User) 
# to invoke the services, bypassing "Unauthenticated" restrictions.

echo "🔓 Authorizing Service Account ($COMPUTE_SA) to call agents..."
gcloud run services add-iam-policy-binding agent-beta \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/run.invoker" \
    --region=$REGION \
    --project=$PROJECT_ID --quiet > /dev/null

gcloud run services add-iam-policy-binding agent-alpha \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/run.invoker" \
    --region=$REGION \
    --project=$PROJECT_ID --quiet > /dev/null

echo "🔓 Authorizing Current User ($CURRENT_USER) to call agents..."
gcloud run services add-iam-policy-binding agent-beta \
    --member="user:${CURRENT_USER}" \
    --role="roles/run.invoker" \
    --region=$REGION \
    --project=$PROJECT_ID --quiet > /dev/null

gcloud run services add-iam-policy-binding agent-alpha \
    --member="user:${CURRENT_USER}" \
    --role="roles/run.invoker" \
    --region=$REGION \
    --project=$PROJECT_ID --quiet > /dev/null

# --- PHASE 8: Summary ---
echo "--- 8. Deployment Complete ---"
BETA_URL=$(gcloud run services describe agent-beta --region $REGION --format 'value(status.url)')
ALPHA_URL=$(gcloud run services describe agent-alpha --region $REGION --format 'value(status.url)')

echo ""
echo "========================================================"
echo "🎯 TARGET (Agent Beta):   $BETA_URL"
echo "⚔️  ATTACKER (Agent Alpha): $ALPHA_URL"
echo "========================================================"
echo "You are now authorized. Run the mass attack:"
echo "bash scripts/mass.sh"