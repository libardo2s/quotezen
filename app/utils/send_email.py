from flask import current_app
import boto3
from app.config import Config

def send_email(recipient, subject, body_text, body_html=None):
    config = current_app.config

    ses = boto3.client('ses', region_name="us-east-1")

    body = {
        'Text': {'Data': body_text}
    }

    if body_html:
        body['Html'] = {'Data': body_html}

    response = ses.send_email(
        Source="adrip@quotezen.com",
        Destination={'ToAddresses': [recipient]},
        Message={
            'Subject': {'Data': subject},
            'Body': body
        }
    )
    print(response)

    return response