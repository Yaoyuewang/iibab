import os
import sqlite3
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Path to your service account key JSON file
service_account_key_file = ''
# Set the environment variable to use the service account key
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = service_account_key_file

# Create a Google Docs API service object
doc_scopes = ['https://www.googleapis.com/auth/documents']
doc_creds = service_account.Credentials.from_service_account_file(
    service_account_key_file, scopes=doc_scopes
)
docs_service = build('docs', 'v1', credentials=doc_creds)

drive_scopes = ['https://www.googleapis.com/auth/drive.file']
drive_creds = service_account.Credentials.from_service_account_file(
    service_account_key_file, scopes=drive_scopes
)
drive_service = build('drive', 'v3', credentials=drive_creds)

def list_docs_files():
    results = []
    page_token = None
    while True:
        response = drive_service.files().list(
            q="mimeType='application/vnd.google-apps.document'",
            spaces='drive',
            fields='nextPageToken, files(id, name)',
            pageToken=page_token
        ).execute()
        files = response.get('files', [])
        results.extend(files)
        page_token = response.get('nextPageToken', None)
        if not page_token:
            break
    return results
def delete_doc_file(file_id):
    try:
        drive_service.files().delete(fileId=file_id).execute()
        print(f"Deleted Google Docs file with ID: {file_id}")
    except Exception as e:
        print(f"Error deleting Google Docs file with ID {file_id}: {str(e)}")

def clear_database():
    db_connection = sqlite3.connect('user_docs.db', check_same_thread=False)
    cursor = db_connection.cursor()

    # Delete all rows from user_docs
    cursor.execute("DELETE FROM user_docs;")

    # Reset doc_counter to initial state
    cursor.execute("UPDATE doc_counter SET count = 1;")

    db_connection.commit()  # Commit the changes
    db_connection.close()   # Close the connection


if __name__ == "__main__":
    # List all Google Docs files
    doc_files = list_docs_files()
    clear_database()
    if doc_files:
        print(f"Found {len(doc_files)} Google Docs files:")
        for file in doc_files:
            print(f"File ID: {file['id']}, Name: {file['name']}")
            # Delete the Google Docs file by its ID
            delete_doc_file(file['id'])
    else:
        print("No Google Docs files found.")





