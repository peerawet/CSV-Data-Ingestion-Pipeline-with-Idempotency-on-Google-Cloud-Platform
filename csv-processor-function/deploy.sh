#!/bin/bash

# Deploy Cloud Function triggered by Storage events
gcloud functions deploy process-csv-upload \
    --gen2 \
    --runtime=python311 \
    --region=asia-southeast1 \
    --source=. \
    --entry-point=process_csv_upload \
    --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
    --trigger-event-filters="bucket=dormy-sheets-csv-uploads" \
    --memory=256MB \
    --timeout=540s

# Deploy HTTP function for status checking
gcloud functions deploy get-upload-status \
    --gen2 \
    --runtime=python311 \
    --region=asia-southeast1 \
    --source=. \
    --entry-point=get_upload_status \
    --trigger-http \
    --allow-unauthenticated \
    --memory=256MB \
    --timeout=60s

# Deploy HTTP function for listing uploads
gcloud functions deploy list-uploads \
    --gen2 \
    --runtime=python311 \
    --region=asia-southeast1 \
    --source=. \
    --entry-point=list_uploads \
    --trigger-http \
    --allow-unauthenticated \
    --memory=256MB \
    --timeout=60s
