import json
import hashlib
import base64
from datetime import datetime
from google.cloud import firestore
from google.cloud import storage
from google.cloud import pubsub_v1
import functions_framework


# Initialize clients
db = firestore.Client(database='uploads')


def generate_upload_id(bucket_name, file_name, file_size, created_time):
    """Generate a unique upload ID based on file metadata"""
    content = f"{bucket_name}-{file_name}-{file_size}-{created_time}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@functions_framework.cloud_event
def on_file_upload(cloud_event):
    
    """
    Trigger: Cloud Storage finalized event
    Action: Publish file info to Pub/Sub for processing
    """
    try:
        data = cloud_event.data
        bucket_name = data["bucket"]
        file_name = data["name"]
        
        # Only process CSV files
        if not file_name.lower().endswith('.csv'):
            print(f"Ignoring non-CSV file: {file_name}")
            return
        
        # Get file metadata
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        
        upload_id = generate_upload_id(
            bucket_name,
            file_name,
            blob.size,
            blob.time_created.isoformat() if blob.time_created else ""
        )
        
        print(f"File uploaded: {file_name}, Upload ID: {upload_id}")
        
        # Check idempotency
        upload_ref = db.collection('uploads').document(upload_id)
        upload_doc = upload_ref.get()
        
        if upload_doc.exists and upload_doc.to_dict().get('status') == 'done':
            print(f"Upload {upload_id} already processed. Skipping.")
            return
        
        # Mark as pending
        upload_ref.set({
            'upload_id': upload_id,
            'bucket_name': bucket_name,
            'file_name': file_name,
            'file_size': blob.size,
            'status': 'pending',
            'queued_at': firestore.SERVER_TIMESTAMP
        }, merge=True)
        
        # Publish to Pub/Sub
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path('dormy-sheets', 'csv-uploads')
        
        message = {
            'upload_id': upload_id,
            'bucket_name': bucket_name,
            'file_name': file_name
        }
        
        future = publisher.publish(topic_path, json.dumps(message).encode('utf-8'))
        message_id = future.result(timeout=10)
        print(f"Published to Pub/Sub: message_id={message_id}")
        
    except Exception as e:
        print(f"Error in on_file_upload: {str(e)}")
        raise


@functions_framework.cloud_event
def process_csv(cloud_event):
    """
    Trigger: Pub/Sub message from csv-uploads topic
    Action: Process CSV file
    Note: If this function throws exception, Pub/Sub will retry → eventually goes to DLQ
    """
    try:
        # Decode Pub/Sub message
        message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode('utf-8')
        payload = json.loads(message_data)
        
        upload_id = payload['upload_id']
        bucket_name = payload['bucket_name']
        file_name = payload['file_name']
        
        print(f"Processing: {file_name}, upload_id={upload_id}")
        
        upload_ref = db.collection('uploads').document(upload_id)
        
        # Mark as processing
        upload_ref.update({
            'status': 'processing',
            'processing_started_at': firestore.SERVER_TIMESTAMP
        })
        
        # Process the CSV file
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        
        csv_content = blob.download_as_text()
        lines = csv_content.split('\n')
        
        print(f"CSV has {len(lines)} lines")
        
        # Validate
        if len(lines) < 2:
            raise ValueError("CSV file is empty or has only headers")
        
        # Simulate processing
        # Add your actual CSV processing logic here
        
        # Mark as done
        upload_ref.update({
            'status': 'done',
            'processing_completed_at': firestore.SERVER_TIMESTAMP,
            'lines_processed': len(lines)
        })
        
        print(f"Successfully processed: {file_name}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error processing CSV: {error_msg}")
        
        # Update Firestore with error
        try:
            if 'upload_id' in locals():
                db.collection('uploads').document(upload_id).update({
                    'status': 'failed',
                    'error_message': error_msg,
                    'failed_at': firestore.SERVER_TIMESTAMP
                })
        except:
            pass
        
        # Re-raise so Pub/Sub knows it failed and will retry
        raise