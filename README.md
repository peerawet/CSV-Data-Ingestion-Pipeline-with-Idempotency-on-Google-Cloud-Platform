# CSV Data Ingestion Pipeline with Idempotency

ระบบ Data Ingestion Pipeline ที่มีคุณสมบัติ event-driven และ idempotent สำหรับการประมวลผลไฟล์ CSV บน Google Cloud Platform

## คุณสมบัติหลัก

### 🔄 Event-Driven Processing

- Cloud Function จะถูก trigger อัตโนมัติเมื่อมีการอัปโหลดไฟล์ CSV ใหม่ใน Cloud Storage
- ไม่ต้องรอ schedule หรือ manual trigger

### 🛡️ Idempotent Processing

- ระบบจะไม่ประมวลผลไฟล์เดิมซ้ำ
- ใช้ `upload_id` ที่สร้างจาก metadata ของไฟล์เป็น unique identifier
- ตรวจสอบสถานะใน Firestore ก่อนการประมวลผล

### 📊 Status Tracking

- บันทึกสถานะการประมวลผล: `pending`, `processing`, `done`, `failed`
- สามารถติดตามย้อนหลังได้ผ่าน HTTP APIs

## สถาปัตยกรรมระบบ

```
CSV Upload → Cloud Storage → Cloud Function → Firestore
                ↓
            Process CSV → Update Status
```

### Components

1. **Cloud Storage Bucket**: `dormy-sheets-csv-uploads`
2. **Firestore Database**: `uploads` collection
3. **Cloud Functions**:
   - `process-csv-upload`: Storage trigger function
   - `get-upload-status`: HTTP endpoint สำหรับตรวจสอบสถานะ
   - `list-uploads`: HTTP endpoint สำหรับดูรายการ uploads

## การใช้งาน

### 1. อัปโหลดไฟล์ CSV

```bash
gcloud storage cp your-file.csv gs://dormy-sheets-csv-uploads/
```

### 2. ตรวจสอบสถานะการประมวลผล

```bash
curl "https://asia-southeast1-dormy-sheets.cloudfunctions.net/get-upload-status?upload_id=YOUR_UPLOAD_ID"
```

### 3. ดูรายการ uploads ทั้งหมด

```bash
curl "https://asia-southeast1-dormy-sheets.cloudfunctions.net/list-uploads"
```

### 4. กรองตามสถานะ

```bash
curl "https://asia-southeast1-dormy-sheets.cloudfunctions.net/list-uploads?status=done&limit=10"
```

## Upload ID Generation

Upload ID ถูกสร้างจาก SHA256 hash ของ:

- Bucket name
- File name
- File size
- Created timestamp

นี่ทำให้ไฟล์เดิมจะได้ upload_id เดิม แต่ไฟล์ใหม่จะได้ upload_id ใหม่

## Status Flow

```
Upload → pending → processing → done/failed
```

- **pending**: ยังไม่เริ่มประมวลผล
- **processing**: กำลังประมวลผล
- **done**: ประมวลผลสำเร็จ
- **failed**: ประมวลผลล้มเหลว

## ตัวอย่างการทำงาน

### การอัปโหลดครั้งแรก

```
Upload test-data.csv → Generate upload_id: ce05376591fe5c7d
Check Firestore → Not found → Start processing
Update status: processing → Process CSV → Update status: done
```

### การอัปโหลดซ้ำ (Idempotency)

```
Upload test-data.csv → Generate upload_id: ce05376591fe5c7d
Check Firestore → Found with status: done → Skip processing
Log: "File already processed successfully. Skipping..."
```

## การ Deploy

### วิธีที่ 1: Deploy จาก GitHub Repository (แนะนำ)

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/gcp-csv-ingestion-pipeline.git
cd gcp-csv-ingestion-pipeline

# Run deployment script
chmod +x csv-processor-function/deploy-from-github.sh
./csv-processor-function/deploy-from-github.sh
```

### วิธีที่ 2: Deploy จาก Local Source

```bash
cd csv-processor-function

# Deploy storage trigger function
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

# Deploy HTTP functions
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
```

## ข้อดีของระบบนี้

1. **Event-Driven**: ประมวลผลทันทีที่มีการอัปโหลด
2. **Idempotent**: ไม่มีการประมวลผลซ้ำ ประหยัดทรัพยากร
3. **Scalable**: Cloud Functions scale อัตโนมัติ
4. **Traceable**: ติดตามสถานะและประวัติได้
5. **Fault-Tolerant**: จัดการ error และ retry ได้
6. **Cost-Effective**: จ่ายเฉพาะเมื่อใช้งาน

## การขยายระบบ

- เพิ่มการ validate CSV format
- เพิ่มการ transform data
- เชื่อมต่อกับ BigQuery หรือ data warehouse
- เพิ่ม notification เมื่อประมวลผลเสร็จ
- เพิ่ม retry mechanism สำหรับ failed jobs
