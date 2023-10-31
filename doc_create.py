import os
import sqlite3 
from slack_sdk import WebClient
from pathlib import Path
from dotenv import main
from google.oauth2 import service_account
from googleapiclient.discovery import build
from concurrent.futures import ThreadPoolExecutor
from threading import Lock 

# Load environment variables from .env file
env_path = Path('.') / '.env'
main.load_dotenv(dotenv_path=env_path)
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
download_directory = " "
#Database 
user_docs_db = sqlite3.connect('user_docs.db', check_same_thread=False)
cursor = user_docs_db.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS user_docs (user_id TEXT, doc_link TEXT, doc_count INTEGER)''')
cursor.execute("CREATE TABLE IF NOT EXISTS doc_counter (count INTEGER);")
cursor.execute("INSERT OR IGNORE INTO doc_counter (count) VALUES (1);")
#Indexes to speed up search 
cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON user_docs (user_id);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_link ON user_docs (doc_link);")

user_docs_db.commit()

db_lock = Lock()

def doc_URL(user_id):
    docs_service, drive_service = create_google_services()
    document = docs_service.documents().create().execute()
    #increment document counter 
    #get the document ID 
    document_id = document['documentId']
    user_info = client.users_info(user=user_id)
    # Extract the email address from the user info
    email = user_info["user"]["profile"]["email"]
    #change role to owner/viewer ect 
    role = 'writer' 
    permission = {
        'emailAddress': email,
        'type': 'user',
        'role': role,
    }
    # Execute the sharing request
    drive_service.permissions().create(fileId=document_id, body=permission).execute()
    # Get a shareable link to the document
    doc_link = f'https://docs.google.com/document/d/{document_id}/edit'
    client.chat_postMessage(channel=user_id, text= doc_link)
    # Add the document link and user ID to the dictionary
    with ThreadPoolExecutor(max_workers=5) as executor:
        future = executor.submit(insert_into_db, user_id, doc_link)
        future.result()
        
def insert_into_db(user_id, doc_link):
    with db_lock:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("SELECT count FROM doc_counter;")
        count = cursor.fetchone()[0]
        cursor.execute("INSERT INTO user_docs (user_id, doc_link, doc_count) VALUES (?, ?, ?);", (user_id, doc_link, count))
        count = count + 1 
        cursor.execute("UPDATE doc_counter SET count = ?;", (count,))
        cursor.execute("COMMIT;")
        user_docs_db.commit()
        print_user_docs()

def get_doc_title(user_id): 
    with db_lock: 
        # Retrieve document URLs associated with the user from the database
        cursor.execute("SELECT doc_link FROM user_docs WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        doc_data = {}
        
        # Initialize Google Drive service
        service_account_key_file = ""
        scopes = ['https://www.googleapis.com/auth/drive.file']
        credentials = service_account.Credentials.from_service_account_file(
        service_account_key_file, scopes=scopes
        )
        drive_service = build('drive', 'v3', credentials=credentials)
        # Populate the dictionary with data from the database
        for row in rows:
            doc_url = row[0]
            # Extract the document title using the Google Drive API
            parts = doc_url.split('/')
            document_id = parts[-2]
            file_metadata = drive_service.files().get(fileId=document_id, fields='name').execute()
            doc_title = file_metadata.get('name', 'Untitled Document')
            doc_data[doc_url] = doc_title
        return doc_data
    
def create_google_services():
    # Initialize Google Docs and Drive services
    service_account_key_file = ""
    # Set the environment variable to use the service account key
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = service_account_key_file

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
    return docs_service, drive_service

def print_user_docs():
    cursor.execute("SELECT * FROM user_docs")
    rows = cursor.fetchall()
    print("user_id | doc_link | doc_count")
    for row in rows:
        print(f"{row[0]} | {row[1]} | {row[2]}")