# CSV Data Ingestion Pipeline - Simple Architecture

## 🎯 Overview

**Event-driven, idempotent CSV processing pipeline** บน GCP ที่ใช้ Pub/Sub managed retry + DLQ policy

## 🏗️ Architecture

```
CSV Upload
    ↓
Cloud Storage (bucket: dormy-sheets-csv-uploads)
    ↓
📢 Storage Event
    ↓
Cloud Function: on-file-upload
    ├─ Check idempotency (Firestore)
    ├─ Mark as 'pending'
    └─ Publish to Pub/Sub topic: csv-uploads
         ↓
    Pub/Sub Subscription (auto-created by Cloud Function)
    ├─ DLQ Policy: max 5 delivery attempts
    ├─ Retry on failure (exponential backoff)
    └─ If fail 5 times → Forward to csv-uploads-dlq
         ↓
Cloud Function: process-csv
    ├─ Download CSV from Storage
    ├─ Validate & Process
    ├─ Update Firestore status
    └─ If throw exception → Pub/Sub retries automatically
```

## 📦 Components

### 1. Cloud Functions

#### `on-file-upload` (Storage Trigger)

- **Trigger**: Cloud Storage object.finalized event
- **Action**:
  - Generate upload_id (idempotent)
  - Check if already processed
  - Publish message to Pub/Sub
- **No retry needed**: Simple publisher

#### `process-csv` (Pub/Sub Trigger)

- **Trigger**: Pub/Sub topic `csv-uploads`
- **Retry**: **Enabled** (`--retry` flag)
- **Action**:
  - Download CSV from Storage
  - Validate content
  - Process data
  - Update Firestore
- **Error handling**: Throws exception → Pub/Sub retries automatically

### 2. Pub/Sub Topics

#### `csv-uploads` (Main Topic)

- Receives file upload events
- Triggers `process-csv` function

#### `csv-uploads-dlq` (Dead Letter Queue)

- Receives failed messages after max retries
- Has subscription `csv-uploads-dlq-sub` for investigation

### 3. Pub/Sub Subscription

#### `eventarc-asia-southeast1-process-csv-160735-sub-065`

- **Auto-created** by Cloud Function deployment
- **DLQ Policy**:
  - `maxDeliveryAttempts`: 5
  - `deadLetterTopic`: csv-uploads-dlq
- **Retry Behavior**:
  - Exponential backoff
  - If function throws error 5 times → message goes to DLQ

### 4. Firestore Database

#### Collection: `uploads`

- Document ID: upload_id (SHA256 hash)
- Fields:
  ```javascript
  {
    upload_id: string,
    bucket_name: string,
    file_name: string,
    file_size: number,
    status: 'pending' | 'processing' | 'done' | 'failed',
    queued_at: timestamp,
    processing_started_at: timestamp,
    processing_completed_at: timestamp,
    failed_at: timestamp,
    error_message: string,
    lines_processed: number
  }
  ```

## 🔄 Message Flow

### Success Case:

```
1. CSV uploaded → Storage event
2. on-file-upload:
   - Create upload doc (status: pending)
   - Publish to csv-uploads topic
3. process-csv triggered:
   - Update status: processing
   - Process CSV successfully
   - Update status: done
4. Message ACK'd → removed from queue
```

### Failure Case (with Retries):

```
1. CSV uploaded → Storage event
2. on-file-upload: Publish to csv-uploads
3. process-csv triggered (Attempt 1):
   - Throws ValueError("CSV empty")
   - No ACK sent
4. Pub/Sub waits → retry (Attempt 2)
   - Still fails
5. Retry attempts 3, 4, 5 → all fail
6. After 5 failures → Message forwarded to csv-uploads-dlq
7. Message available in csv-uploads-dlq-sub for investigation
```

## ✅ Key Features

### 1. Idempotency

- Upload ID generated from file metadata (hash)
- Duplicate uploads with same content = same upload_id
- Check Firestore before processing

### 2. Managed Retries

- **No manual retry logic needed**
- Pub/Sub handles exponential backoff automatically
- Just throw exception → automatic retry

### 3. Dead Letter Queue

- Failed messages after max attempts → DLQ topic
- Separate subscription for manual investigation
- No data loss

### 4. Simple Code

- No manual DLQ publish logic
- No complex error handling
- Let Pub/Sub manage retry/DLQ flow

## 🚀 Deployment

### Prerequisites

```bash
# Enable APIs
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable firestore.googleapis.com
```

### Deploy

```bash
cd csv-processor-function

# Deploy storage trigger
gcloud functions deploy on-file-upload \
  --gen2 \
  --runtime=python311 \
  --region=asia-southeast1 \
  --source=. \
  --entry-point=on_file_upload \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=dormy-sheets-csv-uploads" \
  --memory=256MB \
  --timeout=60s

# Deploy Pub/Sub consumer with retry
gcloud functions deploy process-csv \
  --gen2 \
  --runtime=python311 \
  --region=asia-southeast1 \
  --source=. \
  --entry-point=process_csv \
  --trigger-topic=csv-uploads \
  --retry \
  --memory=256MB \
  --timeout=60s

# Add DLQ policy to auto-created subscription
SUBSCRIPTION=$(gcloud pubsub subscriptions list \
  --filter="topic:csv-uploads" \
  --format="value(name)" | grep eventarc)

gcloud pubsub subscriptions update $SUBSCRIPTION \
  --dead-letter-topic=csv-uploads-dlq \
  --max-delivery-attempts=5
```

## 🧪 Testing

### Test Success Case

```bash
# Upload valid CSV
gcloud storage cp test-data.csv gs://dormy-sheets-csv-uploads/

# Check logs
gcloud functions logs read process-csv --region=asia-southeast1 --limit=10
```

### Test Failure + DLQ

```bash
# Upload bad CSV (only header)
gcloud storage cp bad-only-header.csv gs://dormy-sheets-csv-uploads/fail-test.csv

# Wait for retries (~1-2 minutes)
sleep 120

# Check DLQ
gcloud pubsub subscriptions pull csv-uploads-dlq-sub --limit=5
```

## 📊 Monitoring

### Check Function Logs

```bash
gcloud functions logs read on-file-upload --region=asia-southeast1 --limit=20
gcloud functions logs read process-csv --region=asia-southeast1 --limit=20
```

### Check Subscription Status

```bash
gcloud pubsub subscriptions describe eventarc-asia-southeast1-process-csv-160735-sub-065
```

### View DLQ Messages

```bash
gcloud pubsub subscriptions pull csv-uploads-dlq-sub --limit=10
```

## 🎯 สำหรับสัมภาษณ์

**คำถาม**: "อธิบาย architecture และวิธี handle failure"

**คำตอบ**:

> "ระบบใช้ event-driven architecture บน GCP โดย Storage event trigger Cloud Function ที่ publish ไป Pub/Sub จากนั้น Function อีกตัว subscribe และประมวลผล CSV สำหรับ failure handling ใช้ Pub/Sub managed retry policy ที่ตั้งไว้ 5 ครั้ง ถ้า function throw exception Pub/Sub จะ retry อัตโนมัติด้วย exponential backoff และหลังจาก retry ครบแล้วยังไม่สำเร็จ message จะถูกส่งไป Dead Letter Queue อัตโนมัติ ทำให้ไม่สูญหายข้อมูลและสามารถ investigate ทีหลังได้ โค้ดเรียบง่ายไม่ต้อง handle retry เอง"

**ข้อดี**:

- ✅ Simple code (ไม่ต้อง manual retry)
- ✅ Managed by GCP (reliable)
- ✅ No data loss (DLQ)
- ✅ Idempotent (check Firestore)
- ✅ Scalable (serverless)
- ✅ Observable (logs + metrics)
