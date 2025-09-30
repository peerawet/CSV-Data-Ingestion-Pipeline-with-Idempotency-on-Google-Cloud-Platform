#!/bin/bash

# Deploy Cloud Function from GitHub Repository
# Make sure to update REPO_URL and BRANCH variables

REPO_URL="https://github.com/peerawet/CSV-Data-Ingestion-Pipeline-with-Idempotency-on-Google-Cloud-Platform"
BRANCH="main"
SOURCE_DIR="csv-processor-function"

echo "Deploying Cloud Functions from GitHub repository..."
echo "Repository: $REPO_URL"
echo "Branch: $BRANCH"
echo "Source Directory: $SOURCE_DIR"

# Deploy Storage trigger function from GitHub
echo "Deploying process-csv-upload function..."
gcloud functions deploy process-csv-upload \
    --gen2 \
    --runtime=python311 \
    --region=asia-southeast1 \
    --source=$REPO_URL \
    --source-branch=$BRANCH \
    --source-dir=$SOURCE_DIR \
    --entry-point=process_csv_upload \
    --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
    --trigger-event-filters="bucket=dormy-sheets-csv-uploads" \
    --memory=256MB \
    --timeout=540s

echo "Deploying get-upload-status function..."
gcloud functions deploy get-upload-status \
    --gen2 \
    --runtime=python311 \
    --region=asia-southeast1 \
    --source=$REPO_URL \
    --source-branch=$BRANCH \
    --source-dir=$SOURCE_DIR \
    --entry-point=get_upload_status \
    --trigger-http \
    --allow-unauthenticated \
    --memory=256MB \
    --timeout=60s

echo "Deploying list-uploads function..."
gcloud functions deploy list-uploads \
    --gen2 \
    --runtime=python311 \
    --region=asia-southeast1 \
    --source=$REPO_URL \
    --source-branch=$BRANCH \
    --source-dir=$SOURCE_DIR \
    --entry-point=list_uploads \
    --trigger-http \
    --allow-unauthenticated \
    --memory=256MB \
    --timeout=60s

echo "All functions deployed successfully from GitHub!"
echo "Repository: $REPO_URL"
echo ""
echo "Functions:"
echo "- process-csv-upload: Storage trigger"
echo "- get-upload-status: https://asia-southeast1-dormy-sheets.cloudfunctions.net/get-upload-status"
echo "- list-uploads: https://asia-southeast1-dormy-sheets.cloudfunctions.net/list-uploads"
