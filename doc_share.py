import re
import sqlite3
import os
import json
from slack_sdk import WebClient
from doc_create import create_google_services, print_user_docs, get_doc_title, db_lock
from doc_archive import doc_num, db_path

client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

def open_modal(payload_dict):
    trigger_id = payload_dict['trigger_id']
    link = payload_dict['message']['text']
    bot_id = payload_dict['message']['user']
    modal = {
        "type": "modal",
        "callback_id": "share_doc",
        "title": {
            "type": "plain_text",
            "text": "Share Document"
        },
        "blocks": [
            {
                "type": "input",
                "block_id": "email_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "email",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Enter email addresses that are registered with Slack accounts. Please separate by commas."
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Email Addresses"
                }
            }
        ],
        "submit": {
            "type": "plain_text",
            "text": "Submit"
        },
        "private_metadata": json.dumps({"link": link, "bot_id": bot_id}),
    }
    Response = client.views_open(trigger_id=trigger_id, view=modal)
    return Response

def handle_modal_submission(payload):
    view = payload['view']
    small_payload = json.loads(view.get('private_metadata', '{}'))
    #print (small_payload)
    user_id = payload['user']['id']
    values = view['state']['values']
    email_input_block = values['email_input']
    email_input_action = email_input_block['email']
    emails = email_input_action['value']
    email_list = emails.split(',')
    email_list = [email.strip() for email in email_list]
    # Share the document with the email addresses
    invalid_emails = [] # List to keep track of invalid emails 
    for email in email_list:
        user_id_email = get_user_id(email)
        if user_id_email is not None:
            # Share the document with the user
            share_doc(small_payload, email, user_id_email) 
        else:
            invalid_emails.append(email)
    if invalid_emails:
        invalid_emails_str = ", ".join(invalid_emails)
        client.chat_postMessage(channel=user_id, text= "The following emails are invalid: " + invalid_emails_str + 
                                " Make sure to share only with emails associated with Slack accounts")
    else: 
        client.chat_postMessage(channel=user_id, text= "Successfuly shared document with provided emails")
                                
def get_user_id(email):
    try:
        response = client.users_lookupByEmail(email=email)
        user_id = response['user']['id']
        return user_id
    except: 
        return None
   #HANDLE IF DOCUMENT HAS ALREADY BEEN SHARED WITH AN EMAIL/USERID 
def share_doc(payload_dict, email, user_id):
    link = payload_dict['link']
    link = link.strip('<>')
    bot_id = payload_dict['bot_id']
    pattern = r'https://docs.google.com/document/d/([a-zA-Z0-9_-]+)/edit'
    match = re.search(pattern, link)
    doc_count = doc_num(user_id, link)
    if match and bot_id == 'U05RM56MUAU' and doc_count is None: 
        # Check if doc_link already exists in user_docs
        doc_id = match.group(1)
        # Share the Google Doc with the user
        permissions = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': email
        }
        _, drive_service = create_google_services()
        drive_service.permissions().create(fileId=doc_id, body=permissions).execute()
        client.chat_postMessage(channel=user_id, text='A document has been shared with you')
        with db_lock:
            db_connection = sqlite3.connect(db_path)
            cursor = db_connection.cursor()
            # Insert the new entry into the user_docs table
            query = "INSERT INTO user_docs (user_id, doc_link, doc_count) VALUES (?, ?, ?)"
            cursor.execute(query, (user_id, link, doc_count))
            # Commit the changes and close the database connection
            db_connection.commit()
            db_connection.close()
        send_doc_list(user_id)
        print_user_docs()
        #else: send message saying it has already been shared with that user 
            
def send_doc_list(user_id):
    doc_data = get_doc_title(user_id)
    num_documents = len(doc_data)
    initial_message = f"You have {num_documents} document{'s' if num_documents != 1 else ''} open:"
    client.chat_postMessage(channel=user_id, text=initial_message)
    print_user_docs()
    for doc_url, doc_title in doc_data.items():
        client.chat_postMessage(channel=user_id, text= f"Document Title: {doc_title}")
        client.chat_postMessage(channel=user_id, text= doc_url)


