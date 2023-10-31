import os
import json
from flask import Flask, request, Response 
from slackeventsapi import SlackEventAdapter
from slack_sdk import WebClient
import threading
from doc_create import doc_URL, print_user_docs
from doc_archive import archive 
from doc_share import open_modal, handle_modal_submission, send_doc_list

app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'],'/slack/events', app)

client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

def send_ack():
    # Send a 200 OK response
    return Response(status=200) 

@slack_event_adapter.on('app_mention')  
def document_ack(payload): 
    event = payload.get('event', {})
    user_id = event.get('user')
    client.chat_postMessage(channel=user_id, text= "Creating your document")
    # Start a new thread to send acknowledgment
    acknowledgment_thread = threading.Thread(target=send_ack)
    acknowledgment_thread.start()
    # Start another thread to complete the code
    completion_thread = threading.Thread(target=doc_URL, args=(user_id,))
    completion_thread.start()

@app.route('/slack/actions', methods=['POST'])
def button_ack():
    payload = request.form.get('payload')
    payload_dict = json.loads(payload)
    if 'view' not in payload_dict:
        callback_id = payload_dict['callback_id']
        if callback_id == 'share_doc':
            # Handle the share_doc shortcut
            acknowledgment_thread = threading.Thread(target=send_ack)
            acknowledgment_thread.start()
            # Start another thread to open modal
            open_modal_thread = threading.Thread(target=open_modal, args=(payload_dict,))
            open_modal_thread.start()
        if callback_id == 'archive':
            # Handle the archive shortcut
            acknowledgment_thread = threading.Thread(target=send_ack)
            acknowledgment_thread.start()
            # Start another thread to complete the code
            completion_thread = threading.Thread(target=archive, args=(payload_dict,))
            completion_thread.start()  
    else: 
        if payload_dict['view']['callback_id'] == 'share_doc':
            # Handle the share_doc shortcut
            acknowledgment_thread = threading.Thread(target=send_ack)
            acknowledgment_thread.start()
            # Start another thread to open modal
            open_modal_thread = threading.Thread(target=handle_modal_submission, args=(payload_dict,))
            open_modal_thread.start()
    return Response(status=200)


@app.route('/list_files', methods=['POST'])
def doc_list():
    data = request.form
    user_id = data.get('user_id')
    acknowledgment_thread = threading.Thread(target=send_ack)
    acknowledgment_thread.start()
    completion_thread = threading.Thread(target=send_doc_list, args=(user_id,))
    completion_thread.start()
    return Response(status=200)

if __name__ == "__main__": 
    app.run(debug=True)
