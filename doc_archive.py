import os
import re
import sqlite3
import html2text
from doc_create import create_google_services, db_lock
from slack_sdk import WebClient
from concurrent.futures import ThreadPoolExecutor

download_directory = ''
db_path = ''
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

def archive(payload_dict):
    link = payload_dict['message']['text']
    link = link.strip('<>')
    bot_id = payload_dict['message']['user']
    user_id = payload_dict['user']['id']
    pattern = r'https?://docs\.google\.com/document/d/([a-zA-Z0-9_-]+)/edit'
    match = re.search(pattern, link) 
    post_number = doc_num(user_id, link)
    if match and bot_id == '' and post_number is not None: 
        _, drive_service = create_google_services() 
        document_id = match.group(1)
        file_metadata = drive_service.files().get(fileId=document_id, fields='name').execute()
        filename = file_metadata['name']
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            filename = filename.replace(char, '')
        filename = os.path.join(download_directory, filename)
        request = drive_service.files().export_media(fileId=document_id, mimeType='text/html')
        response = request.execute()
        with open(filename, 'wb') as file:
            file.write(response)
        with open(filename, 'r', encoding='utf-8') as html_file:
            html_content = html_file.read()
        # Convert the HTML content to Markdown using html2text
        converter = html2text.HTML2Text()
        markdown_text = converter.handle(html_content)
        # Write the Markdown content to the Markdown file
        with open(filename + '.md', 'w', encoding='utf-8') as markdown_file:
            markdown_file.write(markdown_text) 
        #os.remove(filename)
        response = client.files_upload(
            channels='', 
            file=filename + '.md',
            title="Post #" + str(post_number) + " " + file_metadata['name'],
        )
        drive_service.files().delete(fileId=document_id).execute()
        # Delete the row containing the document link from the database
        delete_from_db(link)
        client.chat_postMessage(channel=payload_dict['channel']['id'], text= file_metadata['name'] + " successfully archived see Post #" + str(post_number))
    else:
        client.chat_postMessage(channel=payload_dict['channel']['id'], text= 'Invalid, please click on active document link') 

def delete_from_db(doc_link):
    with db_lock:
        db_connection = sqlite3.connect('user_docs.db')
        cursor = db_connection.cursor()
        query = "DELETE FROM user_docs WHERE doc_link = ?"
        cursor.execute(query, (doc_link,))
        db_connection.commit()
        db_connection.close()

def doc_num(user_id, doc_link):
    with db_lock:
        db_connection = sqlite3.connect(db_path)
        cursor = db_connection.cursor()
        query = "SELECT doc_count FROM user_docs WHERE user_id = ? AND doc_link = ?"
        cursor.execute(query, (user_id, doc_link))
        result = cursor.fetchone()
        if result is not None:
            post_number = result[0]
        else:
            post_number = None
        db_connection.close()
        return post_number
