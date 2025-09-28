import json
import hashlib
from datetime import datetime
from google.cloud import firestore
from google.cloud import storage
import functions_framework


# Initialize Firestore client
db = firestore.Client(database='uploads')


def generate_upload_id(bucket_name, file_name, file_size, created_time):
    """Generate a unique upload ID based on file metadata"""
    content = f"{bucket_name}-{file_name}-{file_size}-{created_time}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@functions_framework.cloud_event
def process_csv_upload(cloud_event):
    """
    Cloud Function triggered by Cloud Storage upload events.
    Implements idempotent processing for CSV files.
    """
    try:
        # Extract event data
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
        
        # Generate upload ID
        upload_id = generate_upload_id(
            bucket_name, 
            file_name, 
            blob.size, 
            blob.time_created.isoformat() if blob.time_created else ""
        )
        
        print(f"Processing file: {file_name}, Upload ID: {upload_id}")
        
        # Check if this upload has been processed before
        upload_ref = db.collection('uploads').document(upload_id)
        upload_doc = upload_ref.get()
        
        if upload_doc.exists:
            status = upload_doc.to_dict().get('status', 'unknown')
            print(f"Upload ID {upload_id} already exists with status: {status}")
            
            if status == 'done':
                print("File already processed successfully. Skipping...")
                return
            elif status == 'processing':
                print("File is currently being processed. Skipping to avoid duplicate processing...")
                return
            elif status == 'failed':
                print("Previous processing failed. Retrying...")
            else:
                print(f"Unknown status: {status}. Proceeding with processing...")
        
        # Create or update upload tracking record
        upload_data = {
            'upload_id': upload_id,
            'bucket_name': bucket_name,
            'file_name': file_name,
            'file_size': blob.size,
            'created_time': blob.time_created,
            'status': 'processing',
            'processing_started_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        # Use set with merge=True to handle both create and update cases
        upload_ref.set(upload_data, merge=True)
        print(f"Updated status to 'processing' for upload ID: {upload_id}")
        
        # Simulate CSV processing (replace with actual processing logic)
        success = process_csv_file(bucket_name, file_name)
        
        if success:
            # Update status to done
            upload_ref.update({
                'status': 'done',
                'processing_completed_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            print(f"Successfully processed file: {file_name}")
        else:
            # Update status to failed
            upload_ref.update({
                'status': 'failed',
                'error_message': 'Processing failed',
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            print(f"Failed to process file: {file_name}")
            
    except Exception as e:
        print(f"Error processing upload: {str(e)}")
        # Try to update status to failed if we have upload_id
        try:
            if 'upload_id' in locals():
                upload_ref = db.collection('uploads').document(upload_id)
                upload_ref.update({
                    'status': 'failed',
                    'error_message': str(e),
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
        except:
            pass  # If we can't update status, just log the original error


def process_csv_file(bucket_name, file_name):
    """
    Process the CSV file. Replace this with your actual processing logic.
    Returns True if processing succeeds, False otherwise.
    """
    try:
        print(f"Starting to process CSV file: {file_name} from bucket: {bucket_name}")
        
        # Download and read the CSV file
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        
        # Download as text
        csv_content = blob.download_as_text()
        lines = csv_content.split('\n')
        
        print(f"CSV file has {len(lines)} lines")
        
        # Example processing: validate CSV structure
        if len(lines) < 2:  # At least header + 1 data row
            print("CSV file appears to be empty or has only headers")
            return False
        
        # Add your actual CSV processing logic here
        # For example:
        # - Parse CSV data
        # - Validate data format
        # - Transform data
        # - Load into database/warehouse
        # - Generate reports
        
        print("CSV processing completed successfully")
        return True
        
    except Exception as e:
        print(f"Error during CSV processing: {str(e)}")
        return False


@functions_framework.http
def get_upload_status(request):
    """
    HTTP endpoint to check upload status by upload_id
    """
    try:
        upload_id = request.args.get('upload_id')
        if not upload_id:
            return {'error': 'upload_id parameter is required'}, 400
        
        upload_ref = db.collection('uploads').document(upload_id)
        upload_doc = upload_ref.get()
        
        if not upload_doc.exists:
            return {'error': 'Upload ID not found'}, 404
        
        return upload_doc.to_dict(), 200
        
    except Exception as e:
        return {'error': str(e)}, 500


@functions_framework.http
def list_uploads(request):
    """
    HTTP endpoint to list recent uploads with their status
    """
    try:
        limit = int(request.args.get('limit', 10))
        status_filter = request.args.get('status')
        
        query = db.collection('uploads').order_by('updated_at', direction=firestore.Query.DESCENDING).limit(limit)
        
        if status_filter:
            query = query.where('status', '==', status_filter)
        
        docs = query.stream()
        uploads = []
        
        for doc in docs:
            upload_data = doc.to_dict()
            upload_data['id'] = doc.id
            uploads.append(upload_data)
        
        return {'uploads': uploads}, 200
        
    except Exception as e:
        return {'error': str(e)}, 500
