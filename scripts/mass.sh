#!/bin/bash

# 1. Configuration
export PROJECT_ID=$(gcloud config get-value project)
ALPHA_URL=$(gcloud run services describe agent-alpha --region us-central1 --project $PROJECT_ID --format 'value(status.url)')
BETA_URL=$(gcloud run services describe agent-beta --region us-central1 --project $PROJECT_ID --format 'value(status.url)')
AUTH_TOKEN=$(gcloud auth print-identity-token)

TOTAL_REQUESTS=5000
BATCH_SIZE=50  # Number of concurrent agents
DELAY=2        # Seconds to wait between batches to respect API rate limits

echo "🚀 Starting Campaign: $TOTAL_REQUESTS attacks in batches of $BATCH_SIZE..."

for ((i=1; i<=TOTAL_REQUESTS; i+=BATCH_SIZE)); do
    echo "⚡ Launching Batch $((i)) to $((i+BATCH_SIZE-1))..."
    
    # Launch a batch of background jobs
    for ((j=0; j<BATCH_SIZE; j++)); do
        curl -X POST "$ALPHA_URL/start" \
          -H "Authorization: Bearer $AUTH_TOKEN" \
          -H "Content-Type: application/json" \
          -d "{\"target_url\": \"$BETA_URL\"}" \
          --silent --output /dev/null &
    done

    # Wait for this batch to clear before starting the next
    # This prevents the "Fork Bomb" and helps manage API Quota
    wait 
    
    # Optional: Brief pause to cool down the API quota buckets
    sleep $DELAY
done

echo "✅ Campaign Complete. Check your Alert Policy email."